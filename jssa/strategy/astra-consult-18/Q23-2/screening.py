"""Fixed Q23-2 screens. Writes only beside this file; never runs a local solver."""
from __future__ import annotations

import argparse
import collections
import datetime
from decimal import Decimal, localcontext
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, obj):
    path = HERE / name
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite {name}")
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def family(cid):
    upper = cid.upper()
    return next((s for s in ("AIME", "HMMT", "JMO") if upper.startswith(s)), "other")


def source_manifest():
    files = sorted((ROOT / "src").rglob("*.py"))
    return {str(p.relative_to(ROOT)): sha(p) for p in files}


def freeze():
    archive = sorted((ROOT / "jssa/difficulty/nomad-wall/runs/B/runs").glob("*/0.json"))
    groups = collections.defaultdict(list)
    for p in sorted((ROOT / "benchmarks/dsl").glob("*.json")):
        data = json.loads(p.read_text())
        cid = data.get("id", p.stem)
        if len(data.get("variables", [])) >= 2 and sum(c.get("operator") == "=" for c in data.get("conditions", [])) >= 2:
            groups[family(cid)].append((cid, p))
    selected = [p for f in ("AIME", "HMMT", "JMO") for cid, p in sorted(groups[f])[:4]]
    result = {
        "created_at": stamp(), "root": str(ROOT),
        "preregistration_sha256": sha(HERE / "preregistration.md"),
        "screening_sha256": sha(Path(__file__)),
        "archive": [{"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha(p)} for p in archive],
        "probe_inputs": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in selected],
        "source_files": source_manifest(),
    }
    write("manifest.json", result)
    print(json.dumps({"archive_files": len(archive), "probe_inputs": [p.stem for p in selected]}), flush=True)


def manifest():
    m = json.loads((HERE / "manifest.json").read_text())
    assert sha(HERE / "preregistration.md") == m["preregistration_sha256"]
    assert sha(Path(__file__)) == m["screening_sha256"]
    return m


def load_archives(m):
    for item in m["archive"]:
        p = ROOT / item["path"]
        assert sha(p) == item["sha256"], p
        j = json.loads(p.read_text())
        sr = j.get("solver_result") or {}
        ps = (sr.get("diagnostics") or {}).get("pipeline_summary") or {}
        yield j.get("case_id", p.parent.name), j, ps


def finite(v):
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError, OverflowError):
        return False


def t1(m):
    started = time.monotonic()
    rows, excluded = [], collections.Counter()
    for cid, j, ps in load_archives(m):
        accepted = set(ps.get("answer_extraction_candidate_ids") or [])
        records = ps.get("exact_candidate_records") or []
        deltas = []
        for r in records:
            c = r.get("candidate") or {}
            if c.get("candidate_id") not in accepted:
                excluded["record_not_in_accepted_ids"] += 1
                continue
            s = c.get("source") or {}
            xf, xh = s.get("x_float"), c.get("x_hp")
            residual = s.get("residual_norm_float")
            if not s.get("guard_ok") or not finite(residual) or float(residual) > 1e-8:
                excluded["source_guard_or_residual_ineligible"] += 1
                continue
            if not isinstance(xf, list) or not isinstance(xh, list) or not xf or len(xf) != len(xh) or not all(finite(x) for x in xf + xh):
                excluded["source_or_hp_coordinates_missing_or_ineligible"] += 1
                continue
            with localcontext() as ctx:
                ctx.prec = 80
                delta = max(abs(Decimal(str(b)) - Decimal(str(a))) / max(Decimal(1), abs(Decimal(str(a)))) for a, b in zip(xf, xh))
            deltas.append({"candidate_uid": c.get("candidate_uid"), "candidate_id": c.get("candidate_id"), "source_residual": float(residual), "relative_movement": float(delta), "large": delta >= Decimal("0.001")})
        rows.append({"case_id": cid, "family": family(cid), "source_hash": j.get("source_hash"), "status": (j.get("solver_result") or {}).get("status"), "exact_record_count": len(records), "eligible_candidate_count": len(deltas), "large_count": sum(d["large"] for d in deltas), "max_movement": max((d["relative_movement"] for d in deltas), default=None), "candidates": deltas})
    eligible = [r for r in rows if r["eligible_candidate_count"]]
    large = [r for r in rows if r["large_count"]]
    summary = {"test": "T1", "completed_at": stamp(), "elapsed_seconds": time.monotonic() - started, "archive_runs": len(rows), "eligible_cases": len(eligible), "eligible_candidates": sum(r["eligible_candidate_count"] for r in rows), "large_movement_cases": len(large), "large_movement_families": sorted({r["family"] for r in large}), "max_movement": max((r["max_movement"] for r in eligible), default=None), "coverage_sufficient": len(eligible) >= 10, "effect_gate": len(large) >= 3 and len({r["family"] for r in large}) >= 2, "excluded_records": dict(excluded)}
    summary["gate_pass"] = summary["coverage_sufficient"] and summary["effect_gate"]
    write("t1.json", {"summary": summary, "rows": rows})
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def t2(m):
    started = time.monotonic()
    from geosolver.problem.models import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
    from geosolver.engine.standard.orchestration.run_initial_probe import run_initial_probe, derive_initial_probe_seeds
    rows = []
    for item in m["probe_inputs"]:
        p = ROOT / item["path"]
        assert sha(p) == item["sha256"]
        doc = json.loads(p.read_text())
        cid = doc["id"]
        row = {"case_id": cid, "family": family(cid), "probes": []}
        try:
            ir = GeometryProblem.model_validate(doc).engine_document()
            bundle = load_problem_bundle(ir)
            bounds = infer_problem_bounds(bundle)
            row["variable_count"] = len(bundle.var_names)
            row["compiled_constraint_count"] = len(bundle.spec.constraints)
            row["bounds"] = bounds
            for external in (501, 502, 503):
                evaluator = build_ir_evaluator(bundle)
                result = run_initial_probe(evaluator=evaluator, bounds=bounds, seeds=derive_initial_probe_seeds(external, count=5), points_per_seed=50)
                nrows = len(bundle.spec.constraints)
                scales = list(result.constraint_scales) if result.constraint_scales is not None else [1.0] * nrows
                if not scales or not all(finite(s) and s > 0 for s in scales):
                    raise ValueError("empty or invalid scale vector")
                gm = math.exp(sum(math.log(s) for s in scales) / len(scales))
                row["probes"].append({"external_seed": external, "seeds": list(derive_initial_probe_seeds(external, count=5)), "scales": result.constraint_scales, "normalized_scales": [s / gm for s in scales], "total_random_points": result.metrics["total_random_points"], "finite_residual_ratio": result.metrics["finite_residual_ratio"], "guard_pass_ratio": result.metrics["guard_pass_ratio"]})
            shapes = {len(p["normalized_scales"]) for p in row["probes"]}
            if len(shapes) != 1:
                raise ValueError("scale-vector length changed")
            ratios = [max(v) / min(v) for v in zip(*(p["normalized_scales"] for p in row["probes"]))]
            row["max_normalized_scale_ratio"] = max(ratios)
            row["unstable"] = max(ratios) >= 4
            row["evaluable"] = True
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            row["evaluable"] = False
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k not in ("probes", "bounds")}, ensure_ascii=False), flush=True)
    eligible = [r for r in rows if r["evaluable"]]
    unstable = [r for r in eligible if r["unstable"]]
    summary = {"test": "T2", "completed_at": stamp(), "elapsed_seconds": time.monotonic() - started, "planned_cases": len(rows), "evaluable_cases": len(eligible), "unstable_cases": len(unstable), "unstable_families": sorted({r["family"] for r in unstable}), "max_normalized_scale_ratio": max((r["max_normalized_scale_ratio"] for r in eligible), default=None), "random_points": sum(p["total_random_points"] for r in rows for p in r["probes"]), "coverage_sufficient": len(eligible) >= 10, "effect_gate": len(unstable) >= 4 and len({r["family"] for r in unstable}) >= 2}
    summary["gate_pass"] = summary["coverage_sufficient"] and summary["effect_gate"]
    write("t2.json", {"summary": summary, "rows": rows})
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def t3(m):
    started = time.monotonic()
    rows = []
    for cid, j, ps in load_archives(m):
        debug = ps.get("debug_candidates") or []
        uid = {d["candidate_uid"]: d for d in debug if d.get("candidate_uid")}
        ids = {d["candidate_id"]: d for d in debug if d.get("candidate_id") is not None}
        good, bad = [], []
        skips = collections.Counter()
        for c in ps.get("candidate_ledger") or []:
            if not c.get("guard_ok") or c.get("hard_feasible") is not True or not finite(c.get("residual_norm")):
                skips["float_ineligible"] += 1
                continue
            d = uid.get(c["candidate_uid"]) if c.get("candidate_uid") else ids.get(c.get("candidate_id"))
            if d is None:
                skips["not_in_debug"] += 1
                continue
            if "deadline" in str(d.get("refinement_status", "")):
                skips["deadline_status"] += 1
                continue
            r = {"candidate_uid": c.get("candidate_uid"), "candidate_id": c.get("candidate_id"), "residual": float(c["residual_norm"]), "refinement_status": d.get("refinement_status"), "hard_violation_tags": d.get("hard_violation_tags") or [], "rejection_tag": d.get("rejection_tag")}
            if d.get("rejection_tag") is None:
                good.append(r)
            elif d.get("rejection_tag") == "rejected_by_exact_assembly":
                bad.append(r)
            else:
                skips["other_rejection_tag"] += 1
        inversions, strict = [], []
        for a in good:
            for b in bad:
                if a["residual"] > 0 and 0 <= b["residual"] <= a["residual"] / 100:
                    pair = {"accepted": a, "rejected": b}
                    inversions.append(pair)
                    if max(a["residual"], b["residual"]) <= 1e-6 and not b["hard_violation_tags"]:
                        strict.append(pair)
        rows.append({"case_id": cid, "family": family(cid), "ledger_count": len(ps.get("candidate_ledger") or []), "debug_count": len(debug), "accepted_linked": len(good), "rejected_linked": len(bad), "evaluable": bool(good and bad), "inversion_count": len(inversions), "strict_inversion_count": len(strict), "inversion_examples": inversions[:3], "strict_examples": strict[:3], "skips": dict(skips)})
    eligible = [r for r in rows if r["evaluable"]]
    strict = [r for r in rows if r["strict_inversion_count"]]
    summary = {"test": "T3", "completed_at": stamp(), "elapsed_seconds": time.monotonic() - started, "archive_runs": len(rows), "evaluable_cases": len(eligible), "inversion_cases": sum(bool(r["inversion_count"]) for r in rows), "strict_inversion_cases": len(strict), "strict_inversion_families": sorted({r["family"] for r in strict}), "linked_accepted": sum(r["accepted_linked"] for r in rows), "linked_rejected": sum(r["rejected_linked"] for r in rows), "coverage_sufficient": len(eligible) >= 10, "effect_gate": len(strict) >= 3 and len({r["family"] for r in strict}) >= 2}
    summary["gate_pass"] = summary["coverage_sufficient"] and summary["effect_gate"]
    write("t3.json", {"summary": summary, "rows": rows})
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def verify(m):
    unchanged = source_manifest() == m["source_files"]
    inputs_unchanged = all(sha(ROOT / i["path"]) == i["sha256"] for i in m["archive"] + m["probe_inputs"])
    result = {"verified_at": stamp(), "src_unchanged": unchanged, "inputs_unchanged": inputs_unchanged, "preregistration_unchanged": sha(HERE / "preregistration.md") == m["preregistration_sha256"], "files": [{"name": p.name, "bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(HERE.iterdir()) if p.is_file()]}
    write("verification.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "files"}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "t1", "t2", "t3", "verify"))
    args = parser.parse_args()
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("one-hour limit")))
    signal.alarm(3600)
    if args.action == "freeze":
        freeze()
    else:
        globals()[args.action](manifest())
