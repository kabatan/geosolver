"""Change only the scalar returned to primary NOMAD; preserve candidate records."""
from __future__ import annotations

import hashlib
import json
import os
from contextvars import ContextVar
from pathlib import Path

SCOPE = ContextVar("q14_scope", default=None)
CAPTURE = ContextVar("q14_capture", default=None)
CALL = ContextVar("q14_nomad_call", default=None)
ORIGINALS = {}


class BufferedPoint:
    def __init__(self, point):
        self.point = point
        self.payload = None

    def size(self):
        return self.point.size()

    def get_coord(self, index):
        return self.point.get_coord(index)

    def setBBO(self, payload):
        assert self.payload is None, "multiple setBBO calls"
        self.payload = payload


def equality_score(residual, scales):
    # Deliberately use the same arithmetic order as frozen nomad_blackbox_adapter.
    if scales is not None:
        scaled = [r / s for r, s in zip(residual.residual_vector, scales, strict=False)]
        return sum(r * r for r in scaled)
    return residual.residual_norm_float * residual.residual_norm_float


def install(mode=None, emit=None):
    from geosolver.engine.standard.orchestration import run_search as search
    from geosolver.engine.standard.search import nomad_blackbox_adapter as adapter
    from geosolver.engine.standard.search.nomad_backend import NomadBackend
    from geosolver.engine.standard.search.nomad_config import NomadConfig

    assert not ORIGINALS, "hook installed twice"
    mode = mode or os.environ["NOMAD_WALL_MODE"]
    assert mode in ("B", "N")
    if emit is None:
        stream = Path(os.environ["NOMAD_WALL_AUDIT"]).open("a", buffering=1)

        def emit(event, **data):
            stream.write(json.dumps({"event": event, "mode": mode, "pid": os.getpid(), **data},
                                    ensure_ascii=False, separators=(",", ":")) + "\n")

    ORIGINALS.update(
        baseline=search._run_search_baseline,
        evaluate=adapter.NomadBlackboxAdapter._evaluate,
        point=adapter.evaluate_search_point,
        backend=NomadBackend.run_search,
        params=NomadConfig.build_params,
    )
    sequence = [0]

    def baseline(*args, **kwargs):
        token = SCOPE.set(kwargs.get("search_mode", "disco_mads"))
        try:
            return ORIGINALS["baseline"](*args, **kwargs)
        finally:
            SCOPE.reset(token)

    def search_point(*args, **kwargs):
        result = ORIGINALS["point"](*args, **kwargs)
        capture = CAPTURE.get()
        if capture is not None:
            assert "result" not in capture
            capture["result"] = result
        return result

    def params(self, **kwargs):
        result = ORIGINALS["params"](self, **kwargs)
        emit("params", call=CALL.get(), scope=SCOPE.get(), params=result,
             guard_penalty=self.guard_penalty)
        return result

    def evaluate(self, point):
        if SCOPE.get() != "disco_mads":
            return ORIGINALS["evaluate"](self, point)
        capture = {}
        token = CAPTURE.set(capture)
        proxy = BufferedPoint(point)
        before = len(self.records)
        try:
            result = ORIGINALS["evaluate"](self, proxy)
        finally:
            CAPTURE.reset(token)
        record = self.records[-1] if len(self.records) > before else None
        if result != 1:
            assert proxy.payload is None
            emit("evaluation_failure", call=CALL.get(), count=self.evaluation_count,
                 status=record.evaluation_status.value if record else "deadline",
                 x=list(record.x_float) if record else None)
            return result
        assert record is not None and proxy.payload is not None
        evaluation = capture["result"]
        eq = equality_score(evaluation.residual, self.constraint_scales)
        penalty = 0.0 if record.hard_feasible else self.config.guard_penalty
        original = float(proxy.payload)
        assert original == eq + penalty == record.score, "objective audit mismatch"
        sent = eq if mode == "N" and not record.hard_feasible else original
        payload = str(sent).encode("utf-8") if sent != original else proxy.payload
        point.setBBO(payload)
        emit("evaluation", call=CALL.get(), count=self.evaluation_count,
             candidate_id=record.candidate_id, x=list(record.x_float),
             hard=record.hard_feasible, guard=record.guard_ok,
             tags=list(record.hard_violation_tags), equality_sq=eq,
             original_score=original, sent_score=sent, changed=sent != original,
             preserved_record_score=record.score)
        return result

    def backend(self, **kwargs):
        sequence[0] += 1
        number = sequence[0]
        token = CALL.set(number)
        emit("nomad_start", call=number, scope=SCOPE.get(),
             search_mode=kwargs.get("search_mode", "disco_mads"),
             seeds=list(self.config.seed_values), starts=self.start_points,
             bounds=kwargs["bounds"], scales=self.constraint_scales,
             max_bb_eval=self.config.max_bb_eval, max_time_sec=self.config.max_time_sec)
        try:
            result = ORIGINALS["backend"](self, **kwargs)
            emit("nomad_end", call=number, scope=SCOPE.get(), evaluations=result.evaluation_count,
                 failures=result.evaluation_failure_count,
                 hard_records=sum(r.hard_feasible for r in result.all_records),
                 selected=len(result.candidates),
                 selected_hard=sum(r.hard_feasible for r in result.candidates),
                 ledger=len(result.guard_feasible_ledger))
            return result
        except BaseException as error:
            emit("nomad_exception", call=number, scope=SCOPE.get(),
                 exception=type(error).__name__, message=str(error)[:1000])
            raise
        finally:
            CALL.reset(token)

    search._run_search_baseline = baseline
    adapter.evaluate_search_point = search_point
    adapter.NomadBlackboxAdapter._evaluate = evaluate
    NomadBackend.run_search = backend
    NomadConfig.build_params = params
    emit("installed", patch_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         import_root=str(Path(adapter.__file__).resolve()),
         only_primary=True, candidate_records_changed=False,
         final_verifier_changed=False, lm_changed=False)


def uninstall():
    """Only for synthetic protocol checks; no live campaign uses uninstall."""
    from geosolver.engine.standard.orchestration import run_search as search
    from geosolver.engine.standard.search import nomad_blackbox_adapter as adapter
    from geosolver.engine.standard.search.nomad_backend import NomadBackend
    from geosolver.engine.standard.search.nomad_config import NomadConfig
    search._run_search_baseline = ORIGINALS["baseline"]
    adapter.NomadBlackboxAdapter._evaluate = ORIGINALS["evaluate"]
    adapter.evaluate_search_point = ORIGINALS["point"]
    NomadBackend.run_search = ORIGINALS["backend"]
    NomadConfig.build_params = ORIGINALS["params"]
    ORIGINALS.clear()
