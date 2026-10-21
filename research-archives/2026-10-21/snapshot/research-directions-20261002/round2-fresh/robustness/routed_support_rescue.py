"""Sampled static ground-support routes for the ORIGINAL 26-link baseline.

Six separate bearing stubs rise half a layer to rigid planar support arms.
Each arm routes between swept moving pins to an exterior frame post.
No original moving trajectory or rod layer changes. This is not CAD, a
continuous-motion collision certificate, or a stiffness/joint-body analysis.
"""
from collections import deque
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import label
from scipy.spatial import cKDTree

from explore import FIXED, IX
from support_layer_audit import INCIDENT, RODS, SOURCE
from verify import old

OUT = Path(__file__).resolve().parent
GRID_STEP = .02
PITCH = .1  # At 50 mm nominal pole spacing this is a 5 mm layer pitch.
REQUIRED_CLEARANCE = .04  # Combined centerline-clearance budget, not actual part radii.


def segment_distance(points, a, b):
    ab = b-a
    t = np.clip((points-a) @ ab / (ab @ ab), 0, 1)
    return np.linalg.norm(points-a-t[:, None]*ab, axis=1)


def shortest_path(free, start):
    ny, nx = free.shape
    queue = deque([start])
    previous = {start: None}
    target = None
    while queue:
        cell = queue.popleft()
        iy, ix = cell
        if iy in (0, ny-1) or ix in (0, nx-1):
            target = cell
            break
        for nxt in ((iy-1, ix), (iy+1, ix), (iy, ix-1), (iy, ix+1)):
            if free[nxt] and nxt not in previous:
                previous[nxt] = cell
                queue.append(nxt)
    if target is None:
        return None
    path = []
    while target is not None:
        path.append(target)
        target = previous[target]
    return path[::-1]


def main():
    design = old()
    design.track(900)
    pts = design.points(np.concatenate(design.tracks).reshape(-1))
    layers = next(c["rod_layer_order"] for c in
                  json.loads((OUT/"layers_0.040.json").read_text())
                  if c["name"] == "real_negative")
    moving = [j for j in IX if j not in FIXED]
    spans = {j: (min(layers[h] for h in INCIDENT[j]),
                 max(layers[h] for h in INCIDENT[j])) for j in moving}
    low = np.floor((pts.min(axis=(0, 1))-.4)/GRID_STEP)*GRID_STEP
    high = np.ceil((pts.max(axis=(0, 1))+.4)/GRID_STEP)*GRID_STEP
    xs = np.arange(low[0], high[0]+GRID_STEP/2, GRID_STEP)
    ys = np.arange(low[1], high[1]+GRID_STEP/2, GRID_STEP)
    xx, yy = np.meshgrid(xs, ys)
    grid = np.c_[xx.ravel(), yy.ravel()]
    results = []
    for anchor in FIXED:
        for rod in INCIDENT[anchor]:
            z = layers[rod]+.5
            at = pts[0, IX[anchor]].copy()
            cell = tuple(np.rint((at-low)/GRID_STEP).astype(int)[::-1])
            crossing = [j for j in moving if spans[j][0] < z < spans[j][1]]
            obs = np.concatenate([pts[:, IX[j]] for j in crossing])
            distance = cKDTree(obs).query(grid, workers=1)[0].reshape(xx.shape)

            def reaches_outside(radius):
                labels, _ = label(distance > radius)
                value = labels[cell]
                edges = np.r_[labels[0], labels[-1], labels[:, 0], labels[:, -1]]
                return bool(value and value in edges)

            lower, upper = 0., float(distance[cell])
            for _ in range(14):
                middle = (lower+upper)/2
                if reaches_outside(middle):
                    lower = middle
                else:
                    upper = middle
            grid_radius = min(.16, .80*lower)
            required = grid_radius-GRID_STEP*.75
            assert required > REQUIRED_CLEARANCE, (anchor, rod, lower)
            raw_cells = shortest_path(distance > grid_radius, cell)
            assert raw_cells is not None
            path = np.array([[xs[x], ys[y]] for y, x in raw_cells])
            path[0] = at
            simplified = [path[0]]
            i = 0
            while i < len(path)-1:
                for k in range(len(path)-1, i, -1):
                    if np.min(segment_distance(obs, path[i], path[k])) >= required:
                        simplified.append(path[k]); i = k
                        break
                else:
                    raise RuntimeError("No verified segment")
            polyline = np.array(simplified)
            min_planar, min_3d, min_stub = np.inf, np.inf, np.inf
            closest_planar, closest_3d, closest_stub = None, None, None
            for j in moving:
                xy_dist = min(float(np.min(segment_distance(pts[:, IX[j]], a, b)))
                              for a, b in zip(polyline[:-1], polyline[1:]))
                lo, hi = spans[j]
                dz = max(lo-z, z-hi, 0.)*PITCH
                dist_3d = float(np.hypot(xy_dist, dz))
                if j in crossing and xy_dist < min_planar:
                    min_planar, closest_planar = xy_dist, j
                if dist_3d < min_3d:
                    min_3d, closest_3d = dist_3d, j
                stub_gap = max(lo-z, layers[rod]-hi, 0.)*PITCH
                stub_xy = float(np.min(np.linalg.norm(pts[:, IX[j]]-at, axis=1)))
                stub_dist = float(np.hypot(stub_xy, stub_gap))
                if stub_dist < min_stub:
                    min_stub, closest_stub = stub_dist, j
            endpoint = polyline[-1]
            post_min = np.inf
            for a_name, *_, b_name in RODS:
                a, b = pts[:, IX[a_name]], pts[:, IX[b_name]]
                ab = b-a
                t = np.clip(np.sum((endpoint-a)*ab, axis=1)/np.sum(ab*ab, axis=1), 0, 1)
                post_min = min(post_min, float(np.min(np.linalg.norm(endpoint-a-t[:, None]*ab, axis=1))))
            assert min_3d > REQUIRED_CLEARANCE and min_stub > REQUIRED_CLEARANCE
            assert post_min > REQUIRED_CLEARANCE
            result = {
                "anchor": anchor, "fixed_rod_index": rod, "fixed_rod_layer": layers[rod],
                "support_arm_layer": z, "bearing_stub_layer_interval": [layers[rod], z],
                "arm_polyline_xy": polyline.tolist(), "outside_post_xy": endpoint.tolist(),
                "crossing_pin_joints": crossing,
                "grid_bottleneck_bracket": [lower, upper],
                "minimum_sampled_arm_planar_distance_to_crossing_pins": min_planar,
                "closest_planar_pin": closest_planar,
                "minimum_sampled_arm_3d_distance_to_all_moving_pins": min_3d,
                "closest_3d_pin": closest_3d,
                "minimum_sampled_bearing_stub_distance_to_all_moving_pins": min_stub,
                "closest_stub_pin": closest_stub,
                "arm_to_all_rod_centerlines_vertical_lower_bound": PITCH/2,
                "stub_to_nonattached_rod_centerlines_vertical_lower_bound": PITCH/2,
                "minimum_sampled_outside_post_distance_to_all_rods": post_min,
                "arm_length": float(np.linalg.norm(np.diff(polyline, axis=0), axis=1).sum()),
            }
            results.append(result)
            print(json.dumps(result), flush=True)
    near = next(c for c in json.loads(SOURCE.read_text()) if c["name"] == "real_negative")
    output = {
        "baseline": "original real_negative, K=-.6, L=1, S=sqrt(1.6), arm=2.3958349462896438",
        "source_near_pairs_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "sampled_configurations": len(pts), "rod_layer_order": layers,
        "layer_pitch_in_nominal_pole_spacing_units": PITCH,
        "required_combined_centerline_clearance": REQUIRED_CLEARANCE,
        "outside_support_frame_rectangle": [low.tolist(), high.tolist()],
        "fixed_anchor_near_pairs": [c for c in near["near_pairs"] if c["joint"] in FIXED],
        "results": results,
        "limitations": "Only sampled original nominal trajectories. No manufactured errors, continuous-time bound, moving pin/pin check, joint bodies, bearing collars, fasteners, input D1 support, stiffness, forces, friction or CAD. The .04 distance is a combined centerline budget; selecting actual parts must respect it.",
    }
    (OUT/"routed_support_rescue_0.040.json").write_text(json.dumps(output, indent=2))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 3, figsize=(15, 9))
        for ax, result in zip(axes.ravel(), results):
            for j in result["crossing_pin_joints"]:
                ax.scatter(pts[:, IX[j], 0], pts[:, IX[j], 1], s=.25, alpha=.3, color="#567a93")
            polyline = np.array(result["arm_polyline_xy"])
            ax.plot(polyline[:, 0], polyline[:, 1], "o-", color="#c85f21", lw=2, ms=3)
            ax.scatter(*polyline[0], color="#192d44", s=35, zorder=5)
            ax.set_title(f"{result['anchor']} / rod {result['fixed_rod_index']}, support z={result['support_arm_layer']}\nplanar pin clearance {result['minimum_sampled_arm_planar_distance_to_crossing_pins']:.3f}")
            ax.set_xlim(low[0]-.1, high[0]+.1); ax.set_ylim(low[1]-.1, high[1]+.1)
            ax.set_aspect("equal"); ax.grid(alpha=.2)
        fig.suptitle("Original 26-link baseline: stationary support arms between moving layers\nBlue: sampled moving pins crossing that height. Orange: verified support centerline.")
        fig.tight_layout()
        fig.savefig(OUT/"routed_support_rescue.png", dpi=150)
    except ImportError:
        pass


if __name__ == "__main__":
    main()
