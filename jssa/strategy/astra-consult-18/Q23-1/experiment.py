"""One preregistered, bounded Q23-1 interface experiment; no source edits."""
from __future__ import annotations

import argparse
import csv
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PYTHON = "/home/kabatan/work/solver/.venv/bin/python"
VARIANTS = ("E", "S", "L", "G", "Q", "GQ", "P")


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(name, obj):
    path = HERE / name
    assert path.resolve().is_relative_to(HERE)
    content = json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    assert len(content.encode()) < 20_000_000
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def csvdump(name, rows):
    if not rows:
        (HERE / name).write_text("")
        return
    with (HERE / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def source_digest():
    entries = [(str(p.relative_to(ROOT)), digest(p)) for p in sorted((ROOT / "src").rglob("*.py"))]
    return hashlib.sha256(json.dumps(entries).encode()).hexdigest(), len(entries)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def bundle_for(dsl):
    from geosolver import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    return load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())


def prepare():
    if (HERE / "registration-lock.json").exists():
        raise RuntimeError("Already frozen")
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
    q4 = load_module("q231_q4_readonly", ROOT / "jssa/difficulty/multiplicity/experiment.py")
    cases_path = ROOT / "benchmarks/cases.jsonl"
    basin_path = ROOT / "jssa/difficulty/minima/basins-323.csv"
    cases = {c["id"]: c for c in map(json.loads, cases_path.read_text().splitlines())}
    basins = {r["id"]: r for r in csv.DictReader(basin_path.open())}
    selected, audit = [], []
    input_hashes = {str(cases_path.relative_to(ROOT)): digest(cases_path),
                    str(basin_path.relative_to(ROOT)): digest(basin_path),
                    "jssa/difficulty/multiplicity/experiment.py": digest(ROOT / "jssa/difficulty/multiplicity/experiment.py")}
    for identifier in sorted(cases):
        row = basins.get(identifier, {})
        n = int(row.get("n_vars") or 0)
        if not 2 <= n <= 6 or not row.get("p") or float(row["p"]) > .30:
            continue
        case = cases[identifier]
        record = dict(id=identifier, n=n, old_p=float(row["p"]), reason="", eligible_k="")
        try:
            bundle = bundle_for(case["dsl"])
            diag = q4.diagnose(bundle)
            if any(diag[k] for k in ("s_applicable", "d_applicable", "r_applicable")):
                record["reason"] = "known_Q4_rewrite"
                audit.append(record)
                continue
            from geosolver.engine.standard.refinement.mpmath_refiner import build_integer_constraint_specs
            if build_integer_constraint_specs(bundle=bundle):
                record["reason"] = "integer_constraint"
                audit.append(record)
                continue
            ev = build_ir_evaluator(bundle)
            bounds = [list(map(float, b)) for b in infer_problem_bounds(bundle)]
            raw_path = ROOT / "jssa/difficulty/minima/raw-323" / f"{identifier}.json"
            input_hashes[str(raw_path.relative_to(ROOT))] = digest(raw_path)
            raw = json.loads(raw_path.read_text())
            chosen = None
            for rec in sorted(raw.get("records", []), key=lambda r: r["k"]):
                if rec.get("cls") != "stuck" or not 1e-8 < rec.get("res", math.inf) <= 1e-2:
                    continue
                x, start = rec.get("x"), rec.get("start")
                if not x or not start or len(x) != n or len(start) != n or not all(math.isfinite(v) for v in x + start):
                    continue
                if not all(lo <= v <= hi for v, (lo, hi) in zip(x, bounds)):
                    continue
                guard, _ = ev.evaluate_guard(x)
                hard = ev.evaluate_float_hard_feasibility(x, include_margins=False)
                if not guard or not hard.hard_feasible:
                    continue
                chosen = rec
                break
            if chosen is None:
                record["reason"] = "no_eligible_endpoint"
                audit.append(record)
                continue
            x = chosen["x"]
            q = []
            for v, (lo, hi) in zip(x, bounds):
                if not math.isfinite(hi-lo) or hi <= lo:
                    raise ValueError("nonfinite or empty box")
                cell = min(255, max(0, math.floor((v-lo)/(hi-lo)*256)))
                q.append(lo + (cell+.5)*(hi-lo)/256)
            selected.append(dict(id=identifier, dsl=case["dsl"], answer_for_scoring_only=case["answer"],
                                 old_p=float(row["p"]), n=n, k=chosen["k"], x=x, start=chosen["start"],
                                 quantized=q, saved_residual=chosen["res"], bounds=bounds,
                                 diagnosis=diag, var_names=list(bundle.var_names)))
            record["reason"], record["eligible_k"] = "selected", chosen["k"]
            audit.append(record)
            if len(selected) == 12:
                break
        except Exception as exc:
            record["reason"] = "prepare_error:" + repr(exc)
            audit.append(record)
    dump("inputs.json", selected)
    csvdump("selection-audit.csv", audit)
    src_hash, nsrc = source_digest()
    files = {p: digest(HERE / p) for p in ("preregistration.md", "experiment.py", "inputs.json", "selection-audit.csv")}
    lock = dict(utc=now(), files=files, input_hashes=input_hashes, source_hash=src_hash, source_files=nsrc,
                git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                source_diff_from_60db4b6=subprocess.check_output(["git", "diff", "--stat", "60db4b6", "--", "src"], cwd=ROOT, text=True),
                selected=len(selected), variants=VARIANTS, tasks=len(selected)*len(VARIANTS), max_workers=1)
    dump("registration-lock.json", lock)
    print(json.dumps(dict(selected=[x["id"] for x in selected], count=len(selected), tasks=lock["tasks"], source_same_as_frozen=not lock["source_diff_from_60db4b6"]), ensure_ascii=False))


def check_lock():
    lock = json.loads((HERE / "registration-lock.json").read_text())
    for path, expected in lock["files"].items():
        assert digest(HERE / path) == expected, path
    for path, expected in lock["input_hashes"].items():
        assert digest(ROOT / path) == expected, path
    assert source_digest()[0] == lock["source_hash"], "src changed"
    return lock


class BoundedTimeout(BaseException):
    pass


def alarm_handler(signum, frame):
    raise BoundedTimeout()


def reference_values_hp(answer):
    import re
    import sympy as sp
    from mpmath import mp
    probe = load_module("q231_probe_readonly", ROOT / "jssa/difficulty/probe_basins.py")
    values = answer if isinstance(answer, list) else [answer]
    flat = []
    for item in values:
        text = re.sub(r"\(\d+個\)", "", str(item))
        flat.extend(text.split(",") if "CRootOf" not in text else [text])
    return [mp.mpf(str(sp.N(sp.sympify(probe._ascii_expr(t), locals={"cbrt":sp.cbrt,"CRootOf":sp.CRootOf}), 170))) for t in flat if t.strip()]


def score(point, ev, bounds, refs):
    from mpmath import mp
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
    with mp.workdps(160), high_precision_mode():
        x = [mp.mpf(v) for v in point]
        evaluation = ev.evaluate_hp_residual(x, precision=160)
        out = dict(x=[mp.nstr(v, 170) for v in x], low=False, high=False, ref=None,
                   evaluation_status=str(evaluation.evaluation_status), norm=None, answer=None, error=None)
        if evaluation.evaluation_status != EvaluationStatus.OK:
            return out
        norm = mp.sqrt(mp.fsum(v*v for v in evaluation.residual_vector))
        guard, tags = ev.evaluate_guard(x)
        hard = ev.evaluate_hp_hard_feasibility(x, precision=160)
        inside = all(mp.mpf(str(lo)) <= v <= mp.mpf(str(hi)) for v,(lo,hi) in zip(x,bounds))
        value = ev.evaluate_answer_hp(x, precision=160).answer_hp
        out.update(norm=mp.nstr(norm, 35), guard=bool(guard), hard=bool(hard.hard_feasible), inside=bool(inside), tags=[*tags, *hard.failure_tags])
        if value is None or not mp.isfinite(value):
            return out
        errors = [abs(value-ref)/max(1,abs(ref)) for ref in refs]
        j = min(range(len(errors)), key=errors.__getitem__)
        err = errors[j]
        out.update(answer=mp.nstr(value, 170), error=mp.nstr(err,35), ref=int(j))
        valid = bool(guard and hard.hard_feasible and inside)
        out["low"] = bool(valid and norm <= mp.mpf("1e-8") and err <= mp.mpf("1e-6"))
        out["high"] = bool(valid and norm <= mp.mpf("1e-60") and err <= mp.mpf("1e-50"))
        return out


def worker(index, variant):
    resource.setrlimit(resource.RLIMIT_AS, (3*1024**3,3*1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (20_000_000,20_000_000))
    from mpmath import mp
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
    from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
    from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
    from geosolver.engine.standard.refinement.refiner_config import RefinerConfig
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    from geosolver.engine.standard.search import scipy_multistart_backend as smb
    item = json.loads((HERE / "inputs.json").read_text())[index]
    path = f"runs/{index:02d}-{variant}.json"
    result = dict(id=item["id"], index=index, variant=variant, utc=now(), status="initializing", low=False, high=False,
                  numerical_timeout=False, score_error=None, outputs=[], phase_history=[], nfev=None)
    signal.signal(signal.SIGALRM, alarm_handler)
    t0 = time.monotonic()
    try:
        bundle = bundle_for(item["dsl"])
        ev = build_ir_evaluator(bundle)
        x = item["start"] if variant == "S" else item["quantized"] if variant in ("Q","GQ") else item["x"]
        initial = ev.evaluate_float_residual(x)
        guard, _ = ev.evaluate_guard(x)
        hard = ev.evaluate_float_hard_feasibility(x, include_margins=False)
        result["initial_guard"], result["initial_hard"] = bool(guard), bool(hard.hard_feasible)
        result["initial_norm"] = str(initial.residual_norm_float)
        result["initial_x"] = x
        candidate = FloatCandidate(x_float=tuple(x), score=float(initial.residual_norm_float), residual_norm_float=float(initial.residual_norm_float),
                                   guard_ok=bool(guard), evaluation_status=initial.evaluation_status, origin_seed=231,
                                   origin_start_point_index=item["k"], candidate_id=item["k"], hard_feasible=bool(hard.hard_feasible),
                                   origin_backend="q231_frozen_endpoint", initial_point_decimal=tuple(repr(v) for v in x))
        points = []
        num_start = time.monotonic()
        signal.setitimer(signal.ITIMER_REAL, 12)
        try:
            if variant in ("E","S","Q","P"):
                config = RefinerConfig() if variant != "P" else replace(RefinerConfig(), schedule_dps=(120,120,120))
                batch = MpmathRefiner(config=config).refine_candidates(bundle=bundle, evaluator=ev, candidates=(candidate,), deadline_monotonic=num_start+12)
                points = [list(c.x_hp) for c in batch.candidates]
                result["phase_history"] = [list(c.phase_history) for c in batch.candidates]
                result["refinement_statuses"] = [c.refinement_status for c in batch.candidates]
                result["numerical_timeout"] = any(c.refinement_status=="deadline_reached" for c in batch.candidates)
            elif variant == "L":
                import numpy as np
                telemetry = smb._SearchTelemetry()
                config = ExternalPipelineConfig.production_baseline_tier(seed=231,total_time_budget_sec=180).search
                c = smb._collect_local_start_record(bundle=bundle,evaluator=ev,bounds=item["bounds"],config=config,seed=231,
                            start_index=item["k"],start=np.array(x),deadline_monotonic=num_start+12,telemetry=telemetry)
                points = [[mp.mpf(repr(v)) for v in c.x_float]] if c else []
                result["nfev"] = telemetry.evaluation_count
            else:
                calls = [0]
                def f(*args):
                    if time.monotonic() >= num_start+12:
                        raise BoundedTimeout()
                    calls[0] += 1
                    with mp.workdps(120), high_precision_mode():
                        r = ev.evaluate_hp_residual(list(args), precision=120)
                    return tuple(r.residual_vector)
                with mp.workdps(120), high_precision_mode():
                    root = mp.findroot(f, tuple(mp.mpf(repr(v)) for v in x), solver="mdnewton", multidimensional=True,
                                       tol=mp.mpf("1e-160"), maxsteps=80, verify=False)
                    points = [[v for v in root]]
                result["nfev"] = calls[0]
            result["status"] = "returned"
        except (BoundedTimeout, TimeoutError, smb._SearchDeadlineExceeded):
            result["status"], result["numerical_timeout"] = "numerical_timeout", True
        except Exception as exc:
            result["status"], result["numerical_error"] = "numerical_error", repr(exc)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        result["numerical_seconds"] = time.monotonic()-num_start
        signal.setitimer(signal.ITIMER_REAL, 5)
        try:
            with mp.workdps(180):
                refs = reference_values_hp(item["answer_for_scoring_only"])
            for p in points:
                result["outputs"].append(score(p,ev,item["bounds"],refs))
            result["low"] = any(v["low"] for v in result["outputs"])
            result["high"] = any(v["high"] for v in result["outputs"])
        except BoundedTimeout:
            result["score_error"] = "score_timeout_5s"
        except Exception as exc:
            result["score_error"] = repr(exc)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    except Exception as exc:
        result["status"], result["initialization_error"] = "initialization_error", repr(exc)
        result["traceback"] = traceback.format_exc(limit=6)
    result["worker_seconds"] = time.monotonic()-t0
    dump(path, result)


def run():
    lock = check_lock()
    inputs = json.loads((HERE / "inputs.json").read_text())
    (HERE / "tmp").mkdir(exist_ok=True)
    (HERE / "runs").mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(ROOT/"src"), PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(HERE/"tmp"),
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    start = time.monotonic()
    done = 0
    for i,item in enumerate(inputs):
        variants = VARIANTS[i%7:]+VARIANTS[:i%7]
        for v in variants:
            path = HERE / f"runs/{i:02d}-{v}.json"
            if path.exists():
                raise RuntimeError(f"Refuse repeated numerical run: {path.name}")
            t0 = time.monotonic()
            try:
                child = subprocess.run([PYTHON,"-B",str(Path(__file__)),"worker","--index",str(i),"--variant",v],cwd=ROOT,env=env,
                                       capture_output=True,text=True,timeout=22)
                if child.returncode or not path.exists():
                    dump(path.relative_to(HERE), dict(id=item["id"],index=i,variant=v,status="process_error",low=False,high=False,
                         outputs=[],phase_history=[],numerical_timeout=False,returncode=child.returncode,stdout=child.stdout[-1000:],stderr=child.stderr[-5000:]))
            except subprocess.TimeoutExpired:
                dump(path.relative_to(HERE), dict(id=item["id"],index=i,variant=v,status="process_timeout",low=False,high=False,
                     outputs=[],phase_history=[],numerical_timeout=True))
            row = json.loads(path.read_text())
            row["process_seconds"] = time.monotonic()-t0
            dump(path.relative_to(HERE),row)
            done += 1
            if done%7 == 0:
                print(json.dumps(dict(done=done,total=lock["tasks"],elapsed_s=round(time.monotonic()-start,1),id=item["id"])),flush=True)
    dump("completion.json", dict(utc=now(),tasks=done,wall_seconds=time.monotonic()-start,workers=1))
    summarize()


def summarize():
    lock = check_lock()
    inputs = json.loads((HERE / "inputs.json").read_text())
    rows = [json.loads(p.read_text()) for p in sorted((HERE/"runs").glob("*.json"))]
    by = {(r["index"],r["variant"]):r for r in rows}
    matrix = []
    for i,item in enumerate(inputs):
        row = dict(id=item["id"],n=item["n"],old_p=item["old_p"],saved_residual=item["saved_residual"])
        for v in VARIANTS:
            r = by.get((i,v),{})
            for key in ("low","high","status","numerical_timeout"):
                row[v+"_"+key] = r.get(key)
        matrix.append(row)
    csvdump("per-problem.csv",matrix)
    tallies = {v:dict(n=sum(r["variant"]==v for r in rows),low=sum(r["low"] for r in rows if r["variant"]==v),
                      high=sum(r["high"] for r in rows if r["variant"]==v),
                      timeouts=sum(r.get("numerical_timeout",False) for r in rows if r["variant"]==v),
                      errors=sum("error" in r["status"] or bool(r.get("score_error")) for r in rows if r["variant"]==v)) for v in VARIANTS}
    def count(a,b,bkey="high"):
        return sum(bool(r[a+"_high"]) and not bool(r[b+"_"+bkey]) for r in matrix)
    def refs(r):
        return {x["ref"] for x in r.get("outputs",[]) if x.get("high")}
    same_qe = sum(bool(refs(by.get((i,"Q"),{})) & refs(by.get((i,"E"),{}))) for i in range(len(inputs)))
    epdiff = []
    for i,item in enumerate(inputs):
        e,p = by.get((i,"E"),{}),by.get((i,"P"),{})
        if e.get("high") and (not p.get("high") or refs(e) != refs(p)):
            epdiff.append(dict(id=item["id"],both_no_timeout=not(e.get("numerical_timeout") or p.get("numerical_timeout"))))
    h1 = dict(E_success=tallies["E"]["high"],E_not_S=count("E","S"),E_not_L_low=count("E","L","low"),E_not_G=count("E","G"))
    h1["numerical_gate"] = bool(h1["E_success"]>=max(4,math.ceil(len(inputs)/2)) and all(h1[k]>=3 for k in ("E_not_S","E_not_L_low","E_not_G")))
    h2 = dict(Q_same_ref_as_E=same_qe,Q_not_S=count("Q","S"),Q_not_GQ=count("Q","GQ"))
    h2["numerical_gate"] = bool(same_qe>=math.ceil(2*len(inputs)/3) and h2["Q_not_S"]>=3 and h2["Q_not_GQ"]>=3)
    h3 = dict(E_advantage_or_branch_change=epdiff,opposite_success=count("P","E"))
    h3["numerical_gate"] = bool(len(epdiff)>=3 and sum(r["both_no_timeout"] for r in epdiff)>=2)
    summary = dict(utc=now(),n=len(inputs),tasks=len(rows),expected_tasks=lock["tasks"],tallies=tallies,H1=h1,H2=h2,H3=h3,
                   completion=json.loads((HERE/"completion.json").read_text()) if (HERE/"completion.json").exists() else None,
                   lock_verified=True,source_same=True)
    dump("summary.json",summary)
    print(json.dumps(summary,ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command",choices=("prepare","run","worker","summarize","verify"))
    ap.add_argument("--index",type=int)
    ap.add_argument("--variant",choices=VARIANTS)
    args = ap.parse_args()
    if args.command=="worker":
        worker(args.index,args.variant)
    elif args.command=="verify":
        print(json.dumps(dict(lock=bool(check_lock()))))
    else:
        {"prepare":prepare,"run":run,"summarize":summarize}[args.command]()
