"""Research CLI: admission analysis, single solves, and paired comparisons."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from statistics import median
from typing import Any

import psutil

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
    result = solve_problem(
        problem,
        mode=args.mode,
        seconds=args.seconds,
        seed=args.seed,
        completeness=args.completeness,
    )
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


def _isolated_json_worker(
    problem: dict[str, Any],
    *,
    command_builder: Any,
    seconds: float,
    timeout_detail: str,
) -> dict[str, Any]:
    """Run one comparison arm with a hard wall and process-group cleanup."""

    started = time.monotonic()
    root = Path(__file__).resolve().parents[2]
    def terminate_tree(pid: int) -> None:
        try:
            root_process = psutil.Process(pid)
            descendants = root_process.children(recursive=True)
        except psutil.Error:
            descendants = []
        with suppress(ProcessLookupError):
            os.killpg(pid, signal.SIGTERM)
        for child in descendants:
            with suppress(psutil.Error):
                child.terminate()
        _gone, alive = psutil.wait_procs(descendants, timeout=3.0)
        with suppress(ProcessLookupError):
            os.killpg(pid, signal.SIGKILL)
        for child in alive:
            with suppress(psutil.Error):
                child.kill()

    with tempfile.TemporaryDirectory(prefix="geotarget-comparison-") as directory:
        workspace = Path(directory)
        source = workspace / "problem.json"
        output = workspace / "result.json"
        source.write_text(
            json.dumps(problem, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        command = command_builder(source, output)
        try:
            completed = subprocess.Popen(
                command,
                cwd=root,
                env=os.environ.copy(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                stdout, stderr = completed.communicate(timeout=max(0.1, float(seconds)))
            except subprocess.TimeoutExpired:
                terminate_tree(completed.pid)
                with suppress(subprocess.TimeoutExpired):
                    completed.wait(timeout=5.0)
                elapsed = time.monotonic() - started
                return {
                    "status": "timeout",
                    "detail": timeout_detail,
                    "elapsed_seconds": elapsed,
                    "harness_elapsed_seconds": elapsed,
                    "timings": {"total_seconds": elapsed},
                    "answers": [],
                }
        except OSError as error:
            elapsed = time.monotonic() - started
            return {
                "status": "engine_error",
                "detail": str(error),
                "elapsed_seconds": elapsed,
                "harness_elapsed_seconds": elapsed,
                "timings": {"total_seconds": elapsed},
                "answers": [],
            }
        if output.is_file():
            try:
                result = json.loads(output.read_text(encoding="utf-8"))
                if isinstance(result, dict):
                    result["harness_elapsed_seconds"] = time.monotonic() - started
                    if stderr:
                        result["harness_stderr_tail"] = stderr[-4000:]
                    return result
            except json.JSONDecodeError:
                pass
        elapsed = time.monotonic() - started
        return {
            "status": "engine_error",
            "detail": (stderr or stdout)[-4000:],
            "elapsed_seconds": elapsed,
            "harness_elapsed_seconds": elapsed,
            "timings": {"total_seconds": elapsed},
            "answers": [],
        }


def _current_control(problem: dict[str, Any], seconds: float, seed: int) -> dict[str, Any]:
    """Run the product control in an isolated, hard-deadline subprocess."""

    def command(source: Path, output: Path) -> list[str]:
        return [
            sys.executable,
            "-m",
            "geotarget.cli",
            "solve",
            str(source),
            "--engine",
            "optimized",
            "--run-mode",
            "fixed_time",
            "--max-time",
            str(max(180.0, float(seconds))),
            "--cores",
            "1",
            "--seed",
            str(int(seed)),
            "--output",
            str(output),
        ]

    return _isolated_json_worker(
        problem,
        command_builder=command,
        seconds=seconds,
        timeout_detail="current control exceeded the hard wall deadline",
    )


def _homotopy_control(
    problem: dict[str, Any], *, mode: str, completeness: str, seconds: float, seed: int
) -> dict[str, Any]:
    """Run the HC arm out-of-process so SymPy/Julia cannot overrun the cap."""

    def command(source: Path, output: Path) -> list[str]:
        return [
            sys.executable,
            "-m",
            "research.homotopy_baseline",
            "solve",
            str(source),
            "--mode",
            mode,
            "--completeness",
            completeness,
            "--seconds",
            str(float(seconds)),
            "--seed",
            str(int(seed)),
            "--output",
            str(output),
        ]

    return _isolated_json_worker(
        problem,
        command_builder=command,
        seconds=seconds,
        timeout_detail="homotopy arm exceeded the hard wall deadline",
    )


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


def _truth_values(row: dict[str, Any]) -> list[Any] | None:
    """Parse the frozen textual answer only in the post-worker scorer."""

    try:
        import sympy as sp

        raw = row.get("answer", "")
        values = raw if isinstance(raw, list) else [raw]
        result: list[Any] = []
        for item in values:
            value = sp.sympify(str(item), locals={"sqrt": sp.sqrt, "pi": sp.pi})
            if value.is_real is False:
                return None
            result.append(sp.N(value, 80))
        return result
    except Exception:
        return None


def _arm_score(row: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    expected = _truth_values(row)
    actual: list[Any] = []
    descriptors = result.get("answers")
    if not isinstance(descriptors, list):
        descriptors = result.get("distinct_exact_target_descriptors") or result.get(
            "distinct_exact_targets", []
        )
    for descriptor in descriptors:
        try:
            import sympy as sp

            # Product results may use exact rationals (for example ``81/29``)
            # while the HC arm normally emits a decimal expansion.  Parse the
            # descriptor as an expression first so both representations retain
            # exact meaning before the high-precision comparison.
            value = sp.sympify(
                str(descriptor["decimal"]),
                locals={"sqrt": sp.sqrt, "pi": sp.pi},
            )
            if value.is_real is False:
                continue
            actual.append(sp.N(value, 80))
        except (KeyError, TypeError, ValueError, SyntaxError):
            continue
    if expected is None:
        return {
            "truth_available": False,
            "exact_set_match": None,
            "exact_set_recall": None,
            "extra": None,
            "duplicate": None,
            "actual_count": len(actual),
            "expected_count": None,
        }
    import sympy as sp

    tolerance = sp.Float("1e-40", 80)
    matched = [False] * len(expected)
    extras = 0
    duplicates = 0
    for value in actual:
        candidates = [
            index
            for index, target in enumerate(expected)
            if not matched[index] and bool(abs(value - target) <= tolerance)
        ]
        if candidates:
            matched[candidates[0]] = True
        elif any(bool(abs(value - target) <= tolerance) for target in expected):
            duplicates += 1
        else:
            extras += 1
    return {
        "truth_available": True,
        "exact_set_match": bool(all(matched) and extras == 0),
        "exact_set_recall": sum(matched) / len(expected) if expected else 1.0,
        "extra": extras,
        "duplicate": duplicates,
        "actual_count": len(actual),
        "expected_count": len(expected),
    }


def _result_time(result: dict[str, Any], cap: float) -> float:
    if "harness_elapsed_seconds" in result:
        try:
            return float(result["harness_elapsed_seconds"])
        except (TypeError, ValueError):
            pass
    timings = result.get("timings")
    if isinstance(timings, dict) and "total_seconds" in timings:
        try:
            return float(timings["total_seconds"])
        except (TypeError, ValueError):
            pass
    try:
        return float(result.get("elapsed_seconds", cap))
    except (TypeError, ValueError):
        return cap


def _arm_metrics(cases: list[dict[str, Any]], arm: str, cap: float) -> dict[str, Any]:
    results = [case.get(arm, {}) for case in cases]
    scores = [case.get("offline_score", {}).get(arm, {}) for case in cases]
    available = [score for score in scores if score.get("truth_available")]
    statuses = [str(result.get("status", "unknown")) for result in results]
    if arm == "homotopy":
        # A subprocess timeout before admission has no ``admission`` payload;
        # it must not inflate the conditional success denominator.  Only a
        # completed polynomialized report with ``supported=true`` is admitted.
        admitted = [
            index
            for index, result in enumerate(results)
            if (result.get("admission") or {}).get("supported") is True
        ]
    else:
        admitted = [
            index
            for index, result in enumerate(results)
            if str(result.get("status")) not in {"unsupported", "invalid_problem"}
        ]
    times = [_result_time(result, cap) for result in results]
    ordered_times = sorted(times)
    p95_index = (
        max(0, min(len(ordered_times) - 1, math.ceil(0.95 * len(ordered_times)) - 1))
        if ordered_times
        else 0
    )
    exact_matches = [score.get("exact_set_match") is True for score in available]
    recalls = [float(score.get("exact_set_recall", 0.0)) for score in available]
    return {
        "case_count": len(cases),
        "truth_available_count": len(available),
        "admission_coverage": (
            len(admitted) / len(cases) if cases else 0.0
        ),
        "exact_complete_rate": (
            sum(status == "exact_complete" for status in statuses) / len(cases)
            if cases
            else 0.0
        ),
        "exact_set_match_count": sum(exact_matches),
        "exact_set_match_rate": sum(exact_matches) / len(available) if available else None,
        "exact_set_recall": sum(recalls) / len(recalls) if recalls else None,
        "extra_count": sum(int(score.get("extra", 0) or 0) for score in available),
        "duplicate_count": sum(int(score.get("duplicate", 0) or 0) for score in available),
        "answer_count": sum(
            len(result.get("answers", []))
            if isinstance(result.get("answers", []), list)
            else 0
            for result in results
        ),
        "conditional_answer_rate": (
            sum(bool(result.get("answers")) for result in (results[index] for index in admitted))
            / len(admitted)
            if admitted
            else None
        ),
        "conditional_exact_set_match_rate": (
            sum(scores[index].get("exact_set_match") is True for index in admitted)
            / sum(scores[index].get("truth_available") is True for index in admitted)
            if sum(scores[index].get("truth_available") is True for index in admitted)
            else None
        ),
        "status_counts": {
            status: statuses.count(status) for status in sorted(set(statuses))
        },
        "timeout_count": statuses.count("timeout"),
        "admission_timeout_count": sum(
            status == "timeout" and not (results[index].get("admission") or {})
            for index, status in enumerate(statuses)
        )
        if arm == "homotopy"
        else 0,
        "unsupported_count": statuses.count("unsupported"),
        "certification_failure_count": statuses.count("certification_failed"),
        "median_wall_seconds": median(times) if times else None,
        "p95_wall_seconds": ordered_times[p95_index] if ordered_times else None,
        "restricted_mean_wall_seconds": (
            sum(min(value, cap) for value in times) / len(times) if times else None
        ),
        "peak_rss_kib_max": max(
            (int(result.get("peak_rss_kib", 0)) for result in results), default=0
        ),
    }


def _comparison_metrics(cases: list[dict[str, Any]], cap: float) -> dict[str, Any]:
    current_success: dict[int, bool] = {}
    homotopy_success: dict[int, bool] = {}
    for index, case in enumerate(cases):
        current_score = case.get("offline_score", {}).get("current", {})
        homotopy_score = case.get("offline_score", {}).get("homotopy", {})
        if current_score.get("truth_available") and homotopy_score.get("truth_available"):
            current_success[index] = current_score.get("exact_set_match") is True
            homotopy_success[index] = homotopy_score.get("exact_set_match") is True
    b = sum(not current_success[index] and homotopy_success[index] for index in current_success)
    c = sum(current_success[index] and not homotopy_success[index] for index in current_success)
    statistic = ((abs(b - c) - 1) ** 2 / (b + c)) if b + c else 0.0
    p_value = math.erfc(math.sqrt(statistic / 2.0)) if b + c else 1.0
    homotopy = _arm_metrics(cases, "homotopy", cap)
    current = _arm_metrics(cases, "current", cap)
    return {
        "case_count": len(cases),
        "arms": {"current": current, "homotopy": homotopy},
        # Keep the homotopy fields at the top level for compatibility with the
        # exploratory reports produced before the target/completeness split.
        **homotopy,
        "paired_wins": b,
        "paired_losses": c,
        "mcnemar": {
            "truth_available_pairs": len(current_success),
            "b": b,
            "c": c,
            "chi_square_cc": statistic,
            "p_value_asymptotic": p_value,
        },
        "phase_seconds": {
            "compile": sum(
                float(case.get("homotopy", {}).get("timings", {}).get("compile_seconds", 0.0))
                for case in cases
            ),
            "homotopy": sum(
                float(case.get("homotopy", {}).get("timings", {}).get("homotopy_seconds", 0.0))
                for case in cases
            ),
            "certification": sum(
                float(
                    case.get("homotopy", {})
                    .get("timings", {})
                    .get("certification_seconds", 0.0)
                )
                for case in cases
            ),
            "elimination": sum(
                float(
                    case.get("homotopy", {})
                    .get("timings", {})
                    .get("elimination_seconds", 0.0)
                )
                for case in cases
            ),
        },
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
                arms[arm] = _homotopy_control(
                    problem,
                    mode=args.mode,
                    completeness=args.completeness,
                    seconds=args.seconds,
                    seed=args.seed,
                )
        cases.append(
            {
                "ordinal": ordinal,
                "problem_id": row.get("problem_id", problem.get("id")),
                "order": "current_first" if current_first else "homotopy_first",
                "current": arms["current"],
                "homotopy": arms["homotopy"],
                "_source_row": row,
            }
        )
        print(
            f"case {ordinal + 1}/{len(rows)} {cases[-1]['problem_id']} "
            f"current={arms['current'].get('status')} homotopy={arms['homotopy'].get('status')}",
            file=sys.stderr,
            flush=True,
        )
    # The truth-bearing answer is read only after every worker has terminated.
    # It is not passed into either solver arm, and it is not consulted for
    # admission, stopping, or candidate generation.
    for case, row in zip(cases, rows, strict=True):
        case["offline_score"] = {
            "current": _arm_score(row, case["current"]),
            "homotopy": _arm_score(row, case["homotopy"]),
        }
        case.pop("_source_row", None)
    summary = {
        "schema_version": "geotarget.homotopy-comparison/v1",
        "dataset": str(args.dataset),
        "dataset_sha256": hashlib.sha256(Path(args.dataset).read_bytes()).hexdigest(),
        "expected_development145_sha256": DATASET_SHA256,
        "mode": args.mode,
        "completeness_policy": args.completeness,
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
    solve.add_argument(
        "--completeness",
        choices=("complete", "target"),
        default="complete",
        help="global all-roots proof or target-only certified witness policy",
    )
    solve.add_argument("--seconds", type=float, default=180.0)
    solve.add_argument("--seed", type=int, default=0)
    solve.add_argument("--output")
    solve.set_defaults(function=_solve)

    compare = subparsers.add_parser("compare", help="run paired current/homotopy workers")
    compare.add_argument("dataset")
    compare.add_argument("--mode", choices=("core", "extended"), default="core")
    compare.add_argument(
        "--completeness",
        choices=("complete", "target"),
        default="complete",
        help="global all-roots proof or target-only certified witness policy",
    )
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
