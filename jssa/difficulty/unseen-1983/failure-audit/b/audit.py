"""Q29b diagnostic only: original DSL, hand-derived witnesses, frozen solver.

Run with the existing Python 3.12 environment. No sealed archive is read.
Every output is capped below 5 MB; the source and original scores are read-only.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import math
import importlib
import signal
from dataclasses import asdict, is_dataclass
from contextlib import contextmanager

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
BASE = OUT.parents[1]
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTHONPATH"] = str(ROOT / "src")
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
sys.path.insert(0, str(ROOT / "src"))
resource.setrlimit(resource.RLIMIT_FSIZE, (4_900_000, 4_900_000))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

import numpy as np
from mpmath import mp
from geosolver import GeometryProblem, SolveOptions, solve
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.high_precision_expressions import build_solution_context_high_precision
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.problem.ir.compiler import safe_eval_expr_hp

IDS = ["AIME-1996-13", "AIME-1996-15", "AIME-1997-04",
       "HMMT-2022-FEB-GEO-07", "HMMT-2023-FEB-GEO-06"]
ANSWERS = dict(zip(IDS, [65, 777, 17, 16902, 68]))


def clean(x):
    if is_dataclass(x):
        return clean(asdict(x))
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray)):
        return [clean(v) for v in x]
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x,float) and not math.isfinite(x):
        return str(x)
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    return str(x)


def save(name, data):
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(clean(data), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    assert len(payload.encode()) < 4_900_000
    p.write_text(payload)


def bounded_public_result(data):
    """Keep decision-relevant data when a public diagnostic payload is too large."""
    encoded=json.dumps(clean(data),ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    if len(encoded.encode())<4_900_000: return data
    from collections import Counter
    d=data.get("diagnostics") or {}
    s=d.get("pipeline_summary") or {}
    minimal=dict(data)
    minimal["diagnostics"]={k:v for k,v in d.items() if k in
        ("numeric_feasible","exact_identified","public_solved","process_info","config_snapshot",
         "exact_answer_attempt_count","exact_answer_identified_count","pipeline_backend")}
    minimal["diagnostics"]["pipeline_summary"]={k:v for k,v in s.items() if k in
        ("initial_probe","refinement","exact_assembly","search_staged_fallback","pipeline_backend")}
    minimal["diagnostics"]["verification_status_counts"]=dict(Counter(v.get("status") for v in s.get("verification_records",[])))
    minimal["output_compaction"]={"reason":"user_file_limit_5MB","full_pretty_json_bytes":len(encoded.encode()),
                                  "decision_fields_preserved":True,"solver_computation_changed":False}
    return minimal


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(cid):
    d = json.loads((BASE / "dsl" / f"{cid}.json").read_text())
    p = GeometryProblem.model_validate(d)
    b = load_problem_bundle(p.engine_document())
    return d, p, b, build_ir_evaluator(b)


def witness(cid):
    """Closed form, calculated afresh at the active precision; no fitting to DSL."""
    if cid == IDS[0]:
        return dict(cx=7*mp.sqrt(30)/20, cy=mp.sqrt(930)/20,
                    t=mp.mpf(27)/19, m=mp.mpf(27), n=mp.mpf(38), u=mp.mpf(-7), v=mp.mpf(5))
    if cid == IDS[1]:
        return dict(dx=(1-mp.sqrt(3))/2, dy=(mp.sqrt(3)-1)/2, r=mp.mpf(7)/9)
    if cid == IDS[2]:
        return dict(cx=mp.mpf(5), cy=mp.mpf(12), dx=mp.mpf(5), dy=mp.mpf(28)/9,
                    r=mp.mpf(8)/9, m=mp.mpf(8), n=mp.mpf(9), u=mp.mpf(-1), v=mp.mpf(1))
    if cid == IDS[3]:
        q=5-mp.sqrt(69)/2
        return dict(x=q, y=q, a=mp.mpf(169), b=mp.mpf(2), h=mp.mpf(1), k=mp.mpf(-84))
    if cid == IDS[4]:
        dx=2*mp.sin(77*mp.pi/180)*mp.cos(73*mp.pi/180)
        dy=2*mp.sin(77*mp.pi/180)*mp.sin(73*mp.pi/180)
        s=(dx*dx+dy*dy-1)/(2*((dx-1)*mp.cos(mp.pi/6)+dy*mp.sin(mp.pi/6)))
        return dict(cx=s*mp.cos(mp.pi/6), cy=s*mp.sin(mp.pi/6), dx=dx, dy=dy, n=mp.mpf(68))
    raise ValueError(cid)


def audit_witness(cid, dps):
    d,p,b,ev=load(cid)
    with mp.workdps(dps), high_precision_mode():
        w=witness(cid)
        x=[w[n] for n in b.var_names]
        ctx=build_solution_context_high_precision(b.spec,list(b.var_names),x,b.base_context,dps)
        rows=[]
        for i,c in enumerate(d["conditions"]):
            l=mp.mpf(safe_eval_expr_hp(c["left"],ctx))
            r=mp.mpf(safe_eval_expr_hp(str(c["right"]),ctx))
            delta=l-r
            op=c["operator"]
            margin=delta if op in (">",">=") else -delta if op in ("<","<=") else None
            ok=abs(delta)<mp.mpf(10)**(-dps+15) if op=="=" else (margin>0 if op in (">","<") else margin>=0)
            rows.append(dict(index=i,left=c["left"],operator=op,right=c["right"],
                             lhs=l,rhs=r,residual=delta,margin=margin,passed=bool(ok)))
        hp=ev.evaluate_hp_residual(x,precision=dps)
        guard=ev.evaluate_guard(x)
        hard=ev.evaluate_hp_hard_feasibility(x,precision=dps)
        ans=ev.evaluate_answer_hp(x,precision=dps)
        points={c["name"]:[ctx[c["name"]].x,ctx[c["name"]].y] for c in d["constructions"]
                if hasattr(ctx[c["name"]],"x")}
        box=infer_problem_bounds(b)
        from geosolver.engine.standard.search.nomad_backend import _expand_bounds
        from geosolver.engine.standard.search.nomad_config import BOUND_EXPANSION_RATIO_DEFAULT
        from geosolver.engine.standard.interpreter.compile.infer_bounds import infer_bound_expansion_locks
        expanded_box=_expand_bounds(box,BOUND_EXPANSION_RATIO_DEFAULT,
                                   expansion_locks=tuple(infer_bound_expansion_locks(b.spec,b.var_names)))
        return clean(dict(id=cid,dps=dps,variables=w,points=points,conditions=rows,
                          max_abs_equality_residual=max(abs(mp.mpf(r["residual"])) for r in rows if r["operator"]=="="),
                          min_original_inequality_margin=min(r["margin"] for r in rows if r["margin"] is not None),
                          solver_residual=hp,solver_guard=guard,solver_hard=hard,solver_answer=ans,
                          all_original_conditions_pass=all(r["passed"] for r in rows),
                          search_box=dict(zip(b.var_names,box)),
                          nomad_expanded_search_box=dict(zip(b.var_names,expanded_box)),
                          witness_outside_search_box=[n for n,(lo,hi) in zip(b.var_names,box) if not mp.mpf(str(lo))<=w[n]<=mp.mpf(str(hi))]))


def prepare():
    diff=subprocess.check_output(["git","diff","60db4b6","--","src"],cwd=ROOT)
    if diff: raise RuntimeError("src differs from frozen commit; use a frozen source extraction")
    manifest={"frozen_commit":subprocess.check_output(["git","rev-parse","60db4b6"],cwd=ROOT,text=True).strip(),
              "current_src_equals_frozen":True,"python":sys.version,"max_parallel_compute":4,
              "original_score":"85/130; immutable; diagnostic runs excluded", "natural_seed":201,
              "natural_budget_seconds":900, "sources":{}}
    paths=[BASE/"prereg/result.md",BASE/"prereg/q19-scored/assessment.jsonl",
           BASE/"audit/primary-extracts.json",BASE/"audit/hmmt-primary-evidence.json"]
    paths += [BASE/"dsl"/f"{cid}.json" for cid in IDS]
    manifest["sources"]={str(p.relative_to(ROOT)):sha(p) for p in paths}
    manifest["src_files"]={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/"src").rglob("*.py"))}
    save("manifest.json",manifest)
    for cid in IDS:
        rec=[audit_witness(cid,dps) for dps in (80,160)]
        save(f"witnesses/{cid}.json",rec)
        print(cid, [(r["max_abs_equality_residual"],r["solver_guard"],r["solver_hard"],r["solver_answer"]) for r in rec],flush=True)
        assert all(r["all_original_conditions_pass"] for r in rec)


def natural(cid, cpu, budget, observe_io=False):
    os.sched_setaffinity(0,{cpu})
    d,p,b,ev=load(cid)
    runner_module=importlib.import_module("geosolver.engine.runner")
    original_temp=runner_module.tempfile.TemporaryDirectory
    io_records=[]
    @contextmanager
    def observed_temp(*args,**kw):
        with original_temp(*args,**kw) as directory:
            try: yield directory
            finally:
                path=Path(directory)
                rec={"files":{f.name:f.stat().st_size for f in path.iterdir() if f.is_file()}}
                for name in ("stdout.log","stderr.log"):
                    f=path/name
                    if f.exists(): rec[name]=f.read_text(errors="replace")[-16000:]
                io_records.append(rec)
    if observe_io: runner_module.tempfile.TemporaryDirectory=observed_temp
    try: result=solve(p,SolveOptions(time_limit_seconds=budget,cores=1,seed=201))
    finally: runner_module.tempfile.TemporaryDirectory=original_temp
    data=result.model_dump(mode="json")
    data.update(audit_kind="unmodified_DSL_unmodified_frozen_solver_new_diagnostic_run",
                frozen_score_unchanged="85/130",affinity_cpu=cpu)
    suffix="-io-observed" if observe_io else ""
    if observe_io: data["io_observation"]=io_records
    save(f"runs/natural-{budget}-{cid}{suffix}.json",bounded_public_result(data))
    print(cid,budget,result.status,result.elapsed_seconds,flush=True)


def start_point(cid, epsilon, seed):
    _,_,b,_=load(cid)
    with mp.workdps(80):
        w=witness(cid)
        x=np.array([float(w[n]) for n in b.var_names])
    noise=np.random.default_rng(seed).uniform(-1,1,len(x))
    return x + epsilon*np.maximum(1,np.abs(x))*noise


def worker_precision(function):
    """Match runtime.worker.execute's ambient precision around the full pipeline."""
    def wrapped(*args,**kwargs):
        with mp.workdps(180):
            return function(*args,**kwargs)
    return wrapped


def direct_candidate(ev, x):
    from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
    f=ev.evaluate_float_residual(x)
    g=ev.evaluate_guard(x)
    h=ev.evaluate_float_hard_feasibility(x)
    return FloatCandidate(x_float=tuple(map(float,x)),score=float(f.residual_norm_float),
        residual_norm_float=float(f.residual_norm_float),guard_ok=g[0],evaluation_status=f.evaluation_status,
        origin_seed=2900,origin_start_point_index=0,candidate_id=290000,hard_feasible=h.hard_feasible,
        hard_violation_tags=h.failure_tags,origin_phase="oracle_near_diagnostic",origin_backend="q29b")


@worker_precision
def local(cid,cpu):
    """Frozen float LM at 7 starts; frozen HP refiner and Phase C at one near start."""
    os.sched_setaffinity(0,{cpu})
    from geosolver.engine.standard.search import scipy_multistart_backend as smb
    from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
    from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
    from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
    d,p,b,ev=load(cid)
    box=infer_problem_bounds(b)
    config=ExternalPipelineConfig.production_baseline_tier(seed=201,total_time_budget_sec=180).search
    records=[]
    for eps,seed in [(0,2900)]+[(eps,seed) for eps in (1e-4,1e-2) for seed in (2900,2901,2902)]:
        x=start_point(cid,eps,seed)
        t=time.monotonic()
        tel=smb._SearchTelemetry()
        r=dict(epsilon=eps,noise_seed=seed,start=x)
        try:
            c=smb._collect_local_start_record(bundle=b,evaluator=ev,bounds=box,config=config,seed=201,
                start_index=len(records),start=x,deadline_monotonic=t+30,telemetry=tel)
            r["candidate"]=clean(c)
            if c is not None:
                # Evaluate the endpoint independently even if the search box rejects it.
                f=ev.evaluate_float_residual(c.x_float)
                r["endpoint_residual_without_box_filter"]=clean(f)
        except Exception as e:
            r["error"]=type(e).__name__+": "+str(e)
        r.update(elapsed=time.monotonic()-t,evaluations=tel.evaluation_count)
        records.append(clean(r))
    save(f"local/{cid}-float.json",records)
    print(cid,"float local completed",flush=True)
    # This direct injection tests only the frozen refiner/verifier, not its heuristic box filter.
    x=start_point(cid,1e-4,2900)
    c=direct_candidate(ev,x)
    t=time.monotonic()
    data=dict(id=cid,kind="oracle_near_direct_HP_refiner_and_original_Phase_C",epsilon=1e-4,ambient_dps=180,
              noise_seed=2900,start=x,not_a_natural_solve=True,heuristic_search_box_bypassed=True)
    try:
        r=MpmathRefiner().refine_candidates(bundle=b,evaluator=ev,candidates=(c,),deadline_monotonic=t+90)
        data["refinement"]=clean(r)
        data["assembly"]=clean(assemble_exact_results(refined_candidates=r.candidates,evaluator=ev,
            input_precision_dps=120,deadline_monotonic=t+120))
    except Exception as e:
        data["error"]=type(e).__name__+": "+str(e)
    data["elapsed"]=time.monotonic()-t
    save(f"local/{cid}-hp.json",data)
    print(cid,"HP completed",data["elapsed"],flush=True)


@worker_precision
def near_pipeline(cid,cpu,budget,expanded=False):
    """All frozen pipeline stages, replacing only start selection (oracle diagnostic)."""
    import faulthandler
    faulthandler.enable()
    os.sched_setaffinity(0,{cpu})
    rp=importlib.import_module("geosolver.engine.standard.orchestration.run_external_pipeline")
    rs=importlib.import_module("geosolver.engine.standard.orchestration.run_search")
    from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
    d,p,b,ev=load(cid)
    x=start_point(cid,1e-4,2900)
    old_select=rs.select_search_start_points
    old_bounds=rp.infer_problem_bounds
    calls=[]
    boxes=[]
    def select(**kw):
        calls.append({"required_count":kw["required_count"],"bounds":kw["bounds"],"start":list(x)})
        return [list(x)]
    def bounds(bundle):
        box=old_bounds(bundle)
        if expanded:
            box=[(min(lo,float(v)-max(1,abs(v))), max(hi,float(v)+max(1,abs(v))))
                 for (lo,hi),v in zip(box,x)]
        boxes.append(box)
        return box
    rs.select_search_start_points=select
    rp.infer_problem_bounds=bounds
    t=time.monotonic()
    data=dict(id=cid,kind="oracle_near_full_frozen_pipeline",seed=201,epsilon=1e-4,noise_seed=2900,ambient_dps=180,
              budget=budget,expanded_heuristic_box_control=expanded,DSL_changed=False,start=x,
              frozen_score_unchanged="85/130",not_a_natural_solve=True)
    try:
        conf=ExternalPipelineConfig.production_baseline_tier(seed=201,total_time_budget_sec=budget)
        r=rp.run_external_pipeline(p.engine_document(),seed=201,pipeline_config=conf,
                                   deadline_monotonic=t+budget)
        data.update(status=r.status,accepted_answers=r.accepted_answers,exact_results=r.exact_results,
                    summary=r.summary)
    except Exception as e:
        data.update(status="diagnostic_exception",error=type(e).__name__+": "+str(e))
    finally:
        rs.select_search_start_points=old_select
        rp.infer_problem_bounds=old_bounds
    data.update(elapsed=time.monotonic()-t,start_selection_calls=calls,boxes=boxes)
    suffix="-expanded-box-control" if expanded else ""
    save(f"runs/near-{budget}-{cid}{suffix}.json",data)
    print(cid,"near",data["status"],data["elapsed"],flush=True)


def supervised_near(cid,cpu,budget,expanded=False):
    """Persist crashes from native NOMAD, including an out-of-box oracle start."""
    suffix="-expanded-box-control" if expanded else ""
    stem=f"near-{budget}-{cid}{suffix}"
    cmd=[sys.executable,str(Path(__file__).resolve()),"near-worker","--id",cid,"--cpu",str(cpu),"--budget",str(budget)]
    if expanded: cmd.append("--expanded")
    t=time.monotonic()
    log=OUT/"runs"/f"{stem}.log"
    log.parent.mkdir(exist_ok=True)
    timed_out=False
    with log.open("w") as f:
        p=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        try: p.wait(timeout=budget+15)
        except subprocess.TimeoutExpired:
            timed_out=True
            os.killpg(p.pid,signal.SIGKILL)
            p.wait()
    receipt=dict(command=cmd,returncode=p.returncode,elapsed=time.monotonic()-t,
                 supervisor_timeout=timed_out,log=log.name)
    save(f"runs/{stem}-process.json",receipt)
    if p.returncode!=0:
        save(f"runs/{stem}.json",dict(id=cid,kind="oracle_near_full_frozen_pipeline",status="process_failed",
             budget=budget,seed=201,epsilon=1e-4,noise_seed=2900,expanded_heuristic_box_control=expanded,
             DSL_changed=False,not_a_natural_solve=True,ambient_dps=180,**receipt))
    print(cid,"near subprocess",p.returncode,receipt["elapsed"],flush=True)


def features(d):
    texts=[c["expression"] for c in d["constructions"]]+[d["target"]]
    texts += [str(c[k]) for c in d["conditions"] for k in ("left","right","predicate") if k in c]
    calls=[]
    floordiv=0
    for s in texts:
        tree=ast.parse(s,mode="eval")
        calls += [n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        floordiv+=sum(isinstance(n,ast.FloorDiv) for n in ast.walk(tree))
    point_types={"Point","Midpoint","Circumcenter","Incenter","Orthocenter","Centroid",
                 "PointOnLine","PointOnSegment","PointOnCircle","PointOnRay","PointOnArc",
                 "Projection","Reflect","Rotate","Translate","LineIntersection"}
    top_calls=[ast.parse(c["expression"],mode="eval").body for c in d["constructions"]]
    names=[n.func.id for n in top_calls if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
    integers=set()
    for c in d["conditions"]:
        if c.get("operator")=="=" and str(c.get("right"))=="0":
            tree=ast.parse(c["left"],mode="eval").body
            if isinstance(tree,ast.Call) and isinstance(tree.func,ast.Name) and tree.func.id=="IsInteger" and isinstance(tree.args[0],ast.Name):
                integers.add(tree.args[0].id)
    bezout=False
    for c in d["conditions"]:
        if c.get("operator")!="=" or str(c.get("right"))!="1": continue
        t=ast.parse(c["left"],mode="eval").body
        if isinstance(t,ast.BinOp) and isinstance(t.op,ast.Add):
            terms=[t.left,t.right]
            if all(isinstance(z,ast.BinOp) and isinstance(z.op,ast.Mult) and
                   isinstance(z.left,ast.Name) and isinstance(z.right,ast.Name) and
                   z.left.id in integers and z.right.id in integers for z in terms): bezout=True
    return dict(id=d["id"],variables=len(d["variables"]),equalities=sum(c.get("operator")=="=" for c in d["conditions"]),
                inequalities=sum(c.get("operator") in (">",">=","<","<=","!=") for c in d["conditions"]),
                predicates=sum("predicate" in c for c in d["conditions"]),constructions=len(d["constructions"]),
                explicit_Point_constructions=names.count("Point"),
                derived_point_constructions=sum(n in point_types and n!="Point" for n in names),
                IsInteger_calls=calls.count("IsInteger"),integer_variables=len(integers),
                Bezout_condition=bezout,Angle_calls=calls.count("Angle"),Distance_calls=calls.count("Distance"),
                Area_calls=calls.count("Area"),Circumcenter_calls=calls.count("Circumcenter"),
                min_max_calls=calls.count("min")+calls.count("max"),floor_divisions=floordiv)


def compare():
    dev=[features(json.loads(line)["dsl"]) for line in (ROOT/"benchmarks/cases.jsonl").read_text().splitlines()]
    targets=[features(load(cid)[0]) for cid in IDS]
    for name,rows in [("development-features.csv",dev),("target-features.csv",targets)]:
        with (OUT/name).open("w") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={"development_n":len(dev),"source":"benchmarks/cases.jsonl embedded DSL", "metrics":{},"targets":targets}
    for key in list(dev[0])[1:]:
        v=np.array([r[key] for r in dev],dtype=float)
        summary["metrics"][key]=dict(min=float(v.min()),median=float(np.median(v)),q90=float(np.quantile(v,.9)),
            max=float(v.max()),positive_count=int(np.count_nonzero(v)))
    summary["integer_counts"]={str(n):sum(r["IsInteger_calls"]==n for r in dev) for n in sorted(set(r["IsInteger_calls"] for r in dev))}
    save("development-comparison.json",summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


def floor_probe():
    d,p,b,ev=load(IDS[1])
    with mp.workdps(160),high_precision_mode():
        w=witness(IDS[1]);x=[w[n] for n in b.var_names]
        ctx=build_solution_context_high_precision(b.spec,list(b.var_names),x,b.base_context,160)
        data=dict(id=IDS[1],target=d["target"],hand_calculated_r="7/9",correct_floor=777)
        try: data["value"]=safe_eval_expr_hp(d["target"],ctx)
        except Exception as e: data["exception"]=type(e).__name__+": "+str(e)
        data["residual"]=ev.evaluate_hp_residual(x,precision=160)
        data["answer"]=ev.evaluate_answer_hp(x,precision=160)
        data["unfloored_value"]=safe_eval_expr_hp("1000*r",ctx)
    from geosolver import validate
    data["public_validation"]=validate(p).model_dump(mode="json")
    save("floor-operator-probe.json",data)
    print(json.dumps(clean(data),ensure_ascii=False,indent=2),flush=True)


@worker_precision
def exact_oracle(cid,cpu):
    """Diagnose the remaining HMMT-2022 verification gate with a 550-digit oracle.

    This is not a start sampled by the solver and is never counted as a solve rate.
    """
    from dataclasses import replace
    from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
    from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
    os.sched_setaffinity(0,{cpu})
    d,p,b,ev=load(cid)
    with mp.workdps(560):
        w=witness(cid)
        decimals=tuple(mp.nstr(w[n],550) for n in b.var_names)
    x=np.array([float(v) for v in decimals])
    c=replace(direct_candidate(ev,x),initial_point_decimal=decimals)
    t=time.monotonic()
    data=dict(id=cid,kind="550_digit_exact_oracle_refiner_and_Phase_C",not_a_natural_solve=True,
              heuristic_search_box_bypassed=True,initial_point_decimal=decimals)
    try:
        r=MpmathRefiner().refine_candidates(bundle=b,evaluator=ev,candidates=(c,),deadline_monotonic=t+90)
        with mp.workdps(550): data["refinement"]=clean(r)
        a=assemble_exact_results(refined_candidates=r.candidates,evaluator=ev,input_precision_dps=120,deadline_monotonic=t+120)
        with mp.workdps(550): data["assembly"]=clean(a)
    except Exception as e:
        data["error"]=type(e).__name__+": "+str(e)
    data["elapsed"]=time.monotonic()-t
    save(f"local/{cid}-exact-oracle.json",data)
    print(cid,"exact oracle",data.get("assembly",{}).get("answer_values"),data["elapsed"],flush=True)


def memory_worker(cid,cpu,budget):
    """Unchanged frozen worker.execute; retain only bounded diagnostic output.

    The ordinary API writes all candidate records to one artifact. This route
    tests its computation separately from that IPC file, under the user's cap.
    """
    from collections import Counter
    from geosolver.runtime.worker import execute
    from geosolver.runtime.protocol import WorkerRequest
    from geosolver.runtime.artifact_records import normalize_artifact
    os.sched_setaffinity(0,{cpu})
    d,p,b,ev=load(cid)
    t=time.monotonic()
    request=WorkerRequest(engine_document=p.engine_document(),seed=201,deadline_monotonic=t+budget,
                          effective_cores=1,config_snapshot={"seed":201,"cores":1,"time_limit_seconds":budget})
    a=execute(request)
    # Serializing to memory creates no file larger than the user's limit.
    full=a.model_dump(mode="json")
    normalized=normalize_artifact(full)
    encoded=json.dumps(normalized,ensure_ascii=False,separators=(",",":"))+"\n"
    summary=a.diagnostics.get("pipeline_summary",{})
    verification=summary.get("verification_records",[])
    data={k:v for k,v in full.items() if k not in ("candidate_records","diagnostics")}
    data.update(id=cid,kind="frozen_worker_execute_in_memory_original_DSL",
                original_score_unchanged="85/130",not_the_public_IPC_protocol=True,
                normalized_artifact_bytes=len(encoded.encode()),normalized_artifact_sha256=hashlib.sha256(encoded.encode()).hexdigest(),
                candidate_count=len(a.candidate_records),
                refinement_status_counts=dict(Counter(c.get("refinement_status") for c in a.candidate_records)),
                verification_status_counts=dict(Counter(v.get("status") for v in verification)),
                pipeline_summary={k:v for k,v in summary.items() if k in ("initial_probe","refinement","exact_assembly","search_staged_fallback","pipeline_backend")})
    save(f"runs/worker-memory-{budget}-{cid}.json",data)
    print(cid,"worker memory",a.status,a.solver_status,a.elapsed_seconds,"serialized bytes",data["normalized_artifact_bytes"],flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=["prepare","natural","local","local-all","near","near-worker","compare","floor","exact","memory-worker"])
    parser.add_argument("--id",choices=IDS)
    parser.add_argument("--cpu",type=int,default=3)
    parser.add_argument("--budget",type=int,default=900)
    parser.add_argument("--expanded",action="store_true")
    parser.add_argument("--observe-io",action="store_true")
    a=parser.parse_args()
    if a.mode=="prepare": prepare()
    elif a.mode=="natural": natural(a.id,a.cpu,a.budget,a.observe_io)
    elif a.mode=="local": local(a.id,a.cpu)
    elif a.mode=="local-all":
        for cid in IDS: local(cid,a.cpu)
    elif a.mode=="near": supervised_near(a.id,a.cpu,a.budget,a.expanded)
    elif a.mode=="near-worker": near_pipeline(a.id,a.cpu,a.budget,a.expanded)
    elif a.mode=="compare": compare()
    elif a.mode=="floor": floor_probe()
    elif a.mode=="exact": exact_oracle(a.id,a.cpu)
    elif a.mode=="memory-worker": memory_worker(a.id,a.cpu,a.budget)
