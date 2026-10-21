"""Translation sensitivity only: unfold H's definition into all 3 altitudes.

Uses the already saved H01 inputs from probe.py/results.json. Does not add a
point or the target relation. The sole queried target remains AM*MP=BM^2.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
AG2 = ROOT / "qwen/.runtime/alphageometry2-inspect-20260926"


def worker(case):
    sys.path.insert(0, str(AG2))
    from ddar import DDAR
    from parse import AGPredicate, AGProblem
    data = json.loads((OUT / "results.json").read_text())
    source = next(c for c in data["cases"] if c["case"] == case)
    problem = AGProblem.parse(source["problem_string"])
    by_name = {p.name: p for p in problem.points}
    extra = AGPredicate.parse("perp c h a b").replace_points(by_name)
    problem.preds.append(extra)
    assert str(problem.goal) not in list(map(str, problem.preds))
    wall, cpu = time.perf_counter(), time.process_time()
    engine = DDAR(problem.points)
    for premise in problem.preds:
        engine.force_pred(premise)
    after_premises = engine.check_pred(problem.goal)
    engine.deduction_closure(progress_dot=False)
    print(json.dumps({
        "case": case + "_three_altitudes", "status": "complete",
        "original_case": case, "added_premise": str(extra),
        "forced_premises": list(map(str, problem.preds)),
        "goal": str(problem.goal), "problem_string": problem.pstring(),
        "after_premises": after_premises,
        "after_closure": engine.check_pred(problem.goal),
        "seconds_wall_worker": time.perf_counter() - wall,
        "seconds_cpu_worker": time.process_time() - cpu,
    }))


def main():
    started = time.perf_counter()
    results = []
    for case in ("h01_shape1", "h01_shape2"):
        env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        try:
            p = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", case], capture_output=True, text=True, timeout=30, cwd=ROOT, env=env)
            (OUT / (case + "_three_altitudes.stdout")).write_text(p.stdout)
            (OUT / (case + "_three_altitudes.stderr")).write_text(p.stderr)
            results.append(json.loads(p.stdout) if p.returncode == 0 else {"case": case, "status": "error", "stderr": p.stderr})
        except subprocess.TimeoutExpired:
            results.append({"case": case, "status": "timeout", "limit_seconds": 30})
    result = {
        "scope": "Post-probe definition-unfolding sensitivity, not new geometry discovery",
        "source_results_sha256": hashlib.sha256((OUT / "results.json").read_bytes()).hexdigest(),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "ag2_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=AG2, text=True).strip(),
        "seconds_wall_total": time.perf_counter() - started,
        "cases": results,
    }
    (OUT / "results-sensitivity.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(sys.argv[2])
    else:
        main()
