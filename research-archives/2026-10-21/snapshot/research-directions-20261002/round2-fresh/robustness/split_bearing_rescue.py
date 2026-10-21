"""Original .04 baseline: separate coaxial bearings for each fixed link.

The two incident rods at O_j need not share a shaft between their layers.
Each fixed rod chooses a shaft from the bottom or top plate independently.
Moving joints still use a straight through-pin. This checks sampled ordering,
not continuous clearance, mechanical stiffness, or controlled-input support.
"""
import hashlib
import itertools
import json
from pathlib import Path
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from support_layer_audit import ANCHORS, CASE, INCIDENT, RODS, SOURCE

OUT = Path(__file__).resolve().parent
NR = len(RODS)
MOVING = [c for c in CASE["near_pairs"] if c["joint"] not in ANCHORS]
FIXED_RODS = [(j, h) for j in ANCHORS for h in INCIDENT[j]]


def solve():
    pairs = list(itertools.combinations(range(NR), 2))
    support_start = NR + len(pairs) + len(MOVING)
    n = support_start + len(FIXED_RODS)
    rows, low, high = [], [], []
    big_m = NR + 1

    def add(row, lo=-np.inf, hi=np.inf):
        rows.append(row); low.append(lo); high.append(hi)

    def outside(i, h, binary):
        add({i: 1, h: -1, binary: big_m}, lo=1)
        add({i: -1, h: 1, binary: -big_m}, lo=1-big_m)

    for k, (i, j) in enumerate(pairs):
        outside(i, j, NR+k)
    for k, c in enumerate(MOVING):
        for h in INCIDENT[c["joint"]]:
            outside(c["rod_index"], h, NR+len(pairs)+k)
    for c in CASE["near_pairs"]:
        j = c["joint"]
        if j in ANCHORS:
            for h in INCIDENT[j]:
                outside(c["rod_index"], h,
                        support_start+FIXED_RODS.index((j, h)))

    a = lil_matrix((len(rows), n))
    for i, row in enumerate(rows):
        for j, value in row.items():
            a[i, j] = value
    start = time.monotonic()
    result = milp(
        np.zeros(n), integrality=np.ones(n),
        bounds=Bounds(np.zeros(n), np.r_[np.full(NR, NR-1), np.ones(n-NR)]),
        constraints=LinearConstraint(a.tocsr(), low, high),
        options={"time_limit": 180, "mip_rel_gap": 0},
    )
    record = {
        "baseline": "original real_negative, K=-.6, L=1, S=sqrt(1.6), arm=2.3958349462896438",
        "source": str(SOURCE),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "threshold": CASE["threshold"], "sampled_configurations": CASE["configs"],
        "status": int(result.status), "message": result.message,
        "seconds": time.monotonic()-start, "variables": n, "constraints": len(rows),
        "rod_layer_order": None, "supports": None, "verification": None,
        "limitations": "Sampled projected pin/rod threshold only; excludes continuous paths, pin/pin, rod thickness and bodies, support bearing collars, frame structure, stiffness, and controlled D1 routing.",
    }
    if result.x is not None:
        layers = np.rint(result.x[:NR]).astype(int).tolist()
        supports = [{"anchor": j, "rod_index": h, "rod": RODS[h],
                     "side": "top" if result.x[support_start+k] > .5 else "bottom",
                     "layer": layers[h]}
                    for k, (j, h) in enumerate(FIXED_RODS)]
        for support in supports:
            support["shaft_layer_interval"] = (
                [support["layer"], NR] if support["side"] == "top"
                else [-1, support["layer"]])
        violations, gap_passes = [], []
        assert sorted(layers) == list(range(NR))
        for c in CASE["near_pairs"]:
            i, j = c["rod_index"], c["joint"]
            hmin, hmax = min(layers[h] for h in INCIDENT[j]), max(layers[h] for h in INCIDENT[j])
            if j not in ANCHORS:
                if not (layers[i] < hmin or layers[i] > hmax):
                    violations.append({"joint": j, "rod_index": i, "type": "moving_pin"})
            else:
                if hmin < layers[i] < hmax:
                    gap_passes.append({"joint": j, "rod_index": i,
                                       "rod_layer": layers[i], "fixed_rod_layers": [hmin, hmax],
                                       "minimum_projected_distance": c["min_sampled_distance"]})
                for support in supports:
                    if support["anchor"] == j:
                        lo, hi = support["shaft_layer_interval"]
                        if lo <= layers[i] <= hi:
                            violations.append({"joint": j, "rod_index": i,
                                               "type": "support_shaft", "support": support})
        assert not violations, violations
        record.update(rod_layer_order=layers, supports=supports,
                      verification={"violations": violations,
                                    "near_pairs_checked": len(CASE["near_pairs"]),
                                    "fixed_anchor_pairs_passing_open_shaft_gap": gap_passes})
    (OUT / "split_bearing_rescue_0.040.json").write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2), flush=True)


if __name__ == "__main__":
    solve()
