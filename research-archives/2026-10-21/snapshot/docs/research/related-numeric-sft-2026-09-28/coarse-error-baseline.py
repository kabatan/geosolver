#!/usr/bin/env python3
"""Post-hoc constant-prediction baseline for the frozen numeric diagnostic.

Uses only train.json, data-provenance.json and diagnostic-error-analysis.json.
No scale fitting, shape features, formulas, model loading or GPU work is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "qwen/.runtime/related_numeric_sft_20260928"
DEFAULT_TRAIN = RUNTIME / "train.json"
DEFAULT_PROVENANCE = RUNTIME / "data-provenance.json"
DEFAULT_DIAGNOSTICS = RUNTIME / "diagnostic-error-analysis.json"
DEFAULT_OUT = RUNTIME / "coarse-error-baseline.json"
ARMS = ("base", "sft-a", "sft-b")
SPLITS = ("trained_example", "new_shape")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target_number(value: Any, label: str) -> float:
    if not isinstance(value, str):
        raise ValueError(f"{label}: target must be a string")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label}: target must be finite and positive")
    if format(number, ".17g") != value:
        raise ValueError(f"{label}: target is not the frozen .17g representation")
    return number


def relative_error(prediction: float, expected: float) -> float:
    return abs(prediction - expected) / expected


def absolute_log_ratio(prediction: float, expected: float) -> float:
    if prediction <= 0 or expected <= 0:
        raise ValueError("absolute log ratio requires positive values")
    return abs(math.log(prediction / expected))


def summarize_errors(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    rel = [row["relative_error"] for row in rows]
    log_ratio = [row["absolute_log_ratio"] for row in rows]
    return {
        "n": len(rows),
        "mean_relative_error": statistics.mean(rel),
        "median_relative_error": statistics.median(rel),
        "mean_absolute_log_ratio": statistics.mean(log_ratio),
        "median_absolute_log_ratio": statistics.median(log_ratio),
    }


def error_record(prediction: float, expected: float) -> dict[str, float]:
    return {
        "prediction": prediction,
        "relative_error": relative_error(prediction, expected),
        "absolute_log_ratio": absolute_log_ratio(prediction, expected),
    }


def error_row(
    source_id: str,
    split: str,
    predictor: str,
    prediction: float,
    expected: float,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "split": split,
        "predictor": predictor,
        "expected": expected,
        **error_record(prediction, expected),
    }


def build_report(train_path: Path, provenance_path: Path, diagnostic_path: Path) -> dict[str, Any]:
    train = load_json(train_path)
    provenance = load_json(provenance_path)
    diagnostics = load_json(diagnostic_path)
    if not isinstance(train, list) or len(train) != 80:
        raise ValueError("expected exactly 80 frozen training rows")
    if not isinstance(provenance, list) or len(provenance) != 120:
        raise ValueError("expected exactly 120 provenance rows")
    if diagnostics.get("status") != "exploratory_posthoc_error_analysis":
        raise ValueError("unexpected diagnostic analysis status")

    provenance_by_id = {row["id"]: row for row in provenance}
    if len(provenance_by_id) != len(provenance):
        raise ValueError("duplicate provenance IDs")
    train_by_id = {row["id"]: row for row in train}
    if len(train_by_id) != len(train):
        raise ValueError("duplicate training IDs")

    targets_by_source: dict[str, list[tuple[str, float]]] = {}
    for row in train:
        if row.get("kind") != "numeric":
            raise ValueError(f"non-numeric training row: {row.get('id')}")
        source_id = row["source_id"]
        item = provenance_by_id.get(row["id"])
        if item is None or item.get("source_id") != source_id or item.get("split") != "train":
            raise ValueError(f"training row provenance mismatch: {row['id']}")
        value = target_number(row["target"], row["id"])
        if item.get("target") != row["target"]:
            raise ValueError(f"training target differs from provenance: {row['id']}")
        targets_by_source.setdefault(source_id, []).append((row["id"], value))
    if len(targets_by_source) != 10 or any(len(rows) != 8 for rows in targets_by_source.values()):
        raise ValueError("expected 10 sources with exactly 8 training values each")

    source_stats: dict[str, dict[str, float | int]] = {}
    all_values = [value for rows in targets_by_source.values() for _, value in rows]
    for source_id, rows in sorted(targets_by_source.items()):
        values = [value for _, value in rows]
        source_stats[source_id] = {
            "n": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
        }
    global_stats = {
        "n": len(all_values),
        "mean": statistics.mean(all_values),
        "median": statistics.median(all_values),
    }

    diagnostic_rows = diagnostics.get("rows")
    if not isinstance(diagnostic_rows, list) or len(diagnostic_rows) != 60:
        raise ValueError("expected 60 diagnostic rows (3 arms × 2 splits × 10 sources)")
    diagnostic_by_key = {}
    for row in diagnostic_rows:
        key = (row["arm"], row["split"], row["source_id"])
        if key in diagnostic_by_key:
            raise ValueError(f"duplicate diagnostic row: {key}")
        if row["arm"] not in ARMS or row["split"] not in SPLITS:
            raise ValueError(f"unexpected diagnostic row key: {key}")
        diagnostic_by_key[key] = row
    expected_keys = {(arm, split, source) for arm in ARMS for split in SPLITS for source in targets_by_source}
    if set(diagnostic_by_key) != expected_keys:
        raise ValueError("diagnostic rows do not cover every arm/split/source exactly once")

    llm_errors: dict[str, dict[str, list[dict[str, Any]]]] = {
        arm: {split: [] for split in SPLITS} for arm in ARMS
    }
    for (arm, split, source_id), row in diagnostic_by_key.items():
        variant = "01" if split == "trained_example" else "09"
        provenance_id = f"{source_id}-variant-{variant}"
        label = provenance_by_id.get(provenance_id)
        if label is None or label.get("source_id") != source_id:
            raise ValueError(f"diagnostic provenance missing: {provenance_id}")
        expected_split = "train" if split == "trained_example" else "heldout"
        if label.get("split") != expected_split:
            raise ValueError(f"unexpected provenance split: {provenance_id}")
        expected = target_number(label["target"], provenance_id)
        if float(row["expected"]) != expected:
            raise ValueError(f"diagnostic expected value differs from provenance: {row['job_id']}")
        prediction = float(row["value"])
        if not math.isfinite(prediction) or prediction <= 0:
            raise ValueError(f"diagnostic prediction must be finite and positive: {row['job_id']}")
        computed = error_record(prediction, expected)
        if not math.isclose(computed["relative_error"], float(row["relative_error"]), rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError(f"diagnostic relative error differs from recomputation: {row['job_id']}")
        if not math.isclose(computed["absolute_log_ratio"], float(row["absolute_log_ratio"]), rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError(f"diagnostic log ratio differs from recomputation: {row['job_id']}")
        llm_errors[arm][split].append({
            "source_id": source_id,
            "job_id": row["job_id"],
            "expected": expected,
            "prediction": prediction,
            "relative_error": computed["relative_error"],
            "absolute_log_ratio": computed["absolute_log_ratio"],
        })

    new_shape_rows: list[dict[str, Any]] = []
    for source_id in sorted(targets_by_source):
        expected = float(provenance_by_id[f"{source_id}-variant-09"]["target"])
        source_mean = float(source_stats[source_id]["mean"])
        source_median = float(source_stats[source_id]["median"])
        row: dict[str, Any] = {
            "source_id": source_id,
            "provenance_id": f"{source_id}-variant-09",
            "expected": expected,
            "source_train_n": 8,
            "source_train_mean_prediction": source_mean,
            "source_train_median_prediction": source_median,
            "source_train_mean_error": error_record(source_mean, expected),
            "source_train_median_error": error_record(source_median, expected),
            "global_train_mean_prediction": global_stats["mean"],
            "global_train_median_prediction": global_stats["median"],
            "global_train_mean_error": error_record(float(global_stats["mean"]), expected),
            "global_train_median_error": error_record(float(global_stats["median"]), expected),
            "llm": {},
        }
        for arm in ARMS:
            pred_row = next(x for x in llm_errors[arm]["new_shape"] if x["source_id"] == source_id)
            row["llm"][arm] = {
                "prediction": pred_row["prediction"],
                "relative_error": pred_row["relative_error"],
                "absolute_log_ratio": pred_row["absolute_log_ratio"],
            }
        new_shape_rows.append(row)

    # The ten seen-example labels are excluded individually from both the
    # source and global statistics, preventing self-label leakage.
    trained_loo_rows: list[dict[str, Any]] = []
    for source_id in sorted(targets_by_source):
        train_id = f"{source_id}-variant-01"
        if train_id not in train_by_id:
            raise ValueError(f"missing trained-example diagnostic row: {train_id}")
        expected = target_number(train_by_id[train_id]["target"], train_id)
        source_loo = [v for other_id, v in targets_by_source[source_id] if other_id != train_id]
        global_loo = [
            value
            for rows in targets_by_source.values()
            for other_id, value in rows
            if other_id != train_id
        ]
        predictors = {
            "source_loo_mean": statistics.mean(source_loo),
            "source_loo_median": statistics.median(source_loo),
            "global_loo_mean": statistics.mean(global_loo),
            "global_loo_median": statistics.median(global_loo),
        }
        row = {"source_id": source_id, "train_id": train_id, "expected": expected, "loo_n_source": 7, "loo_n_global": 79, "baselines": {}}
        for name, prediction in predictors.items():
            row["baselines"][name] = error_record(float(prediction), expected)
        for arm in ARMS:
            pred_row = next(x for x in llm_errors[arm]["trained_example"] if x["source_id"] == source_id)
            row.setdefault("llm", {})[arm] = {
                "prediction": pred_row["prediction"],
                "relative_error": pred_row["relative_error"],
                "absolute_log_ratio": pred_row["absolute_log_ratio"],
            }
        trained_loo_rows.append(row)

    aggregate: dict[str, Any] = {}
    for name, get_rows in (
        ("source_train_mean", lambda split: new_shape_rows),
        ("source_train_median", lambda split: new_shape_rows),
        ("global_train_mean", lambda split: new_shape_rows),
        ("global_train_median", lambda split: new_shape_rows),
    ):
        selected = get_rows("new_shape")
        relative_key = f"{name}_error"
        aggregate[name] = summarize_errors([
            {"relative_error": row[relative_key]["relative_error"], "absolute_log_ratio": row[relative_key]["absolute_log_ratio"]}
            for row in selected
        ])
    aggregate["trained_example_leave_one_out"] = {}
    for name in ("source_loo_mean", "source_loo_median", "global_loo_mean", "global_loo_median"):
        aggregate["trained_example_leave_one_out"][name] = summarize_errors([
            {"relative_error": row["baselines"][name]["relative_error"], "absolute_log_ratio": row["baselines"][name]["absolute_log_ratio"]}
            for row in trained_loo_rows
        ])
    aggregate["llm"] = {
        arm: {split: summarize_errors(llm_errors[arm][split]) for split in SPLITS}
        for arm in ARMS
    }

    return {
        "status": "exploratory_posthoc_constant_baseline",
        "primary_metric_changed": False,
        "interpretation": "A deliberately coarse prediction baseline using arithmetic mean/median only; not a geometry solver, not a fitted scale rule, and not part of the preregistered strict score.",
        "inputs": {
            "train_json": str(train_path.resolve()),
            "train_json_sha256": sha256(train_path),
            "data_provenance_json": str(provenance_path.resolve()),
            "data_provenance_sha256": sha256(provenance_path),
            "diagnostic_error_analysis_json": str(diagnostic_path.resolve()),
            "diagnostic_error_analysis_sha256": sha256(diagnostic_path),
        },
        "definitions": {
            "source_baseline": "Mean or median of that source's 8 training targets; applied unchanged to that source's variant-09 heldout example.",
            "global_baseline": "Mean or median of all 80 training targets; applied unchanged to each variant-09 heldout example.",
            "trained_example_baseline": "Leave-one-out mean or median, excluding the evaluated variant-01 target from its source's 8 and from all 80 training targets.",
            "relative_error": "abs(prediction - expected) / expected",
            "absolute_log_ratio": "abs(log(prediction / expected)); only defined here for positive distances and predictions.",
            "aggregation": "Across one example per source (n=10), report unweighted mean and median for relative error and absolute log ratio.",
        },
        "training_target_statistics": {"overall": global_stats, "by_source": source_stats},
        "heldout_new_shape_by_source": new_shape_rows,
        "trained_example_leave_one_out_by_source": trained_loo_rows,
        "aggregates": aggregate,
        "existing_diagnostic_summary": diagnostics.get("summary"),
        "row_counts": {"training": len(train), "new_shape": 10, "trained_example": 10, "diagnostic_rows": len(diagnostic_rows)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--diagnostics", type=Path, default=DEFAULT_DIAGNOSTICS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = build_report(args.train, args.provenance, args.diagnostics)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "out": str(args.out.resolve()), "aggregate": report["aggregates"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
