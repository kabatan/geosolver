"""Summarize every scheduled run. Optional full-coordinate checking is read-only."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from fractions import Fraction
from functools import cache
from statistics import median

from experiment import HERE, LIMIT, RAW, SEEDS, SOURCE, canonical, digest, read, save


@cache
def exact_key(expr):
    from geosolver.exact import describe_exact

    return canonical(describe_exact(expr).canonical_key())


def figure_key(coords):
    values = []
    for val in coords:
        v = float(val)
        if not math.isfinite(v):
            return None
        values.append("0" if abs(v) < 1e-8 else format(v, ".8g"))
    return tuple(values)


def csv_write(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(
            {k: canonical(v) if isinstance(v, dict | list | tuple) else v for k, v in row.items()}
            for row in rows
        )


@cache
def evaluator_variant(variant):
    from geosolver import GeometryProblem
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle

    doc = read(HERE / "inputs" / f"{variant}.json")
    return build_ir_evaluator(
        load_problem_bundle(GeometryProblem.model_validate(doc).engine_document())
    )


@cache
def coordinate_layout(variant):
    doc = read(HERE / "inputs" / f"{variant}.json")
    bundle = evaluator_variant(variant).bundle
    fixed = {}
    for name in doc["variables"]:
        if name not in bundle.var_names:
            expression = next(c.expr for c in bundle.spec.construction if c.name == name)
            fixed[name] = str(Fraction(expression))
    return doc["variables"], list(bundle.var_names), fixed


def expand_coordinates(variant, x):
    from mpmath import mp

    all_names, active, fixed = coordinate_layout(variant)
    values = dict(zip(active, x, strict=True))
    with mp.workdps(80):
        for name, value in fixed.items():
            ratio = Fraction(value)
            values[name] = str(mp.mpf(ratio.numerator) / ratio.denominator)
    return [values[name] for name in all_names]


def check_full(index, coords):
    from mpmath import mp

    from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )

    variant = f"single-{index:02d}"
    ev = evaluator_variant(variant)
    try:
        with mp.workdps(80), high_precision_mode():
            names = coordinate_layout(variant)[0]
            mapping = dict(zip(names, coords, strict=True))
            x = [mp.mpf(mapping[name]) for name in ev.bundle.var_names]
            res = ev.evaluate_hp_residual(x, precision=80)
            hard = ev.evaluate_hp_hard_feasibility(x, precision=80, include_margins=False)
            good = bool(
                res.is_finite and res.residual_norm_hp <= mp.mpf("1e-20") and hard.hard_feasible
            )
            answer = ev.evaluate_answer_hp(x, precision=80).answer_hp if good else None
            return {
                "full_numeric_feasible": good,
                "residual": str(res.residual_norm_hp),
                "hard_feasible": hard.hard_feasible,
                "answer": str(answer) if answer is not None else None,
            }
    except Exception as error:
        return {"full_numeric_feasible": False, "error": repr(error)}


def analyze(check_coordinates=False, partial=False):
    from benchmarks.research_runner import _answer_keys

    manifest = read(HERE / "manifest.json")
    variants = {v["id"]: v for v in manifest["variants"]}
    bases = manifest["selected"]
    rows, sets, missing = [], {}, []
    for job in manifest["schedule"]:
        variant, seed = job["variant"], job["seed"]
        v = variants[variant]
        key = f"{variant}__s{seed}"
        path = RAW / "runs" / (key + ".json")
        receipt_path = RAW / "receipts" / (key + ".json")
        if not receipt_path.exists():
            missing.append(key)
            if partial:
                continue
        receipt = read(receipt_path) if receipt_path.exists() else {}
        raw = read(path) if path.exists() else {}
        result = raw.get("solver_result") or {}
        diagnostics = result.get("diagnostics") or {}
        info = diagnostics.get("process_info") or {}
        issues = raw.get("execution_contract_issues", [])
        status = result.get("status", "missing")
        if receipt.get("external_timeout"):
            status = "external_timeout"
        normal = status in ("solved", "no_answer_found") and not issues
        actual = _answer_keys(result)
        expected = sorted(set(exact_key(r) for r in v["references"]))
        matches = normal and actual == expected
        wall = result.get("elapsed_seconds", receipt.get("elapsed_seconds", LIMIT))
        timeout = (
            result.get("termination_reason") == "time_limit_reached" or status == "external_timeout"
        )
        cs = diagnostics.get("candidate_records") or []
        coordinates, accepted, geometrically_good, projections, full_good = (
            {},
            set(),
            set(),
            {},
            set(),
        )
        checked = []
        for c in cs:
            x = c.get("x_hp")
            if x is None:
                continue
            assert len(x) == len(coordinate_layout(variant)[1]), (variant, len(x))
            try:
                expanded = expand_coordinates(variant, x)
                sig = figure_key(expanded)
            except (ValueError, OverflowError):
                continue
            if sig is None:
                continue
            coordinates.setdefault(sig, expanded)
            if c.get("accepted"):
                accepted.add(sig)
            try:
                good = bool(
                    c.get("hard_feasible") and float(c.get("residual_norm_hp", "inf")) <= 1e-20
                )
            except (ValueError, OverflowError):
                good = False
            if good:
                geometrically_good.add(sig)
        offset = 0
        for i in v["components"]:
            n = bases[i]["n_vars"]
            projections[str(i)] = sorted({sig[offset : offset + n] for sig in geometrically_good})
            offset += n
        if check_coordinates and v["kind"].startswith("half"):
            for sig in sorted(geometrically_good):
                checked_one = check_full(v["components"][0], coordinates[sig])
                checked.append({"figure": sig, **checked_one})
                if checked_one["full_numeric_feasible"]:
                    full_good.add(sig)
        row = {
            "variant": variant,
            "kind": v["kind"],
            "components": v["components"],
            "seed": seed,
            "status": status,
            "normal_completion": normal,
            "timeout": timeout,
            "matches_reference_set": matches,
            "correct": matches if not v["kind"].startswith("half") else None,
            "wall_seconds": wall,
            "cpu_seconds": info.get("cpu_seconds"),
            "capped_cost_seconds": min(wall, LIMIT) if matches else LIMIT,
            "n_vars": v["n_vars"],
            "active_n_vars": len(coordinate_layout(variant)[1]),
            "n_conditions": v["n_conditions"],
            "answer_count": len(actual),
            "extra_answers": len(set(actual) - set(expected)),
            "missing_answers": len(set(expected) - set(actual)),
            "record_count": len(cs),
            "accepted_figures": len(accepted),
            "numeric_figures": len(geometrically_good),
            "full_feasible_figures": len(full_good)
            if check_coordinates and v["kind"].startswith("half")
            else None,
            "evaluation_count": (diagnostics.get("counters") or {}).get("evaluation_count"),
            "source_hash_ok": raw.get("source_hash") == SOURCE,
            "input_hash_ok": raw.get("input_sha256") == v["input_sha256"],
            "contract_issues": issues,
            "raw_sha256": digest(path.read_bytes()) if path.exists() else None,
            "raw_bytes": path.stat().st_size if path.exists() else 0,
            "peak_rss_bytes": info.get("peak_rss_bytes"),
            "load_start": raw.get("load_start"),
            "phase_timings": diagnostics.get("phase_timings", {}),
            "rejection_tags": diagnostics.get("rejection_tags", []),
        }
        rows.append(row)
        sets[key] = {
            "actual_exact_keys": [json.loads(a) for a in actual],
            "expected_exact_keys": [json.loads(a) for a in expected],
            "answer_decimals": [
                a.get("decimal", a.get("value", {}).get("decimal"))
                for a in result.get("answers", [])
            ],
            "accepted_figures": sorted(accepted),
            "numeric_figures": sorted(geometrically_good),
            "component_projections": projections,
            "original_condition_checks": checked,
        }

    lookup = {(r["variant"], r["seed"]): r for r in rows}
    pairs = []
    for group, (left, right) in enumerate(manifest["pairs"]):
        for seed in SEEDS:
            names = [f"single-{left:02d}", f"single-{right:02d}"]
            if not all((name, seed) in lookup for name in names):
                continue
            ls, rs = (lookup[(name, seed)] for name in names)
            for mode in ("left", "right", "sum"):
                vid = f"pair-{mode}-{group:02d}"
                if (vid, seed) not in lookup:
                    continue
                combined = lookup[(vid, seed)]
                target_single = ls if mode == "left" else rs if mode == "right" else None
                output = {
                    "pair": group,
                    "left_id": bases[left]["id"],
                    "right_id": bases[right]["id"],
                    "seed": seed,
                    "mode": mode,
                    "left_nvars": bases[left]["n_vars"],
                    "right_nvars": bases[right]["n_vars"],
                    "single_left_correct": ls["correct"],
                    "single_right_correct": rs["correct"],
                    "both_singles_correct": ls["correct"] and rs["correct"],
                    "combined_correct": combined["correct"],
                    "combined_timeout": combined["timeout"],
                    "single_left_wall": ls["wall_seconds"],
                    "single_right_wall": rs["wall_seconds"],
                    "single_sum_wall": ls["wall_seconds"] + rs["wall_seconds"],
                    "combined_wall": combined["wall_seconds"],
                    "wall_ratio_to_sum": combined["wall_seconds"]
                    / (ls["wall_seconds"] + rs["wall_seconds"]),
                    "combined_cost": combined["capped_cost_seconds"],
                    "ratio_to_successful_single_sum": combined["capped_cost_seconds"]
                    / (ls["wall_seconds"] + rs["wall_seconds"])
                    if ls["correct"] and rs["correct"]
                    else None,
                    "correct_target_lost": bool(
                        target_single and target_single["correct"] and not combined["correct"]
                    ),
                    "target_rescued": bool(
                        target_single and not target_single["correct"] and combined["correct"]
                    ),
                    "numeric_figures": combined["numeric_figures"],
                }
                for label, i in [("left", left), ("right", right)]:
                    single_set = {
                        tuple(x) for x in sets[f"single-{i:02d}__s{seed}"]["numeric_figures"]
                    }
                    projection = {
                        tuple(x) for x in sets[f"{vid}__s{seed}"]["component_projections"][str(i)]
                    }
                    output[label + "_figure_overlap"] = len(single_set & projection)
                    output[label + "_figure_union"] = len(single_set | projection)
                pairs.append(output)

    by_kind = {}
    for kind in sorted({r["kind"] for r in rows}):
        group = [r for r in rows if r["kind"] == kind]
        by_kind[kind] = {
            "n": len(group),
            "matches_reference_set": sum(r["matches_reference_set"] for r in group),
            "timeout": sum(r["timeout"] for r in group),
            "status": dict(Counter(r["status"] for r in group)),
            "median_wall_seconds": median(r["wall_seconds"] for r in group),
            "numeric_figure_found": sum(r["numeric_figures"] > 0 for r in group),
            "full_feasible_found": sum((r["full_feasible_figures"] or 0) > 0 for r in group),
            "by_seed": {
                str(seed): {
                    "n": sum(r["seed"] == seed for r in group),
                    "matches": sum(r["seed"] == seed and r["matches_reference_set"] for r in group),
                }
                for seed in SEEDS
            },
        }
    summary = {
        "scheduled_runs": len(manifest["schedule"]),
        "summarized_runs": len(rows),
        "missing_receipts": missing,
        "coordinate_checks": check_coordinates,
        "source_hash_ok": all(r["source_hash_ok"] for r in rows),
        "input_hash_ok": all(r["input_hash_ok"] for r in rows),
        "contract_issues": [r["variant"] for r in rows if r["contract_issues"]],
        "by_kind": by_kind,
        "raw_bytes": sum(r["raw_bytes"] for r in rows),
        "max_raw_bytes": max((r["raw_bytes"] for r in rows), default=0),
        "external_directory": str(RAW),
    }
    prefix = "partial-" if partial else ""
    destination = RAW if partial else HERE
    csv_write(destination / (prefix + "per-run.csv"), rows)
    csv_write(destination / (prefix + "per-pair.csv"), pairs)
    save(destination / (prefix + "sets.json"), sets)
    save(destination / (prefix + "summary.json"), summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--check-coordinates", action="store_true")
    p.add_argument("--partial", action="store_true")
    args = p.parse_args()
    analyze(args.check_coordinates, args.partial)
