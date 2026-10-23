"""Q1 preregistered all-start paired experiment. All writes stay in HERE."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import resource
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
G = ROOT / "jssa/strategy/astra-consult-17/G"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(G))
from common import case_context, classify, clean, reference_values, smb, ExternalPipelineConfig
from mechanism import NativeTrace
from g2 import DistancePenalty, boolean_kinds
import numpy as np
import scipy
from scipy.optimize import _minpack

ARMS = ("B", "N", "G2")
EXPECTED_PREREG = "f4a72cadf217c76c47b1466cdcaf1adf36696f3449feef7182e3f6b0e05586ac"


def stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, obj):
    # Replace atomically; both temporary and destination files are in HERE.
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def init_worker():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2, 16 * 1024**2))


def has_ne(g):
    return g.operator == "!=" or any(has_ne(child) for child in g.children)


def prepare_case(item):
    index, cid = item
    case, bundle, ev, raw, bounds, lo, width = case_context(cid)
    counts = Counter()
    starts = []
    diagnostics = Counter()
    for r in raw["records"]:
        if "start" not in r:
            starts.append({"k": r["k"], "F": None, "diagnostic": False, "missing_start": True})
            counts["missing_start"] += 1
            continue
        try:
            h = ev.evaluate_float_hard_feasibility(r["start"], include_margins=False)
            F = bool(h.hard_feasible)
        except Exception as ex:
            F = None
            counts["F_error:" + type(ex).__name__] += 1
        is_diagnostic = F is not None and diagnostics[F] < 10
        if is_diagnostic:
            diagnostics[F] += 1
        starts.append({"k": r["k"], "F": F, "diagnostic": is_diagnostic})
        counts[str(F)] += 1
    old_wrong = sum(r["cls"] in ("wrong_branch", "wrong_answer") for r in raw["records"])
    risk_reasons = []
    if old_wrong / len(raw["records"]) >= 0.10:
        risk_reasons.append("old_wrong_branch_or_answer_ge_0.10")
    if any(has_ne(g) for g in ev.compiled_guards):
        risk_reasons.append("guard_ne")
    if any(c.kind in ("intersection_exclude_distinct", "intersection_selection_trace") for c in bundle.hard_feasibility_checks):
        risk_reasons.append("intersection_branch")
    return {"id": cid, "index": index, "n_vars": len(bounds),
            "n_constraints": len(bundle.spec.constraints),
            "method": "Powell" if len(bounds) > len(bundle.spec.constraints) else "LM",
            "n": len(starts), "starts_requested": raw.get("starts_requested"),
            "old_seconds": sum(r.get("sec", 0) for r in raw["records"]),
            "raw_sha256": sha(ROOT / "jssa/difficulty/minima/raw-323" / (cid + ".json")),
            "case_sha256": hashlib.sha256(json.dumps(case, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            "risk": bool(risk_reasons), "risk_reasons": risk_reasons,
            "counts": dict(counts), "guard_kinds": dict(Counter(g.kind for g in ev.compiled_guards)),
            "boolean_kinds": dict(Counter(k for g in ev.compiled_guards for k in boolean_kinds(g))),
            "hard_kinds": dict(Counter(c.kind for c in bundle.hard_feasibility_checks)),
            "starts": starts}


def prepare():
    assert sha(HERE / "preregistration.md") == EXPECTED_PREREG
    assert not (HERE / "manifest.json").exists(), "Manifest already fixed; do not replace it"
    ids, excluded = [], []
    for path in sorted((ROOT / "jssa/difficulty/minima/raw-323").glob("*.json")):
        raw = json.loads(path.read_text())
        if raw.get("n_vars", 0) and raw.get("records"):
            ids.append(path.stem)
        else:
            excluded.append({"id": path.stem, "n_vars": raw.get("n_vars"), "status": raw.get("status")})
    rows = []
    with ProcessPoolExecutor(max_workers=4, initializer=init_worker) as pool:
        for row in pool.map(prepare_case, enumerate(ids)):
            rows.append(row)
    manifest = {"fixed_utc": stamp(), "preregistration_sha256": EXPECTED_PREREG,
                "python": sys.executable, "numpy": np.__version__, "scipy": scipy.__version__,
                "max_workers": 4, "blas_threads": 1, "start_seconds": 10,
                "excluded": excluded, "problems": rows}
    write_json(HERE / "manifest.json", manifest)
    print(json.dumps({"prepared": len(rows), "starts": sum(r["n"] for r in rows),
                      "diagnostic": sum(s["diagnostic"] for r in rows for s in r["starts"]),
                      "risk": sum(r["risk"] for r in rows),
                      "methods": dict(Counter(r["method"] for r in rows)),
                      "excluded": len(excluded)}), flush=True)


def solve(context, start, k, arm, diagnostic, refs, config):
    case, bundle, ev, raw, bounds, lo, width = context
    trace = NativeTrace(ev, width, arm) if diagnostic and len(bounds) <= len(bundle.spec.constraints) else None
    orig_lmder = _minpack._lmder
    orig_hard = smb._evaluate_hard_feasibility_penalty
    orig_ls = smb.least_squares
    orig_min = smb.minimize
    status = {}
    g2 = DistancePenalty(ev) if arm == "G2" else None

    def traced_lmder(*args, **kwargs):
        assert not kwargs and len(args) == 12
        args = list(args)
        args[0] = trace.wrap_fun(args[0])
        args[1] = trace.wrap_jac(args[1])
        if arm == "S":
            args[6] = args[8] = 0.0
        ans = orig_lmder(*args)
        trace.finish(ans)
        if ans[2] in (6, 7, 8):
            status["raw_info_remapped"] = int(ans[2])
            return ans[0], ans[1], {6: 1, 7: 2, 8: 4}[ans[2]]
        return ans

    def logged_ls(*args, **kwargs):
        try:
            ans = orig_ls(*args, **kwargs)
        except Exception as exc:
            status["exception"] = repr(exc)
            raise
        status.update(status=int(ans.status), message=str(ans.message), nfev=int(ans.nfev),
                      cost=float(ans.cost), optimality=float(ans.optimality))
        return ans

    def logged_min(*args, **kwargs):
        try:
            ans = orig_min(*args, **kwargs)
        except Exception as exc:
            status["exception"] = repr(exc)
            raise
        status.update(status=int(ans.status), message=str(ans.message), nfev=int(ans.nfev),
                      cost=float(ans.fun), nit=int(ans.nit))
        return ans

    if trace is not None:
        _minpack._lmder = traced_lmder
    smb.least_squares = logged_ls
    smb.minimize = logged_min
    if arm == "N":
        smb._evaluate_hard_feasibility_penalty = lambda **kwargs: 0.0
    elif arm == "G2":
        smb._evaluate_hard_feasibility_penalty = g2
    telemetry = smb._SearchTelemetry()
    t0 = time.monotonic()
    try:
        cand = smb._collect_local_start_record(
            bundle=bundle, evaluator=ev, bounds=bounds, config=config,
            seed=0, start_index=k, start=np.asarray(start, dtype=float),
            deadline_monotonic=t0 + 10.0, telemetry=telemetry)
        result = classify(ev, cand, refs)
    except (smb._SearchDeadlineExceeded, TimeoutError):
        result = {"cls": "timeout"}
    except Exception as exc:
        result = {"cls": "error", "exception": repr(exc)}
    finally:
        _minpack._lmder = orig_lmder
        smb.least_squares = orig_ls
        smb.minimize = orig_min
        smb._evaluate_hard_feasibility_penalty = orig_hard
    result.update(seconds=time.monotonic() - t0, evaluations=telemetry.evaluation_count,
                  optimizer=status)
    if trace is not None:
        result["native"] = trace.summary()
        # Both conditions must be on the SAME trial; marginal counts do not suffice.
        result["native"]["wall_reject_joint"] = sum(
            t["decision"] == "rejected" and t["base"].get("F") and not t["F"]
            and t["hard"]**2 > t["base"].get("hard", math.inf)**2
            and t["eq_ss"] + t["guard"]**2 < t["base"].get("eq_ss", -math.inf) + t["base"].get("guard", 0)**2
            for t in trace.trials)
    if g2 is not None:
        result["g2"] = dict(g2.counts)
    return clean(result)


def run_case(meta):
    cid = meta["id"]
    path = HERE / "records" / (cid + ".jsonl")
    summary_path = HERE / "case-summary" / (cid + ".json")
    if summary_path.exists():
        return json.loads(summary_path.read_text())
    t0 = time.monotonic()
    try:
        context = case_context(cid)
        case, bundle, ev, raw, bounds, lo, width = context
        assert sha(ROOT / "jssa/difficulty/minima/raw-323" / (cid + ".json")) == meta["raw_sha256"]
        assert hashlib.sha256(json.dumps(case, sort_keys=True, ensure_ascii=False).encode()).hexdigest() == meta["case_sha256"]
        refs = reference_values(case["answer"])
        config = ExternalPipelineConfig.production_baseline_tier(seed=0, total_time_budget_sec=180.0).search
        done = {}
        if path.exists():
            for line in path.read_text().splitlines():
                r = json.loads(line)
                done[r["k"]] = r
        saved = {r["k"]: r for r in raw["records"]}
        with path.open("a", buffering=1) as f:
            for spec in meta["starts"]:
                k = spec["k"]
                if k in done:
                    continue
                old = saved[k]
                rec = {"k": k, "F": spec["F"], "diagnostic": spec["diagnostic"],
                       "start": old.get("start"), "old_cls": old["cls"]}
                order = (meta["index"] + k) % 3
                arms = ARMS[order:] + ARMS[:order]
                if spec["diagnostic"] and meta["method"] == "LM":
                    arms += ("S",)
                rec["order"] = arms
                for arm in arms:
                    rec[arm] = ({"cls": "missing_start"} if "start" not in old else
                                solve(context, old["start"], k, arm, spec["diagnostic"], refs, config))
                f.write(json.dumps(clean(rec), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
                done[k] = rec
        rows = list(done.values())
        out = {"id": cid, "n": len(rows), "method": meta["method"], "seconds": time.monotonic()-t0,
               "counts": {a: dict(Counter(r[a]["cls"] for r in rows)) for a in ARMS},
               "B_old_disagree": sum(r["B"]["cls"] != r["old_cls"] for r in rows),
               "completed_utc": stamp()}
    except Exception as exc:
        out = {"id": cid, "case_error": repr(exc), "traceback": traceback.format_exc(),
               "seconds": time.monotonic()-t0, "completed_utc": stamp()}
    write_json(summary_path, out)
    return out


def freeze_implementation():
    inputs = list((ROOT / "src").rglob("*.py"))
    inputs += [G / n for n in ("common.py", "mechanism.py")]
    inputs += [ROOT / p for p in ("jssa/difficulty/probe_basins.py", "benchmarks/cases.jsonl",
               "jssa/difficulty/ghost-1023/human_feat.csv", "jssa/difficulty/start-feasibility-1023/per-problem.csv")]
    inputs += [HERE / n for n in ("run.py", "g2.py", "preregistration.md", "manifest.json")]
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(inputs))}


def run():
    assert sha(HERE / "preregistration.md") == EXPECTED_PREREG
    manifest = json.loads((HERE / "manifest.json").read_text())
    fixed_path = HERE / "execution-freeze.json"
    hashes = freeze_implementation()
    if fixed_path.exists():
        assert json.loads(fixed_path.read_text())["sha256"] == hashes, "Frozen execution inputs changed"
    else:
        write_json(fixed_path, {"started_utc": stamp(), "sha256": hashes, "python": sys.executable,
                               "numpy": np.__version__, "scipy": scipy.__version__})
    (HERE / "records").mkdir(exist_ok=True)
    (HERE / "case-summary").mkdir(exist_ok=True)
    completed = []
    # Long historical cases first; all starts and the within-start arm order remain fixed.
    ordered = sorted(manifest["problems"], key=lambda r: (-r["old_seconds"], r["id"]))
    with ProcessPoolExecutor(max_workers=4, initializer=init_worker) as pool:
        futures = {pool.submit(run_case, meta): meta["id"] for meta in ordered}
        for future in as_completed(futures):
            row = future.result()
            completed.append(row)
            write_json(HERE / "progress.json", {"updated_utc": stamp(), "completed": len(completed),
                                                "total": len(ordered), "cases": completed})
            print(json.dumps({"completed": len(completed), **row}, ensure_ascii=False), flush=True)
    write_json(HERE / "run-complete.json", {"completed_utc": stamp(), "cases": len(completed),
                                           "case_errors": sum("case_error" in r for r in completed)})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("prepare", "run"))
    args = ap.parse_args()
    if args.stage == "prepare":
        prepare()
    else:
        run()
