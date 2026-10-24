"""No experimental problem or objective evaluation: syntax and observation equivalence."""
import ast
import importlib.util
import os
import sys
from pathlib import Path

from mpmath import mp

OUT = Path(__file__).resolve().parent
for p in OUT.glob("*.py"):
    ast.parse(p.read_text(), filename=str(p))
sys.path.insert(0, "/tmp/s3-impl/src")
from geosolver.runtime.integrity import source_tree_hash
assert source_tree_hash() == "sha256:add5afaf829806ca3cbd11fb07b69d956102752e1c6738b0630581a3ceb121eb"
from observe_iterations import Observer
with mp.workdps(80):
    baseline = mp.findroot(lambda x, y: (x*x-2, y-3), (1, 2))
    scalar = {solver: mp.findroot(lambda x: x*x-2, 1, solver=solver)
              for solver in ("secant", "mnewton")}
    observer = Observer()
    observer.uid = "synthetic-no-experimental-objective"
    observer.install()
    observed = mp.findroot(lambda x, y: (x*x-2, y-3), (1, 2))
    assert tuple(baseline) == tuple(observed)
    assert len(observer.rows) > 0 and all(len(r["point"]) == 2 for r in observer.rows)
    for solver in scalar:
        assert scalar[solver] == mp.findroot(lambda x: x*x-2, 1, solver=solver)

    def _run_rank_aware_findroot():
        def assemble_point(values):
            return [values[0], mp.mpf(3)]
        return mp.findroot(lambda x: x*x-2, 1)

    observer.rows.clear()
    _run_rank_aware_findroot()
    assert observer.rows and all(len(r["point"]) == 2 for r in observer.rows)
print("preflight ok: source hash, Python syntax, observation hook exact synthetic root equality")
