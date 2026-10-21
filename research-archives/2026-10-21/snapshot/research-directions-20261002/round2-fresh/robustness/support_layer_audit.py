"""Static layer feasibility for the ORIGINAL real negative-K 26-rod baseline.

Uses the saved .04 sampled near pairs, not the later bias/capsule designs.
Distinct rod layers and straight vertical through-pins are assumed. Ground
pins extend to a common bottom plate, or individually to a bottom/top frame.
This is a sampled necessary-order check, not a physical collision certificate.
"""
import hashlib
import itertools
import json
from pathlib import Path
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from clearance_audit import RODS

OUT = Path(__file__).resolve().parent
SOURCE = OUT / "clearance_0.040.json"
CASE = next(c for c in json.loads(SOURCE.read_text()) if c["name"] == "real_negative")
ANCHORS = ("O0", "O1", "O2")
INCIDENT = {j: [i for i, rod in enumerate(RODS) if j in rod]
            for j in {j for rod in RODS for j in rod}}


def validate(layers, sides):
    violations = []
    if sorted(layers) != list(range(len(RODS))):
        violations.append({"type": "not_a_layer_permutation"})
    for c in CASE["near_pairs"]:
        i, j = c["rod_index"], c["joint"]
        heights = [layers[h] for h in INCIDENT[j]]
        if not (layers[i] < min(heights) or layers[i] > max(heights)):
            violations.append({"type": "through_pin", "rod": i, "joint": j})
        if j in sides:
            ok = (layers[i] > max(heights) if sides[j] == "bottom"
                  else layers[i] < min(heights))
            if not ok:
                violations.append({"type": "support_pin", "rod": i, "joint": j})
    return violations


def solve(mode):
    pairs = list(itertools.combinations(range(len(RODS)), 2))
    near = CASE["near_pairs"]
    anchor_start = len(RODS) + len(pairs) + len(near)
    n = anchor_start + (len(ANCHORS) if mode == "split_frames" else 0)
    rows, lower, upper = [], [], []
    big_m = len(RODS) + 1

    def add(row, lo=-np.inf, hi=np.inf):
        rows.append(row)
        lower.append(lo)
        upper.append(hi)

    def above_or_below(i, h, binary):
        add({i: 1, h: -1, binary: big_m}, lo=1)
        add({i: -1, h: 1, binary: -big_m}, lo=1-big_m)

    for k, (i, j) in enumerate(pairs):
        above_or_below(i, j, len(RODS) + k)
    support_pairs = 0
    for k, c in enumerate(near):
        i, j = c["rod_index"], c["joint"]
        for h in INCIDENT[j]:
            above_or_below(i, h, len(RODS) + len(pairs) + k)
            if j in ANCHORS:
                support_pairs += 1
                if mode == "common_bottom":
                    add({i: 1, h: -1}, lo=1)
                else:
                    above_or_below(i, h, anchor_start + ANCHORS.index(j))

    a = lil_matrix((len(rows), n))
    for i, row in enumerate(rows):
        for j, value in row.items():
            a[i, j] = value
    start = time.monotonic()
    result = milp(
        np.zeros(n), integrality=np.ones(n),
        bounds=Bounds(np.zeros(n), np.r_[np.full(len(RODS), len(RODS)-1),
                                       np.ones(n-len(RODS))]),
        constraints=LinearConstraint(a.tocsr(), lower, upper),
        options={"time_limit": 120, "mip_rel_gap": 0},
    )
    record = {"mode": mode, "status": int(result.status),
              "message": result.message, "seconds": time.monotonic()-start,
              "variables": n, "constraints": len(rows),
              "support_rod_pair_constraints": support_pairs,
              "rod_layer_order": None, "anchor_support_sides": None,
              "validation_violations": None}
    if result.x is not None:
        layers = np.rint(result.x[:len(RODS)]).astype(int).tolist()
        sides = {j: "bottom" for j in ANCHORS}
        if mode == "split_frames":
            sides = {j: "top" if result.x[anchor_start+k] > .5 else "bottom"
                     for k, j in enumerate(ANCHORS)}
        violations = validate(layers, sides)
        assert not violations, violations
        record.update(rod_layer_order=layers, anchor_support_sides=sides,
                      validation_violations=violations)
    print(json.dumps(record), flush=True)
    return record


if __name__ == "__main__":
    old_layers = next(c["rod_layer_order"] for c in
                      json.loads((OUT / "layers_0.040.json").read_text())
                      if c["name"] == "real_negative")
    payload = {
        "baseline": "original real_negative: poles (-1,0,1), K=-.6, L=1, S=sqrt(1.6), arm=2.3958349462896438",
        "source": str(SOURCE),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "threshold": CASE["threshold"], "sampled_configurations": CASE["configs"],
        "near_pair_count": len(CASE["near_pairs"]), "rods": RODS,
        "previous_assignment_common_bottom_violations": validate(
            old_layers, {j: "bottom" for j in ANCHORS}),
        "results": [],
        "limitations": "Sampled .04 near-pair order feasibility only. Excludes continuous-path certification, pin/pin and joint bodies, rod thickness, stiffness, frame structure, and the controlled D1 support.",
    }
    payload["results"].append(solve("common_bottom"))
    if payload["results"][-1]["status"] == 2:
        payload["results"].append(solve("split_frames"))
    (OUT / "support_layers_0.040.json").write_text(json.dumps(payload, indent=2))
