"""One preregistered Q23-3 experiment. All writes are confined to HERE."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(name, obj):
    path = (HERE / name).resolve()
    if not path.is_relative_to(HERE):
        raise RuntimeError("write outside assigned directory")
    payload = json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if len(payload.encode()) > 10_000_000:
        raise RuntimeError("artifact too large")
    path.write_text(payload)


def fingerprint():
    rows = [(str(p.relative_to(ROOT)), digest(p)) for p in sorted((ROOT / "src").rglob("*.py"))]
    return {"sha256": hashlib.sha256(json.dumps(rows).encode()).hexdigest(), "files": len(rows)}


def finite_record(r):
    return (isinstance(r.get("x"), list) and isinstance(r.get("start"), list)
            and all(math.isfinite(float(v)) for v in [*r["x"], *r["start"], r.get("res", float("nan"))]))


def contest(identifier):
    return identifier.upper().split("-")[0]


def freeze():
    if (HERE / "registration-lock.json").exists():
        raise RuntimeError("already frozen")
    cases_path = ROOT / "benchmarks/cases.jsonl"
    exclusion_path = ROOT / "jssa/difficulty/multiplicity/manifest.json"
    excluded = {x["id"] for x in json.loads(exclusion_path.read_text())}
    sources = {str(p.relative_to(ROOT)): digest(p) for p in (cases_path, exclusion_path)}
    candidates, multivalue = [], []
    for case in map(json.loads, cases_path.read_text().splitlines()):
        cid = case["id"]
        p = ROOT / "jssa/difficulty/minima/raw-323" / (cid + ".json")
        if not p.exists():
            continue
        raw = json.loads(p.read_text())
        records = sorted([r for r in raw.get("records", []) if finite_record(r)], key=lambda r: r["k"])
        item = {"id": cid, "dsl": case["dsl"], "answer": case["answer"],
                "box": raw.get("box", []), "references": raw.get("references", []),
                "source": str(p.relative_to(ROOT)), "n_vars": raw.get("n_vars", 0), "records": records}
        if len(item["references"]) > 1:
            item["multivalue_records"] = [r for j in range(len(item["references"]))
                                          for r in records if r["cls"] == "hit" and r.get("ref") == j]
            chosen = []
            for j in range(len(item["references"])):
                chosen.extend([r for r in item["multivalue_records"] if r.get("ref") == j][:2])
            item["multivalue_records"] = chosen
            multivalue.append(item)
        text = json.dumps(case["dsl"])
        fail = [r for r in records if r["cls"] == "stuck"]
        hits = [r for r in records if r["cls"] == "hit"]
        if (1 <= item["n_vars"] <= 6 and cid not in excluded
                and "IsInteger" not in text and "IsPrime" not in text
                and len(fail) >= 2 and len(hits) >= 2):
            item["main_records"] = fail[:2] + hits[:2]
            item["sort_hash"] = hashlib.sha256(("Q23-3-handoff-v1/" + cid).encode()).hexdigest()
            candidates.append(item)
    main = []
    eligibility = {}
    for group in ("AIME", "HMMT", "JMO"):
        eligible = sorted([x for x in candidates if contest(x["id"]) == group], key=lambda x: x["sort_hash"])
        eligibility[group] = {"n_eligible": len(eligible), "selected": [x["id"] for x in eligible[:4]]}
        main.extend(eligible[:4])
    selected = {x["id"]: x for x in [*main, *multivalue]}
    jobs = {}
    def add(item, rec, mode, place, hypothesis):
        key = f"{item['id']}::{rec['k']}::{place}::{mode}"
        if key not in jobs:
            jobs[key] = {"job_id": key, "id": item["id"], "record": rec, "mode": mode,
                         "place": place, "hypotheses": []}
        jobs[key]["hypotheses"].append(hypothesis)
    for item in main:
        for rec in item["main_records"]:
            add(item, rec, "native", "endpoint", "H1/H2")
            add(item, rec, "first_chart", "endpoint", "H2")
            if rec["cls"] == "stuck":
                add(item, rec, "native", "start", "H1")
    for item in sorted(multivalue, key=lambda x: x["id"]):
        for rec in item["multivalue_records"]:
            add(item, rec, "native", "endpoint", "H3")
    for item in selected.values():
        sources[item["source"]] = digest(ROOT / item["source"])
    cases = [{k: v for k, v in item.items() if k not in ("records", "multivalue_records", "main_records")}
             for item in selected.values()]
    manifest = {"created_utc": now(), "eligibility": eligibility,
                "main_ids": [x["id"] for x in main], "multivalue_ids": sorted(x["id"] for x in multivalue),
                "multi_observed": {x["id"]: {str(j): sum(r.get("ref") == j for r in x["multivalue_records"])
                                            for j in range(len(x["references"]))} for x in multivalue},
                "cases": cases, "jobs": list(jobs.values()), "source_hashes": sources}
    dump("manifest.json", manifest)
    lock = {"created_utc": now(), "files": {n: digest(HERE / n) for n in ("preregistration.md", "pilot.py", "manifest.json")},
            "source": fingerprint(), "source_60db4b6_diff": subprocess.check_output(
                ["git", "diff", "--stat", "60db4b6", "--", "src"], cwd=ROOT, text=True)}
    dump("registration-lock.json", lock)
    print(json.dumps({"jobs": len(jobs), "main": manifest["main_ids"], "multi": manifest["multivalue_ids"]}))


class BudgetExpired(BaseException):
    pass


def alarm(signum, frame):
    raise BudgetExpired()


def parse_references(answer):
    import sympy as sp
    from mpmath import mp
    items = answer if isinstance(answer, list) else [answer]
    values = []
    for item in items:
        text = re.sub(r"\(\d+個\)", "", str(item))
        parts = [text] if "CRootOf" in text else text.split(",")
        for s in parts:
            s = s.strip().replace("−", "-").replace("×", "*").replace("π", "pi")
            s = re.sub(r"\\sqrt\{([^}]*)\}", r"sqrt(\1)", s)
            s = re.sub(r"∛\s*(\d+|\([^)]*\))", r"cbrt(\1)", s)
            s = re.sub(r"√\s*\(", "sqrt(", s)
            s = re.sub(r"√\s*(\d+(?:\.\d+)?|[A-Za-z_]\w*)", r"sqrt(\1)", s)
            s = re.sub(r"(\d|\))\s*(sqrt|pi|\()", r"\1*\2", s)
            expr = sp.sympify(s, locals={"cbrt": sp.cbrt, "CRootOf": sp.CRootOf})
            values.append(mp.mpf(str(sp.N(expr, 110))))
    return values


def snapshot(evaluator, point, precision=120):
    from mpmath import mp
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
    try:
        with mp.workdps(precision), high_precision_mode():
            ev = evaluator.evaluate_hp_residual(list(point), precision=precision)
            guard, _ = evaluator.evaluate_guard(list(point))
            hard = evaluator.evaluate_hp_hard_feasibility(list(point), precision=precision)
            ans = evaluator.evaluate_answer_hp(list(point), precision=precision)
            norm = mp.sqrt(mp.fsum(mp.mpf(v)**2 for v in ev.residual_vector))
            return {"x": [mp.nstr(v, 115) for v in point], "norm": mp.nstr(norm, 30),
                    "guard": bool(guard), "hard": bool(hard.hard_feasible),
                    "answer": mp.nstr(ans.answer_hp, 110) if ans.answer_hp is not None else None,
                    "valid": ev.evaluation_status == EvaluationStatus.OK,
                    "tags": list(hard.failure_tags)}
    except Exception as exc:
        return {"error": repr(exc), "valid": False}


def process(job, item):
    from mpmath import mp
    from geosolver import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
    from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
    from geosolver.runtime.deadline import runtime_session, deadline_scope
    from geosolver.engine.standard.refinement import mpmath_refiner as mr
    t0 = time.monotonic()
    rec = job["record"]
    row = {k: v for k, v in job.items() if k != "record"}
    row.update(k=rec["k"], old_cls=rec["cls"], old_ref=rec.get("ref"), status="started", utc=now(),
               chart_trace=[], refined=[], accepted=[], exact_values=[], timed_out=False, correct_refs=[])
    chart_orig = mr._select_rank_revealing_subsystem
    first = {}
    def traced(matrix, *, dps, relative_tolerance=None):
        original = chart_orig(matrix, dps=dps, relative_tolerance=relative_tolerance)
        shape = (len(matrix), len(matrix[0]) if matrix else 0)
        if original is not None and shape not in first:
            first[shape] = original
        used = first.get(shape, original) if job["mode"] == "first_chart" else original
        row["chart_trace"].append({"shape": shape, "dps": dps, "original": original, "used": used})
        return used
    mr._select_rank_revealing_subsystem = traced
    signal.setitimer(signal.ITIMER_REAL, 16)
    try:
        bundle = load_problem_bundle(GeometryProblem.model_validate(item["dsl"]).engine_document())
        evaluator = build_ir_evaluator(bundle)
        values = rec["x"] if job["place"] == "endpoint" else rec["start"]
        ev = evaluator.evaluate_float_residual(values)
        guard, _ = evaluator.evaluate_guard(values)
        hard = evaluator.evaluate_float_hard_feasibility(values, include_margins=False)
        norm = math.sqrt(sum(float(v)**2 for v in ev.residual_vector))
        cand = FloatCandidate(x_float=tuple(values), score=norm, residual_norm_float=norm,
                              guard_ok=bool(guard), evaluation_status=ev.evaluation_status,
                              origin_seed=0, origin_start_point_index=rec["k"], candidate_id=rec["k"],
                              hard_feasible=bool(hard.hard_feasible), origin_backend="Q23-3-saved-local")
        with mp.workdps(120):
            row["initial"] = snapshot(evaluator, [mp.mpf(repr(v)) for v in values], 80)
        total_deadline = time.monotonic() + 12
        with runtime_session(total_deadline) as timings:
            t1 = time.monotonic()
            refine_deadline = t1 + 6
            result = mr.MpmathRefiner().refine_candidates(
                bundle=bundle, evaluator=evaluator, candidates=(cand,), deadline_monotonic=refine_deadline)
            row["refinement_seconds"] = time.monotonic() - t1
            row["timed_out"] |= time.monotonic() >= refine_deadline or any(c.refinement_status == "deadline_reached" for c in result.candidates)
            for c in result.candidates:
                row["refined"].append({**snapshot(evaluator, c.x_hp), "status": c.refinement_status,
                                       "history": list(c.phase_history), "internal_norm": str(c.residual_norm_hp)})
            # The ablation concerns refinement only; final verification stays unchanged.
            mr._select_rank_revealing_subsystem = chart_orig
            t2 = time.monotonic()
            assembly_deadline = min(total_deadline, t2 + 6)
            with deadline_scope(assembly_deadline):
                assembly = assemble_exact_results(refined_candidates=result.candidates, evaluator=evaluator,
                                                  input_precision_dps=120, deadline_monotonic=assembly_deadline)
            row["assembly_seconds"] = time.monotonic() - t2
            row["timed_out"] |= time.monotonic() >= assembly_deadline
            row["exact_values"] = list(assembly.answer_values)
            row["rejection_tags"] = list(assembly.rejection_tags)
            for c in assembly.accepted_candidates:
                row["accepted"].append(snapshot(evaluator, c.x_hp))
            row["counters"] = dict(timings.counters)
        row["status"] = "returned"
    except BudgetExpired:
        row["status"] = "external_timeout"
        row["timed_out"] = True
    except TimeoutError as exc:
        row["status"] = "deadline"
        row["timed_out"] = True
        row["error"] = repr(exc)
    except Exception as exc:
        row["status"] = "error"
        row["error"] = repr(exc)
        row["traceback"] = traceback.format_exc(limit=5)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        mr._select_rank_revealing_subsystem = chart_orig
        row["seconds"] = time.monotonic() - t0
    try:
        with mp.workdps(120):
            refs = parse_references(item["answer"])
            row["reference_decimals"] = [mp.nstr(v, 110) for v in refs]
            for result in row["accepted"]:
                if result.get("answer") is None:
                    continue
                value = mp.mpf(result["answer"])
                result["matched_refs"] = [j for j, ref in enumerate(refs)
                                          if abs(value-ref) <= mp.mpf("1e-40")*max(1, abs(ref))]
                row["correct_refs"].extend(result["matched_refs"])
            row["correct_refs"] = sorted(set(row["correct_refs"]))
    except Exception as exc:
        row["score_error"] = repr(exc)
    return row


def check_lock():
    lock = json.loads((HERE / "registration-lock.json").read_text())
    if any(digest(HERE / name) != expected for name, expected in lock["files"].items()):
        raise RuntimeError("registration changed")
    return lock


def run():
    lock = check_lock()
    manifest = json.loads((HERE / "manifest.json").read_text())
    if (HERE / "results.jsonl").exists():
        raise RuntimeError("results already exist; refuse extra experiment")
    (HERE / "tmp").mkdir(exist_ok=True)
    os.environ["TMPDIR"] = str(HERE / "tmp")
    import tempfile
    tempfile.tempdir = str(HERE / "tmp")
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    signal.signal(signal.SIGALRM, alarm)
    cases = {x["id"]: x for x in manifest["cases"]}
    started = time.monotonic()
    done = 0
    with (HERE / "results.jsonl").open("x") as out:
        for job in manifest["jobs"]:
            if time.monotonic() - started > 3000:
                break
            row = process(job, cases[job["id"]])
            payload = json.dumps(row, ensure_ascii=False, allow_nan=False)
            if len(payload) > 1_000_000:
                raise RuntimeError("unexpected per-job volume")
            out.write(payload + "\n")
            out.flush()
            done += 1
            if done % 10 == 0:
                print(json.dumps({"done": done, "planned": len(manifest["jobs"]), "elapsed": round(time.monotonic()-started, 1)}), flush=True)
    dump("run-receipt.json", {"finished_utc": now(), "seconds": time.monotonic()-started, "completed": done,
                              "planned": len(manifest["jobs"]), "source_after": fingerprint(),
                              "source_unchanged": fingerprint() == lock["source"], "results_sha256": digest(HERE / "results.jsonl")})
    summarize()


def summarize():
    from mpmath import mp
    manifest = json.loads((HERE / "manifest.json").read_text())
    rows = [json.loads(line) for line in (HERE / "results.jsonl").read_text().splitlines()]
    lookup = {r["job_id"]: r for r in rows}
    def get(cid, k, place="endpoint", mode="native"):
        return lookup.get(f"{cid}::{k}::{place}::{mode}")
    def good(row):
        return row is not None and bool(row.get("correct_refs"))
    h1, h2, h3 = [], [], []
    for row in rows:
        if row["id"] not in manifest["main_ids"] or row["place"] != "endpoint" or row["mode"] != "native":
            continue
        cid, k = row["id"], row["k"]
        fixed = get(cid, k, mode="first_chart")
        choices = [json.dumps(t["used"]) for t in row["chart_trace"] if t["used"] is not None]
        by_shape = {}
        for t in row["chart_trace"]:
            if t["used"] is not None:
                by_shape.setdefault(tuple(t["shape"]), set()).add(json.dumps(t["used"]))
        changed = any(len(s) > 1 for s in by_shape.values())
        h2.append({"id": cid, "k": k, "native_good": good(row), "fixed_good": good(fixed), "chart_changed": changed,
                   "native_timeout": row["timed_out"], "fixed_timeout": None if fixed is None else fixed["timed_out"],
                   "qualifies": bool(good(row) and fixed is not None and not good(fixed) and changed
                                     and not row["timed_out"] and not fixed["timed_out"] and fixed["status"] == "returned")})
        if row["old_cls"] == "stuck":
            start = get(cid, k, place="start")
            h1.append({"id": cid, "k": k, "endpoint_good": good(row), "start_good": good(start),
                       "endpoint_timeout": row["timed_out"], "start_timeout": None if start is None else start["timed_out"],
                       "qualifies": bool(good(row) and start is not None and not good(start)
                                         and not row["timed_out"] and not start["timed_out"] and start["status"] == "returned")})
    with mp.workdps(120):
        for row in rows:
            if row["id"] not in manifest["multivalue_ids"] or "H3" not in row["hypotheses"]:
                continue
            initial = row.get("initial", {})
            old_ref = row["old_ref"]
            old_valid = False
            try:
                old_value = mp.mpf(row["reference_decimals"][old_ref])
                old_valid = bool(initial.get("valid") and initial.get("guard") and initial.get("hard")
                                 and mp.mpf(initial["norm"]) <= mp.mpf("1e-8")
                                 and abs(mp.mpf(initial["answer"])-old_value) <= mp.mpf("1e-6")*max(1, abs(old_value)))
                moved = [j for j in row["correct_refs"] if j != old_ref
                         and abs(mp.mpf(row["reference_decimals"][j])-old_value) > mp.mpf("1e-4")*max(1, abs(old_value))]
            except Exception:
                moved = []
            h3.append({"id": row["id"], "k": row["k"], "old_ref": old_ref, "old_valid_at80": old_valid,
                       "new_refs": row["correct_refs"], "timeout": row["timed_out"],
                       "qualifies": bool(old_valid and moved and not row["timed_out"])})
    qualified1 = [r for r in h1 if r["qualifies"]]
    cases1 = sorted({r["id"] for r in qualified1})
    cases2 = sorted({r["id"] for r in h2 if r["qualifies"]})
    cases3 = sorted({r["id"] for r in h3 if r["qualifies"]})
    out = {"H1": {"pairs": len(h1), "qualifying_pairs": len(qualified1), "qualifying_cases": cases1,
                   "pass": len(cases1) >= 4 and len(qualified1) >= 8 and len({contest(c) for c in cases1}) >= 2,
                   "details": h1},
           "H2": {"pairs": len(h2), "qualifying_cases": cases2, "pass": len(cases2) >= 4, "details": h2},
           "H3": {"records": len(h3), "qualifying_cases": cases3, "pass": len(cases3) >= 2, "details": h3},
           "jobs": len(rows), "timeouts": sum(r["timed_out"] for r in rows),
           "status_counts": {s: sum(r["status"] == s for r in rows) for s in sorted({r["status"] for r in rows})},
           "score_errors": [{"job_id": r["job_id"], "error": r["score_error"]} for r in rows if r.get("score_error")]}
    dump("summary.json", out)
    with (HERE / "per-job.csv").open("w", newline="") as handle:
        fields = ["job_id", "id", "k", "old_cls", "old_ref", "place", "mode", "status", "timed_out", "seconds", "correct_refs"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fields})
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "details"} if isinstance(v, dict) else v
                      for k, v in out.items()}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("freeze", "run", "summarize"))
    args = parser.parse_args()
    globals()[args.command]()
