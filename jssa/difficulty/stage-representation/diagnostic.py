"""Q39 stage 2: frozen solver wiring and bounded, reference-blind evidence.

Only the entry points enumerated in diagnostic-design.md are patched, inside
one worker process. The original evaluator is always used for certification.
"""
from __future__ import annotations

import ast
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, replace
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time

BASE = Path(__file__).resolve().parent
WORKSPACE_ROOT = BASE.parents[2]
_runtime_location = BASE / "runtime-location.json"
ROOT = (Path(json.loads(_runtime_location.read_text())["root"])
        if _runtime_location.exists() else WORKSPACE_ROOT)
OUT = BASE / "execution"
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
    os.environ[_name] = "1"

from mpmath import mp
from geosolver.problem.models import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.search_point import evaluate_search_point
from geosolver.engine.standard.evaluation.float_expressions import residual_norm
from geosolver.engine.standard.contracts.candidate_record import FloatCandidate, RefinedCandidate
from geosolver.engine.standard.refinement import mpmath_refiner as mr
from geosolver.engine.standard.refinement.refiner_config import RefinerConfig
from geosolver.engine.standard.search.nomad_config import NomadConfig
from geosolver.engine.standard.search.nomad_blackbox_adapter import NomadBlackboxAdapter
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.runtime.deadline import runtime_session, expired
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
    boundary_float_to_mpf, BoundaryOrigin,
)

FROZEN_SMOOTH = mr._smooth_zero_constraint_residuals
SEEDS = (39001, 39002, 39003)


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    value = json.loads(Path(path).read_text())
    if isinstance(value, dict) and set(value) == {"q39_split_parts"}:
        return json.loads(b"".join(bytes.fromhex(read(Path(path).parent / p)["hex"])
                                  for p in value["q39_split_parts"]))
    return value


def save(path, value):
    """Atomic writes; oversized records split without dropping any content.

    Normal records are a few KB. Splitting, rather than a small assertion,
    preserves evidence even if an unexpected diagnostic becomes verbose.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) + "\n").encode()
    if len(data) >= 4_000_000:
        parts = []
        for i, offset in enumerate(range(0, len(data), 1_500_000)):
            part = path.with_name(path.name + f".part{i:04d}.json")
            save(part, {"hex": data[offset:offset + 1_500_000].hex()})
            parts.append(part.name)
        data = (json.dumps({"q39_split_parts": parts}) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".q39-", delete=False) as f:
        temporary = Path(f.name)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


def finite_number(value):
    v = float(value)
    return v if math.isfinite(v) else None


def packed(point):
    # Exact binary mpf serialization, independent of ambient decimal precision.
    return [[int(v._mpf_[0]), str(v._mpf_[1]), int(v._mpf_[2]), int(v._mpf_[3])]
            for v in point]


def unpacked(point):
    return [mp.make_mpf(tuple(int(x) for x in row)) for row in point]


def number(value):
    if value is None:
        return None
    return packed([value])[0]


def unnumber(value):
    return None if value is None else unpacked([value])[0]


def uniform(prefix):
    h = int.from_bytes(hashlib.sha256(prefix.encode()).digest()[:8], "big")
    return ((h >> 11) + 0.5) / 2**53


def hashpoint(prefix, bounds):
    return [lo + (hi - lo) * uniform(f"{prefix}|{j}")
            for j, (lo, hi) in enumerate(bounds)]


def selected():
    return {r["id"]: r for r in read(BASE / "selection.json")["selected"]}


def problem(identifier):
    row = selected()[identifier]
    path = ROOT / row["dsl_path"]
    if sha(path) != row["dsl_sha256"]:
        raise RuntimeError("locked DSL hash mismatch: " + identifier)
    document = GeometryProblem.model_validate(read(path)).engine_document()
    bundle = load_problem_bundle(document)
    return bundle, build_ir_evaluator(bundle), row


def mapping(bundle, row):
    import select_static
    helpers, _ = select_static.syntax_helpers()
    spec = bundle.spec
    dsl = {"id": row["id"], "variables": list(bundle.var_names),
           "constructions": [{"name": c.name, "expression": c.expr}
                             for c in spec.construction],
           "conditions": [{"left": s, "operator": "=", "right": str(t)}
                          for s, t in zip(spec.constraints, bundle.targets, strict=True)],
           "target": spec.answer_expr}
    classified = select_static.classify(
        {"id": row["id"], "dsl_path": row["dsl_path"].removeprefix("benchmarks/"),
         "dsl": dsl}, helpers)
    rewrites = classified["rewrites"]
    byrow = {r["equality_index_before_lowering"]: r for r in rewrites
             if "equality_index_before_lowering" in r}
    blocks, offset = [], 0
    for i, source in enumerate(spec.constraints):
        r = byrow.get(i, {})
        width = 2 if r.get("kind") == "distance_point_zero" else 1
        blocks.append({"a": i, "b": list(range(offset, offset + width)),
                       "kind": r.get("kind", "unchanged"), "source": source,
                       "rewrite": r})
        offset += width
    for r in rewrites:
        if r["kind"] == "positive_radius_aux":
            for source in r["sources"]:
                blocks.append({"a": None, "b": [offset], "kind": r["kind"],
                               "source": source, "rewrite": r})
                offset += 1
    def signatures(rows):
        return Counter((r["kind"], len(r.get("sources", []))) for r in rows)
    verified = (signatures(row["rewrites"]) == signatures(rewrites)
                and not classified["unsupported"])
    return {"status": "verified" if verified else "mapping_unverified",
            "static_rewrites": row["rewrites"], "compiled_rewrites": rewrites,
            "unsupported": classified["unsupported"], "blocks": blocks,
            "a_rows": len(spec.constraints), "b_rows": offset,
            "vars": list(bundle.var_names), "guards": list(spec.guards)}


class Representations:
    def __init__(self, bundle, plan, scales=None):
        self.bundle, self.plan, self.scales = bundle, plan, scales
        self.counters = Counter()
        with mp.workdps(180):
            self.scale_mp = ({k: [boundary_float_to_mpf(float(x), origin=BoundaryOrigin.OBJECTIVE_VALUE)
                                  for x in scales[k]] for k in ("a", "b")}
                             if scales else None)

    def both(self, point, residuals, dps):
        with mp.workdps(dps):
            point = [boundary_float_to_mpf(v, origin=BoundaryOrigin.INITIAL_POINT,
                                           allow_nonfinite=True) if isinstance(v, float) else v for v in point]
            source = [boundary_float_to_mpf(v, origin=BoundaryOrigin.OBJECTIVE_VALUE,
                                            allow_nonfinite=True) if isinstance(v, float) else v for v in residuals]
            b = FROZEN_SMOOTH(bundle=self.bundle, point=point, dps=dps, residuals=source)
        fallback = bool(self.plan["compiled_rewrites"]) and b is source
        wrong_rows = len(b) != self.plan["b_rows"]
        self.counters["evaluations"] += 1
        self.counters["rewrite_fallback"] += int(fallback)
        self.counters["row_count_mismatch"] += int(wrong_rows)
        valid = not (fallback or wrong_rows) and all(mp.isfinite(v) for v in b)
        return b, valid

    def line_gaps(self, point, dps):
        sources = []
        lineblocks = [b for b in self.plan["blocks"] if b["kind"] == "tangency_line_gap"]
        for block in lineblocks:
            sources.extend(block["rewrite"]["arguments"])
        with mp.workdps(dps):
            point = [boundary_float_to_mpf(v, origin=BoundaryOrigin.INITIAL_POINT,
                                           allow_nonfinite=True) if isinstance(v, float) else v for v in point]
        with mp.workdps(dps), high_precision_mode():
            context = mr.build_solution_context_high_precision(
                self.bundle.spec, list(self.bundle.var_names), point,
                self.bundle.base_context, dps, expressions=sources)
            values = {}
            for block in lineblocks:
                left, right = [mr.safe_eval_expr_hp(s, context)
                               for s in block["rewrite"]["arguments"]]
                left, right = getattr(left, "circle", left), getattr(right, "circle", right)
                line, circle = (left, right) if hasattr(left, "a") else (right, left)
                s = line.a * circle.center.x + line.b * circle.center.y + line.c
                values[block["b"][0]] = abs(s) - circle.radius
            return values

    def transform(self, mode, point, residuals, dps, b=None, valid=None):
        if mode == "A":
            return residuals
        if b is None:
            b, valid = self.both(point, residuals, dps)
        if not valid:
            # Preserve the frozen helper fallback, but never count it as a
            # successful B evaluation in Q/R. The failure is explicitly saved.
            return b
        if mode == "B":
            return b
        with mp.workdps(dps):
            if mode in ("L", "R0"):
                result = list(b)
                for i, value in self.line_gaps(point, dps).items():
                    result[i] = value
                if mode == "R0":
                    for k, block in enumerate(self.plan["blocks"]):
                        if block["kind"] in ("tangency_contact", "distance_radius_contact"):
                            ai, bi = block["a"], block["b"][0]
                            sign = -1 if b[bi] < 0 else 1
                            result[bi] = (self.scale_mp["b"][k] * sign
                                          * mp.sqrt(abs(residuals[ai])
                                                    / self.scale_mp["a"][ai]))
                return result
            if mode.startswith("mask:"):
                tag = mode.split(":", 1)[1]
                result = []
                for block in self.plan["blocks"]:
                    if block["kind"] == tag:
                        result.extend(b[i] for i in block["b"])
                    elif block["a"] is not None:
                        result.append(residuals[block["a"]])
                return result
        raise ValueError(mode)

    def norms(self, a, b):
        with mp.workdps(max(53, mp.dps)):
            aa = [abs(v) for v in a]
            bb = [mp.sqrt(mp.fsum(b[i]**2 for i in block["b"]))
                  for block in self.plan["blocks"]]
            return aa, bb

    def quality(self, a, b, valid):
        if not valid or not all(mp.isfinite(v) for v in a):
            return mp.inf, mp.inf, mp.inf
        aa, bb = self.norms(a, b)
        qa = max((v / s for v, s in zip(aa, self.scale_mp["a"], strict=True)), default=mp.mpf(0))
        qb = max((v / s for v, s in zip(bb, self.scale_mp["b"], strict=True)), default=mp.mpf(0))
        return max(qa, qb), qa, qb


def prepare(identifier):
    started = time.monotonic()
    bundle, evaluator, row = problem(identifier)
    plan = mapping(bundle, row)
    bounds = infer_problem_bounds(bundle)
    reps = Representations(bundle, plan)
    avals = [[] for _ in range(plan["a_rows"])]
    bvals = [[] for _ in plan["blocks"]]
    probes = []
    with mp.workdps(180), runtime_session(started + 20):
        for i in range(32):
            x = hashpoint(f"Q39-scale-v1|{identifier}|{i}", bounds)
            if expired():
                probes.append({"probe": i, "status": "preparation_timeout"})
                continue
            a = evaluator.evaluate_float_residual(x)
            b, valid = reps.both(x, list(a.residual_vector), 15)
            for dest, value in zip(avals, a.residual_vector, strict=True):
                if math.isfinite(value):
                    dest.append(abs(value))
            if len(b) == plan["b_rows"]:
                aa, bb = reps.norms(a.residual_vector, b)
                for dest, value in zip(bvals, bb, strict=True):
                    if valid and mp.isfinite(value):
                        dest.append(float(value))
            probes.append({"probe": i, "x_hex": [v.hex() for v in x],
                           "a_finite": a.is_finite, "b_valid": valid})
    scales = {"a": [max(1., statistics.median(v)) if v else 1. for v in avals],
              "b": [max(1., statistics.median(v)) if v else 1. for v in bvals],
              "a_finite_counts": list(map(len, avals)),
              "b_finite_counts": list(map(len, bvals))}
    result = {"id": identifier, "utc": utc(), "elapsed_seconds": time.monotonic() - started,
              "stratum": row["stratum"], "mapping": plan, "bounds": bounds,
              "scales": scales, "scale_probes": probes, "rewrite_audit": dict(reps.counters),
              "starts": {str(seed): [[v.hex() for v in hashpoint(
                  f"Q39-start-v1|{identifier}|{seed}|{i}", bounds)] for i in range(8)]
                         for seed in SEEDS}}
    save(OUT / "prepared" / f"{identifier}.json", result)
    return {"mapping": plan["status"], "rows": [plan["a_rows"], plan["b_rows"]],
            "probe_failures": sum(not p.get("b_valid", False) for p in probes)}


class SearchProxy:
    def __init__(self, original, reps, mode, bounds):
        self.original, self.reps, self.mode, self.bounds = original, reps, mode, bounds
        self.last = None

    def __getattr__(self, name):
        return getattr(self.original, name)

    def evaluate_float_residual(self, values):
        a = self.original.evaluate_float_residual(values)
        b, valid = self.reps.both(values, list(a.residual_vector), 15)
        q, qa, qb = self.reps.quality(a.residual_vector, b, valid)
        self.last = {"x_hex": [v.hex() for v in values], "Q": finite_number(q),
                     "QA": finite_number(qa), "QB": finite_number(qb),
                     "b_valid": valid, "a_finite": a.is_finite,
                     "box_valid": all(math.isfinite(v) and lo <= v <= hi
                                      for v, (lo, hi) in zip(values, self.bounds, strict=True))}
        if self.mode == "A":
            return a
        values_b = [float(v) for v in self.reps.transform(self.mode, values,
                   list(a.residual_vector), 15, b, valid)]
        finite = all(math.isfinite(v) for v in values_b)
        return replace(a, residual_vector=values_b,
                       residual_norm_float=residual_norm(values_b) if finite else math.inf,
                       evaluation_status=a.evaluation_status if finite else EvaluationStatus.NON_FINITE,
                       is_finite=a.is_finite and finite)


def front_dir(identifier, seed, mode):
    return OUT / "front" / identifier / str(seed) / mode.replace(":", "_")


def front(identifier, seed, mode):
    import PyNomad
    prep = read(OUT / "prepared" / f"{identifier}.json")
    summary = []
    for start_index in range(8):
        # A new evaluator per start prevents caches crossing search replicates.
        bundle, evaluator, _ = problem(identifier)
        reps = Representations(bundle, prep["mapping"], prep["scales"])
        proxy = SearchProxy(evaluator, reps, mode, prep["bounds"])
        x0 = [float.fromhex(v) for v in prep["starts"][str(seed)][start_index]]
        config = NomadConfig(max_bb_eval=1200, max_time_sec=6,
                             bound_expansion_ratio=0, seed_values=(seed * 100 + start_index,))
        start = time.monotonic()
        adapter = NomadBlackboxAdapter(evaluator=proxy, config=config, origin_seed=seed,
                   origin_start_point_index=start_index, deadline_monotonic=start + 6)
        ledger = {"best_any": None, "best_feasible": None, "prefixes": {},
                  "calls": 0, "valid": 0, "b_only_near_original_not_near": 0}
        def callback(point):
            ledger["calls"] += 1
            proxy.last = None
            previous = len(adapter.records)
            result = adapter(point)
            entry = proxy.last
            if entry is not None:
                rec = adapter.records[-1] if len(adapter.records) > previous else None
                entry = dict(entry, callback=ledger["calls"],
                             guard_ok=bool(rec and rec.guard_ok),
                             hard_feasible=bool(rec and rec.hard_feasible),
                             evaluation_complete=rec is not None,
                             candidate_id=rec.candidate_id if rec else -1,
                             score=finite_number(rec.score) if rec else None,
                             residual_norm_float=finite_number(rec.residual_norm_float) if rec else None)
                if entry["box_valid"] and entry["Q"] is not None:
                    ledger["valid"] += 1
                    if ledger["best_any"] is None or entry["Q"] < ledger["best_any"]["Q"]:
                        ledger["best_any"] = entry
                    if entry["guard_ok"] and entry["hard_feasible"]:
                        if ledger["best_feasible"] is None or entry["Q"] < ledger["best_feasible"]["Q"]:
                            ledger["best_feasible"] = entry
                if (entry["QB"] is not None and entry["QB"] <= 1e-4
                        and (entry["QA"] is None or entry["QA"] > 1e-4)):
                    ledger["b_only_near_original_not_near"] += 1
            if ledger["calls"] in (200, 800, 1200):
                best = ledger["best_feasible"] or ledger["best_any"]
                ledger["prefixes"][str(ledger["calls"])] = {
                    "reached": True, "Q": best["Q"] if best else None, "carried": False}
            return result
        error = None
        native = None
        with mp.workdps(180), runtime_session(start + 6):
            try:
                PyNomad.setSeed(seed * 100 + start_index)
                native = PyNomad.optimize(callback, x0,
                         [b[0] for b in prep["bounds"]], [b[1] for b in prep["bounds"]],
                         config.build_params(dimension=len(x0), seed=seed * 100 + start_index,
                                             search_mode="disco_mads"))
            except Exception as exc:
                error = {"type": type(exc).__name__, "message": str(exc)[:2000]}
        elapsed = time.monotonic() - start
        timeout = adapter.deadline_reached or elapsed >= 6
        best = ledger["best_feasible"] or ledger["best_any"]
        for prefix in (200, 800, 1200):
            ledger["prefixes"].setdefault(str(prefix), {
                "reached": False, "carried": not timeout and not error,
                "Q": best["Q"] if best and not timeout and not error else None})
        record = {"id": identifier, "seed": seed, "start_index": start_index, "mode": mode,
                  "utc": utc(), "initial_x_hex": prep["starts"][str(seed)][start_index],
                  "elapsed_seconds": elapsed, "timeout": timeout, "error": error,
                  "callback_count": ledger["calls"], "evaluation_count": adapter.evaluation_count,
                  "evaluation_failures": adapter.failure_count, "finite_box_points": ledger["valid"],
                  "rewrite_audit": dict(reps.counters), "prefixes": ledger["prefixes"],
                  "b_only_near_original_not_near": ledger["b_only_near_original_not_near"],
                  "native_stop_reason": str(native.get("stop_reason")) if isinstance(native, dict) else None,
                  "candidate": best,
                  "F": bool(best and best["guard_ok"] and best["hard_feasible"] and best["Q"] <= 1e-4
                            and not error and not timeout),
                  "callback_limit_ok": ledger["calls"] <= 1200}
        save(front_dir(identifier, seed, mode) / f"{start_index}.json", record)
        summary.append({k: record[k] for k in ("start_index", "F", "timeout", "callback_count", "callback_limit_ok")})
    return summary


def float_candidate(record, mode):
    r = record["candidate"]
    return FloatCandidate(x_float=tuple(float.fromhex(x) for x in r["x_hex"]),
            score=r["score"] if r["score"] is not None else math.inf,
            residual_norm_float=r["residual_norm_float"] if r["residual_norm_float"] is not None else math.inf,
            guard_ok=r["guard_ok"], evaluation_status=EvaluationStatus.OK,
            origin_seed=record["seed"], origin_start_point_index=record["start_index"],
            candidate_id=r["candidate_id"], hard_feasible=r["hard_feasible"],
            origin_backend="nomad", origin_family="Q39:" + mode,
            origin_evaluation_index=r["callback"])


def pack_candidate(c):
    return {"x": packed(c.x_hp), "residual_norm": number(c.residual_norm_hp),
            "answer": number(c.answer_hp), "status": c.refinement_status,
            "phase_history": list(c.phase_history), "candidate_id": c.candidate_id,
            "hard_feasible": c.hard_feasible, "hard_violation_tags": list(c.hard_violation_tags),
            "validity_margin": number(c.validity_margin_hp), "revision": c.revision,
            "coordinate_precision_dps": c.coordinate_precision_dps,
            "answer_precision_dps": c.answer_precision_dps,
            "coordinate_uncertainty": packed(c.coordinate_uncertainty),
            "answer_uncertainty": number(c.answer_uncertainty)}


def restore_candidate(c, source):
    return RefinedCandidate(x_hp=tuple(unpacked(c["x"])), residual_norm_hp=unnumber(c["residual_norm"]),
            answer_hp=unnumber(c["answer"]), refinement_status=c["status"],
            phase_history=tuple(c["phase_history"]), source=source, candidate_id=c["candidate_id"],
            hard_feasible=c["hard_feasible"], hard_violation_tags=tuple(c["hard_violation_tags"]),
            validity_margin_hp=unnumber(c["validity_margin"]), revision=c["revision"],
            coordinate_precision_dps=c["coordinate_precision_dps"],
            answer_precision_dps=c["answer_precision_dps"],
            coordinate_uncertainty=tuple(unpacked(c["coordinate_uncertainty"])),
            answer_uncertainty=unnumber(c["answer_uncertainty"]))


@contextmanager
def rear_hooks(reps, mode, snapshots, started, audit):
    original = {"smooth": mr._smooth_zero_constraint_residuals, "plan": mr.derivative_plan,
                "jacobian": mr.compute_finite_difference_jacobian,
                "stage": mr.MpmathRefiner._run_stage, "closure": mr._run_findroot_closure}
    def snapshot(label, point, dps, **extra):
        if len(snapshots) < 64:
            snapshots.append({"label": label, "elapsed_seconds": time.monotonic() - started,
                              "dps": dps, "point": packed(point), **extra})
        else:
            audit["snapshot_cap_reached"] += 1
    def smooth(**kwargs):
        audit["smoothing_calls"] += 1
        return reps.transform(mode, kwargs["point"], kwargs["residuals"], kwargs["dps"])
    def no_plan(*args, **kwargs):
        audit["analytic_plan_disabled"] += 1
        return None
    def jacobian(**kwargs):
        audit["finite_difference_calls"] += 1
        kwargs["row_dependencies"] = None
        if mode == "R0":
            kwargs["one_sided_at_cusp"] = True
        return original["jacobian"](**kwargs)
    def stage(self, **kwargs):
        audit["stage_calls"] += 1
        result = original["stage"](self, **kwargs)
        snapshot("stage_return", result[1], kwargs["dps"], status=result[0])
        return result
    def closure(**kwargs):
        audit["closure_calls"] += 1
        if mode == "R0":
            kwargs["one_sided_at_cusp"] = True
        result = original["closure"](**kwargs)
        if result is not None:
            snapshot("closure_return", result[0], kwargs["dps"])
        return result
    mr._smooth_zero_constraint_residuals, mr.derivative_plan = smooth, no_plan
    mr.compute_finite_difference_jacobian = jacobian
    mr.MpmathRefiner._run_stage, mr._run_findroot_closure = stage, closure
    try:
        yield snapshot
    finally:
        mr._smooth_zero_constraint_residuals, mr.derivative_plan = original["smooth"], original["plan"]
        mr.compute_finite_difference_jacobian = original["jacobian"]
        mr.MpmathRefiner._run_stage, mr._run_findroot_closure = original["stage"], original["closure"]


def rear_dir(identifier, seed, front_mode, rear_mode):
    return OUT / "rear" / identifier / str(seed) / (front_mode + "--" + rear_mode).replace(":", "_")


def rear(identifier, seed, front_mode, rear_mode):
    prep = read(OUT / "prepared" / f"{identifier}.json")
    destination = rear_dir(identifier, seed, front_mode, rear_mode)
    all_candidates = []
    summary = []
    for index in range(8):
        fr = read(front_dir(identifier, seed, front_mode) / f"{index}.json")
        result = {"id": identifier, "seed": seed, "start_index": index,
                  "front_mode": front_mode, "rear_mode": rear_mode,
                  "input_sha256": sha(front_dir(identifier, seed, front_mode) / f"{index}.json"),
                  "missing": fr["candidate"] is None, "candidates": [], "snapshots": []}
        if fr["candidate"] is not None:
            bundle, evaluator, _ = problem(identifier)
            reps = Representations(bundle, prep["mapping"], prep["scales"])
            source = float_candidate(fr, front_mode)
            audit = Counter()
            start = time.monotonic()
            with mp.workdps(180), rear_hooks(reps, rear_mode, result["snapshots"], start, audit) as observe:
                observe("input", [mp.mpf(x) for x in source.x_float], 180)
                try:
                    with runtime_session(start + 8) as timings:
                        batch = mr.MpmathRefiner(config=RefinerConfig()).refine_candidates(
                            bundle=bundle, evaluator=evaluator, candidates=(source,),
                            deadline_monotonic=start + 8)
                    all_candidates.extend(batch.candidates)
                    result["candidates"] = [pack_candidate(c) for c in batch.candidates]
                    for c in batch.candidates:
                        # Mandatory final point is kept separately even at cap.
                        observe("final", c.x_hp, c.coordinate_precision_dps,
                                refinement_status=c.refinement_status)
                    result["timings"] = dict(timings)
                    result["counters"] = timings.counters
                except Exception as exc:
                    result["error"] = {"type": type(exc).__name__, "message": str(exc)[:2000]}
            result.update(elapsed_seconds=time.monotonic() - start,
                          hook_audit=dict(audit), rewrite_audit=dict(reps.counters))
        save(destination / f"{index}.json", result)
        summary.append({"start_index": index, "missing": result["missing"],
                        "statuses": [c["status"] for c in result["candidates"]],
                        "error": result.get("error")})
    # All pre-identification points are durable before the unchanged Phase C.
    # Reference access happens in a separate, pinned observation subprocess.
    from measure_stage2 import observe_job_in_child
    observe_job_in_child(identifier, seed, front_mode, rear_mode)
    bundle, evaluator, _ = problem(identifier)
    start = time.monotonic()
    with mp.workdps(180), runtime_session(start + 20) as timings:
        assembly = assemble_exact_results(refined_candidates=tuple(all_candidates),
                      evaluator=evaluator, input_precision_dps=120, deadline_monotonic=start + 20)
        time_limited = expired() or any("deadline" in t for t in assembly.rejection_tags)
    answers, seen = [], set()
    for c in assembly.candidate_records:
        desc = c.exact_result.descriptor
        if desc is not None and desc.canonical_key() not in seen:
            seen.add(desc.canonical_key())
            answers.append(desc.model_dump(mode="json"))
    # Original verifier outputs are kept separately, never used as pre-C x.
    verified = [{"start_index": c.source.origin_start_point_index if c.source else -1,
                 "candidate": pack_candidate(c)} for c in assembly.numeric_feasible_candidates]
    phase_c = {"id": identifier, "seed": seed, "front_mode": front_mode, "rear_mode": rear_mode,
               "elapsed_seconds": time.monotonic() - start, "time_limited": time_limited,
               "answers": answers, "verified_candidates": verified,
               "numeric_feasible_count": len(assembly.numeric_feasible_candidates),
               "accepted_count": len(assembly.accepted_candidates),
               "rejection_tags": list(assembly.rejection_tags),
               "verification_summary": [{k: r.get(k) for k in
                    ("candidate_id", "candidate_uid", "verified", "status", "precision_dps",
                     "input_revision", "revision", "hard_failure_tags")}
                                        for r in assembly.verification_records],
               "timings": dict(timings), "counters": timings.counters,
               "status": "solved" if answers else "no_answer_found",
               "termination_reason": "time_limit_reached" if time_limited else "completed"}
    save(destination / "phase-c.json", phase_c)
    return {"candidates": summary, "answers": len(answers), "phase_c_timeout": time_limited}
