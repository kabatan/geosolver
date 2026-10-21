"""Bounded AG2 DDAR interface probe; no ML, search, training, or GPU.

The H01 definition and the query predicates are manually translated. Numerical
coordinates come from this repository's geometry primitives, not solver.solve.
Only original construction assumptions are forced; no query is a premise.
Each worker gets 30 s wall time and the run gets a 300 s total wall budget.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
AG2 = ROOT / "qwen/.runtime/alphageometry2-inspect-20260926"


def worker(case):
    sys.path.insert(0, str(AG2))
    import numpy as np
    from ddar import DDAR
    from parse import AGPoint, AGPredicate, AGProblem

    wall, cpu = time.perf_counter(), time.process_time()
    if case == "official_2004_p5":
        from test import problems_without_aux
        problem = AGProblem.parse(problems_without_aux["2004_p5"])
        queries = {"official_goal": problem.goal}
        evidence = {"source": "Unmodified official test.py problems_without_aux[2004_p5]"}
    else:
        import sympy as s
        from geosolver.geometry import FootOfPerpendicular, Line, Midpoint, Orthocenter, Point
        u, v, b = (s.Integer(x) for x in ((2, 5, 4) if case.endswith("shape2") else (1, 4, 3)))
        # Python integer zero would become 0.0 in Midpoint's y division.
        # Give exact SymPy zeros to keep independent residual checks rational.
        points = {"a": Point(u, v), "b": Point(-b, s.S.Zero), "c": Point(b, s.S.Zero)}
        points["m"] = Midpoint(points["b"], points["c"])
        points["h"] = Orthocenter(points["a"], points["b"], points["c"])
        points["p"] = FootOfPerpendicular(points["h"], Line(points["a"], points["m"]))
        xy = {n: (s.cancel(p.x), s.cancel(p.y)) for n, p in points.items()}
        assert all(value.is_Rational for pair in xy.values() for value in pair)
        ag_points = {n: AGPoint(n, np.array([float(x), float(y)])) for n, (x, y) in xy.items()}
        assumptions = [
            "coll b m c", "cong b m m c",  # midpoint
            "perp a h b c", "perp b h a c",  # orthocenter
            "coll a m p", "perp h p a m",  # foot of H on AM
        ]
        if case.startswith("h01_no_premises"):
            assumptions = []
        def pred(text):
            return AGPredicate.parse(text).replace_points(ag_points)
        query_text = {
            "target_true": "eqratio a m b m b m p m",  # AM*PM = BM^2
            "third_altitude_true": "perp c h a b",
            "wrong_target_false": "eqratio a m b m b m p a",  # AM*AP = BM^2
            "isosceles_false": "cong a b a c",
        }
        queries = {name: pred(text) for name, text in query_text.items()}
        problem = AGProblem(list(ag_points.values()), [pred(a) for a in assumptions], queries["target_true"])
        def d2(a, b):
            return s.cancel(sum((x-y)**2 for x, y in zip(xy[a], xy[b])))
        dot_ch_ab = s.cancel(sum((xy["h"][i]-xy["c"][i])*(xy["b"][i]-xy["a"][i]) for i in (0, 1)))
        residuals = {
            "target_true": d2("a", "m")*d2("p", "m")-d2("b", "m")**2,
            "third_altitude_true": dot_ch_ab,
            "wrong_target_false": d2("a", "m")*d2("p", "a")-d2("b", "m")**2,
            "isosceles_false": d2("a", "b")-d2("a", "c"),
        }
        evidence = {
            "coordinates_exact": {n: list(map(str, p)) for n, p in xy.items()},
            "query_predicates": query_text,
            "exact_residuals_in_this_instance": {n: str(s.cancel(r)) for n, r in residuals.items()},
            "instance_truth_only_not_general_proof": {n: bool(s.cancel(r) == 0) for n, r in residuals.items()},
            "h01_definition_active": bool(assumptions),
        }
    engine = DDAR(problem.points)
    before = {k: engine.check_pred(p) for k, p in queries.items()}
    for premise in problem.preds:
        engine.force_pred(premise)
    after_premises = {k: engine.check_pred(p) for k, p in queries.items()}
    engine.deduction_closure(progress_dot=False)
    after_closure = {k: engine.check_pred(p) for k, p in queries.items()}
    result = {
        "case": case, "status": "complete",
        "problem_string": problem.pstring(),
        "forced_premises": list(map(str, problem.preds)),
        "queries": list(map(str, queries.values())),
        "before_premises": before, "after_premises": after_premises,
        "after_closure": after_closure,
        "return_types": {k: type(v).__name__ for k, v in after_closure.items()},
        "seconds_wall_worker": time.perf_counter()-wall,
        "seconds_cpu_worker": time.process_time()-cpu,
        "evidence": evidence,
    }
    print(json.dumps(result, ensure_ascii=False))


def main():
    cases = ["official_2004_p5", "h01_shape1", "h01_shape2", "h01_no_premises_shape1"]
    results = []
    started = time.perf_counter()
    for case in cases:
        if time.perf_counter() - started > 300 - 30:
            results.append({"case": case, "status": "skipped_total_budget"})
            continue
        env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        try:
            proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", case], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            (OUT / f"{case}.stdout").write_text(proc.stdout)
            (OUT / f"{case}.stderr").write_text(proc.stderr)
            if proc.returncode == 0:
                results.append(json.loads(proc.stdout))
            else:
                results.append({"case": case, "status": "error", "returncode": proc.returncode, "stderr": proc.stderr})
        except subprocess.TimeoutExpired:
            results.append({"case": case, "status": "timeout", "limit_seconds": 30})
    result = {
        "scope": "Hand-translated DDAR interoperability probe, not ML discovery, learning, or transfer",
        "ag2_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=AG2, text=True).strip(),
        "python": sys.executable,
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "seconds_wall_total": time.perf_counter()-started,
        "cases": results,
    }
    (OUT / "results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(sys.argv[2])
    else:
        main()
