"""Q4: static diagnosis, frozen endpoints, isolated five-way residual experiment.

All writes stay beside this file. No solver-source or environment changes.
Use the exact Python and PYTHONPATH in README/answer.md; -B is required.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
VARIANTS = ("O", "S", "D", "R", "A")
PYTHON = "/home/kabatan/work/solver/.venv/bin/python"


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    content = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if len(content.encode()) > 20_000_000:
        raise ValueError("artifact would exceed 20 MB")
    Path(path).write_text(content)


def csv_write(path, rows):
    if not rows:
        Path(path).write_text("")
        return
    with Path(path).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def source_fingerprint():
    entries = [(str(p.relative_to(ROOT)), digest(p)) for p in sorted((ROOT / "src").rglob("*.py"))]
    return hashlib.sha256(json.dumps(entries).encode()).hexdigest(), len(entries)


def bundle_for(dsl):
    from geosolver import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    return load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())


def depends_on(source, definitions, variables, active=frozenset()):
    names = {n.id for n in ast.walk(ast.parse(source, mode="eval")) if isinstance(n, ast.Name)}
    result = names & set(variables)
    for name in (names & set(definitions)) - active:
        result |= depends_on(definitions[name], definitions, variables, active | {name})
    return result


def diagnose(bundle):
    from geosolver.engine.standard.problem.tangency_contacts import contact_tangency_source, distance_contact_sources
    from geosolver.engine.standard.problem.positive_radius_contacts import positive_radius_contact_sources
    from geosolver.engine.standard.refinement.mpmath_refiner import _zero_constraint_plans
    constructions = tuple((x.name, x.expr) for x in bundle.spec.construction)
    equalities = tuple(zip(bundle.spec.constraints, map(str, bundle.targets), strict=True))
    plans = _zero_constraint_plans(tuple(bundle.spec.constraints), tuple(bundle.targets))
    contact = dict(distance_contact_sources(constructions, equalities))
    structural = dict(distance_contact_sources(constructions, ()))
    tangencies, distances = [], []
    for i, (kind, args) in plans.items():
        if kind == "istangent":
            tangencies.append(i)
            src = contact_tangency_source(*args, constructions, equalities)
            if src:
                contact[i] = src
            src0 = contact_tangency_source(*args, constructions, ())
            if src0:
                structural[i] = src0
        elif kind == "distance":
            distances.append(i)
    radius = positive_radius_contact_sources(tuple(bundle.var_names), constructions, equalities)
    details = []
    for i, source in sorted(contact.items()):
        dep = sorted(depends_on(source, dict(constructions), bundle.var_names))
        details.append(dict(index=i, source=source, variables=dep,
                            incidence="construction" if i in structural else "other_equalities",
                            active=bool(dep)))
    return dict(n_vars=len(bundle.var_names), n_equalities=len(bundle.spec.constraints),
                tangencies=tangencies, distances=distances, contacts=details,
                radius_sources=list(radius), q_active=any(d["active"] for d in details),
                s_applicable=bool(tangencies or contact), d_applicable=bool(distances),
                r_applicable=bool(radius))


def freeze():
    if (HERE / "registration-lock.json").exists():
        raise RuntimeError("registration already frozen; refusing to overwrite")
    old = {r["case_id"] for r in csv.DictReader((ROOT / "jssa/results/tangency-signed/per-case.csv").open())}
    cases = sorted((json.loads(line) for line in (ROOT / "benchmarks/cases.jsonl").read_text().splitlines()), key=lambda c: c["id"])
    manifest, frozen, predictions, census = [], {}, [], []
    for case in cases:
        identifier, dsl = case["id"], case["dsl"]
        try:
            b = bundle_for(dsl)
            diag = diagnose(b)
        except Exception as exc:
            census.append(dict(id=identifier, status="parse_error", error=repr(exc)))
            continue
        eligible = "IsTangent" in json.dumps(dsl) or diag["d_applicable"] or bool(diag["contacts"]) or diag["r_applicable"]
        census.append(dict(id=identifier, status="ok", eligible=eligible, **diag))
        if not eligible:
            continue
        raw_path = ROOT / "jssa/difficulty/minima/raw-323" / (identifier + ".json")
        selected = []
        raw_count, usable_count = 0, 0
        missing_reason = None
        if not diag["n_vars"]:
            missing_reason = "no_variables"
        elif not raw_path.exists():
            missing_reason = "raw_missing"
        else:
            # Neither reference answers nor correctness labels enter selection.
            raw = json.loads(raw_path.read_text())
            raw_count = len(raw.get("records", []))
            valid = []
            for row in raw.get("records", []):
                x, res = row.get("x"), row.get("res")
                if (isinstance(x, list) and len(x) == diag["n_vars"]
                        and all(isinstance(v, (int, float)) and math.isfinite(v) for v in x)
                        and isinstance(res, (int, float)) and math.isfinite(res) and res <= 1e-4):
                    valid.append(dict(k=int(row["k"]), x=x, saved_residual=res))
            valid.sort(key=lambda r: (r["saved_residual"], r["k"]))
            usable_count = len(valid)
            selected = valid[:3]
            if not selected:
                missing_reason = "no_candidate_at_threshold"
        item = dict(id=identifier, dsl=dsl, dsl_sha256=hashlib.sha256(json.dumps(dsl, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                    raw_sha256=digest(raw_path) if raw_path.exists() else None,
                    old12=identifier in old, diagnosis=diag, n_candidates=len(selected),
                    raw_count=raw_count, usable_count=usable_count, missing_reason=missing_reason)
        manifest.append(item)
        frozen[identifier] = selected
        predictions.append(dict(id=identifier, old12=identifier in old, n_vars=diag["n_vars"],
                                q_active=int(diag["q_active"]), q_rows=len(diag["contacts"]),
                                s=int(diag["s_applicable"]), d=int(diag["d_applicable"]), r=int(diag["r_applicable"]),
                                predict_stall=int(diag["q_active"]), predict_rescue="S" if diag["q_active"] else "unspecified",
                                n_candidates=len(selected), missing_reason=missing_reason or ""))
    dump(HERE / "dsl-census.json", census)
    dump(HERE / "manifest.json", manifest)
    dump(HERE / "frozen-candidates.json", frozen)
    csv_write(HERE / "predictions.csv", predictions)
    fingerprint, n_src = source_fingerprint()
    paths = ("preregistration.md", "manifest.json", "frozen-candidates.json", "predictions.csv", "experiment.py")
    lock = dict(utc=now(), files={p: digest(HERE / p) for p in paths}, src_sha256=fingerprint,
                n_src_files=n_src, git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                python=PYTHON, case_count=len(manifest), candidate_count=sum(map(len, frozen.values())),
                task_count=sum(map(len, frozen.values())) * 5, max_workers=4)
    dump(HERE / "registration-lock.json", lock)
    print(json.dumps({k: v for k, v in lock.items() if k != "files"}, ensure_ascii=False))


def verify_lock():
    lock = json.loads((HERE / "registration-lock.json").read_text())
    for name, wanted in lock["files"].items():
        if digest(HERE / name) != wanted:
            raise RuntimeError(f"frozen artifact changed: {name}")
    if source_fingerprint()[0] != lock["src_sha256"]:
        raise RuntimeError("solver source changed")


def smoother(variant):
    """Copy exact implementation; only the three registered gates are inserted."""
    import geosolver.engine.standard.refinement.mpmath_refiner as mr
    source = inspect.getsource(mr._smooth_zero_constraint_residuals)
    marker = "    if not plans and not contact_sources and not radius_deflations:\n"
    assert source.count(marker) == 1
    gates = '''    _stats["calls"] += 1
    if not _enable_s:
        contact_sources = {}
    if not _enable_r:
        radius_deflations = ()
    plans = {i: p for i, p in plans.items()
             if (_enable_s and p[0] == "istangent") or (_enable_d and p[0] == "distance")}
    _stats["selected_rows"] += len(plans) + len(contact_sources) + len(radius_deflations)
'''
    source = source.replace(marker, gates + marker)
    source = source.replace("    except Exception:\n", "    except Exception as exc:\n        _stats['fallbacks'] += 1\n        _stats['last_fallback'] = repr(exc)\n")
    stats = dict(calls=0, selected_rows=0, fallbacks=0, last_fallback=None)
    namespace = dict(mr.__dict__, _enable_s=variant in {"S", "A"},
                     _enable_d=variant in {"D", "A"}, _enable_r=variant in {"R", "A"}, _stats=stats)
    exec(compile(source, str(HERE / "in_memory_smoother.py"), "exec"), namespace)
    return namespace["_smooth_zero_constraint_residuals"], stats


def audit():
    verify_lock()
    from mpmath import mp
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    import geosolver.engine.standard.refinement.mpmath_refiner as mr
    frozen = json.loads((HERE / "frozen-candidates.json").read_text())
    rows = []
    for item in json.loads((HERE / "manifest.json").read_text()):
        row = dict(id=item["id"], status="no_candidate", all_equal=None, original_equal=None, noops_equal=None, error=None)
        if frozen[item["id"]]:
            try:
                b = bundle_for(item["dsl"])
                evaluator = build_ir_evaluator(b)
                with mp.workdps(120), high_precision_mode():
                    point = [mp.mpf(repr(v)) for v in frozen[item["id"]][0]["x"]]
                    ev = evaluator.evaluate_hp_residual(point, precision=120)
                    kwargs = dict(bundle=b, point=point, dps=120, residuals=list(ev.residual_vector))
                    original = mr._smooth_zero_constraint_residuals(**kwargs)
                    rewritten, stats = smoother("A")
                    row["all_equal"] = original == rewritten(**kwargs)
                    row["original_equal"] = smoother("O")[0](**kwargs) == kwargs["residuals"]
                    row["noops_equal"] = all(smoother(v)[0](**kwargs) == kwargs["residuals"]
                                             for v, field in (("S", "s_applicable"), ("D", "d_applicable"), ("R", "r_applicable"))
                                             if not item["diagnosis"][field])
                    row["status"] = "pass" if row["all_equal"] and row["original_equal"] and row["noops_equal"] and not stats["fallbacks"] else "fail"
            except Exception as exc:
                row["status"], row["error"] = "evaluation_error", repr(exc)
        rows.append(row)
    dump(HERE / "implementation-audit.json", rows)
    print(json.dumps({status: sum(r["status"] == status for r in rows) for status in sorted({r["status"] for r in rows})}))
    if any(r["status"] in {"fail", "evaluation_error"} for r in rows):
        raise RuntimeError("preflight audit failed")


class ScoreTimeout(BaseException):
    pass


def score_timeout(signum, frame):
    raise ScoreTimeout()


def score_output(candidate, evaluator, bounds):
    from mpmath import mp
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
    with mp.workdps(500), high_precision_mode():
        point = list(candidate.x_hp)
        ev = evaluator.evaluate_hp_residual(point, precision=500)
        row = dict(internal_status=candidate.refinement_status, history=list(candidate.phase_history),
                   original_status=str(ev.evaluation_status), x=[mp.nstr(v, 510) for v in point],
                   digits=None, norm=None, guard=False, hard=False, bounds=False, answer_finite=False, passed=False)
        if ev.evaluation_status != EvaluationStatus.OK:
            return row
        norm = mp.sqrt(mp.fsum(mp.mpf(v) ** 2 for v in ev.residual_vector))
        row["norm"] = mp.nstr(norm, 30)
        if mp.isfinite(norm):
            row["digits"] = 500.0 if norm == 0 else float(min(mp.mpf(500), -mp.log10(norm)))
        row["guard"], tags = evaluator.evaluate_guard(point)
        hard = evaluator.evaluate_hp_hard_feasibility(point, precision=500)
        row["hard"] = bool(hard.hard_feasible)
        row["tags"] = [*tags, *hard.failure_tags]
        row["bounds"] = all((lo is None or x >= lo) and (hi is None or x <= hi) for x, (lo, hi) in zip(point, bounds, strict=True))
        ans = evaluator.evaluate_answer_hp(point, precision=500)
        value = ans.answer_hp
        row["answer_finite"] = bool(ans.evaluation_status == EvaluationStatus.OK and value is not None and mp.isfinite(value))
        row["answer"] = mp.nstr(value, 100) if value is not None else None
        row["passed"] = bool(norm <= mp.mpf("1e-80") and row["guard"] and row["hard"] and row["bounds"] and row["answer_finite"])
        return row


def worker(identifier, index, variant, outpath):
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (20_000_000, 20_000_000))
    from mpmath import mp
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
    import geosolver.engine.standard.refinement.mpmath_refiner as mr
    item = next(x for x in json.loads((HERE / "manifest.json").read_text()) if x["id"] == identifier)
    point = json.loads((HERE / "frozen-candidates.json").read_text())[identifier][index]
    result = dict(id=identifier, index=index, k=point["k"], variant=variant, utc=now(), status="started", passed=False,
                  outputs=[], seconds=None, score_error=None, init_error=None)
    t0 = time.perf_counter()
    try:
        bundle = bundle_for(item["dsl"])
        evaluator = build_ir_evaluator(bundle)
        initial = evaluator.evaluate_float_residual(point["x"])
        guard, _ = evaluator.evaluate_guard(point["x"])
        hard = evaluator.evaluate_float_hard_feasibility(point["x"], include_margins=False)
        result["initial_guard"], result["initial_hard"] = bool(guard), bool(hard.hard_feasible)
        candidate = FloatCandidate(x_float=tuple(point["x"]), score=point["saved_residual"],
                    residual_norm_float=point["saved_residual"], guard_ok=bool(guard),
                    evaluation_status=initial.evaluation_status, origin_seed=0,
                    origin_start_point_index=point["k"], candidate_id=point["k"], hard_feasible=bool(hard.hard_feasible),
                    origin_backend="frozen_raw323", initial_point_decimal=tuple(repr(x) for x in point["x"]))
        rewrite, stats = smoother(variant)
        mr._smooth_zero_constraint_residuals = rewrite
        mr.derivative_plan = lambda bundle: None
        refiner = mr.MpmathRefiner()
        bounds = mr._convert_problem_bounds(bundle)
        t1 = time.perf_counter()
        deadline = time.monotonic() + 15.0
        batch = refiner.refine_candidates(bundle=bundle, evaluator=evaluator, candidates=(candidate,), deadline_monotonic=deadline)
        result["seconds"] = time.perf_counter() - t1
        result["deadline_hit"] = time.monotonic() >= deadline or any(c.refinement_status == "deadline_reached" for c in batch.candidates)
        result["rewrite_stats"] = stats
        result["status"] = "returned"
        signal.signal(signal.SIGALRM, score_timeout)
        signal.setitimer(signal.ITIMER_REAL, 5)
        try:
            for refined in batch.candidates:
                result["outputs"].append(score_output(refined, evaluator, bounds))
        except ScoreTimeout:
            result["score_error"] = "timeout_5s"
        except Exception as exc:
            result["score_error"] = repr(exc)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        result["passed"] = any(c["passed"] for c in result["outputs"])
    except Exception as exc:
        result["status"], result["init_error"] = "error", repr(exc)
        result["traceback"] = traceback.format_exc(limit=8)
    result["worker_seconds"] = time.perf_counter() - t0
    dump(outpath, result)


def run():
    verify_lock()
    audit_rows = json.loads((HERE / "implementation-audit.json").read_text())
    if any(r["status"] not in {"pass", "no_candidate"} for r in audit_rows):
        raise RuntimeError("audit is not passing")
    output = HERE / "runs"
    output.mkdir(exist_ok=True)
    frozen = json.loads((HERE / "frozen-candidates.json").read_text())
    tasks = []
    for problem_index, identifier in enumerate(sorted(frozen)):
        for index in range(len(frozen[identifier])):
            offset = (problem_index + index) % 5
            for variant in VARIANTS[offset:] + VARIANTS[:offset]:
                tasks.append((identifier, index, variant))
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1",
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    start = time.perf_counter()
    def launch(task):
        identifier, index, variant = task
        path = output / f"{identifier}__{index}__{variant}.json"
        if path.exists():
            return task, "existing"
        command = [PYTHON, "-B", str(Path(__file__)), "worker", "--id", identifier, "--index", str(index), "--variant", variant, "--out", str(path)]
        t0 = time.perf_counter()
        try:
            child = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            if child.returncode != 0 or not path.exists():
                dump(path, dict(id=identifier, index=index, variant=variant, status="process_error", passed=False,
                                returncode=child.returncode, stdout=child.stdout[-3000:], stderr=child.stderr[-6000:], outputs=[]))
        except subprocess.TimeoutExpired:
            dump(path, dict(id=identifier, index=index, variant=variant, status="process_timeout_30s", passed=False, outputs=[]))
        value = json.loads(path.read_text())
        value["process_seconds"] = time.perf_counter() - t0
        dump(path, value)
        return task, value["status"]
    done = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(launch, task) for task in tasks]
        for future in as_completed(futures):
            task, status = future.result()
            done += 1
            if done % 20 == 0 or done == len(tasks):
                print(json.dumps(dict(done=done, total=len(tasks), elapsed=round(time.perf_counter()-start, 1), last=task, status=status)), flush=True)
    dump(HERE / "run-completion.json", dict(utc=now(), tasks=done, wall_seconds=time.perf_counter()-start, max_workers=4))


def synthetic():
    verify_lock()
    from mpmath import mp
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    def dsl(identifier, definitions, conditions, variable="h"):
        return dict(id=identifier, variables=[variable], constructions=[dict(name=n, expression=e) for n,e in definitions],
                    conditions=[dict(left=l, operator="=", right=r) for l,r in conditions], target=variable)
    examples = [
        ("contact", dsl("Q4-contact", [("P","Point(1,0)"),("Q","Point(0,1)"),("Z","Point(-1,0)"),
                ("C","Circumcircle(P,Q,Z)"),("L","Line(P,Point(1+h,1))")], [("IsTangent(L,C)",0)]), "S", "0", 0),
        ("generic_tangent", dsl("Q4-generic", [("C","Circle(Point(0,0),1)"),("L","Line(Point(0,1+h),Point(1,1+h))")],
                [("IsTangent(L,C)",0)]), "S", "0", 0),
        ("zero_distance", dsl("Q4-distance", [("P","Point(h,2*h)"),("O","Point(0,0)")], [("Distance(P,O)",0)]), "D", "0", 0),
        ("positive_radius", dsl("Q4-radius", [("B","Point(0,0)"),("A","Point(2,0)"),("C","Point(0,2)"),
                ("G","Circumcircle(A,B,C)"),("T","Point(r,r)"),("c","Circle(T,r)")],
                [("Distance(T,Center(G))","Radius(G)-r")], "r"), "R", "4-2*sqrt(2)", -1),
    ]
    rows, metadata = [], []
    for name, doc, variant, root, row_index in examples:
        b = bundle_for(doc)
        evaluator = build_ir_evaluator(b)
        rewrite, stats = smoother(variant)
        metadata.append(dict(name=name, dsl=doc, diagnosis=diagnose(b)))
        for sign in (-1, 1):
            prev = None
            for exponent in (2,4,6,8):
                row = dict(example=name, sign=sign, exponent=exponent, original=None, transformed=None, original_order=None, transformed_order=None, error=None)
                try:
                    with mp.workdps(120), high_precision_mode():
                        xstar = mp.mpf(0) if root == "0" else 4-2*mp.sqrt(2)
                        x = xstar + sign*mp.power(10,-exponent)
                        ev = evaluator.evaluate_hp_residual([x], precision=120)
                        original = abs(ev.residual_vector[0])
                        transformed = rewrite(bundle=b, point=[x], dps=120, residuals=list(ev.residual_vector))
                        value = abs(transformed[row_index]) if variant != "D" else mp.sqrt(mp.fsum(t*t for t in transformed))
                        row["original"], row["transformed"] = mp.nstr(original,40), mp.nstr(value,40)
                        if prev:
                            row["original_order"] = float(mp.log10(prev[0]/original)/2)
                            row["transformed_order"] = float(mp.log10(prev[1]/value)/2)
                        prev = original, value
                except Exception as exc:
                    row["error"] = repr(exc)
                rows.append(row)
    csv_write(HERE / "synthetic-orders.csv", rows)
    dump(HERE / "synthetic-manifest.json", metadata)
    print(json.dumps(dict(synthetic_rows=len(rows), errors=sum(r["error"] is not None for r in rows))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("freeze","audit","run","worker","synthetic","verify"))
    parser.add_argument("--id")
    parser.add_argument("--index", type=int)
    parser.add_argument("--variant", choices=VARIANTS)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.command == "worker":
        worker(args.id, args.index, args.variant, args.out)
    else:
        {"freeze":freeze, "audit":audit, "run":run, "synthetic":synthetic, "verify":verify_lock}[args.command]()
