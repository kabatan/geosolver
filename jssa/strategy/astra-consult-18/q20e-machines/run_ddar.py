"""Bounded, headless replay of official DD+AR; no upstream edits or LM weights."""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import logging
import os
from pathlib import Path
import random
import re
import resource
import signal
import sys
import time
import types

BASE = Path(__file__).resolve().parent
UPSTREAM = BASE / "upstream"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--renamed", action="store_true")
    args = parser.parse_args()
    stamp = time.monotonic()
    result = {"seed": args.seed, "renamed": args.renamed, "status": "not_started"}
    out = BASE / f"ddar-{args.seed}-{'renamed' if args.renamed else 'original'}.json"
    def deadline(_sig, _frame):
        raise TimeoutError("90 second total wall limit")
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(90)
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    shim_calls = []
    try:
        absl = types.ModuleType("absl")
        absl.logging = logging
        sys.modules["absl"] = absl
        mpl = types.ModuleType("matplotlib")
        pyplot = types.ModuleType("matplotlib.pyplot")
        colors = types.ModuleType("matplotlib.colors")
        def unavailable(name):
            raise RuntimeError(f"Plotting must not be used in proof replay: {name}")
        pyplot.__getattr__ = unavailable
        colors.__getattr__ = unavailable
        def use(backend):
            assert backend == "TkAgg"
            shim_calls.append("matplotlib.use(TkAgg)")
        mpl.use = use
        mpl.pyplot = pyplot
        mpl.colors = colors
        sys.modules.update({"matplotlib": mpl, "matplotlib.pyplot": pyplot, "matplotlib.colors": colors})
        sys.path.insert(0, str(UPSTREAM))
        import numpy as np
        import scipy
        from scipy import optimize
        # HiGHS has its own worker pool; keep it at one independently of BLAS.
        original_linprog = optimize.linprog
        def serial_linprog(*a, **kw):
            kw["options"] = dict(kw.get("options", {}), threads=1)
            return original_linprog(*a, **kw)
        optimize.linprog = serial_linprog
        import graph
        import problem
        import ddar
        result["environment"] = {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__, "pythonhashseed": os.environ.get("PYTHONHASHSEED")}
        result["environment"]["highs_threads"] = 1
        np.random.seed(args.seed)
        random.seed(args.seed)
        lines = (UPSTREAM / "imo_ag_30.txt").read_text().splitlines()
        source = dict(zip(lines[::2], lines[1::2]))["translated_imo_2008_p1a"]
        premise = source.split(" ? ")[0]
        p = problem.Problem.from_txt(premise, translate=False)
        point_names = [x for c in p.clauses for x in c.points]
        rename = dict(zip(point_names, reversed("abcdefghijklmnopqrstuvwxyz"[:len(point_names)]))) if args.renamed else {x: x for x in point_names}
        if args.renamed:
            premise = re.sub(r"\b[a-z][a-z0-9]*\b", lambda m: rename.get(m[0], m[0]), premise)
            p = problem.Problem.from_txt(premise, translate=False)
        assert p.goal is None
        definitions = problem.Definition.from_txt_file(str(UPSTREAM / "defs.txt"), to_dict=True)
        rules = problem.Theorem.from_txt_file(str(UPSTREAM / "rules.txt"), to_dict=True)
        t0 = time.monotonic()
        g, added = graph.Graph.build_problem(p, definitions, verbose=False)
        result["build_seconds"] = time.monotonic() - t0
        result["source_premise_sha256"] = hashlib.sha256(source.split(" ? ")[0].encode()).hexdigest()
        result["rename"] = rename
        result["coordinates"] = {orig: [g.names2points([new])[0].num.x, g.names2points([new])[0].num.y] for orig, new in rename.items()}
        queries = list(itertools.combinations(["a1", "a2", "b1", "b2", "c1", "c2"], 4))
        initial = {q: bool(g.check("cyclic", g.names2points([rename[x] for x in q]))) for q in queries}
        t0 = time.monotonic()
        g, level_times, status, branches, added = ddar.solve(g, rules, p, max_level=1000, timeout=85)
        result.update({"solve_seconds": time.monotonic() - t0, "status": status, "level_times": level_times, "branches": branches, "added_dependencies": len(added)})
        result["saturation_confirmed"] = status == "saturated" and len(level_times) < 1000 and all(t < 85 for t in level_times)
        rows = []
        for q in queries:
            mapped = [rename[x] for x in q]
            proven = bool(g.check("cyclic", g.names2points(mapped)))
            occupancy = sorted([sum(x[0] == side for x in q) for side in "abc"], reverse=True)
            row = {"points": list(q), "occupancy": occupancy, "initial": initial[q], "derived": proven}
            if proven:
                goal = problem.Construction("cyclic", mapped)
                setup, aux, log, refs = ddar.get_proof_steps(g, goal)
                row.update({"proof_steps": len(log), "setup_steps": len(setup), "aux_steps": len(aux)})
            rows.append(row)
        result["queries"] = rows
        result["shim_calls"] = shim_calls
        assert shim_calls == ["matplotlib.use(TkAgg)"]
    except BaseException as exc:
        import traceback
        result.update({"status": "timeout" if isinstance(exc, TimeoutError) else "error", "exception": repr(exc), "traceback": traceback.format_exc()})
    finally:
        signal.alarm(0)
        result["total_seconds"] = time.monotonic() - stamp
        result["max_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result["source_hashes"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(UPSTREAM.iterdir()) if p.is_file()}
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({"file": out.name, "status": result["status"], "seconds": result["total_seconds"], "derived": sum(q["derived"] for q in result.get("queries", [])), "exception": result.get("exception")}))

if __name__ == "__main__":
    main()
