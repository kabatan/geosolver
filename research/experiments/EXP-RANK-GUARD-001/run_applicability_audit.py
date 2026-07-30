#!/usr/bin/env python3
"""Static, truth-free applicability census for the charted rank/guard arm."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping, Sequence


DEFAULT_INPUT_DIRECTORY = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/results/"
    "current-baseline-development145-180s-seed0-20260722-v2/inputs"
)
FORBIDDEN_TOP_LEVEL_KEYS = {
    "gold",
    "expected",
    "expected_answer",
    "expected_descriptor",
    "result",
    "score",
    "scorer",
    "truth",
}
NONSMOOTH_OR_BRANCH_CALLS = {
    "abs",
    "angle",
    "ceil",
    "clip",
    "distance",
    "floor",
    "max",
    "min",
    "piecewise",
    "round",
    "sign",
}
STARTS = 256
CALLBACKS_PER_START = 600
AGGREGATE_CALLBACK_CAP = 153_600
BASELINE_PREFIX_FRACTION = 0.75
OVERLAY_CALLBACK_FRACTION_MAX = 0.05
OVERLAY_CALLBACK_ABSOLUTE_MAX = 64
PROPOSAL_RADIUS_COUNT = 2


def _call_name(call: ast.Call) -> str | None:
    function = call.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return None


def _number(node: ast.AST, *, lower_endpoint: bool) -> float | None:
    if isinstance(node, ast.Constant):
        if node.value is None:
            return -math.inf if lower_endpoint else math.inf
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _number(node.operand, lower_endpoint=lower_endpoint)
        if value is None:
            return None
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.Name):
        if node.id.lower() in {"inf", "infinity", "oo"}:
            return math.inf
        if node.id.lower() == "pi":
            return math.pi
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
    ):
        left = _number(node.left, lower_endpoint=lower_endpoint)
        right = _number(node.right, lower_endpoint=lower_endpoint)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if right == 0.0:
            return None
        return left / right
    return None


def _bound_guard(
    text: str,
) -> tuple[str, float, float, bool, bool] | None:
    try:
        expression = ast.parse(text, mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(expression, ast.Call) or _call_name(expression) != "Bound":
        return None
    if len(expression.args) < 2:
        return None
    variable_node, interval_node = expression.args[:2]
    if isinstance(variable_node, ast.Name):
        variable = variable_node.id
    elif isinstance(variable_node, ast.Constant) and isinstance(
        variable_node.value, str
    ):
        variable = variable_node.value
    else:
        return None
    if not isinstance(interval_node, (ast.Tuple, ast.List)) or len(
        interval_node.elts
    ) != 2:
        return None
    lower = _number(interval_node.elts[0], lower_endpoint=True)
    upper = _number(interval_node.elts[1], lower_endpoint=False)
    if lower is None or upper is None:
        return None
    inclusive = True
    for keyword in expression.keywords:
        if keyword.arg == "inclusive":
            if not isinstance(keyword.value, ast.Constant) or not isinstance(
                keyword.value.value, bool
            ):
                return None
            inclusive = keyword.value.value
    return variable, lower, upper, not inclusive, not inclusive


def _expression_strings(document: Mapping[str, object]) -> list[str]:
    expressions: list[str] = []
    construction = document.get("construction")
    if isinstance(construction, list):
        for item in construction:
            if isinstance(item, Mapping) and isinstance(item.get("expr"), str):
                expressions.append(str(item["expr"]))
    constraints = document.get("constraints")
    if isinstance(constraints, list):
        for item in constraints:
            if not isinstance(item, Mapping):
                continue
            for key in ("def", "value"):
                value = item.get(key)
                if isinstance(value, str):
                    expressions.append(value)
    return expressions


def _expression_features(expressions: Sequence[str]) -> tuple[set[str], bool, int]:
    calls: set[str] = set()
    has_branch_node = False
    parse_failures = 0
    for text in expressions:
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError:
            parse_failures += 1
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node)
                if name is not None:
                    calls.add(name.lower())
            elif isinstance(node, (ast.BoolOp, ast.Compare, ast.IfExp)):
                has_branch_node = True
    return calls, has_branch_node, parse_failures


def _guard_has_semantic_branch(guards: Sequence[object]) -> tuple[bool, int]:
    branch = False
    parse_failures = 0
    for raw in guards:
        if not isinstance(raw, str):
            parse_failures += 1
            continue
        try:
            tree = ast.parse(raw, mode="eval")
        except SyntaxError:
            parse_failures += 1
            continue
        if any(isinstance(node, (ast.BoolOp, ast.Compare, ast.IfExp)) for node in ast.walk(tree)):
            branch = True
    return branch, parse_failures


def _variable_names(document: Mapping[str, object]) -> list[str] | None:
    variables = document.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    if not isinstance(names, list) or not all(
        isinstance(name, str) and name for name in names
    ):
        return None
    if len(set(names)) != len(names):
        return None
    return list(names)


def _case_bound_summary(
    names: Sequence[str], guards: Sequence[object]
) -> tuple[Counter[str], bool, int]:
    bounds = {
        name: [-math.inf, math.inf, False, False]
        for name in names
    }
    parse_failures = 0
    valid = True
    for raw in guards:
        if not isinstance(raw, str) or not raw.lstrip().startswith("Bound("):
            continue
        parsed = _bound_guard(raw)
        if parsed is None:
            parse_failures += 1
            valid = False
            continue
        variable, lower, upper, lower_strict, upper_strict = parsed
        if variable not in bounds or not lower < upper:
            valid = False
            continue
        current = bounds[variable]
        if lower > current[0]:
            current[0] = lower
            current[2] = lower_strict
        elif lower == current[0]:
            current[2] = bool(current[2] or lower_strict)
        if upper < current[1]:
            current[1] = upper
            current[3] = upper_strict
        elif upper == current[1]:
            current[3] = bool(current[3] or upper_strict)
    categories: Counter[str] = Counter()
    for lower, upper, lower_strict, upper_strict in bounds.values():
        if lower > upper or (lower == upper and (lower_strict or upper_strict)):
            valid = False
            categories["invalid_or_empty"] += 1
        elif math.isfinite(lower) and math.isfinite(upper):
            if lower_strict and upper_strict:
                categories["two_sided_strict"] += 1
            else:
                categories["two_sided_with_inclusive_endpoint"] += 1
        elif math.isfinite(lower):
            if lower_strict:
                categories["lower_only_strict"] += 1
            else:
                categories["lower_only_inclusive"] += 1
        elif math.isfinite(upper):
            if upper_strict:
                categories["upper_only_strict"] += 1
            else:
                categories["upper_only_inclusive"] += 1
        else:
            categories["unbounded"] += 1
    return categories, valid, parse_failures


def _aggregate_digest(documents: Sequence[Mapping[str, object]]) -> str:
    hashes: list[bytes] = []
    for document in documents:
        canonical = (
            json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
        hashes.append(hashlib.sha256(canonical).digest())
    digest = hashlib.sha256(b"geotarget.rank-guard.id-stripped-formulations/v1\0")
    for item in sorted(hashes):
        digest.update(item)
    return digest.hexdigest()


def run_audit(input_directory: Path) -> dict[str, object]:
    paths = sorted(input_directory.glob("*.json"))
    if len(paths) != 145:
        raise RuntimeError("source-only development corpus must contain 145 files")

    documents: list[dict[str, object]] = []
    dimensions: Counter[int] = Counter()
    coordinate_categories: Counter[str] = Counter()
    case_bound_mixes: Counter[str] = Counter()
    structural_eligible = 0
    static_ineligible: Counter[str] = Counter()
    nonsmooth_guarded = 0
    semantic_branch_guarded = 0
    expression_parse_failures = 0
    guard_parse_failures = 0
    bound_parse_failures = 0
    overhead_by_callbacks: Counter[int] = Counter()

    callback_cap = min(STARTS * CALLBACKS_PER_START, AGGREGATE_CALLBACK_CAP)
    overlay_callback_budget = min(
        OVERLAY_CALLBACK_ABSOLUTE_MAX,
        math.floor(OVERLAY_CALLBACK_FRACTION_MAX * callback_cap),
    )
    baseline_minimum_slots = math.ceil(BASELINE_PREFIX_FRACTION * STARTS)
    baseline_reserved_callbacks = baseline_minimum_slots * CALLBACKS_PER_START

    for path in paths:
        raw = json.loads(path.read_bytes())
        if not isinstance(raw, dict) or raw.get("task") != "solve":
            raise RuntimeError("non-solve source formulation encountered")
        forbidden = FORBIDDEN_TOP_LEVEL_KEYS.intersection(
            str(key).lower() for key in raw
        )
        if forbidden:
            raise RuntimeError(f"forbidden evaluation field present: {sorted(forbidden)}")
        # Problem identity is discarded before any digest, feature, or count is
        # formed.  It is never copied into an audit record.
        document = dict(raw)
        document.pop("id", None)
        documents.append(document)

        names = _variable_names(document)
        if names is None:
            static_ineligible["malformed_variables"] += 1
            continue
        dimension = len(names)
        dimensions[dimension] += 1
        guards = document.get("guards")
        guard_values = guards if isinstance(guards, list) else []
        bound_summary, bounds_valid, bound_failures = _case_bound_summary(
            names, guard_values
        )
        bound_parse_failures += bound_failures
        coordinate_categories.update(bound_summary)
        active_categories = sorted(
            category for category, count in bound_summary.items() if count
        )
        case_bound_mixes["+".join(active_categories) or "zero_dimensional"] += 1

        calls, expression_branch, parse_failures = _expression_features(
            _expression_strings(document)
        )
        expression_parse_failures += parse_failures
        possible_nonsmooth = bool(
            calls.intersection(NONSMOOTH_OR_BRANCH_CALLS) or expression_branch
        )
        guard_branch, failures = _guard_has_semantic_branch(guard_values)
        guard_parse_failures += failures

        constraints = document.get("constraints")
        constraint_count = len(constraints) if isinstance(constraints, list) else -1
        required_callbacks = 1 + 4 * dimension + 2 * PROPOSAL_RADIUS_COUNT
        reasons: list[str] = []
        if dimension < 2:
            reasons.append("dimension_below_two")
        if constraint_count != dimension:
            reasons.append("nonsquare_residual_variable_system")
        if not bounds_valid:
            reasons.append("invalid_or_unparsed_bounds")
        if required_callbacks > overlay_callback_budget:
            reasons.append("rank_probe_exceeds_overlay_envelope")
        if callback_cap - required_callbacks < baseline_reserved_callbacks:
            reasons.append("baseline_callback_reservation_would_be_narrowed")
        if reasons:
            static_ineligible.update(set(reasons))
            continue
        structural_eligible += 1
        overhead_by_callbacks[required_callbacks] += 1
        if possible_nonsmooth:
            nonsmooth_guarded += 1
        if guard_branch:
            semantic_branch_guarded += 1

    if len(documents) != 145:
        raise RuntimeError("audit did not consume exactly 145 formulations")
    maximum_required = max(overhead_by_callbacks, default=0)
    aggregate_probe_callbacks = sum(
        callbacks * count for callbacks, count in overhead_by_callbacks.items()
    )
    evidence: dict[str, object] = {
        "schema_version": "geotarget.exp-rank-guard-001-applicability-audit/v1",
        "status": "PASS",
        "scope": {
            "formulation_count": 145,
            "source_only_json_files": True,
            "problem_id_discarded_before_feature_extraction": True,
            "problem_id_or_per_case_row_retained": False,
            "gold_expected_result_scorer_or_truth_read": False,
            "solver_evaluator_or_callback_executed": False,
            "formal_screen_run": False,
            "id_stripped_formulation_multiset_sha256": _aggregate_digest(documents),
        },
        "dimension_histogram": {
            str(key): dimensions[key] for key in sorted(dimensions)
        },
        "strict_bound_coordinates": {
            key: coordinate_categories[key]
            for key in (
                "two_sided_strict",
                "lower_only_strict",
                "upper_only_strict",
                "two_sided_with_inclusive_endpoint",
                "lower_only_inclusive",
                "upper_only_inclusive",
                "unbounded",
                "invalid_or_empty",
            )
        },
        "case_bound_mix_counts": {
            key: case_bound_mixes[key] for key in sorted(case_bound_mixes)
        },
        "rank_diagnostic_static_applicability": {
            "structurally_eligible_cases": structural_eligible,
            "actual_weak_rank_activation_count": None,
            "actual_activation_requires_charged_runtime_callbacks": True,
            "static_eligibility_is_not_an_activation_or_recall_claim": True,
            "ineligibility_reason_counts_nonexclusive": {
                key: static_ineligible[key] for key in sorted(static_ineligible)
            },
            "eligible_with_possible_nonsmooth_residual_dag": nonsmooth_guarded,
            "eligible_with_semantic_branch_guards": semantic_branch_guarded,
            "nonsmooth_or_branch_policy": (
                "h/h2 projector instability or semantic pair failure returns the "
                "original frozen prefix"
            ),
        },
        "callback_overhead_envelope": {
            "starts": STARTS,
            "callbacks_per_start": CALLBACKS_PER_START,
            "aggregate_callback_cap": callback_cap,
            "configured_fraction_limit": OVERLAY_CALLBACK_FRACTION_MAX,
            "absolute_callback_limit": OVERLAY_CALLBACK_ABSOLUTE_MAX,
            "effective_overlay_callback_limit": overlay_callback_budget,
            "effective_limit_percent_of_cap": (
                100.0 * overlay_callback_budget / callback_cap
            ),
            "baseline_minimum_slots": baseline_minimum_slots,
            "baseline_reserved_callbacks": baseline_reserved_callbacks,
            "maximum_static_probe_callbacks_per_eligible_case": maximum_required,
            "maximum_static_probe_percent_of_cap": (
                100.0 * maximum_required / callback_cap
            ),
            "probe_callback_histogram": {
                str(key): overhead_by_callbacks[key]
                for key in sorted(overhead_by_callbacks)
            },
            "aggregate_probe_callbacks_one_pass": aggregate_probe_callbacks,
            "all_eligible_cases_fit_effective_limit": (
                maximum_required <= overlay_callback_budget
            ),
            "baseline_reservation_preserved_for_all_eligible_cases": all(
                callback_cap - callbacks >= baseline_reserved_callbacks
                for callbacks in overhead_by_callbacks
            ),
        },
        "parser_diagnostics": {
            "bound_guard_parse_failures": bound_parse_failures,
            "residual_dag_expression_parse_failures": expression_parse_failures,
            "semantic_guard_parse_failures": guard_parse_failures,
        },
        "blockers": [
            "actual weak-rank/projector stability cannot be inferred from source bytes",
            "literal-prefix anchor semantic validity requires charged source evaluation",
            "nonsmoothness is a conservative operation-class flag, not a witnessed kink",
        ],
    }
    canonical = json.dumps(
        evidence, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    evidence["evidence_sha256"] = hashlib.sha256(canonical).hexdigest()
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-directory", type=Path, default=DEFAULT_INPUT_DIRECTORY)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    evidence = run_audit(arguments.input_directory.resolve())
    text = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(text, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
