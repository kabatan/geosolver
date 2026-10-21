"""Three bounded real public-API calls; no solver or dependency modifications.

The public time limit remains 180 seconds. A 35-second external cancellation
watchdog bounds each call for this audit; cancelled cases are censored, not failures
at the normal 180-second budget. Expected answers are compared only AFTER solve.
"""

import hashlib
import json
import platform
import resource
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import sympy as s

from geosolver import GeometryProblem, SolveOptions, solve, validate
from geosolver.engine import EngineRunner

ROOT = Path(__file__).resolve().parent


def c(name, expression):
    return {"name": name, "expression": expression}


def eq(left, value, operator="="):
    return {"left": left, "operator": operator, "right": value}


def cases():
    median = {
        "id": "standard-median-6-5-7", "variables": ["x", "y"],
        "constructions": [c("B", "Point(0,0)"), c("C", "Point(6,0)"), c("A", "Point(x,y)"), c("M", "Midpoint(B,C)")],
        "conditions": [eq("Distance(A,B)", 5), eq("Distance(A,C)", 7), eq("y", 0, ">")],
        "target": "Distance(A,M)",
    }
    base = [c("B", "Point(0,0)"), c("C", "Point(6,0)"), c("A", "Point(x,y)"), c("M", "Midpoint(B,C)"), c("H", "Orthocenter(A,B,C)"), c("P", "FootOfPerpendicular(H,Line(A,M))")]
    shape = [eq("y", 0, ">"), {"predicate": "AcuteTriangle(A,B,C)"}, eq("Distance(A,B)", "Distance(A,C)", "!="), eq("Distance(A,B)", "Distance(B,C)", "!="), eq("Distance(A,C)", "Distance(B,C)", "!=")]
    h01 = {
        "id": "H01-original-solve-audit", "variables": ["x", "y"],
        "constructions": [c("B", "Point(-6,0)"), c("C", "Point(6,0)")] + base[2:],
        "conditions": shape + [eq("Distance(A,M)", 10)],
        "target": "Distance(A,P)",
    }
    h04 = {
        "id": "H04-original-solve-audit", "variables": ["x", "y"],
        "constructions": base + [c("T", "IntersectLines(PerpendicularBisector(A,P),Line(B,C))")],
        "conditions": shape + [eq("Distance(B,T)", 2), eq("T.x", 0, "<")],
        "target": "Distance(A,T)",
    }
    # References do not enter any problem object or solve call.
    return [(median, "2*sqrt(7)"), (h01, "32/5"), (h04, "4")]


def usage():
    parent = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return parent.ru_utime + parent.ru_stime + children.ru_utime + children.ru_stime


def main():
    started, cpu_start = time.perf_counter(), usage()
    prepared = []
    for raw, expected in cases():
        problem = GeometryProblem.model_validate(raw)
        report = validate(problem)
        (ROOT / f"{problem.id}.input.json").write_text(problem.model_dump_json(indent=2) + "\n")
        prepared.append((problem, expected, report))
    receipt = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "platform": platform.platform(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "options": {"time_limit_seconds": 180, "cores": 1, "seed": 0},
        "external_cancel_seconds_per_case": 35, "cases": [],
    }
    for problem, expected, validation in prepared:
        row = {"id": problem.id, "validation": validation.model_dump(mode="json"), "expected_reference": expected}
        if not validation.valid:
            row["not_run"] = "input_invalid"
            receipt["cases"].append(row)
            continue
        runner = EngineRunner()
        watchdog = threading.Timer(35, runner.cancel)
        before, cpu_before = time.perf_counter(), usage()
        watchdog.start()
        try:
            result = solve(problem, SolveOptions(time_limit_seconds=180, cores=1, seed=0), runner=runner)
        finally:
            watchdog.cancel()
        row.update(status=str(result.status), elapsed_wall_seconds=time.perf_counter()-before, measured_cpu_seconds=usage()-cpu_before, termination_reason=str(result.termination_reason), completeness=str(result.completeness))
        row["censored_by_external_watchdog"] = result.status == "cancelled"
        (ROOT / f"{problem.id}.result.json").write_text(result.model_dump_json(indent=2) + "\n")
        row["answers"] = [a.model_dump(mode="json") for a in result.answers]
        expected_value = s.sympify(expected)
        symbol = s.Symbol("t")
        expected_poly = [str(x) for x in s.Poly(s.minpoly(expected_value, symbol), symbol).all_coeffs()]
        row["expected_minimal_polynomial"] = expected_poly
        row["single_answer_matches_reference"] = len(result.answers) == 1 and result.answers[0].kind == "algebraic" and result.answers[0].minimal_polynomial == expected_poly and abs(s.N(result.answers[0].decimal, 60)-s.N(expected_value, 60)) < s.Rational(1,10**40)
        row["single_answer_matches_reference"] = bool(row["single_answer_matches_reference"])
        row["error"] = None if result.error is None else result.error.model_dump(mode="json")
        row["solver_process_info"] = (result.diagnostics or {}).get("process_info")
        receipt["cases"].append(row)
        receipt.update(elapsed_wall_seconds=time.perf_counter()-started, measured_cpu_seconds=usage()-cpu_start)
        (ROOT / "receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False)+"\n")
        print(json.dumps({k: v for k, v in row.items() if k not in {"validation", "answers", "solver_process_info"}}, ensure_ascii=False), flush=True)
    receipt.update(elapsed_wall_seconds=time.perf_counter()-started, measured_cpu_seconds=usage()-cpu_start)
    (ROOT / "receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps({k: v for k, v in receipt.items() if k != "cases"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
