"""Observe production LM inputs; replace only the registered start builder."""
import hashlib
import json
import os
from pathlib import Path


def point_hash(point):
    import numpy as np
    return hashlib.sha256(np.asarray(point, dtype="<f8").tobytes()).hexdigest()


def redraw_point(point, lower, upper, seed, index, feasible):
    import numpy as np
    rng = np.random.default_rng([seed, 99, index])
    current = point
    for attempt in range(2001):
        ok = feasible(current)
        if ok or attempt == 2000:
            return current, attempt, ok
        current = rng.uniform(lower, upper)
    raise AssertionError("unreachable")


def install():
    from geosolver.engine.standard.search import scipy_multistart_backend as smb
    from geosolver.runtime.deadline import check_deadline

    mode = os.environ["REDRAW_CONDITION"]
    if mode not in {"normal", "redraw"}:
        raise ValueError(mode)
    external_seed = int(os.environ["REDRAW_SEED"])
    stream = Path(os.environ["REDRAW_AUDIT_PATH"]).open("a", encoding="utf-8", buffering=1)
    original_builder = smb._build_local_start_sequence_with_kinds
    original_search = smb.ScipyMultistartBackend.run_search
    original_collect = smb._collect_local_start_record
    original_lm = smb.least_squares
    original_powell = smb.minimize
    state = {"call": 0, "evaluator": None, "points": {}, "active": None}

    def emit(event, **fields):
        stream.write(json.dumps({"event": event, **fields}, allow_nan=False) + "\n")

    def feasible(point):
        check_deadline()
        try:
            return bool(state["evaluator"].evaluate_float_hard_feasibility(
                list(point), include_margins=False).hard_feasible)
        except TimeoutError:
            raise
        except Exception:
            return False

    def builder(**kwargs):
        starts, kinds, prefix = original_builder(**kwargs)
        replaced = []
        for index, point in enumerate(starts):
            new, retries, ok = redraw_point(
                point, kwargs["lower"], kwargs["upper"], external_seed, index, feasible)
            record = dict(call=state["call"], internal_seed=int(kwargs["seed"]),
                          index=index, kind=kinds[index], retries=retries,
                          attempts=retries + 1, hard_feasible=ok,
                          original_hash=point_hash(point), final_hash=point_hash(new))
            state["points"][(int(kwargs["seed"]), index)] = record
            emit("generated", **record)
            replaced.append(new)
        return tuple(replaced), kinds, prefix

    def search(self, **kwargs):
        state["call"] += 1
        state["evaluator"] = kwargs["evaluator"]
        state["points"] = {}
        emit("search", call=state["call"],
             builder_is_original=smb._build_local_start_sequence_with_kinds is original_builder)
        return original_search(self, **kwargs)

    def collect(**kwargs):
        point = kwargs["start"]
        record = state["points"].get((int(kwargs["seed"]), kwargs["start_index"]))
        digest = point_hash(point)
        matches = record is not None and record["final_hash"] == digest
        if mode == "redraw" and not matches:
            emit("mismatch", index=kwargs["start_index"], hash=digest)
            raise RuntimeError("redrawn start was not delivered to local solver")
        observation = dict(call=state["call"], internal_seed=int(kwargs["seed"]),
             index=kwargs["start_index"], hash=digest, matches_generated=matches,
             retries=record["retries"] if record else 0,
             hard_feasible=record["hard_feasible"] if record else feasible(point),
             builder_is_original=smb._build_local_start_sequence_with_kinds is original_builder)
        emit("scheduled", **observation)
        state["active"] = observation
        try:
            return original_collect(**kwargs)
        finally:
            state["active"] = None

    def optimizer(original, method):
        def observed(fun, x0, *args, **kwargs):
            active = state["active"]
            if active is not None:
                if point_hash(x0) != active["hash"]:
                    emit("mismatch", index=active["index"], hash=point_hash(x0))
                    raise RuntimeError("local optimizer did not receive scheduled start")
                # Receipt is emitted at the actual optimizer boundary, after the
                # collector's deadline check, not merely when a point is generated.
                emit("consumed", optimizer=method, **active)
            return original(fun, x0, *args, **kwargs)
        return observed

    # Normal leaves the registered builder untouched. Both modes share observers.
    if mode == "redraw":
        smb._build_local_start_sequence_with_kinds = builder
    smb.ScipyMultistartBackend.run_search = search
    smb._collect_local_start_record = collect
    smb.least_squares = optimizer(original_lm, "LM")
    smb.minimize = optimizer(original_powell, "Powell")
    emit("installed", condition=mode, pid=os.getpid(), external_seed=external_seed,
         builder_is_original=smb._build_local_start_sequence_with_kinds is original_builder)
    return stream.close
