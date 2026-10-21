#!/usr/bin/env python3
"""Posthoc, single-feature length-scale diagnostic for the dose-control study.

This deliberately fits only one coefficient per source: the median of y/L over
its eight correct training examples. L is selected mechanically as the first
positive two-point length assignment in the problem body after the fixed
instruction prefix. The selected field is checked for consistency in all
training and reserved prompts. No heldout target or prediction is consulted
until after feature selection and coefficient fitting are complete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
DEFAULT_RUNTIME = REPO_ROOT / "qwen/.runtime/numeric_sft_dose_control_20260928"
PREFIX = (
    "Solve the following numerical geometry problem. Give only the requested "
    "numerical value, with at least 10 significant digits when appropriate. "
    "Do not give a proof or explanation.\n\n"
)
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
TARGET_RE = re.compile(rf"\s*(?:Answer:\s*)?({NUMBER})\s*")
# Current source templates give lengths as two-point segment assignments (e.g.
# AB=12.3). Three-letter angle names and colon ratios are intentionally skipped.
LENGTH_ASSIGNMENT = re.compile(
    rf"(?<![A-Za-z0-9_:])(?P<field>[A-Z]{{2}})\s*=\s*(?P<value>{NUMBER})"
)

SOURCE_NOTES = {
    "DA02": "The statement begins with angle BAC=60 degrees; skip this angle and select the first length assignment, AB.",
    "DB12": "The statement begins with angle BAC=45 degrees; skip this angle and select BC, which appears before the stated division ratios.",
}


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def user_text(record: dict[str, Any]) -> str:
    users = [m.get("content", "") for m in record.get("messages", []) if m.get("role") == "user"]
    if len(users) != 1:
        raise ValueError(f"expected exactly one user message for {record.get('id')}")
    return users[0]


def problem_body(record: dict[str, Any]) -> str:
    text = user_text(record)
    if not text.startswith(PREFIX):
        raise ValueError(f"instruction prefix mismatch for {record.get('id')}")
    return text[len(PREFIX):].strip()


def first_explicit_length(record: dict[str, Any]) -> tuple[str, float, str]:
    body = problem_body(record)
    match = LENGTH_ASSIGNMENT.search(body)
    if not match:
        raise ValueError(f"no explicit two-point length found for {record.get('id')}")
    value = float(match.group("value"))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"first length is not positive for {record.get('id')}")
    return match.group("field"), value, match.group(0)


def numeric_target(value: Any, context: str) -> float:
    match = TARGET_RE.fullmatch(str(value))
    if not match:
        raise ValueError(f"non-numeric target for {context}: {value!r}")
    result = float(match.group(1))
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"target must be positive for {context}")
    return result


def score_point(value: float, target: float, abs_tol: float, rel_tol: float) -> dict[str, Any]:
    if not (math.isfinite(value) and math.isfinite(target) and value > 0 and target > 0):
        raise ValueError("metrics require finite positive values")
    abs_error = abs(value - target)
    relative_error = abs_error / abs(target)
    return {
        "value": value,
        "target": target,
        "absolute_error": abs_error,
        "relative_error": relative_error,
        "absolute_log_ratio": abs(math.log(value / target)),
        "precise": abs_error <= abs_tol or relative_error <= rel_tol,
        "within_10_percent": relative_error <= 0.10,
    }


def summarize(points: list[dict[str, Any]]) -> dict[str, Any]:
    if not points:
        raise ValueError("cannot summarize an empty group")
    re_values = [p["relative_error"] for p in points]
    abslog_values = [p["absolute_log_ratio"] for p in points]
    precise = sum(bool(p["precise"]) for p in points)
    within10 = sum(bool(p["within_10_percent"]) for p in points)
    n = len(points)
    return {
        "n": n,
        "precise_count": precise,
        "precise_rate": precise / n,
        "REmedian": statistics.median(re_values),
        "REmean": statistics.mean(re_values),
        "mean_absolute_log_ratio": statistics.mean(abslog_values),
        "within10_count": within10,
        "within10_rate": within10 / n,
    }


def macro_source_average(summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    keys = ("precise_rate", "REmedian", "REmean", "mean_absolute_log_ratio", "within10_rate")
    result = {f"mean_source_{key}": statistics.mean(s[key] for s in summaries.values()) for key in keys}
    result["n_sources"] = len(summaries)
    return result


def fmt(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def make_markdown(result: dict[str, Any]) -> str:
    selection = result["feature_selection"]
    evaluation = result["evaluation"]
    overall = evaluation["overall"]
    scale = overall["scale_baseline"]
    model = overall["correct512"]
    lines = [
        "# Single-length scale baseline",
        "",
        "This is a posthoc exploratory baseline, run after the reserved-shape results had been observed. It asks how much those results can be explained by a one-length size rule. It is not a replacement for the primary evaluation and cannot establish that SFT failed to learn geometry.",
        "",
        "The sole predictor per source is `prediction = c × L`, where `L` is the first positive explicitly assigned two-point length in the problem body after removing the fixed instruction prefix. `c` is the median of `training target / L` over that source's eight correct training examples. No heldout target or model error was used to select `L`; source templates with inconsistent first-length fields cause the script to stop.",
        "",
        "DA02 starts with a 60° angle, so the first length is AB. DB12 starts with a 45° angle, so the first length is BC; its ratio statements occur later. The other first-length fields are selected directly by problem-text order.",
        "",
        "## Feature and fitted scale by source",
        "",
        "| Source | First length L | n train | c = median(y/L) |",
        "|---|---:|---:|---:|",
    ]
    for source, row in selection["by_source"].items():
        lines.append(f"| {source} | {row['field']} | {row['n_train']} | {row['c_median_y_over_L']:.10g} |")
    lines.extend([
        "",
        "## Reserved-shape comparison",
        "",
        "`precise` uses the frozen scorer tolerances (absolute error ≤ `absolute_tol` or relative error ≤ `relative_tol`). RE is absolute relative error. `within10` counts relative error ≤10%. All values aggregate the same 30 reserved prompts.",
        "",
        "| Predictor | Precise | RE median | RE mean | Mean abs log ratio | Within 10% |",
        "|---|---:|---:|---:|---:|---:|",
        f"| First-length scale baseline | {scale['precise_count']}/{scale['n']} | {fmt(scale['REmedian'])} | {fmt(scale['REmean'])} | {fmt(scale['mean_absolute_log_ratio'])} | {scale['within10_count']}/{scale['n']} |",
        f"| Correct512 | {model['precise_count']}/{model['n']} | {fmt(model['REmedian'])} | {fmt(model['REmean'])} | {fmt(model['mean_absolute_log_ratio'])} | {model['within10_count']}/{model['n']} |",
        "",
        result["interpretation"],
        "",
        "Macro average of the ten source-level means:",
        "",
        f"- Scale baseline: mean-source RE `{fmt(overall['scale_baseline_source_macro']['mean_source_REmean'])}`, mean-source abs-log `{fmt(overall['scale_baseline_source_macro']['mean_source_mean_absolute_log_ratio'])}`, mean-source within10 `{fmt(overall['scale_baseline_source_macro']['mean_source_within10_rate'] * 100, 2)}%`.",
        f"- Correct512: mean-source RE `{fmt(overall['correct512_source_macro']['mean_source_REmean'])}`, mean-source abs-log `{fmt(overall['correct512_source_macro']['mean_source_mean_absolute_log_ratio'])}`, mean-source within10 `{fmt(overall['correct512_source_macro']['mean_source_within10_rate'] * 100, 2)}%`.",
        "",
        "## Per-source averages",
        "",
        "Each row averages the three reserved variants in that source. `RE mean` and abs-log compare the simple baseline with Correct512 on the same gold values.",
        "",
        "| Source | Scale RE mean | Correct512 RE mean | Scale abs-log | Correct512 abs-log | Scale within10 | Correct512 within10 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for source, row in evaluation["by_source"].items():
        b, m = row["scale_baseline"], row["correct512"]
        lines.append(
            f"| {source} | {fmt(b['REmean'])} | {fmt(m['REmean'])} | {fmt(b['mean_absolute_log_ratio'])} | {fmt(m['mean_absolute_log_ratio'])} | {b['within10_count']}/3 | {m['within10_count']}/3 |"
        )
    lines.extend([
        "",
        "The feature map, per-source coefficients, and per-prompt predictions/errors are preserved in `scale-baseline.json`. The script is rerunnable with the four frozen runtime inputs and uses no model inference.",
        "",
        "This is only a coarse size-scaling diagnostic. A better Correct512 score than this baseline would show that one proportional length per source does not explain all performance; it would not by itself prove general geometric reasoning. A competitive baseline would likewise not disprove geometry learning.",
        "",
        "Input SHA-256 values are recorded in the JSON. Precise tolerances: absolute `" + str(result["metrics_definition"]["absolute_tol"]) + "`, relative `" + str(result["metrics_definition"]["relative_tol"]) + "`.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args()

    runtime = args.runtime_dir.resolve()
    output_dir = args.output_dir.resolve()
    paths = {
        name: runtime / name
        for name in ("train-correct.json", "fit-jobs.json", "fit-answer-key.json", "fit-scores.json")
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)

    train = read_json(paths["train-correct.json"])
    jobs = read_json(paths["fit-jobs.json"])

    train_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in train:
        train_groups[record["source_id"]].append(record)
    sources = sorted(train_groups)
    if len(train) != 80 or any(len(train_groups[s]) != 8 for s in sources):
        raise ValueError("expected exactly 8 correct training examples for each source")

    # Feature selection uses prompt text only. Verify the first explicit length
    # field is stable across all eight train prompts and every reserved prompt.
    reserved_jobs = [j for j in jobs if j.get("split") == "reserved_shape"]
    if len(reserved_jobs) != 30:
        raise ValueError(f"expected 30 reserved_shape jobs, found {len(reserved_jobs)}")
    reserved_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in reserved_jobs:
        reserved_by_source[job["source_id"]].append(job)
    if set(reserved_by_source) != set(sources) or any(len(reserved_by_source[s]) != 3 for s in sources):
        raise ValueError("expected three reserved variants per training source")

    selected: dict[str, dict[str, Any]] = {}
    fitted: dict[str, dict[str, Any]] = {}
    scale_points_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    model_points_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    predicted_rows: list[dict[str, Any]] = []

    # Freeze the text-derived feature map before reading heldout targets or model errors.
    feature_values: dict[str, dict[str, tuple[float, str]]] = {}
    for source in sources:
        chosen_train = [first_explicit_length(r) for r in train_groups[source]]
        fields = {item[0] for item in chosen_train}
        if len(fields) != 1:
            raise ValueError(f"first length field varies across train prompts for {source}: {sorted(fields)}")
        field = chosen_train[0][0]
        chosen_reserved = [first_explicit_length(r) for r in reserved_by_source[source]]
        if any(item[0] != field for item in chosen_reserved):
            raise ValueError(f"first length field differs on reserved prompts for {source}")
        feature_values[source] = {
            record["id"]: (item[1], item[2])
            for record, item in zip(train_groups[source], chosen_train)
        }
        feature_values[source].update({
            job["id"]: (item[1], item[2])
            for job, item in zip(reserved_by_source[source], chosen_reserved)
        })
        selected[source] = {
            "field": field,
            "n_train": len(train_groups[source]),
            "note": SOURCE_NOTES.get(source, "Selected as the first explicit positive two-point length assignment in problem-text order."),
            "prompt_order_consistent": True,
        }

    for source in sources:
        train_points = []
        for record in train_groups[source]:
            length, _match = feature_values[source][record["id"]]
            target = numeric_target(record["target"], record["id"])
            train_points.append(target / length)
        coefficient = statistics.median(train_points)
        fitted[source] = {"n_train": len(train_points), "c_median_y_over_L": coefficient}

    # Feature fields and coefficients are now frozen using only problem text
    # and the 80 training targets. Read reserved golds/model errors afterwards.
    answer_key = read_json(paths["fit-answer-key.json"])
    scores = read_json(paths["fit-scores.json"])
    if scores.get("status") != "complete":
        raise ValueError("fit-scores.json is not complete")
    abs_tol = float(scores["tolerances"]["absolute"])
    rel_tol = float(scores["tolerances"]["relative"])

    # Only now score the frozen predictors against the reserved targets and
    # inspect Correct512 outputs. Golds come from fit-answer-key, not the model rows.
    correct512_rows = [
        r for r in scores["rows"] if r.get("arm") == "correct512" and r.get("split") == "reserved_shape"
    ]
    score_by_id = {r["job_id"]: r for r in correct512_rows}
    if len(score_by_id) != 30:
        raise ValueError(f"expected 30 unique Correct512 reserved scores, found {len(score_by_id)}")

    for job in reserved_jobs:
        job_id = job["id"]
        key_id = f"fit-{job_id.removeprefix('fit-')}" if job_id.startswith("fit-") else f"fit-{job_id}"
        key = answer_key.get(key_id)
        if key is None:
            raise ValueError(f"missing answer-key entry for {job_id} (looked for {key_id})")
        if key.get("source_id") != job["source_id"] or key.get("split") != "reserved_shape":
            raise ValueError(f"answer-key metadata mismatch for {job_id}")
        target = numeric_target(key["answer_exact"], job_id)
        model_row = score_by_id.get(job_id)
        if model_row is None:
            raise ValueError(f"missing Correct512 score for {job_id}")
        model_target = float(model_row["target"])
        if not math.isclose(model_target, target, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError(f"Correct512 gold disagrees with answer-key for {job_id}")
        model_value = float(model_row["value"])
        model_point = score_point(model_value, target, abs_tol, rel_tol)
        if bool(model_row["numeric_correct"]) != model_point["precise"]:
            raise ValueError(f"precision metric disagrees with frozen scorer for {job_id}")
        model_points_by_source[job["source_id"]].append({"job_id": job_id, **model_point})

        length, matched_assignment = feature_values[job["source_id"]][job_id]
        prediction = fitted[job["source_id"]]["c_median_y_over_L"] * length
        scale_point = score_point(prediction, target, abs_tol, rel_tol)
        scale_points_by_source[job["source_id"]].append({"job_id": job_id, **scale_point})
        predicted_rows.append({
            "job_id": job_id,
            "source_id": job["source_id"],
            "selected_length_field": selected[job["source_id"]]["field"],
            "selected_assignment_text": matched_assignment,
            "L": length,
            "c": fitted[job["source_id"]]["c_median_y_over_L"],
            "scale_prediction": prediction,
            "gold": target,
            "scale_relative_error": scale_point["relative_error"],
            "scale_absolute_log_ratio": scale_point["absolute_log_ratio"],
            "scale_precise": scale_point["precise"],
            "scale_within10": scale_point["within_10_percent"],
            "correct512_value": model_value,
            "correct512_relative_error": model_point["relative_error"],
            "correct512_absolute_log_ratio": model_point["absolute_log_ratio"],
            "correct512_precise": model_point["precise"],
            "correct512_within10": model_point["within_10_percent"],
        })

    scale_summary = {s: summarize(scale_points_by_source[s]) for s in sources}
    model_summary = {s: summarize(model_points_by_source[s]) for s in sources}
    source_comparison = {
        s: {"scale_baseline": scale_summary[s], "correct512": model_summary[s]}
        for s in sources
    }
    overall_scale = summarize([p for s in sources for p in scale_points_by_source[s]])
    overall_model = summarize([p for s in sources for p in model_points_by_source[s]])
    macro_scale = macro_source_average(scale_summary)
    macro_model = macro_source_average(model_summary)
    interpretation = (
        f"The scale baseline is competitive but the metrics are mixed: its mean RE is lower "
        f"({overall_scale['REmean']:.4f} vs {overall_model['REmean']:.4f}), while Correct512 "
        f"has lower median RE ({overall_model['REmedian']:.4f} vs {overall_scale['REmedian']:.4f}), "
        f"lower mean abs-log ({overall_model['mean_absolute_log_ratio']:.4f} vs "
        f"{overall_scale['mean_absolute_log_ratio']:.4f}), and more within10 cases "
        f"({overall_model['within10_count']}/{overall_model['n']} vs "
        f"{overall_scale['within10_count']}/{overall_scale['n']}). This simple size rule can "
        "account for some numerical performance, but it does not uniformly match Correct512; "
        "neither result alone establishes or rules out learning geometric relations."
    )

    # Confirm the Correct512 aggregation reproduces the frozen scorer summary.
    expected_model = scores["summary"]["correct512"]["reserved_shape"]
    checks = {
        "n": overall_model["n"] == expected_model["n"],
        "precise_count": overall_model["precise_count"] == expected_model["correct"],
        "REmedian": math.isclose(overall_model["REmedian"], expected_model["median_relative_error"], rel_tol=1e-12, abs_tol=1e-12),
        "REmean": math.isclose(overall_model["REmean"], expected_model["mean_relative_error"], rel_tol=1e-12, abs_tol=1e-12),
        "mean_absolute_log_ratio": math.isclose(overall_model["mean_absolute_log_ratio"], expected_model["mean_absolute_log_ratio"], rel_tol=1e-12, abs_tol=1e-12),
        "within10_count": overall_model["within10_count"] == expected_model["within_10pct"],
    }
    if not all(checks.values()):
        raise ValueError(f"Correct512 metric reproduction failed: {checks}")

    result = {
        "title": "Posthoc first-length scale baseline",
        "analysis_type": "exploratory baseline after reserved-shape evaluation was observed",
        "scope": "Tests whether a single per-source proportional scale from one first-stated length explains the 30 reserved-shape results. This does not negate or establish geometric learning.",
        "feature_selection": {
            "rule": "Remove the exact fixed instruction prefix, then in written problem-body order select the first positive explicit two-point length assignment XY=number. Angle notation and colon-ratio statements are not lengths. No heldout target, answer, or error is used to select XY.",
            "by_source": {
                s: {**selected[s], **fitted[s]}
                for s in sources
            },
            "prompts_checked": {"train": len(train), "reserved_shape": len(reserved_jobs)},
            "consistency": "Every source has one stable first-length field across all 8 train and 3 reserved prompts.",
        },
        "metrics_definition": {
            "precise": "abs(value-target) <= absolute_tol OR abs(value-target)/abs(target) <= relative_tol",
            "absolute_tol": abs_tol,
            "relative_tol": rel_tol,
            "RE": "abs(value-target)/abs(target)",
            "absolute_log_ratio": "abs(log(value/target))",
            "within10": "RE <= 0.10",
            "n_reserved": len(predicted_rows),
        },
        "evaluation": {
            "overall": {
                "scale_baseline": overall_scale,
                "correct512": overall_model,
                "scale_baseline_source_macro": macro_scale,
                "correct512_source_macro": macro_model,
            },
            "by_source": source_comparison,
            "rows": predicted_rows,
            "correct512_reproduces_fit_scores_summary": checks,
        },
        "interpretation": interpretation,
        "inputs": {
            name: {"path": str(path), "sha256": sha256(path)}
            for name, path in paths.items()
        },
        "calibration_note": "The baseline was selected after the heldout results were known, so it is exploratory and should not replace the predeclared primary metric. A comparison diagnoses only this simple scale heuristic; it cannot by itself confirm or refute learning of geometric relations.",
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "scale-baseline.json"
    md_path = output_dir / "scale-baseline.md"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(make_markdown(result), encoding="utf-8")
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(json.dumps(result["evaluation"]["overall"], indent=2))


if __name__ == "__main__":
    main()
