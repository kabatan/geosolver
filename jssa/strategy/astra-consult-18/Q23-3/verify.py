"""Read-only re-evaluation and independent aggregation. No optimization calls."""
from __future__ import annotations
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    from mpmath import mp
    from geosolver import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    manifest = json.loads((HERE / "manifest.json").read_text())
    lock = json.loads((HERE / "registration-lock.json").read_text())
    rows = [json.loads(l) for l in (HERE / "results.jsonl").read_text().splitlines()]
    by_key = {r["job_id"]: r for r in rows}
    jobs = {r["job_id"]: r for r in manifest["jobs"]}
    cases = {c["id"]: c for c in manifest["cases"]}
    assert len(by_key) == len(rows) == len(jobs) == 144
    assert set(jobs) == set(by_key)
    assert all(sha(HERE / n) == s for n, s in lock["files"].items())
    assert all(sha(ROOT / n) == s for n, s in manifest["source_hashes"].items())
    # Decimal arithmetic is separate from the pilot's mpmath matching path.
    matches = {}
    with localcontext() as ctx:
        ctx.prec = 115
        for r in rows:
            observed = set()
            for a in r["accepted"]:
                if a.get("answer") is None:
                    continue
                v = Decimal(a["answer"])
                for i, ref in enumerate(r["reference_decimals"]):
                    target = Decimal(ref)
                    if abs(v-target) <= Decimal("1e-40")*max(Decimal(1), abs(target)):
                        observed.add(i)
            assert sorted(observed) == r["correct_refs"]
            matches[r["job_id"]] = observed
    good = lambda r: bool(matches[r["job_id"]])
    main_native = [r for r in rows if "H1/H2" in r["hypotheses"]]
    assert len(main_native) == 48
    h1, h2 = [], []
    table = []
    for r in main_native:
        fixed_key = f"{r['id']}::{r['k']}::endpoint::first_chart"
        fixed = by_key[fixed_key]
        choices = defaultdict(set)
        for event in r["chart_trace"]:
            if event["used"] is not None:
                choices[tuple(event["shape"])].add(json.dumps(event["used"]))
        changes = any(len(s)>1 for s in choices.values())
        h2.append({"id": r["id"], "k": r["k"], "native_correct": good(r), "fixed_correct": good(fixed),
                   "chart_calls": len(r["chart_trace"]), "changed": changes,
                   "native_timeout": r["timed_out"], "fixed_timeout": fixed["timed_out"],
                   "qualifies": bool(changes and good(r) and not good(fixed) and fixed["status"] == "returned"
                                     and not r["timed_out"] and not fixed["timed_out"])})
        if r["old_cls"] == "stuck":
            start = by_key[f"{r['id']}::{r['k']}::start::native"]
            h1.append({"id": r["id"], "k": r["k"], "endpoint_correct": good(r), "start_correct": good(start),
                       "qualifies": bool(good(r) and not good(start) and start["status"] == "returned"
                                         and not r["timed_out"] and not start["timed_out"])})
    for cid in manifest["main_ids"]:
        p = [r for r in h1 if r["id"] == cid]
        q = [r for r in h2 if r["id"] == cid]
        table.append({"id": cid, "failed_endpoints_accepted": sum(r["endpoint_correct"] for r in p),
                      "paired_starts_accepted": sum(r["start_correct"] for r in p),
                      "H1_qualifies": sum(r["qualifies"] for r in p),
                      "native_all4_accepted": sum(r["native_correct"] for r in q),
                      "fixed_all4_accepted": sum(r["fixed_correct"] for r in q),
                      "chart_changed_candidates": sum(r["changed"] for r in q)})
    # Re-evaluate H3 initial points at the exact binary floats actually passed to
    # the refiner, rather than only the repr(float) strings in initial telemetry.
    h3 = []
    for r in rows:
        if "H3" not in r["hypotheses"]:
            continue
        bundle = load_problem_bundle(GeometryProblem.model_validate(cases[r["id"]]["dsl"]).engine_document())
        ev = build_ir_evaluator(bundle)
        rec = jobs[r["job_id"]]["record"]
        with mp.workdps(80), high_precision_mode():
            ratios = [float(v).as_integer_ratio() for v in rec["x"]]
            point = [mp.mpf(n) / mp.mpf(d) for n, d in ratios]
            e = ev.evaluate_hp_residual(point, precision=80)
            norm = mp.sqrt(mp.fsum(v*v for v in e.residual_vector))
            guard, _ = ev.evaluate_guard(point)
            hard = ev.evaluate_hp_hard_feasibility(point, precision=80)
            value = ev.evaluate_answer_hp(point, precision=80).answer_hp
            ref = mp.mpf(r["reference_decimals"][r["old_ref"]])
            valid = bool(guard and hard.hard_feasible and norm <= mp.mpf("1e-8")
                         and value is not None and abs(value-ref) <= mp.mpf("1e-6")*max(1, abs(ref)))
            migrated = [j for j in matches[r["job_id"]] if j != r["old_ref"]
                        and abs(mp.mpf(r["reference_decimals"][j])-ref)>mp.mpf("1e-4")*max(1,abs(ref))]
        h3.append({"id": r["id"], "k": r["k"], "old_ref": r["old_ref"], "initial_valid": valid,
                   "initial_norm80": mp.nstr(norm, 22), "new_refs": sorted(matches[r["job_id"]]),
                   "qualifies": bool(valid and migrated and not r["timed_out"])})
    h1cases = sorted({r["id"] for r in h1 if r["qualifies"]})
    h2cases = sorted({r["id"] for r in h2 if r["qualifies"]})
    h3cases = sorted({r["id"] for r in h3 if r["qualifies"]})
    correction = ("pilot.py summarize() incorrectly included two H3-only native endpoints from a main-set problem "
                  "in H2's displayed denominator (50, instead of the preregistered 48). They had no paired "
                  "first_chart job. The optimizer was not rerun. Manifest-defined pairs are used here; "
                  "all three gate decisions remain false.")
    report = {"checks": {"input_hashes": True, "preregistration_hashes": True, "jobs_complete_unique": True,
                          "decimal_answer_matching": True},
              "H1": {"pairs": len(h1), "endpoint_correct": sum(r["endpoint_correct"] for r in h1),
                     "start_correct": sum(r["start_correct"] for r in h1),
                     "both": sum(r["endpoint_correct"] and r["start_correct"] for r in h1),
                     "endpoint_only": sum(r["endpoint_correct"] and not r["start_correct"] for r in h1),
                     "start_only": sum(r["start_correct"] and not r["endpoint_correct"] for r in h1),
                     "qualifying_cases": h1cases, "pass": bool(len(h1cases)>=4 and sum(r["qualifies"] for r in h1)>=8
                          and len({cid.upper().split("-")[0] for cid in h1cases})>=2), "details": h1},
              "H2": {"pairs": len(h2), "native_correct": sum(r["native_correct"] for r in h2),
                     "fixed_correct": sum(r["fixed_correct"] for r in h2),
                     "native_candidates_with_chart_calls": sum(bool(r["chart_calls"]) for r in h2),
                     "native_candidates_with_repeated_calls": sum(r["chart_calls"]>1 for r in h2),
                     "native_chart_calls": sum(r["chart_calls"] for r in h2),
                     "native_candidates_with_chart_changes": sum(r["changed"] for r in h2),
                     "fixed_candidates_with_forced_different_choice": sum(any(t["original"] != t["used"] for t in r["chart_trace"])
                           for r in rows if r["mode"] == "first_chart"),
                     "qualifying_cases": h2cases, "pass": len(h2cases)>=4, "details": h2},
              "H3": {"records": len(h3), "initially_valid": sum(r["initial_valid"] for r in h3),
                     "retained_same_ref": sum(r["new_refs"] == [r["old_ref"]] for r in h3),
                     "qualifying_cases": h3cases, "pass": len(h3cases)>=2, "details": h3},
              "per_case": table, "jobs": len(rows), "accepted_jobs": sum(good(r) for r in rows),
              "timeouts": [r["job_id"] for r in rows if r["timed_out"]], "correction": correction,
              "original_summary_sha256": sha(HERE / "summary.json"), "results_sha256": sha(HERE / "results.jsonl")}
    (HERE / "verified-summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "details"} if isinstance(v,dict) else v
                      for k,v in report.items() if k != "per_case"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
