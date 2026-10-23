"""Q20b: fixed finite-budget basin maps. All writes stay beside this file."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
os.environ["MPLCONFIGDIR"] = str(OUT / "mplconfig")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "jssa/difficulty"))

import numpy as np
from mpmath import mp
from geosolver import GeometryProblem
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.snapshots import evaluation_session, numerical_snapshot
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search import scipy_multistart_backend as smb
from probe_basins import answer_float
from ghost_scan import point_names

CASES = [
    ("AIME-2025-I-06", {"A": "D", "D": "A", "B": "C", "C": "B"}),
    ("HMMT-2022-FEB-GEO-05", {"B": "C", "C": "B"}),
    ("HMMT-2025-FEB-GEO-05", {"B": "C", "C": "B"}),
    ("AIME-2025-I-02", {}),
]
N = 32
CAPS = [80, 320]


def clean(obj):
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, np.ndarray)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.generic):
        return clean(obj.item())
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def save(name, obj):
    path = OUT / name
    assert path.resolve().is_relative_to(OUT)
    path.write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def src_hash():
    h = hashlib.sha256()
    paths = sorted((ROOT / "src").rglob("*.py"))
    for p in paths:
        h.update(str(p.relative_to(ROOT)).encode() + b"\0" + p.read_bytes() + b"\0")
    return {"n_files": len(paths), "sha256": h.hexdigest()}


def build(dsl):
    bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
    return bundle, build_ir_evaluator(bundle)


def figure(ev, x, names):
    # Same read-only float snapshot API used in Q9, not a new DSL translator.
    with mp.workprec(53), evaluation_session(ev):
        snap = numerical_snapshot(ev.bundle.spec, ev.bundle.var_names, list(map(float, x)),
                                  ev.bundle.base_context, arithmetic="float")
        ctx = snap.for_expressions(names, partial=True)
        return np.array([[float(ctx[name].x), float(ctx[name].y)] for name in names])


def distance_matrix(p):
    return np.linalg.norm(p[:, None, :] - p[None, :, :], axis=2)


def cluster_old(records, width):
    groups = []
    for r in records:
        if r.get("cls") != "hit":
            continue
        x = np.asarray(r["x"])
        close = [i for i, g in enumerate(groups)
                 if np.max(np.abs((x - g[0]["x"]) / width)) <= 1e-5]
        if close:
            groups[close[0]].append(r)
        else:
            groups.append([r])
    groups.sort(key=lambda g: tuple(g[0]["x"]))
    return [{"center": g[0]["x"], "size": len(g), "answer": g[0]["ans"],
             "max_center_distance": max(float(np.max(np.abs((np.asarray(r["x"]) - g[0]["x"]) / width))) for r in g)}
            for g in groups]


def prepare():
    if (OUT / "registration-lock.json").exists():
        raise RuntimeError("already prepared; do not replace a frozen registration")
    cases = {c["id"]: c for c in map(json.loads, (ROOT / "benchmarks/cases.jsonl").open())}
    human = {r["case_id"]: r["human"] for r in csv.DictReader((ROOT / "jssa/difficulty/ghost-1023/human_feat.csv").open())}
    inputs = []
    for cid, perm in CASES:
        raw_path = ROOT / f"jssa/difficulty/minima/raw-323/{cid}.json"
        raw = json.loads(raw_path.read_text())
        dsl = cases[cid]["dsl"]
        b, ev = build(dsl)
        box = np.asarray(infer_problem_bounds(b))
        assert len(b.var_names) == 2 and len(b.spec.constraints) >= 2
        assert np.array_equal(box, np.asarray(raw["box"]))
        roots = cluster_old(raw["records"], box[:, 1] - box[:, 0])
        assert len(roots) == 2, (cid, roots)
        names = point_names(dsl)
        ps = [figure(ev, r["center"], names) for r in roots]
        ds = [distance_matrix(p) for p in ps]
        scale = max(np.max(d) for d in ds)
        idx = [names.index(perm.get(n, n)) for n in names]
        label_error = float(np.max(np.abs(ds[0] - ds[1])) / scale)
        perm_error = float(np.max(np.abs(ds[0] - ds[1][np.ix_(idx, idx)])) / scale)
        expected_symmetry = bool(perm)
        assert (perm_error < 1e-7) == expected_symmetry, (cid, perm_error)
        assert abs(roots[0]["answer"] - roots[1]["answer"]) <= 1e-6 * max(1, abs(roots[0]["answer"]))
        item = {"id": cid, "dsl": dsl, "var_names": list(b.var_names), "box": box,
                "roots": roots, "references": raw["references"], "old_counts": raw["counts"],
                "old_p": raw["p_any"], "human": human.get(cid), "first_hit": raw["first_hit"],
                "point_names": names, "root_figures": ps, "permutation": perm,
                "labelled_distance_error": label_error, "permuted_distance_error": perm_error,
                "main": expected_symmetry, "old_sha256": sha(raw_path),
                "replay": raw["records"][:5]}
        inputs.append(item)
        print(cid, "roots", [r["size"] for r in roots], "label/permuted errors", label_error, perm_error, flush=True)
    save("inputs.json", inputs)
    basins = list(csv.DictReader((ROOT / "jssa/difficulty/minima/basins-323.csv").open()))
    save("old-census.json", {"rows": len(basins), "multiple_coordinate_basins": sum(int(r.get("n_correct_basins") or 0) > 1 for r in basins),
                              "meaning": "The inherited column counts endpoint clusters, not verified attractors or fractal basins."})
    import scipy
    save("registration-lock.json", {"utc": datetime.now(timezone.utc).isoformat(), "src": src_hash(),
         "files": {n: sha(OUT / n) for n in ("preregistration.md", "experiment.py", "inputs.json")},
         "python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
         "grid_n": N, "caps": CAPS, "time_limit_sec": 3600, "per_start_sec": 3})


class TimeLimit(BaseException):
    pass


@contextmanager
def alarm(seconds):
    old = signal.getsignal(signal.SIGALRM)
    def expired(_sig, _frame):
        raise TimeLimit()
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def labels(rec, inp):
    if rec.get("cls") != "hit":
        return {"X": "F", "G": "F", "T": "F"}
    width = np.diff(np.asarray(inp["box"]), axis=1).ravel()
    distances = [float(np.max(np.abs((np.asarray(rec["x"]) - r["center"]) / width))) for r in inp["roots"]]
    nearest = int(np.argmin(distances))
    if distances[nearest] > 1e-5:
        return {"X": "U", "G": "U", "T": "T0"}
    return {"X": f"R{nearest}", "G": "G0" if inp["main"] else f"G{nearest}", "T": "T0"}


def run_one(inp, b, ev, start, cap, index, deadline):
    telemetry = smb._SearchTelemetry()
    config = ExternalPipelineConfig.production_baseline_tier(seed=20261023, total_time_budget_sec=180.0).search
    status = {}
    native = smb.least_squares
    native_cap = smb._LM_MAX_NFEV
    def capture(*args, **kwargs):
        result = native(*args, **kwargs)
        status.update({"status": int(result.status), "nfev_scipy": int(result.nfev),
                       "optimality": float(result.optimality)})
        return result
    smb.least_squares = capture
    smb._LM_MAX_NFEV = cap
    t0 = time.monotonic()
    rec = {"k": index, "cap": cap, "start": list(map(float, start))}
    try:
        with alarm(min(3.0, max(0.001, deadline - t0))):
            cand = smb._collect_local_start_record(bundle=b, evaluator=ev,
                bounds=[tuple(z) for z in inp["box"]], config=config, seed=20261023,
                start_index=index, start=np.asarray(start), deadline_monotonic=min(deadline, t0 + 3), telemetry=telemetry)
            if cand is None:
                rec["cls"] = "error"
            else:
                rec["x"] = list(cand.x_float)
                rec["res"] = cand.residual_norm_float
                if "out_of_bounds" in tuple(cand.hard_violation_tags):
                    rec["cls"] = "left_box"
                elif not math.isfinite(cand.residual_norm_float):
                    rec["cls"] = "error"
                elif cand.residual_norm_float > 1e-8:
                    rec["cls"] = "stuck"
                elif not (bool(cand.guard_ok) and cand.hard_feasible is not False):
                    rec["cls"] = "wrong_branch"
                else:
                    value = answer_float(ev, cand.x_float)
                    rec["ans"] = value
                    matches = [i for i, r in enumerate(inp["references"])
                               if value is not None and abs(value-r) <= 1e-6 * max(1.0, abs(r))]
                    rec["cls"] = "hit" if matches else "wrong_answer"
                    if matches:
                        rec["ref"] = matches[0]
    except (TimeLimit, smb._SearchDeadlineExceeded, TimeoutError):
        rec["cls"] = "timeout"
    except Exception as exc:
        rec["cls"] = "error"
        rec["error"] = type(exc).__name__ + ": " + str(exc)[:200]
    finally:
        smb.least_squares = native
        smb._LM_MAX_NFEV = native_cap
    rec.update(status)
    rec.update(labels(rec, inp))
    rec["sec"] = time.monotonic() - t0
    rec["evaluations"] = telemetry.evaluation_count
    return clean(rec)


def check_lock():
    lock = json.loads((OUT / "registration-lock.json").read_text())
    assert all(sha(OUT / n) == h for n, h in lock["files"].items()), "frozen file changed"
    assert src_hash() == lock["src"], "src changed"
    return lock


def run():
    check_lock()
    if (OUT / "raw").exists():
        raise RuntimeError("raw already exists; do not silently recompute")
    (OUT / "raw").mkdir()
    inputs = json.loads((OUT / "inputs.json").read_text())
    t0 = time.monotonic()
    deadline = t0 + 3600
    replay = []
    for inp in inputs:
        b, ev = build(inp["dsl"])
        for old in inp["replay"]:
            new = run_one(inp, b, ev, old["start"], 80, old["k"], deadline)
            dx = max(abs(a-b) for a, b in zip(old.get("x", []), new.get("x", []))) if new.get("x") else None
            replay.append({"id": inp["id"], "old": old, "new": new, "same_class": old["cls"] == new["cls"], "max_abs_x_difference": dx})
    save("replay.json", replay)
    print("replay", sum(r["same_class"] for r in replay), "/", len(replay), flush=True)
    progress = []
    for inp in inputs:
        b, ev = build(inp["dsl"])
        box = np.asarray(inp["box"])
        # Interleave budgets by row to reduce unrelated time drift.
        handles = {cap: (OUT / "raw" / f"{inp['id']}-K{cap}.jsonl").open("w") for cap in CAPS}
        counts = {cap: Counter() for cap in CAPS}
        try:
            for j in range(N):
                for cap in CAPS:
                    for i in range(N):
                        if time.monotonic() >= deadline:
                            raise TimeLimit()
                        z = np.array([(i + 0.37) / N, (j + 0.61) / N])
                        start = box[:, 0] + z * (box[:, 1] - box[:, 0])
                        rec = run_one(inp, b, ev, start, cap, j*N+i, deadline)
                        rec.update({"i": i, "j": j, "normalized_start": z.tolist()})
                        handles[cap].write(json.dumps(rec, ensure_ascii=False, allow_nan=False) + "\n")
                        counts[cap][rec["cls"]] += 1
                    handles[cap].flush()
                if (j+1) % 8 == 0:
                    print(inp["id"], "rows", j+1, "counts", dict(counts[80]), dict(counts[320]), "elapsed", round(time.monotonic()-t0, 1), flush=True)
        except TimeLimit:
            print("global deadline", flush=True)
        finally:
            for h in handles.values():
                h.close()
        progress.append({"id": inp["id"], "counts": counts})
        save("run-status.json", {"elapsed": time.monotonic()-t0, "progress": progress, "complete": False})
        if time.monotonic() >= deadline:
            break
    save("run-status.json", {"elapsed": time.monotonic()-t0, "progress": progress,
         "complete": len(progress) == len(inputs) and all(sum(c.values()) == N*N for p in progress for c in p["counts"].values())})
    check_lock()


def read_records(cid, cap):
    path = OUT / "raw" / f"{cid}-K{cap}.jsonl"
    return [json.loads(line) for line in path.open()] if path.exists() else []


def curve(grid):
    out = []
    for stride in (1, 2, 4, 8):
        a = np.concatenate((grid[:, :-stride].ravel(), grid[:-stride, :].ravel()))
        b = np.concatenate((grid[:, stride:].ravel(), grid[stride:, :].ravel()))
        changes = int(np.sum(a != b))
        out.append({"stride": stride, "epsilon": stride / N, "pairs": len(a), "changes": changes, "U": changes / len(a)})
    if out[0]["changes"] < 20 or any(r["changes"] == 0 for r in out):
        return out, None
    alpha = float(np.polyfit(np.log([r["epsilon"] for r in out]), np.log([r["U"] for r in out]), 1)[0])
    return out, alpha


def analyze():
    check_lock()
    inputs = json.loads((OUT / "inputs.json").read_text())
    metrics = []
    checks = []
    for inp in inputs:
        item = {"id": inp["id"], "main": inp["main"], "caps": {}}
        grids = {}
        for cap in CAPS:
            rows = read_records(inp["id"], cap)
            if len(rows) != N*N or len({r["k"] for r in rows}) != N*N:
                item["caps"][str(cap)] = {"incomplete": True, "n": len(rows)}
                continue
            assert all(r["k"] == r["j"] * N + r["i"] for r in rows)
            # Recompute labels from saved coordinates, never trust stored labels alone.
            assert all(labels(r, inp) == {key: r[key] for key in ("X", "G", "T")} for r in rows)
            ls = {}
            grids[cap] = {}
            for label in ("X", "G", "T"):
                grid = np.empty((N, N), dtype="U8")
                for r in rows:
                    grid[r["j"], r["i"]] = r[label]
                grids[cap][label] = grid
                c, alpha = curve(grid)
                ls[label] = {"curve": c, "alpha_finite_scale": alpha}
            ratios = [1 - g["changes"]/x["changes"] if x["changes"] else None
                      for x, g in zip(ls["X"]["curve"], ls["G"]["curve"])]
            item["caps"][str(cap)] = {"n": len(rows), "counts": dict(Counter(r["cls"] for r in rows)),
                "branch_counts": dict(Counter(r["X"] for r in rows)), "cap_stops": sum(r.get("status") == 0 for r in rows),
                "unknown_fraction": sum(r["X"] == "U" for r in rows)/len(rows),
                "seconds": sum(r["sec"] for r in rows), "labels": ls, "removed_fraction_by_symmetry": ratios}
            for k in range(4):
                assert ls["T"]["curve"][k]["changes"] <= ls["G"]["curve"][k]["changes"] <= ls["X"]["curve"][k]["changes"]
        if len(grids) == 2:
            caps = item["caps"]
            q1 = all(caps[str(k)]["removed_fraction_by_symmetry"][s] is not None and caps[str(k)]["removed_fraction_by_symmetry"][s] >= .5 for k in CAPS for s in (0,1))
            q2 = all(caps[str(k)]["labels"]["X"]["alpha_finite_scale"] is not None and caps[str(k)]["labels"]["X"]["alpha_finite_scale"] <= .7 and caps[str(k)]["labels"]["T"]["alpha_finite_scale"] is not None and caps[str(k)]["labels"]["T"]["alpha_finite_scale"] >= .9 for k in CAPS)
            changed = int(np.sum(grids[80]["X"] != grids[320]["X"]))
            q3 = changed/(N*N) <= .02 and all(caps[str(k)]["unknown_fraction"] <= .01 and caps[str(k)]["counts"].get("timeout", 0) == 0 for k in CAPS)
            item.update({"K_label_disagreements": changed, "K_label_disagreement_fraction": changed/(N*N), "Q1": q1, "Q2": q2, "Q3": q3, "pass": q1 and q2 and q3})
        else:
            item.update({"Q1": None, "Q2": None, "Q3": None, "pass": False})
        metrics.append(item)
        print(inp["id"], "Q", item["Q1"], item["Q2"], item["Q3"], "K disagreements", item.get("K_label_disagreements"), flush=True)
    passed = sum(m["pass"] for m in metrics if m["main"])
    save("summary.json", {"metrics": metrics, "main_passed": passed, "main_total": 3,
                          "continuation_supported": passed >= 2, "note": "Finite-grid descriptive counts; no fractal or Wada certification."})
    fields = ["id", "main", "cap", "label", "stride", "epsilon", "pairs", "changes", "U", "alpha_finite_scale"]
    with (OUT / "uncertainty.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for m in metrics:
            for cap, c in m["caps"].items():
                for label, data in c.get("labels", {}).items():
                    for row in data["curve"]:
                        w.writerow({"id": m["id"], "main": m["main"], "cap": cap, "label": label, **row, "alpha_finite_scale": data["alpha_finite_scale"]})
    save("verification.json", {"frozen_hashes_match": True, "source_hash_match": True, "grid_and_label_checks_pass": True,
         "source": src_hash(), "largest_output_bytes": max(p.stat().st_size for p in OUT.rglob("*") if p.is_file())})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prepare", "run", "analyze"])
    action = ap.parse_args().action
    {"prepare": prepare, "run": run, "analyze": analyze}[action]()
