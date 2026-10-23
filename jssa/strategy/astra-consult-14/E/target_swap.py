"""Same-figure, changed-target local-search audit (no source modifications).

The production single-start routine is called, with a process-local subclass
that hashes its complete sequence of augmented residual evaluations. No step
or residual is changed by the subclass. All output goes to this directory.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import scipy

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "jssa/difficulty"))

from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.search import scipy_multistart_backend as smb
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from probe_basins import answer_float, reference_values

N = 64
SEED = 10231406
ORIGINAL_VECTOR = smb._AugmentedResidualVectorFn
ACTIVE = None


class RecordingVector(ORIGINAL_VECTOR):
    def __call__(self, raw_values):
        result = super().__call__(raw_values)
        x, r = np.asarray(raw_values, dtype="<f8"), np.asarray(result, dtype="<f8")
        ACTIVE["hash"].update(np.array([len(x), len(r)], dtype="<i8").tobytes())
        ACTIVE["hash"].update(x.tobytes())
        ACTIVE["hash"].update(r.tobytes())
        ACTIVE["calls"] += 1
        if len(ACTIVE["first_evaluations"]) < 3:
            ACTIVE["first_evaluations"].append({"x": x.tolist(), "R": r.tolist()})
        return result


def hash_sources():
    files = list((ROOT / "src").rglob("*.py")) + [ROOT / "benchmarks/cases.jsonl", ROOT / "jssa/difficulty/probe_basins.py"]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def clean(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        return repr(obj)
    if isinstance(obj, dict):
        return {k:clean(v) for k,v in obj.items()}
    if isinstance(obj, (tuple,list)):
        return [clean(v) for v in obj]
    return obj


def dump(name, data):
    (OUT / name).write_text(json.dumps(clean(data), ensure_ascii=False, indent=2, allow_nan=False)+"\n")


def main():
    global ACTIVE
    t0 = time.monotonic()
    before = hash_sources()
    cases = {c["id"]: c for c in map(json.loads, (ROOT / "benchmarks/cases.jsonl").read_text().splitlines())}
    targets = {
        "AIME-2014-II-14": [("original", None, 37.5), ("area", "Area(A, B, C)", 25*(1+math.sqrt(3))/2),
                            ("side_sq", "Distance(B, C) ** 2", 50.0)],
        "AIME-2021-I-11": [("original", None, 242/59), ("area", "Area(A, B, C, D)", 2*math.sqrt(210)),
                           ("diagonal_sq", "Distance(A, C) ** 2", 1711/31)]}
    config = ExternalPipelineConfig.production_baseline_tier(seed=SEED, total_time_budget_sec=180).search
    summaries, records = [], []
    smb._AugmentedResidualVectorFn = RecordingVector
    try:
        for ci, (cid, choices) in enumerate(targets.items()):
            case = cases[cid]
            setups = []
            for name, target, expected in choices:
                dsl = copy.deepcopy(case["dsl"])
                if target is not None:
                    dsl["target"] = target
                bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
                evaluator = build_ir_evaluator(bundle)
                box = infer_problem_bounds(bundle)
                setups.append(dict(name=name, dsl=dsl, bundle=bundle, evaluator=evaluator, box=box, expected=expected))
            base = setups[0]
            equality_audit=[]
            for s in setups:
                equality_audit.append({"name":s["name"], "target":s["dsl"]["target"],
                    "box":s["box"], "variables_equal":s["bundle"].var_names==base["bundle"].var_names,
                    "constraints_equal":s["bundle"].spec.constraints==base["bundle"].spec.constraints,
                    "constraint_rhs_equal":s["bundle"].targets==base["bundle"].targets,
                    "guards_equal":s["bundle"].spec.guards==base["bundle"].spec.guards,
                    "compiled_guards_equal":s["evaluator"].compiled_guards==base["evaluator"].compiled_guards,
                    "hard_checks_equal":s["bundle"].hard_feasibility_checks==base["bundle"].hard_feasibility_checks,
                    "box_equal":s["box"]==base["box"]})
            bb=np.asarray(base["box"])
            starts=bb[:,0]+np.random.default_rng([SEED,ci]).random((N,len(bb)))*(bb[:,1]-bb[:,0])
            case_rows=[]
            for k,start in enumerate(starts):
                variants={}
                for j in [(k+i)%len(setups) for i in range(len(setups))]:
                    s=setups[j]
                    ACTIVE={"hash":hashlib.sha256(), "calls":0, "first_evaluations":[]}
                    telemetry=smb._SearchTelemetry()
                    t1=time.monotonic()
                    try:
                        candidate=smb._collect_local_start_record(bundle=s["bundle"], evaluator=s["evaluator"],
                            bounds=base["box"], config=config, seed=SEED, start_index=k, start=start.copy(),
                            deadline_monotonic=t1+10, telemetry=telemetry)
                        error=None
                    except Exception as exc:
                        candidate=None; error=f"{type(exc).__name__}: {exc}"
                    rec=dict(sec=time.monotonic()-t1, nfev=telemetry.evaluation_count, vector_calls=ACTIVE["calls"],
                             trace_sha256=ACTIVE["hash"].hexdigest(), error=error, candidate=candidate is not None)
                    if k==0:
                        rec["first_evaluations"]=ACTIVE["first_evaluations"]
                    if candidate is not None:
                        x=candidate.x_float
                        v=answer_float(s["evaluator"],x)
                        original_v=answer_float(base["evaluator"],x)
                        residual=candidate.residual_norm_float
                        original_match=original_v is not None and abs(original_v-base["expected"])<=1e-6*max(1,abs(base["expected"]))
                        geom_ok=(math.isfinite(residual) and residual<=1e-8 and bool(candidate.guard_ok)
                                 and candidate.hard_feasible is not False and original_match)
                        match=v is not None and abs(v-s["expected"])<=1e-6*max(1,abs(s["expected"]))
                        rec.update(x=list(x), residual=residual, guard_ok=bool(candidate.guard_ok),
                                   hard_feasible=candidate.hard_feasible, value=v, original_value=original_v,
                                   original_geometry_hit=bool(geom_ok), target_value_matches=bool(match),
                                   target_hit=bool(geom_ok and match))
                    variants[s["name"]]=rec
                orig=variants["original"]
                paired={}
                for name in variants:
                    if name=="original": continue
                    other=variants[name]
                    paired[name]=dict(
                        trace_equal=orig["trace_sha256"]==other["trace_sha256"],
                        nfev_equal=orig["nfev"]==other["nfev"],
                        endpoint_equal=("x" in orig and "x" in other and np.array_equal(orig["x"],other["x"])),
                        geometry_hit_equal=orig.get("original_geometry_hit")==other.get("original_geometry_hit"))
                case_rows.append(dict(id=cid,k=k,start=start.tolist(),variants=variants,paired=paired))
            records.extend(case_rows)
            summary=dict(id=cid, starts=N, compiled_input_audit=equality_audit,
                         variants={s["name"]:dict(
                             geometry_hits=sum(r["variants"][s["name"]].get("original_geometry_hit",False) for r in case_rows),
                             target_hits=sum(r["variants"][s["name"]].get("target_hit",False) for r in case_rows),
                             expected_value=s["expected"],
                             errors=sum(r["variants"][s["name"]]["error"] is not None for r in case_rows),
                             total_nfev=sum(r["variants"][s["name"]]["nfev"] for r in case_rows),
                             total_sec=sum(r["variants"][s["name"]]["sec"] for r in case_rows)) for s in setups},
                         paired={s["name"]:{q:sum(r["paired"][s["name"]][q] for r in case_rows)
                                 for q in ("trace_equal","nfev_equal","endpoint_equal","geometry_hit_equal")}
                                 for s in setups[1:]})
            summaries.append(summary)
            dump("target-swap-records.json",records)
            dump("target-swap-summary.json", summaries)
            print(json.dumps(summary, ensure_ascii=False), flush=True)
    finally:
        smb._AugmentedResidualVectorFn=ORIGINAL_VECTOR
    after=hash_sources()
    dump("target-swap-manifest.json",dict(seed=SEED,starts_per_case=N,python=sys.version,numpy=np.__version__,scipy=scipy.__version__,
        elapsed_sec=time.monotonic()-t0,inputs_before=before,inputs_after=after,inputs_unchanged=before==after,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))


if __name__=="__main__":
    main()
