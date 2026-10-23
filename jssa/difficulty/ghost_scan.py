"""Where do failed searches end?  Shape of the figure at each endpoint of the 200-start runs.

For every point of the DSL, its position at each saved endpoint (minima/raw-323) is computed from
the variables. Two scale-free numbers describe the figure:
  coinc = min distance between two points / diameter of the figure (0 = two points merged)
  scale = diameter / median diameter of the hit figures (far from 1 = figure blew up or shrank)
  flat  = min area of a triangle of three distinct points / diameter^2 (0 = three points collinear),
          over triples whose points are pairwise apart (coinc covers merged pairs)
A pair (triple) that also coincides (is collinear) in every hit figure is ignored: it is part of the answer.

Usage: ghost_scan.py RAW_DIR OUT.csv [ids...]
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_basins import answer_float, construction_coordinates, load_case  # noqa: E402


def point_names(dsl):
    names = []
    for c in dsl["constructions"]:
        e = c["expression"].split("(")[0]
        if e in ("Line", "Circle", "Circumcircle", "Incircle", "Tangent", "Ray", "Segment", "Polygon", "Triangle"):
            continue
        names.append(c["name"])
    return names


def main():
    raw, out = Path(sys.argv[1]), sys.argv[2]
    ids = sys.argv[3:] or sorted(p.stem for p in raw.glob("*.json"))
    w = csv.writer(open(out, "w", newline=""))
    w.writerow(["id", "k", "cls", "res", "coinc", "scale", "pair", "flat", "triple", "n_pts"])
    for cid in ids:
        d = json.loads((raw / f"{cid}.json").read_text())
        recs = d.get("records") or []
        if not recs or d.get("p_any", 1) >= 0.95:
            continue
        dsl = load_case(cid)["dsl"]
        coords = {}
        for nm in point_names(dsl):
            try:
                cc = construction_coordinates(dsl, [nm])
            except Exception:  # noqa: BLE001
                continue
            coords[nm] = (cc[f"x_{nm}"], cc[f"y_{nm}"])
        if len(coords) < 2:
            continue

        def figure(x):
            pts = {}
            for nm, ((vx, ex), (vy, ey)) in coords.items():
                px, py = answer_float(ex, x), answer_float(ey, x)
                if px is None or py is None or not (math.isfinite(px) and math.isfinite(py)):
                    continue
                pts[nm] = np.array([px, py])
            return pts

        figs = [(r, figure(r["x"])) for r in recs if "x" in r]
        hits = [f for r, f in figs if r["cls"] == "hit" and len(f) >= 2]
        names = sorted(coords)
        always = set()
        if hits:
            for i, a in enumerate(names):
                for b in names[i + 1:]:
                    if all(a in f and b in f and np.linalg.norm(f[a] - f[b]) < 1e-6 * max(1.0, max(np.linalg.norm(v) for v in f.values())) for f in hits):
                        always.add((a, b))
        def area(f, a, b, c):
            u, v = f[b] - f[a], f[c] - f[a]
            return abs(u[0] * v[1] - u[1] * v[0]) / 2

        flat_always = set()
        if hits:
            for i, a in enumerate(names):
                for j in range(i + 1, len(names)):
                    for c in names[j + 1:]:
                        b = names[j]
                        if all(a in f and b in f and c in f and area(f, a, b, c) < 1e-6 * max(1e-300, max(np.linalg.norm(p - q) for p in f.values() for q in f.values())) ** 2 for f in hits):
                            flat_always.add((a, b, c))
        diam_hit = float(np.median([max(np.linalg.norm(p - q) for p in f.values() for q in f.values()) for f in hits])) if hits else float("nan")
        for r, f in figs:
            if len(f) < 2:
                w.writerow([cid, r["k"], r["cls"], r.get("res", ""), "", "", "", "", "", len(f)])
                continue
            ks = sorted(f)
            diam = max(np.linalg.norm(f[a] - f[b]) for a in ks for b in ks)
            best, pair = math.inf, ""
            for i, a in enumerate(ks):
                for b in ks[i + 1:]:
                    if (a, b) in always:
                        continue
                    dd = np.linalg.norm(f[a] - f[b])
                    if dd < best:
                        best, pair = dd, f"{a}-{b}"
            coinc = best / diam if diam > 0 and math.isfinite(best) else 0.0
            fbest, triple = math.inf, ""
            if diam > 0:
                for i, a in enumerate(ks):
                    for j in range(i + 1, len(ks)):
                        b = ks[j]
                        if np.linalg.norm(f[a] - f[b]) < 1e-3 * diam:
                            continue
                        for c in ks[j + 1:]:
                            if (a, b, c) in flat_always or min(np.linalg.norm(f[a] - f[c]), np.linalg.norm(f[b] - f[c])) < 1e-3 * diam:
                                continue
                            ar = area(f, a, b, c) / diam**2
                            if ar < fbest:
                                fbest, triple = ar, f"{a}-{b}-{c}"
            w.writerow([cid, r["k"], r["cls"], r.get("res", ""), f"{coinc:.3e}", f"{diam / diam_hit:.3e}" if diam_hit == diam_hit and diam_hit > 0 else "", pair,
                        f"{fbest:.3e}" if math.isfinite(fbest) else "", triple, len(f)])
        print(cid, len(figs), flush=True)


if __name__ == "__main__":
    main()
