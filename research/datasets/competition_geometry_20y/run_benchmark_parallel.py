#!/usr/bin/env python3
"""Concurrent benchmark driver for the complete audited DSL directory.

The solver itself is still launched in an isolated child process per
case/seed.  Concurrency only shortens wall time; it does not share solver
state or change a case definition.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from run_benchmark import answer_set_complete, answer_set_exact, close_to_expected


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime-root", type=Path, required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[7])
    ap.add_argument("--budget", type=float, default=3.0)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument(
        "--hard-timeout",
        action="store_true",
        help="kill each solver subprocess at the requested budget (wall-clock seconds)",
    )
    ap.add_argument(
        "--require-one-core",
        action="store_true",
        help="fail unless the benchmark process is restricted to exactly one CPU",
    )
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    cpu_affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    if args.require_one_core and len(cpu_affinity) != 1:
        raise SystemExit(
            f"--require-one-core requested, but process affinity is {cpu_affinity or 'unknown'}"
        )

    here = Path(__file__).resolve().parent
    cases = sorted((here / "dsl").glob("*.json"))
    audits = {}
    audit_path = here / "manual_audit.jsonl"
    if audit_path.exists():
        for line in audit_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                # Source rows may use a compact ID (notably AIME 2025),
                # while the canonical DSL filename uses the dedupe key.  All
                # three identifiers point to the same audited answer.
                keys = [row.get("problem_id"), row.get("dedupe_key")]
                dsl_path = row.get("dsl_path")
                if dsl_path:
                    keys.append(Path(dsl_path).stem)
                for key in keys:
                    if key:
                        audits[key] = row
    py = args.runtime_root / "solver/python/.venv/bin/python"
    geo = args.runtime_root / "geosolver/src"
    child = here / "benchmark_child.py"
    subprocess_timeout = max(30.0, args.budget) if args.hard_timeout else max(30.0, args.budget * 5.0)

    def one(case: Path, seed: int) -> dict:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(geo)
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                [str(py), str(child), str(case), str(seed), str(args.budget)],
                cwd=str(args.runtime_root / "geosolver"),
                env=env,
                text=True,
                capture_output=True,
                timeout=subprocess_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            payload = {"status": "timeout", "stdout_tail": str(exc.stdout)[-2000:] if exc.stdout else "", "stderr_tail": str(exc.stderr)[-2000:] if exc.stderr else ""}
        else:
            payload = None
            for line in reversed(proc.stdout.splitlines()):
                try:
                    payload = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
            if payload is None:
                payload = {"status": "runner_error", "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:]}
        expected = audits.get(case.stem, {}).get("published_answer")
        compared = payload.get("reported_answer") or payload.get("selected_answer")
        payload.update({
            "case_id": case.stem,
            "seed": seed,
            "wall_sec": time.monotonic() - t0,
            "expected_answer": expected,
            "raw_selected_answer": payload.get("selected_answer"),
            "answer_match": close_to_expected(compared, expected),
            "answer_set_complete": answer_set_complete(payload.get("accepted_answers", []), expected),
            "answer_set_exact": answer_set_exact(payload.get("accepted_answers", []), expected),
        })
        return payload

    jobs = [(case, seed) for case in cases for seed in args.seeds]
    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = [pool.submit(one, case, seed) for case, seed in jobs]
        for fut in as_completed(futures):
            row = fut.result()
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    rows.sort(key=lambda r: (r["case_id"], r["seed"]))
    reference_only = [p for p in cases if json.loads(p.read_text(encoding="utf-8")).get("solver_coverage", "").startswith("reference_only")]
    summary = {
        "runtime_root": str(args.runtime_root),
        "seeds": args.seeds,
        "budget_sec": args.budget,
        "jobs": args.jobs,
        "hard_timeout": args.hard_timeout,
        "subprocess_timeout_sec": subprocess_timeout,
        "cpu_affinity": cpu_affinity,
        "one_core_enforced": len(cpu_affinity) == 1,
        "cases": len(cases),
        "runnable_cases": len(cases) - len(reference_only),
        "reference_only_cases": len(reference_only),
        "runs": len(rows),
        "success_runs": sum(x.get("status") == "success" for x in rows),
        "no_solution_runs": sum(x.get("status") == "no_solution" for x in rows),
        "correct_runs": sum(x.get("answer_match") is True for x in rows),
        "complete_answer_set_runs": sum(x.get("answer_set_complete") is True for x in rows),
        "answer_set_exact_runs": sum(x.get("answer_set_exact") is True for x in rows),
        "answer_set_covered_but_not_exact_runs": sum(
            x.get("answer_set_complete") is True and x.get("answer_set_exact") is False
            for x in rows
        ),
        "reference_only_runs": sum(x.get("status") == "reference_only" for x in rows),
        "exception_runs": sum(x.get("status") == "exception" for x in rows),
        "timeout_runs": sum(x.get("status") == "timeout" for x in rows),
        "results": rows,
    }
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("cases", "runnable_cases", "reference_only_cases", "runs", "success_runs", "no_solution_runs", "correct_runs", "reference_only_runs", "exception_runs", "timeout_runs")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
