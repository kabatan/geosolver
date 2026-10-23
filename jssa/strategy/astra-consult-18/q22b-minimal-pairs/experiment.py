"""Frozen paired local-search experiment. All output stays beside this file."""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np
import scipy
from scipy.optimize import least_squares

from geosolver import GeometryProblem
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search import scipy_multistart_backend as smb

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0,str(ROOT / "jssa/difficulty"))
from probe_basins import answer_float

SEEDS = [220231,220232]
N_PER_SEED = 32
NATIVE_CAP = 80
LONG_CAP = 320
PER_START_SECONDS = 10
GLOBAL_SECONDS = 2400


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def src_digest():
    h = hashlib.sha256()
    for p in sorted((ROOT / "src").rglob("*.py")):
        h.update(str(p.relative_to(ROOT)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def write(p, value):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n"
    assert len(text.encode()) < 10_000_000
    p.write_text(text)


def scalar(x):
    return float(x) if x is not None and math.isfinite(float(x)) else None


def make(bundle_dsl):
    b = load_problem_bundle(GeometryProblem.model_validate(bundle_dsl).engine_document())
    return b, build_ir_evaluator(b)


def classify(pair, v, b, ev, x):
    x = np.asarray(x,dtype=float)
    box = all(lo <= z <= hi for z,(lo,hi) in zip(x,pair["bounds"]))
    rr = ev.evaluate_float_residual(list(x))
    norm = float(np.linalg.norm(rr.residual_vector))
    guard = bool(ev.evaluate_guard(list(x))[0])
    hard = bool(ev.evaluate_float_hard_feasibility(list(x),include_margins=False).hard_feasible)
    root = np.array(v["root"],dtype=float)
    coordinate_error = float(np.linalg.norm(x-root))
    if pair["group"] == "H":
        root[1] *= -1
        coordinate_error = min(coordinate_error,float(np.linalg.norm(x-root)))
    geom = bool(box and norm<=1e-8 and guard and hard and coordinate_error<=1e-5)
    value = answer_float(ev,x) if geom else None
    answer_ok = value is not None and abs(value-float(v["reference"]))<=1e-6*max(1.0,abs(float(v["reference"])))
    return {"x":list(map(float,x)),"residual":scalar(norm),"in_box":bool(box),"guard":guard,"hard":hard,
            "coordinate_error":scalar(coordinate_error),"geometry_hit":geom,"answer":scalar(value),
            "hit":bool(geom and answer_ok)}


def direct_vector(pair, sign, x):
    a, h = float(pair["a"]),float(pair["h"])
    u, v = x
    return np.array([(u+a)**2+v*v-a*a-1,(u-a)**2+v*v-a*a-1,
                     u*u+(v-h)**2-(sign-h)**2,0.0,0.0])


def run_pair(pair, global_deadline):
    built = {name:make(v["dsl"]) for name,v in pair["variants"].items()}
    modes = [(name,name,"native",NATIVE_CAP) for name in pair["variants"]]
    if pair["group"]=="S":
        modes += [("direct_near","power_near","direct",NATIVE_CAP),
                  ("direct_far","power_far","direct",NATIVE_CAP),
                  ("long_near","power_near","native",LONG_CAP),
                  ("long_far","power_far","native",LONG_CAP)]
    rows = []
    t0 = time.monotonic()
    native_ls = smb.least_squares
    captured = {}

    def capture(*args,**kwargs):
        rr = native_ls(*args,**kwargs)
        captured.update(status=int(rr.status),nfev=int(rr.nfev),njev=None if rr.njev is None else int(rr.njev),
                        cost=scalar(rr.cost),optimality=scalar(rr.optimality),message=str(rr.message))
        return rr

    smb.least_squares = capture
    for seed in SEEDS:
        for k in range(N_PER_SEED):
            rng = np.random.default_rng([seed,int(pair["id"][1:]),1 if pair["group"]=="S" else 2,k])
            lo, hi = np.array(pair["bounds"],dtype=float).T
            start = lo+rng.random(2)*(hi-lo)
            # Alternate processing order without changing paired starts.
            ordered = modes if k%2==0 else list(reversed(modes))
            for name,vname,backend,cap in ordered:
                base = {"pair":pair["id"],"mode":name,"seed":seed,"k":k,"start":list(map(float,start)),
                        "backend":backend,"max_nfev":cap,"hit":False,"geometry_hit":False}
                if time.monotonic()>=global_deadline:
                    base["error"]="global_budget_not_run"
                    rows.append(base)
                    continue
                b,ev=built[vname]
                v=pair["variants"][vname]
                tel=smb._SearchTelemetry()
                cfg=ExternalPipelineConfig.production_baseline_tier(seed=seed,total_time_budget_sec=180).search
                captured.clear()
                ts=time.monotonic()
                try:
                    if backend=="native":
                        smb._LM_MAX_NFEV=cap
                        cand=smb._collect_local_start_record(bundle=b,evaluator=ev,bounds=pair["bounds"],config=cfg,
                            seed=seed,start_index=k,start=start,deadline_monotonic=min(global_deadline,ts+PER_START_SECONDS),telemetry=tel)
                        if cand is None:
                            raise RuntimeError("native_candidate_none")
                        x=cand.x_float
                    else:
                        sign=1 if name.endswith("near") else -1
                        rr=least_squares(lambda q:direct_vector(pair,sign,q),start,method="lm",max_nfev=cap,
                                         ftol=1e-14,xtol=1e-14,gtol=1e-14)
                        x=rr.x
                        captured.update(status=int(rr.status),nfev=int(rr.nfev),cost=scalar(rr.cost),optimality=scalar(rr.optimality))
                    base.update(classify(pair,v,b,ev,x))
                except Exception as err:
                    base["error"]=type(err).__name__+":"+str(err)[:200]
                base.update(seconds=time.monotonic()-ts,telemetry_evaluations=tel.evaluation_count,stop=dict(captured))
                rows.append(base)
    smb.least_squares=native_ls
    smb._LM_MAX_NFEV=NATIVE_CAP
    write(OUT / "raw" / f"{pair['id']}.json",{"pair":pair["id"],"seconds":time.monotonic()-t0,"rows":rows})
    summary={name:{"n":sum(r["mode"]==name for r in rows),"hits":sum(r["mode"]==name and r["hit"] for r in rows),
                   "errors":sum(r["mode"]==name and "error" in r for r in rows)} for name,_,_,_ in modes}
    return {"pair":pair["id"],"seconds":time.monotonic()-t0,"summary":summary}


def main():
    lock=json.loads((OUT / "registration-lock.json").read_text())
    for name,sha in lock["files"].items():
        assert digest(OUT / name)==sha, ("registration changed",name)
    assert src_digest()==lock["src_sha256"],"src changed before experiment"
    assert smb._LM_MAX_NFEV==NATIVE_CAP
    if (OUT / "execution.json").exists():
        raise RuntimeError("Refuse to overwrite an existing execution")
    pairs=json.loads((OUT / "stimuli.json").read_text())
    (OUT / "raw").mkdir(exist_ok=True)
    start=time.monotonic()
    execution={"started_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"numpy":np.__version__,"scipy":scipy.__version__,
               "python":sys.version,"pid":os.getpid(),"workers":2,"global_seconds":GLOBAL_SECONDS,"completed":[]}
    write(OUT / "execution.json",execution)
    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(run_pair,pair,start+GLOBAL_SECONDS) for pair in pairs]
        for f in concurrent.futures.as_completed(futures):
            result=f.result()
            execution["completed"].append(result)
            write(OUT / "execution.json",execution)
            print(json.dumps(result),flush=True)
    execution.update(finished_utc=dt.datetime.now(dt.timezone.utc).isoformat(),seconds=time.monotonic()-start,
                     final_src_sha256=src_digest(),lock_files_unchanged=all(digest(OUT/name)==sha for name,sha in lock["files"].items()))
    write(OUT / "execution.json",execution)


if __name__=="__main__":
    main()
