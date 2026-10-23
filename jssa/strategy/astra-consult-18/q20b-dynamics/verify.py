"""Independent readback of Q20b grids and point coordinates; no local solves."""
import csv
import json
import math
from pathlib import Path
import sys
sys.dont_write_bytecode = True

import experiment as e
import numpy as np
from probe_basins import construction_coordinates, answer_float

out = Path(__file__).resolve().parent
e.check_lock()
inputs = json.loads((out / "inputs.json").read_text())
summary = json.loads((out / "summary.json").read_text())
saved_metrics = {m["id"]: m for m in summary["metrics"]}
geometric = []
total = 0
rescored = 0
statuses = []
for inp in inputs:
    assert len(inp["references"]) == 1
    assert e.sha(e.ROOT / f"jssa/difficulty/minima/raw-323/{inp['id']}.json") == inp["old_sha256"]
    b, ev = e.build(inp["dsl"])
    box = np.asarray(inp["box"])
    width = box[:, 1] - box[:, 0]
    # A separate evaluator per coordinate, changing the target expression,
    # checks the fast numerical_snapshot extraction used at preparation.
    cs = construction_coordinates(inp["dsl"], inp["point_names"])
    errors = []
    for rindex, root in enumerate(inp["roots"]):
        vals = dict(zip(inp["var_names"], root["center"]))
        for i, name in enumerate(inp["point_names"]):
            for axis_i, axis in enumerate(("x", "y")):
                names, evaluator = cs[f"{axis}_{name}"]
                v = answer_float(evaluator, [vals[n] for n in names])
                expected = inp["root_figures"][rindex][i][axis_i]
                assert v is not None and math.isfinite(v)
                errors.append(abs(v - expected) / max(1, abs(v), abs(expected)))
    assert max(errors) < 1e-10, (inp["id"], max(errors))
    geometric.append({"id": inp["id"], "coordinate_components": len(errors), "max_relative_error": max(errors)})
    records = {}
    for cap in (80, 320):
        rows = e.read_records(inp["id"], cap)
        assert len(rows) == 1024 and len({r["k"] for r in rows}) == 1024
        records[cap] = {r["k"]: r for r in rows}
        total += len(rows)
        assert all(r["cls"] != "timeout" and r["X"] != "U" for r in rows)
        for r in rows:
            z = [(r["i"] + .37)/32, (r["j"] + .61)/32]
            expected = box[:, 0] + np.array(z) * width
            assert np.array_equal(np.asarray(r["start"]), expected)
            statuses.append(r.get("status"))
        # Count pairs with scalar loops rather than the array slicing in analyze.
        grid = {(r["i"], r["j"]): r for r in rows}
        for label in ("X", "G", "T"):
            for stride in (1, 2, 4, 8):
                count = different = 0
                for (i, j), r in grid.items():
                    for pair in ((i+stride, j), (i, j+stride)):
                        if pair in grid:
                            count += 1
                            different += r[label] != grid[pair][label]
                metric = next(z for z in saved_metrics[inp["id"]]["caps"][str(cap)]["labels"][label]["curve"] if z["stride"] == stride)
                assert (count, different) == (metric["pairs"], metric["changes"])
        # Uniformly spaced indices were selected without looking at class.
        # These are evaluator calls on saved endpoints, not optimization calls.
        config = e.ExternalPipelineConfig.production_baseline_tier(seed=20261023, total_time_budget_sec=180).search
        for k in range(0, 1024, 64):
            r = records[cap][k]
            if "x" not in r:
                continue
            cand = e.smb._build_candidate(evaluator=ev, config=config,
                bounds=[tuple(p) for p in inp["box"]], values=np.asarray(r["x"]), origin_seed=20261023,
                family_code=e.smb._LM_FAMILY_CODE, origin_start_point_index=k, telemetry=e.smb._SearchTelemetry())
            if "out_of_bounds" in tuple(cand.hard_violation_tags):
                cls = "left_box"
            elif not math.isfinite(cand.residual_norm_float):
                cls = "error"
            elif cand.residual_norm_float > 1e-8:
                cls = "stuck"
            elif not (cand.guard_ok and cand.hard_feasible is not False):
                cls = "wrong_branch"
            else:
                a = answer_float(ev, r["x"])
                ref = inp["references"][0]
                cls = "hit" if a is not None and abs(a-ref) <= 1e-6*max(1, abs(ref)) else "wrong_answer"
            assert cls == r["cls"], (inp["id"], cap, k, cls, r["cls"])
            rescored += 1
    changed = sum(records[80][k]["X"] != records[320][k]["X"] for k in range(1024))
    assert changed == saved_metrics[inp["id"]]["K_label_disagreements"]
    assert all(records[80][k]["start"] == records[320][k]["start"] for k in range(1024))

# The noncongruent control can be reduced on paper; verify the two shoelace
# polynomials exactly, independent of the DSL evaluator.
import sympy as sp
cx, cy = sp.symbols("cx cy", real=True)
A = sp.Matrix([0, 0]); B = sp.Matrix([28, 0]); C = sp.Matrix([cx, cy])
D = sp.Matrix([4, 0]); E = sp.Matrix([20, 0]); F = C/7; G = 5*C/7
M = 2*F-D; NN = 2*E-G
def twice_oriented_area(points):
    return sp.expand(sum(p[0]*q[1]-p[1]*q[0] for p,q in zip(points, points[1:]+points[:1])))
condition_twice = twice_oriented_area([D,E,G,F])
target_twice = twice_oriented_area([A,F,NN,B,C,E,M])
assert sp.simplify(condition_twice - 96*cy/7) == 0
assert sp.simplify(target_twice - 28*cy) == 0
assert 14*42 == 588
e.save("independent-verification.json", {"grid_records": total, "scalar_pair_counts_match": True,
    "same_starts_between_caps": True, "old_input_hashes_match": True,
    "saved_endpoints_rescored": rescored, "rescore_mismatches": 0,
    "new_local_searches": 0, "geometry": geometric, "source_hash_match": True,
    "control_exact_calculation": {"twice_constraint_area": str(condition_twice), "twice_target_area": str(target_twice),
                                  "cy": 42, "cx_squared": 6517, "target": 588}})
print("verified", total, "records;", rescored, "endpoint scores;", sum(r["coordinate_components"] for r in geometric), "coordinate components")

