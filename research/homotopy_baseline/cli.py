"""Research CLI: admission analysis, single solves, and paired comparisons."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from statistics import median
from typing import Any

from .compiler import admission_report
from .runner import DATASET_SHA256, admission_manifest, solve_problem


def _read_problem(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("formulation"), dict):
        return dict(payload["formulation"])
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    return payload


def _write_json(path: str | None, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path:
        Path(path).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _analyze(args: argparse.Namespace) -> int:
    problem = _read_problem(args.input)
    payload = admission_manifest(problem, mode=args.mode)
    if payload.get("supported"):
        report = admission_report(problem, mode=args.mode)
        payload["variable_count"] = report.variable_count
        payload["equation_count"] = report.equation_count
        payload["branch_count"] = report.branch_count
    _write_json(args.output, payload)
    return 0


def _solve(args: argparse.Namespace) -> int:
    problem = _read_problem(args.input)
    result = solve_problem(problem, mode=args.mode, seconds=args.seconds, seed=args.seed)
    _write_json(args.output, result)
    return 0 if result.get("status") not in {"engine_error", "timeout"} else 2


def _load_dataset(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                item = json.loads(line)
                if not isinstance(item, dict) or not isinstance(item.get("formulation"), dict):
                    raise ValueError("dataset row must contain formulation")
                rows.append(item)
    return rows


def _current_control(problem: dict[str, Any], seconds: float, seed: int) -> dict[str, Any]:
    try:
        from geotarget.models import SolveOptions
        from geotarget.service import solve

        options = SolveOptions(
            engine="optimized",
            run_mode="fixed_time",
            max_time_seconds=max(180.0, float(seconds)),
            cores=1,
            seed=int(seed),
        )
        return solve(problem, options).model_dump(mode="json")
    except Exception as error:
        return {"status": "engine_error", "detail": str(error)}


def _product_hash_check() -> dict[str, Any]:
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        changed = subprocess.check_output(
            [
                "git",
                "diff",
                "--name-only",
                "0858883a80583db3670be991f51fb45f7c10b3ca",
                "--",
                "src/geotarget",
            ],
            text=True,
        ).splitlines()
        return {
            "head": head,
            "base": "0858883a80583db3670be991f51fb45f7c10b3ca",
            "product_unchanged": not changed,
        }
    except (OSError, subprocess.CalledProcessError) as error:
        return {"product_unchanged": False, "error": str(error)}


def _truth_values(row: dict[str, Any]) -> list[float] | None:
    """Parse the frozen textual answer only in the post-worker scorer."""

    try:
        import sympy as sp

        raw = row.get("answer", "")
        values = raw if isinstance(raw, list) else [raw]
        result: list[float] = []
        for item in values:
            value = sp.sympify(str(item), locals={"sqrt": sp.sqrt, "pi": sp.pi})
            if value.is_real is False:
                return None
            result.append(float(value.evalf(50)))
        return result
    except Exception:
        return None


def _arm_score(row: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    expected = _truth_values(row)
    actual: list[float] = []
    for descriptor in result.get("answers", []):
        try:
            actual.append(float(descriptor["decimal"]))
        except (KeyError, TypeError, ValueError):
            continue
    if expected is None:
        return {"truth_available": False, "exact_set_match": None, "extra": None, "duplicate": None}
    tolerance = 1e-8
    matched = [False] * len(expected)
    extras = 0
    for value in actual:
        candidates = [
            index
            for index, target in enumerate(expected)
            if not matched[index] and abs(value - target) <= tolerance
        ]
        if candidates:
            matched[candidates[0]] = True
        else:
            extras += 1
    duplicate = max(0, len(actual) - len(expected) - extras)
    return {
        "truth_available": True,
        "exact_set_match": bool(all(matched) and extras == 0),
        "exact_set_recall": sum(matched) / len(expected) if expected else 1.0,
        "extra": extras,
        "duplicate": duplicate,
    }


def _comparison_metrics(cases: list[dict[str, Any]], cap: float) -> dict[str, Any]:
    homotopy = [case["homotopy"] for case in cases]
    statuses = [str(result.get("status")) for result in homotopy]
    successes = [
        bool(case.get("offline_score", {}).get("homotopy", {}).get("exact_set_match"))
        for case in cases
    ]
    current_successes = [
        bool(case.get("offline_score", {}).get("current", {}).get("exact_set_match"))
        for case in cases
    ]
    b = sum(not a and h for a, h in zip(current_successes, successes, strict=True))
    c = sum(a and not h for a, h in zip(current_successes, successes, strict=True))
    statistic = ((abs(b - c) - 1) ** 2 / (b + c)) if b + c else 0.0
    p_value = math.erfc(math.sqrt(statistic / 2.0)) if b + c else 1.0
    homotopy_scores = [case.get("offline_score", {}).get("homotopy", {}) for case in cases]
    available_scores = [score for score in homotopy_scores if score.get("truth_available")]
    admitted = [case for case in cases if case["homotopy"].get("status") != "unsupported"]

    def times(results: list[dict[str, Any]]) -> list[float]:
        return [float(result.get("timings", {}).get("total_seconds", cap)) for result in results]

    all_times = times(homotopy)
    sorted_times = sorted(all_times)
    p95_index = (
        max(0, min(len(sorted_times) - 1, math.ceil(0.95 * len(sorted_times)) - 1))
        if sorted_times
        else 0
    )
    return {
        "case_count": len(cases),
        "admission_coverage": sum(status != "unsupported" for status in statuses) / len(cases)
        if cases
        else 0.0,
        "exact_complete_rate": sum(status == "exact_complete" for status in statuses) / len(cases)
        if cases
        else 0.0,
        "exact_set_recall": (
            sum(float(score.get("exact_set_recall", 0.0)) for score in available_scores)
            / len(available_scores)
            if available_scores
            else None
        ),
        "extra_count": sum(int(score.get("extra", 0) or 0) for score in available_scores),
        "duplicate_count": sum(int(score.get("duplicate", 0) or 0) for score in available_scores),
        "conditional_success": (
            sum(bool(case["homotopy"].get("answers")) for case in admitted) / len(admitted)
            if admitted
            else None
        ),
        "timeout_count": statuses.count("timeout"),
        "unsupported_count": statuses.count("unsupported"),
        "certification_failure_count": statuses.count("certification_failed"),
        "paired_wins": b,
        "paired_losses": c,
        "mcnemar": {"b": b, "c": c, "chi_square_cc": statistic, "p_value_asymptotic": p_value},
        "median_wall_seconds": median(all_times) if all_times else None,
        "p95_wall_seconds": sorted_times[p95_index] if sorted_times else None,
        "restricted_mean_wall_seconds": sum(min(value, cap) for value in all_times) / len(all_times)
        if all_times
        else None,
        "phase_seconds": {
            "compile": sum(
                float(item.get("timings", {}).get("compile_seconds", 0.0)) for item in homotopy
            ),
            "homotopy": sum(
                float(item.get("timings", {}).get("homotopy_seconds", 0.0)) for item in homotopy
            ),
            "certification": sum(
                float(item.get("timings", {}).get("certification_seconds", 0.0))
                for item in homotopy
            ),
            "elimination": sum(
                float(item.get("timings", {}).get("elimination_seconds", 0.0)) for item in homotopy
            ),
        },
        "peak_rss_kib_max": max((int(item.get("peak_rss_kib", 0)) for item in homotopy), default=0),
    }


def _compare(args: argparse.Namespace) -> int:
    rows = _load_dataset(args.dataset)
    if args.limit is not None:
        rows = rows[: max(0, int(args.limit))]
    cases: list[dict[str, Any]] = []
    started = time.monotonic()
    for ordinal, row in enumerate(rows):
        problem = dict(row["formulation"])
        current_first = ordinal % 2 == 0
        arms: dict[str, Any] = {}
        for arm in ["current", "homotopy"] if current_first else ["homotopy", "current"]:
            if arm == "current":
                arms[arm] = _current_control(problem, args.seconds, args.seed)
            else:
                arms[arm] = solve_problem(
                    problem, mode=args.mode, seconds=args.seconds, seed=args.seed
                )
        cases.append(
            {
                "ordinal": ordinal,
                "problem_id": row.get("problem_id", problem.get("id")),
                "order": "current_first" if current_first else "homotopy_first",
                "current": arms["current"],
                "homotopy": arms["homotopy"],
                "offline_score": {
                    "current": _arm_score(row, arms["current"]),
                    "homotopy": _arm_score(row, arms["homotopy"]),
                },
            }
        )
    summary = {
        "schema_version": "geotarget.homotopy-comparison/v1",
        "dataset": str(args.dataset),
        "dataset_sha256": hashlib.sha256(Path(args.dataset).read_bytes()).hexdigest(),
        "expected_development145_sha256": DATASET_SHA256,
        "mode": args.mode,
        "seconds": args.seconds,
        "seed": args.seed,
        "truth_blind": True,
        "official_scoring_stage": "offline_after_workers",
        "product_hash_check": _product_hash_check(),
        "elapsed_seconds": time.monotonic() - started,
        "metrics": _comparison_metrics(cases, args.seconds),
        "cases": cases,
    }
    _write_json(args.output, summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="homotopy-baseline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="report core/extended admission")
    analyze.add_argument("input")
    analyze.add_argument("--mode", choices=("core", "extended"), default="core")
    analyze.add_argument("--output")
    analyze.set_defaults(function=_analyze)

    solve = subparsers.add_parser("solve", help="run one HC + exact-certification solve")
    solve.add_argument("input")
    solve.add_argument("--mode", choices=("core", "extended"), default="core")
    solve.add_argument("--seconds", type=float, default=180.0)
    solve.add_argument("--seed", type=int, default=0)
    solve.add_argument("--output")
    solve.set_defaults(function=_solve)

    compare = subparsers.add_parser("compare", help="run paired current/homotopy workers")
    compare.add_argument("dataset")
    compare.add_argument("--mode", choices=("core", "extended"), default="core")
    compare.add_argument("--seconds", type=float, default=180.0)
    compare.add_argument("--seed", type=int, default=0)
    compare.add_argument("--limit", type=int)
    compare.add_argument("--output", required=True)
    compare.set_defaults(function=_compare)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.function(args))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"homotopy-baseline: {error}", file=sys.stderr)
        return 2


__all__ = ["build_parser", "main"]
