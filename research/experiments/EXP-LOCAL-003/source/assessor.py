"""Independent outcome assessor and frozen statistics for EXP-LOCAL-003.

This module intentionally imports neither the case generator nor product solver
code.  The candidate process writes only opaque case keys and public execution
traces.  A later, physically separate process joins those traces to the
assessor-only Gold document through :func:`assess`.

The JSON interfaces are deliberately closed: unknown keys are errors.  See
``ASSESSOR_INTERFACE.md`` in this directory for the complete C2 runner
contract.
"""

from __future__ import annotations

import hashlib
import json
import math
import posixpath
import struct
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from geotarget.canonical import canonical_bytes

from bootstrap_indices import (
    FAMILY_IDS,
    REPLICATE_COUNT,
    BootstrapIndexTable,
    parse_bootstrap_index_bytes,
)


Stage = Literal["development", "locked"]
Path = Literal["recall", "efficiency"]

CANDIDATE_OUTPUT_SCHEMA: Final = "geotarget.exp-local-003.candidate-output/v1"
ASSESSOR_TRUTH_SCHEMA: Final = "geotarget.exp-local-003.assessor-truth/v1"
ASSESSMENT_SCHEMA: Final = "geotarget.exp-local-003.assessment/v1"
CARD_SHA256: Final = "0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c"

CONTROL: Final = "L0-SEMANTIC"
CANDIDATES: Final[tuple[str, ...]] = (
    "LX-BOUNDS",
    "LR-MODEL",
    "LXR-BOUNDS-MODEL",
)
ALL_VARIANTS: Final[tuple[str, ...]] = (CONTROL, *CANDIDATES)
MODEL_SCALE_VARIANTS: Final = frozenset(("LR-MODEL", "LXR-BOUNDS-MODEL"))
PRIMARY_REPRESENTATIONS: Final[tuple[str, ...]] = (
    "base",
    "signed-permutation",
    "semantic-equivalent-row-rescaling",
)
SAFETY_REPRESENTATION: Final = "orthogonal-safety"
PREFIXES: Final[tuple[int, ...]] = (8, 16, 32)
START_COUNT: Final = 32
MAX_LOCAL_ITERATIONS: Final = 250
MAX_LOCAL_EVALUATIONS: Final = 2_000
CALIBRATION_OBSERVATIONS: Final = 64
RECALL_NONINFERIORITY: Final = -0.02
RECALL_GAIN: Final = 0.05
ERT_REDUCTION: Final = 0.20
RECALL_PATH_MAX_RATIO: Final = 1.10
MINIMUM_POSITIVE_FAMILIES: Final = 3
SIMPLICITY_ORDER: Final = {variant: index for index, variant in enumerate(CANDIDATES)}

_HEX64 = frozenset("0123456789abcdef")
_FORBIDDEN_PATH_PARTS = frozenset(("assessor", "gold", "truth"))
_FORBIDDEN_CANDIDATE_STRINGS = frozenset(
    (
        *FAMILY_IDS,
        "signed-permutation",
        "semantic-equivalent-row-rescaling",
        SAFETY_REPRESENTATION,
    )
)


class InterfaceError(ValueError):
    """A candidate or assessor document violates the frozen C0 interface."""


class AssessmentError(ValueError):
    """An otherwise shaped document cannot be assessed under the frozen card."""


def _exact_keys(value: Mapping[str, Any], expected: set[str], context: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise InterfaceError(f"{context} keys differ; missing={missing}, extra={extra}")


def _mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise InterfaceError(f"{context} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise InterfaceError(f"{context} keys must be strings")
    return value


def _list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise InterfaceError(f"{context} must be an array")
    return value


def _integer(value: Any, context: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InterfaceError(f"{context} must be an integer >= {minimum}")
    return value


def _finite_number(value: Any, context: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InterfaceError(f"{context} must be a finite JSON number")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise InterfaceError(f"{context} must be finite and >= {minimum}")
    return result


def _sha256(value: Any, context: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _HEX64 for character in value)
    ):
        raise InterfaceError(f"{context} must be 64 lowercase hexadecimal digits")
    return value


def _opaque_key(value: Any, context: str) -> str:
    # A full digest prevents an ordinary semantic identifier from satisfying the
    # interface by accident.  Independence/randomness is enforced at C1.
    return _sha256(value, context)


def parse_finite_binary64_hex(value: Any, context: str) -> float:
    """Parse one canonical Python/Julia-compatible binary64 hexadecimal value."""

    if not isinstance(value, str):
        raise InterfaceError(f"{context} must be a binary64 hexadecimal string")
    try:
        parsed = float.fromhex(value)
    except ValueError as error:
        raise InterfaceError(f"{context} is not binary64 hexadecimal") from error
    if not math.isfinite(parsed) or parsed.hex() != value:
        raise InterfaceError(f"{context} must use canonical finite float.hex() form")
    return parsed


def model_scale_bytes(values_hex: Sequence[str]) -> bytes:
    """Canonical bytes whose SHA-256 binds one model-scale vector."""

    values = [
        parse_finite_binary64_hex(value, f"model_scale[{index}]")
        for index, value in enumerate(values_hex)
    ]
    return b"GTLOCAL3AVEC1\0" + struct.pack(">I", len(values)) + b"".join(
        struct.pack(">d", value) for value in values
    )


def model_scale_sha256(values_hex: Sequence[str]) -> str:
    return hashlib.sha256(model_scale_bytes(values_hex)).hexdigest()


def encode_extended_real(value: float) -> float | str:
    """Encode the only two permitted non-finite assessment values."""

    if math.isnan(value):
        raise InterfaceError("NaN has no EXP-LOCAL-003 JSON encoding")
    if value == math.inf:
        return "+Inf"
    if value == -math.inf:
        return "-Inf"
    return value


def decode_extended_real(value: Any, context: str = "extended real") -> float:
    if value == "+Inf":
        return math.inf
    if value == "-Inf":
        return -math.inf
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InterfaceError(f"{context} must be finite, '+Inf', or '-Inf'")
    result = float(value)
    if not math.isfinite(result):
        raise InterfaceError(f"{context} uses a forbidden nonstandard JSON number")
    return result


def _json_ready(value: Any) -> Any:
    if isinstance(value, float):
        return encode_extended_real(value)
    if isinstance(value, dict):
        return {key: _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(child) for child in value]
    return value


def strict_json_loads(payload: str | bytes) -> Any:
    """Load RFC JSON while rejecting NaN/Infinity numeric extensions."""

    def reject_constant(token: str) -> None:
        raise InterfaceError(f"nonstandard JSON numeric literal {token!r} is forbidden")

    try:
        return json.loads(payload, parse_constant=reject_constant)
    except json.JSONDecodeError as error:
        raise InterfaceError("invalid JSON") from error


def strict_json_dumps(value: Any) -> str:
    """RFC 8785 JCS with tagged extended-real values."""

    return canonical_bytes(_json_ready(value)).decode("utf-8")


def ert_reduction(baseline: float, candidate: float) -> float:
    """Frozen extended-real ERT-reduction rule from the card."""

    if math.isnan(baseline) or math.isnan(candidate):
        raise AssessmentError("ERT cannot be NaN")
    if baseline == math.inf:
        return 0.0 if candidate == math.inf else 1.0
    if not math.isfinite(baseline) or baseline <= 0.0:
        raise AssessmentError("every finite baseline ERT must be strictly positive")
    if candidate == math.inf:
        return -math.inf
    if not math.isfinite(candidate) or candidate < 0.0:
        raise AssessmentError("candidate ERT must be nonnegative or +Inf")
    return 1.0 - candidate / baseline


def ert_ratio(baseline: float, candidate: float) -> float:
    """Frozen candidate/L0 ratio, including +Inf/+Inf -> +Inf."""

    if math.isnan(baseline) or math.isnan(candidate):
        raise AssessmentError("ERT cannot be NaN")
    if candidate == math.inf:
        return math.inf
    if baseline == math.inf:
        return 0.0
    if not math.isfinite(baseline) or baseline <= 0.0:
        raise AssessmentError("every finite baseline ERT must be strictly positive")
    if not math.isfinite(candidate) or candidate < 0.0:
        raise AssessmentError("candidate ERT must be nonnegative or +Inf")
    return candidate / baseline


def nearest_rank_bounds(values: Sequence[float]) -> tuple[float, float]:
    """Items 5000 and 95000, one-indexed, from exactly 100000 values."""

    if len(values) != REPLICATE_COUNT:
        raise AssessmentError(
            f"bootstrap length {len(values)} != frozen {REPLICATE_COUNT}"
        )
    if any(math.isnan(value) for value in values):
        raise AssessmentError("bootstrap values contain NaN")
    ordered = sorted(values)
    return ordered[4_999], ordered[94_999]


def _normal_relative_path(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise InterfaceError(f"{context} must be a nonempty POSIX relative path")
    normalized = posixpath.normpath(value)
    if normalized != value or value.startswith("/") or normalized == ".." or normalized.startswith("../"):
        raise InterfaceError(f"{context} must be a normalized relative path")
    return value


def _validate_process_boundary(value: Any) -> None:
    boundary = _mapping(value, "candidate_process")
    _exact_keys(
        boundary,
        {"loaded_source_paths", "opened_artifact_paths"},
        "candidate_process",
    )
    loaded = _list(boundary["loaded_source_paths"], "loaded_source_paths")
    opened = _list(boundary["opened_artifact_paths"], "opened_artifact_paths")
    if not loaded:
        raise InterfaceError("candidate process must report at least one loaded source")
    for index, item in enumerate(loaded):
        path = _normal_relative_path(item, f"loaded_source_paths[{index}]")
        lowered_parts = {part.lower() for part in path.split("/")}
        if lowered_parts & _FORBIDDEN_PATH_PARTS:
            raise InterfaceError("candidate process loaded assessor/Gold/truth source")
    if not opened:
        raise InterfaceError("candidate process must report its opened candidate artifacts")
    for index, item in enumerate(opened):
        path = _normal_relative_path(item, f"opened_artifact_paths[{index}]")
        parts = path.split("/")
        if parts[0] != "candidate":
            raise InterfaceError("candidate process opened a non-candidate artifact root")
        if {part.lower() for part in parts} & _FORBIDDEN_PATH_PARTS:
            raise InterfaceError("candidate process opened assessor/Gold/truth artifact")


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def _validate_clamp_reasons(value: Any, residual_count: int, context: str) -> list[dict[str, bool]]:
    rows = _list(value, context)
    if len(rows) != residual_count:
        raise InterfaceError(f"{context} length differs from residual_count")
    result: list[dict[str, bool]] = []
    for index, item in enumerate(rows):
        row = _mapping(item, f"{context}[{index}]")
        _exact_keys(row, {"lower", "upper"}, f"{context}[{index}]")
        if not isinstance(row["lower"], bool) or not isinstance(row["upper"], bool):
            raise InterfaceError(f"{context}[{index}] flags must be booleans")
        if row["lower"] and row["upper"]:
            raise InterfaceError(f"{context}[{index}] cannot clamp both bounds")
        result.append({"lower": row["lower"], "upper": row["upper"]})
    return result


_FALLBACK_REASONS = frozenset(
    ("insufficient-valid-vectors", "nonfinite-nearest-rank", "nonpositive-nearest-rank")
)


def _validate_calibration(value: Any, residual_count: int, context: str) -> Mapping[str, Any]:
    calibration = _mapping(value, context)
    _exact_keys(
        calibration,
        {
            "observation_evaluation_costs",
            "valid_vector_count",
            "nearest_rank_hex",
            "model_scale_hex",
            "model_scale_sha256",
            "joint_fallback_reason",
            "clamp_reasons",
            "nonfinite_q_count",
            "nonfinite_q_misclassification_count",
        },
        context,
    )
    costs = _list(calibration["observation_evaluation_costs"], f"{context}.costs")
    if len(costs) != CALIBRATION_OBSERVATIONS:
        raise InterfaceError(f"{context} must contain exactly 64 observation costs")
    for index, cost in enumerate(costs):
        _integer(cost, f"{context}.costs[{index}]")
    valid_count = _integer(calibration["valid_vector_count"], f"{context}.valid_count")
    if valid_count > CALIBRATION_OBSERVATIONS:
        raise InterfaceError(f"{context}.valid_vector_count exceeds 64")
    nearest = _list(calibration["nearest_rank_hex"], f"{context}.nearest_rank_hex")
    scales = _list(calibration["model_scale_hex"], f"{context}.model_scale_hex")
    if len(nearest) != residual_count or len(scales) != residual_count:
        raise InterfaceError(f"{context} vector length differs from residual_count")
    for index, item in enumerate(nearest):
        parse_finite_binary64_hex(item, f"{context}.nearest_rank_hex[{index}]")
    parsed_scales = [
        parse_finite_binary64_hex(item, f"{context}.model_scale_hex[{index}]")
        for index, item in enumerate(scales)
    ]
    if any(item <= 0.0 for item in parsed_scales):
        raise InterfaceError(f"{context}.model_scale values must be positive")
    expected_digest = model_scale_sha256(scales)
    if _sha256(calibration["model_scale_sha256"], f"{context}.model_scale_sha256") != expected_digest:
        raise InterfaceError(f"{context}.model_scale_sha256 is not canonical")
    reason = calibration["joint_fallback_reason"]
    if reason is not None and reason not in _FALLBACK_REASONS:
        raise InterfaceError(f"{context}.joint_fallback_reason is unsupported")
    reasons = _validate_clamp_reasons(
        calibration["clamp_reasons"], residual_count, f"{context}.clamp_reasons"
    )
    if reason is not None:
        if any(item != 1.0 for item in parsed_scales) or any(
            row["lower"] or row["upper"] for row in reasons
        ):
            raise InterfaceError(f"{context} joint fallback must produce unclamped all-ones")
    _integer(calibration["nonfinite_q_count"], f"{context}.nonfinite_q_count")
    _integer(
        calibration["nonfinite_q_misclassification_count"],
        f"{context}.nonfinite_q_misclassification_count",
    )
    return calibration


def _validate_canonical(value: Any, variable_count: int, context: str) -> Mapping[str, Any]:
    canonical = _mapping(value, context)
    _exact_keys(
        canonical,
        {"valid", "configuration_hex", "target_hex", "branch_label", "evaluation_cost"},
        context,
    )
    if not isinstance(canonical["valid"], bool):
        raise InterfaceError(f"{context}.valid must be boolean")
    configuration = canonical["configuration_hex"]
    target = canonical["target_hex"]
    if configuration is not None:
        vector = _list(configuration, f"{context}.configuration_hex")
        if len(vector) != variable_count:
            raise InterfaceError(f"{context} configuration length differs from variable_count")
        for index, item in enumerate(vector):
            parse_finite_binary64_hex(item, f"{context}.configuration_hex[{index}]")
    if target is not None:
        parse_finite_binary64_hex(target, f"{context}.target_hex")
    if canonical["valid"] and (configuration is None or target is None):
        raise InterfaceError(f"{context} valid replay requires configuration and target")
    if canonical["branch_label"] is not None and not isinstance(canonical["branch_label"], str):
        raise InterfaceError(f"{context}.branch_label must be string or null")
    _integer(canonical["evaluation_cost"], f"{context}.evaluation_cost")
    return canonical


def _validate_attempt(value: Any, variable_count: int, context: str) -> Mapping[str, Any]:
    attempt = _mapping(value, context)
    _exact_keys(
        attempt,
        {
            "start_index",
            "iterations",
            "accepted",
            "local_observation_evaluation_costs",
            "canonical_replay",
        },
        context,
    )
    start_index = _integer(attempt["start_index"], f"{context}.start_index")
    if start_index >= START_COUNT:
        raise InterfaceError(f"{context}.start_index is out of range")
    _integer(attempt["iterations"], f"{context}.iterations")
    if not isinstance(attempt["accepted"], bool):
        raise InterfaceError(f"{context}.accepted must be boolean")
    costs = _list(
        attempt["local_observation_evaluation_costs"],
        f"{context}.local_observation_evaluation_costs",
    )
    for index, cost in enumerate(costs):
        _integer(cost, f"{context}.local_costs[{index}]")
    _validate_canonical(
        attempt["canonical_replay"], variable_count, f"{context}.canonical_replay"
    )
    return attempt


def _validate_variant_result(
    value: Any,
    variable_count: int,
    residual_count: int,
    context: str,
) -> Mapping[str, Any]:
    result = _mapping(value, context)
    _exact_keys(
        result,
        {
            "variant_id",
            "calibration",
            "attempts",
            "semantic_or_wire_drift_count",
            "identity_access_count",
        },
        context,
    )
    variant = result["variant_id"]
    if variant not in ALL_VARIANTS:
        raise InterfaceError(f"{context}.variant_id is unsupported")
    if variant in MODEL_SCALE_VARIANTS:
        if result["calibration"] is None:
            raise InterfaceError(f"{context} model-scale variant requires calibration")
        _validate_calibration(
            result["calibration"], residual_count, f"{context}.calibration"
        )
    elif result["calibration"] is not None:
        raise InterfaceError(f"{context} L0/LX must not execute calibration")
    attempts = _list(result["attempts"], f"{context}.attempts")
    if len(attempts) != START_COUNT:
        raise InterfaceError(f"{context} must contain exactly 32 attempts")
    indexes = []
    for index, attempt in enumerate(attempts):
        checked = _validate_attempt(
            attempt, variable_count, f"{context}.attempts[{index}]"
        )
        indexes.append(checked["start_index"])
    if sorted(indexes) != list(range(START_COUNT)):
        raise InterfaceError(f"{context} start indexes must be exactly 0..31")
    _integer(result["semantic_or_wire_drift_count"], f"{context}.semantic_or_wire_drift_count")
    _integer(result["identity_access_count"], f"{context}.identity_access_count")
    return result


def _validate_candidate_case(value: Any, expected_variants: set[str], context: str) -> Mapping[str, Any]:
    case = _mapping(value, context)
    _exact_keys(
        case,
        {
            "opaque_case_key",
            "variable_count",
            "residual_count",
            "logical_evaluation_cost",
            "variants",
        },
        context,
    )
    _opaque_key(case["opaque_case_key"], f"{context}.opaque_case_key")
    variable_count = _integer(
        case["variable_count"], f"{context}.variable_count", minimum=1
    )
    residual_count = _integer(
        case["residual_count"], f"{context}.residual_count", minimum=1
    )
    _integer(case["logical_evaluation_cost"], f"{context}.logical_evaluation_cost", minimum=1)
    variants = _list(case["variants"], f"{context}.variants")
    checked = [
        _validate_variant_result(
            item,
            variable_count,
            residual_count,
            f"{context}.variants[{index}]",
        )
        for index, item in enumerate(variants)
    ]
    ids = [item["variant_id"] for item in checked]
    if len(ids) != len(set(ids)) or set(ids) != expected_variants:
        raise InterfaceError(f"{context} variant topology differs from stage contract")
    return case


def _expected_variants(stage: Stage, truth: Mapping[str, Any]) -> set[str]:
    if stage == "development":
        if truth["locked_decision"] is not None:
            raise InterfaceError("development truth must have null locked_decision")
        return set(ALL_VARIANTS)
    decision = _mapping(truth["locked_decision"], "locked_decision")
    _exact_keys(decision, {"candidate_id", "development_path"}, "locked_decision")
    if decision["candidate_id"] not in CANDIDATES:
        raise InterfaceError("locked candidate_id is unsupported")
    if decision["development_path"] not in ("recall", "efficiency"):
        raise InterfaceError("locked development_path is unsupported")
    return {CONTROL, decision["candidate_id"]}


def validate_candidate_raw(document: Any, assessor_truth: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate the closed raw interface and candidate/assessor physical split."""

    candidate = _mapping(document, "candidate raw document")
    _exact_keys(
        candidate,
        {
            "schema_version",
            "stage",
            "candidate_input_sha256",
            "candidate_process",
            "cases",
            "report_only_times",
        },
        "candidate raw document",
    )
    if candidate["schema_version"] != CANDIDATE_OUTPUT_SCHEMA:
        raise InterfaceError("candidate output schema version mismatch")
    stage = candidate["stage"]
    if stage not in ("development", "locked") or stage != assessor_truth["stage"]:
        raise InterfaceError("candidate/assessor stage mismatch")
    if _sha256(candidate["candidate_input_sha256"], "candidate_input_sha256") != assessor_truth["candidate_input_sha256"]:
        raise InterfaceError("candidate/assessor input digest mismatch")
    _validate_process_boundary(candidate["candidate_process"])
    times = _mapping(candidate["report_only_times"], "report_only_times")
    _exact_keys(
        times,
        {"process_cpu_seconds", "end_to_end_cpu_seconds", "formal_wall_seconds", "host_exclusion_passed"},
        "report_only_times",
    )
    _finite_number(times["process_cpu_seconds"], "process_cpu_seconds")
    _finite_number(times["end_to_end_cpu_seconds"], "end_to_end_cpu_seconds")
    if times["formal_wall_seconds"] is not None:
        _finite_number(times["formal_wall_seconds"], "formal_wall_seconds")
    if not isinstance(times["host_exclusion_passed"], bool):
        raise InterfaceError("host_exclusion_passed must be boolean")
    expected_variants = _expected_variants(stage, assessor_truth)
    cases = _list(candidate["cases"], "candidate cases")
    checked = [
        _validate_candidate_case(item, expected_variants, f"candidate cases[{index}]")
        for index, item in enumerate(cases)
    ]
    keys = [item["opaque_case_key"] for item in checked]
    if len(keys) != len(set(keys)):
        raise InterfaceError("candidate opaque_case_key values are not unique")

    # Closed schemas prevent secret key names; this value check also catches a
    # family/group/representation label smuggled into an otherwise string field.
    truth_group_keys = {
        item["latent_group_key"] for item in assessor_truth["cases"]
    }
    forbidden_values = _FORBIDDEN_CANDIDATE_STRINGS | truth_group_keys
    leaked = sorted({value for value in _walk_strings(candidate) if value in forbidden_values})
    if leaked:
        raise InterfaceError(f"assessor-only identity leaked into candidate raw: {leaked}")
    return candidate


def _validate_gold_solution(
    value: Any, variable_count: int, context: str
) -> Mapping[str, Any]:
    solution = _mapping(value, context)
    _exact_keys(
        solution,
        {
            "configuration_hex",
            "target_hex",
            "configuration_abs_tolerance_hex",
            "target_abs_tolerance_hex",
            "branch_label",
        },
        context,
    )
    configuration = _list(solution["configuration_hex"], f"{context}.configuration_hex")
    if len(configuration) != variable_count:
        raise InterfaceError(f"{context} configuration length differs from variable_count")
    for index, item in enumerate(configuration):
        parse_finite_binary64_hex(item, f"{context}.configuration_hex[{index}]")
    parse_finite_binary64_hex(solution["target_hex"], f"{context}.target_hex")
    configuration_tolerance = parse_finite_binary64_hex(
        solution["configuration_abs_tolerance_hex"],
        f"{context}.configuration_abs_tolerance_hex",
    )
    target_tolerance = parse_finite_binary64_hex(
        solution["target_abs_tolerance_hex"],
        f"{context}.target_abs_tolerance_hex",
    )
    if configuration_tolerance < 0.0 or target_tolerance < 0.0:
        raise InterfaceError(f"{context} tolerances must be nonnegative")
    if solution["branch_label"] is not None and not isinstance(solution["branch_label"], str):
        raise InterfaceError(f"{context}.branch_label must be string or null")
    return solution


def _validate_expected_calibration(
    value: Any, residual_count: int, context: str
) -> Mapping[str, Any]:
    # Same closed record as candidate calibration.  Runtime costs are repeated
    # independently in truth so a candidate cannot invent cheap observations.
    return _validate_calibration(value, residual_count, context)


def _validate_truth_case(value: Any, context: str) -> Mapping[str, Any]:
    case = _mapping(value, context)
    _exact_keys(
        case,
        {
            "opaque_case_key",
            "family_id",
            "family_ordinal",
            "latent_group_index",
            "latent_group_key",
            "representation",
            "expected_invariant",
            "scale_from_base",
            "variable_count",
            "residual_count",
            "logical_evaluation_cost",
            "gold_solutions",
            "expected_calibration",
        },
        context,
    )
    _opaque_key(case["opaque_case_key"], f"{context}.opaque_case_key")
    family = case["family_id"]
    if family not in FAMILY_IDS:
        raise InterfaceError(f"{context}.family_id is unsupported")
    ordinal = _integer(case["family_ordinal"], f"{context}.family_ordinal")
    if ordinal >= len(FAMILY_IDS) or FAMILY_IDS[ordinal] != family:
        raise InterfaceError(f"{context}.family_ordinal disagrees with frozen order")
    _integer(case["latent_group_index"], f"{context}.latent_group_index")
    _opaque_key(case["latent_group_key"], f"{context}.latent_group_key")
    representation = case["representation"]
    if representation not in (*PRIMARY_REPRESENTATIONS, SAFETY_REPRESENTATION):
        raise InterfaceError(f"{context}.representation is unsupported")
    expected_invariant = case["expected_invariant"]
    if not isinstance(expected_invariant, bool):
        raise InterfaceError(f"{context}.expected_invariant must be boolean")
    if expected_invariant != (representation in PRIMARY_REPRESENTATIONS):
        raise InterfaceError(f"{context}.expected_invariant disagrees with representation")
    variable_count = _integer(
        case["variable_count"], f"{context}.variable_count", minimum=1
    )
    residual_count = _integer(
        case["residual_count"], f"{context}.residual_count", minimum=1
    )
    _integer(case["logical_evaluation_cost"], f"{context}.logical_evaluation_cost", minimum=1)
    permutation = case["scale_from_base"]
    if representation in PRIMARY_REPRESENTATIONS:
        values = _list(permutation, f"{context}.scale_from_base")
        if len(values) != residual_count or sorted(values) != list(range(residual_count)):
            raise InterfaceError(
                f"{context}.scale_from_base must permute residual_count rows"
            )
    elif permutation is not None:
        raise InterfaceError(f"{context} Safety representation has no hard scale permutation")
    solutions = _list(case["gold_solutions"], f"{context}.gold_solutions")
    if not solutions:
        raise InterfaceError(f"{context} must contain at least one Gold solution")
    for index, solution in enumerate(solutions):
        _validate_gold_solution(
            solution, variable_count, f"{context}.gold_solutions[{index}]"
        )
    _validate_expected_calibration(
        case["expected_calibration"],
        residual_count,
        f"{context}.expected_calibration",
    )
    return case


def validate_assessor_truth(document: Any) -> Mapping[str, Any]:
    """Validate Gold topology without consulting candidate source or generator."""

    truth = _mapping(document, "assessor truth")
    _exact_keys(
        truth,
        {
            "schema_version",
            "stage",
            "candidate_input_sha256",
            "bootstrap_sha256",
            "locked_decision",
            "cases",
        },
        "assessor truth",
    )
    if truth["schema_version"] != ASSESSOR_TRUTH_SCHEMA:
        raise InterfaceError("assessor truth schema version mismatch")
    stage = truth["stage"]
    if stage not in ("development", "locked"):
        raise InterfaceError("assessor stage is unsupported")
    _sha256(truth["candidate_input_sha256"], "candidate_input_sha256")
    _sha256(truth["bootstrap_sha256"], "bootstrap_sha256")
    _expected_variants(stage, truth)
    groups = 2 if stage == "development" else 4
    cases = _list(truth["cases"], "truth cases")
    expected_case_count = len(FAMILY_IDS) * groups * 4
    if len(cases) != expected_case_count:
        raise InterfaceError(
            f"truth case count {len(cases)} != frozen {expected_case_count}"
        )
    checked = [
        _validate_truth_case(item, f"truth cases[{index}]")
        for index, item in enumerate(cases)
    ]
    opaque_keys = [item["opaque_case_key"] for item in checked]
    if len(opaque_keys) != len(set(opaque_keys)):
        raise InterfaceError("truth opaque_case_key values are not unique")

    topology: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
    for case in checked:
        group_index = case["latent_group_index"]
        if group_index >= groups:
            raise InterfaceError("latent_group_index exceeds stage allocation")
        topology.setdefault((case["family_id"], group_index), []).append(case)
    expected_groups = {
        (family, group_index)
        for family in FAMILY_IDS
        for group_index in range(groups)
    }
    if set(topology) != expected_groups:
        raise InterfaceError("family/latent-group allocation differs from frozen topology")
    for key, rows in topology.items():
        representations = [row["representation"] for row in rows]
        if sorted(representations) != sorted((*PRIMARY_REPRESENTATIONS, SAFETY_REPRESENTATION)):
            raise InterfaceError(f"representation allocation differs for {key}")
        group_keys = {row["latent_group_key"] for row in rows}
        if len(group_keys) != 1:
            raise InterfaceError(f"latent_group_key differs within {key}")
        base = next(row for row in rows if row["representation"] == "base")
        if base["scale_from_base"] != list(range(base["residual_count"])):
            raise InterfaceError(f"base scale permutation is not identity for {key}")
        if any(
            row["variable_count"] != base["variable_count"]
            or row["residual_count"] != base["residual_count"]
            for row in rows
        ):
            raise InterfaceError(f"variable/residual counts differ within {key}")
    return truth


def validate_topology(candidate_raw: Any, assessor_truth: Any) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Strictly validate both projections and their opaque-key-only join."""

    truth = validate_assessor_truth(assessor_truth)
    candidate = validate_candidate_raw(candidate_raw, truth)
    candidate_keys = {case["opaque_case_key"] for case in candidate["cases"]}
    truth_keys = {case["opaque_case_key"] for case in truth["cases"]}
    if candidate_keys != truth_keys:
        missing = len(truth_keys - candidate_keys)
        extra = len(candidate_keys - truth_keys)
        raise InterfaceError(f"candidate/Gold opaque join differs; missing={missing}, extra={extra}")
    candidate_cases = {case["opaque_case_key"]: case for case in candidate["cases"]}
    for index, truth_case in enumerate(truth["cases"]):
        candidate_case = candidate_cases[truth_case["opaque_case_key"]]
        for field in (
            "variable_count",
            "residual_count",
            "logical_evaluation_cost",
        ):
            if candidate_case[field] != truth_case[field]:
                raise InterfaceError(f"candidate/Gold {field} differs at truth case {index}")
    return candidate, truth


def _hex_vector(value: Sequence[str], context: str) -> list[float]:
    return [
        parse_finite_binary64_hex(item, f"{context}[{index}]")
        for index, item in enumerate(value)
    ]


def _gold_valid(attempt: Mapping[str, Any], truth_case: Mapping[str, Any]) -> bool:
    """Independent configuration/target/branch match; solver status is not truth."""

    if not attempt["accepted"]:
        return False
    canonical = attempt["canonical_replay"]
    if not canonical["valid"]:
        return False
    if canonical["configuration_hex"] is None or canonical["target_hex"] is None:
        return False
    configuration = _hex_vector(canonical["configuration_hex"], "canonical configuration")
    target = parse_finite_binary64_hex(canonical["target_hex"], "canonical target")
    for solution in truth_case["gold_solutions"]:
        gold_configuration = _hex_vector(solution["configuration_hex"], "Gold configuration")
        gold_target = parse_finite_binary64_hex(solution["target_hex"], "Gold target")
        configuration_tolerance = parse_finite_binary64_hex(
            solution["configuration_abs_tolerance_hex"], "configuration tolerance"
        )
        target_tolerance = parse_finite_binary64_hex(
            solution["target_abs_tolerance_hex"], "target tolerance"
        )
        branch_matches = (
            solution["branch_label"] is None
            or canonical["branch_label"] == solution["branch_label"]
        )
        if (
            max(
                abs(actual - expected)
                for actual, expected in zip(configuration, gold_configuration, strict=True)
            )
            <= configuration_tolerance
            and abs(target - gold_target) <= target_tolerance
            and branch_matches
        ):
            return True
    return False


@dataclass(frozen=True)
class AttemptAssessment:
    accepted: bool
    canonical_valid: bool
    gold_valid: bool
    successful_work: int
    failure_work: int
    budget_overrun: bool

    @property
    def decision(self) -> tuple[bool, bool, bool]:
        return self.accepted, self.canonical_valid, self.gold_valid


@dataclass(frozen=True)
class CaseVariantAssessment:
    attempts: tuple[AttemptAssessment, ...]
    calibration_work: int
    calibration_audit_failures: int
    semantic_or_wire_drift_count: int
    identity_access_count: int
    nonfinite_q_misclassification_count: int


@dataclass(frozen=True)
class Pool:
    work: int
    successes: int

    @property
    def ert(self) -> float:
        return self.work / self.successes if self.successes else math.inf

    def __add__(self, other: "Pool") -> "Pool":
        return Pool(self.work + other.work, self.successes + other.successes)


@dataclass(frozen=True)
class GroupRecord:
    recall_effect: float
    baseline_pool: Pool
    candidate_pool: Pool


def _calibration_differences(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> int:
    fields = (
        "observation_evaluation_costs",
        "valid_vector_count",
        "nearest_rank_hex",
        "model_scale_hex",
        "model_scale_sha256",
        "joint_fallback_reason",
        "clamp_reasons",
        "nonfinite_q_count",
    )
    return sum(actual[field] != expected[field] for field in fields)


def _assess_case_variant(
    candidate_case: Mapping[str, Any],
    truth_case: Mapping[str, Any],
    result: Mapping[str, Any],
) -> CaseVariantAssessment:
    logical_cost = candidate_case["logical_evaluation_cost"]
    attempts_by_index = {attempt["start_index"]: attempt for attempt in result["attempts"]}
    assessments: list[AttemptAssessment] = []
    for start_index in range(START_COUNT):
        attempt = attempts_by_index[start_index]
        canonical = attempt["canonical_replay"]
        gold_valid = _gold_valid(attempt, truth_case)
        replay_cost = canonical["evaluation_cost"]
        successful_work = sum(attempt["local_observation_evaluation_costs"]) + replay_cost
        failure_work = MAX_LOCAL_EVALUATIONS * logical_cost + replay_cost
        assessments.append(
            AttemptAssessment(
                accepted=attempt["accepted"],
                canonical_valid=canonical["valid"],
                gold_valid=gold_valid,
                successful_work=successful_work,
                failure_work=failure_work,
                budget_overrun=(
                    len(attempt["local_observation_evaluation_costs"])
                    > MAX_LOCAL_EVALUATIONS
                    or attempt["iterations"] > MAX_LOCAL_ITERATIONS
                ),
            )
        )
    calibration_work = 0
    calibration_failures = 0
    nonfinite_misclassification = 0
    if result["variant_id"] in MODEL_SCALE_VARIANTS:
        calibration = result["calibration"]
        calibration_work = sum(calibration["observation_evaluation_costs"])
        calibration_failures = _calibration_differences(
            calibration, truth_case["expected_calibration"]
        )
        nonfinite_misclassification = calibration[
            "nonfinite_q_misclassification_count"
        ]
    return CaseVariantAssessment(
        attempts=tuple(assessments),
        calibration_work=calibration_work,
        calibration_audit_failures=calibration_failures,
        semantic_or_wire_drift_count=result["semantic_or_wire_drift_count"],
        identity_access_count=result["identity_access_count"],
        nonfinite_q_misclassification_count=nonfinite_misclassification,
    )


def _prefix_pool(record: CaseVariantAssessment, prefix: int) -> Pool:
    work = record.calibration_work
    successes = 0
    for attempt in record.attempts[:prefix]:
        if attempt.gold_valid:
            work += attempt.successful_work
            successes += 1
        else:
            work += attempt.failure_work
    return Pool(work, successes)


def _build_group_records(
    assessed: Mapping[tuple[str, str], CaseVariantAssessment],
    truth: Mapping[str, Any],
    candidate: str,
    prefix: int,
) -> dict[tuple[int, int], GroupRecord]:
    primary: dict[tuple[int, int], list[Mapping[str, Any]]] = {}
    for case in truth["cases"]:
        if case["representation"] in PRIMARY_REPRESENTATIONS:
            key = (case["family_ordinal"], case["latent_group_index"])
            primary.setdefault(key, []).append(case)
    result: dict[tuple[int, int], GroupRecord] = {}
    for key, cases in primary.items():
        if len(cases) != len(PRIMARY_REPRESENTATIONS):
            raise AssessmentError(f"primary group {key} is incomplete")
        control_pool = Pool(0, 0)
        candidate_pool = Pool(0, 0)
        difference = 0
        for case in cases:
            opaque = case["opaque_case_key"]
            control_record = assessed[(opaque, CONTROL)]
            candidate_record = assessed[(opaque, candidate)]
            control_pool += _prefix_pool(control_record, prefix)
            candidate_pool += _prefix_pool(candidate_record, prefix)
            difference += sum(
                int(candidate_attempt.gold_valid) - int(control_attempt.gold_valid)
                for candidate_attempt, control_attempt in zip(
                    candidate_record.attempts[:prefix],
                    control_record.attempts[:prefix],
                    strict=True,
                )
            )
        result[key] = GroupRecord(
            recall_effect=difference / (len(PRIMARY_REPRESENTATIONS) * prefix),
            baseline_pool=control_pool,
            candidate_pool=candidate_pool,
        )
    return result


def _sum_pools(records: Iterable[GroupRecord], attribute: str) -> Pool:
    result = Pool(0, 0)
    for record in records:
        result += getattr(record, attribute)
    return result


def _bootstrap_statistics(
    groups: Mapping[tuple[int, int], GroupRecord],
    table: BootstrapIndexTable,
) -> dict[str, Any]:
    recall_values: list[float] = []
    reduction_values: list[float] = []
    groups_per_family = table.groups_per_family
    expected_keys = {
        (family, group)
        for family in range(len(FAMILY_IDS))
        for group in range(groups_per_family)
    }
    if set(groups) != expected_keys:
        raise AssessmentError("group records differ from bootstrap topology")
    for replicate in range(REPLICATE_COUNT):
        recall_sum = 0.0
        baseline_pool = Pool(0, 0)
        candidate_pool = Pool(0, 0)
        for family in range(len(FAMILY_IDS)):
            for draw in range(groups_per_family):
                group = table.index(replicate, family, draw)
                record = groups[(family, group)]
                recall_sum += record.recall_effect
                baseline_pool += record.baseline_pool
                candidate_pool += record.candidate_pool
        recall_values.append(
            recall_sum / (len(FAMILY_IDS) * groups_per_family)
        )
        reduction_values.append(
            ert_reduction(baseline_pool.ert, candidate_pool.ert)
        )
    recall_lower, recall_upper = nearest_rank_bounds(recall_values)
    reduction_lower, reduction_upper = nearest_rank_bounds(reduction_values)
    return {
        "recall_lower": recall_lower,
        "recall_upper": recall_upper,
        "ert_reduction_lower": reduction_lower,
        "ert_reduction_upper": reduction_upper,
    }


def _prefix_statistics(
    assessed: Mapping[tuple[str, str], CaseVariantAssessment],
    truth: Mapping[str, Any],
    candidate: str,
    prefix: int,
    table: BootstrapIndexTable,
) -> dict[str, Any]:
    groups = _build_group_records(assessed, truth, candidate, prefix)
    point_recall = sum(record.recall_effect for record in groups.values()) / len(groups)
    baseline_pool = _sum_pools(groups.values(), "baseline_pool")
    candidate_pool = _sum_pools(groups.values(), "candidate_pool")
    family_rows: list[dict[str, Any]] = []
    for family_ordinal, family_id in enumerate(FAMILY_IDS):
        selected = [
            groups[(family_ordinal, group)]
            for group in range(table.groups_per_family)
        ]
        family_recall = sum(record.recall_effect for record in selected) / len(selected)
        family_baseline = _sum_pools(selected, "baseline_pool")
        family_candidate = _sum_pools(selected, "candidate_pool")
        family_rows.append(
            {
                "family_id": family_id,
                "recall_delta": family_recall,
                "baseline_ert": family_baseline.ert,
                "candidate_ert": family_candidate.ert,
                "ert_reduction": ert_reduction(
                    family_baseline.ert, family_candidate.ert
                ),
            }
        )
    result = {
        "prefix": prefix,
        "recall_delta": point_recall,
        "baseline_ert": baseline_pool.ert,
        "candidate_ert": candidate_pool.ert,
        "ert_ratio": ert_ratio(baseline_pool.ert, candidate_pool.ert),
        "ert_reduction": ert_reduction(baseline_pool.ert, candidate_pool.ert),
        "families": family_rows,
    }
    result.update(_bootstrap_statistics(groups, table))
    return result


def _variant_results_by_case(candidate: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    for case in candidate["cases"]:
        for variant in case["variants"]:
            result[(case["opaque_case_key"], variant["variant_id"])] = variant
    return result


def _primary_disagreements(
    assessed: Mapping[tuple[str, str], CaseVariantAssessment],
    raw_results: Mapping[tuple[str, str], Mapping[str, Any]],
    truth: Mapping[str, Any],
    variant: str,
) -> list[dict[str, Any]]:
    groups: dict[tuple[int, int], list[Mapping[str, Any]]] = {}
    for case in truth["cases"]:
        if case["representation"] in PRIMARY_REPRESENTATIONS:
            groups.setdefault(
                (case["family_ordinal"], case["latent_group_index"]), []
            ).append(case)
    disagreements: list[dict[str, Any]] = []
    for (family, group), cases in sorted(groups.items()):
        by_representation = {case["representation"]: case for case in cases}
        for start in range(START_COUNT):
            decisions = {
                representation: assessed[(case["opaque_case_key"], variant)].attempts[
                    start
                ].decision
                for representation, case in by_representation.items()
            }
            if len(set(decisions.values())) != 1:
                disagreements.append(
                    {
                        "kind": "decision",
                        "family_ordinal": family,
                        "latent_group_index": group,
                        "start_index": start,
                    }
                )
        if variant in MODEL_SCALE_VARIANTS:
            base_case = by_representation["base"]
            base_scale = raw_results[(base_case["opaque_case_key"], variant)][
                "calibration"
            ]["model_scale_hex"]
            for representation, case in by_representation.items():
                actual = raw_results[(case["opaque_case_key"], variant)][
                    "calibration"
                ]["model_scale_hex"]
                expected = [base_scale[index] for index in case["scale_from_base"]]
                if actual != expected:
                    disagreements.append(
                        {
                            "kind": "calibration-scale-permutation",
                            "family_ordinal": family,
                            "latent_group_index": group,
                            "representation": representation,
                        }
                    )
    return disagreements


def _orthogonal_safety_disagreements(
    assessed: Mapping[tuple[str, str], CaseVariantAssessment],
    truth: Mapping[str, Any],
    variant: str,
) -> list[dict[str, int]]:
    groups: dict[tuple[int, int], dict[str, Mapping[str, Any]]] = {}
    for case in truth["cases"]:
        groups.setdefault(
            (case["family_ordinal"], case["latent_group_index"]), {}
        )[case["representation"]] = case
    disagreements: list[dict[str, int]] = []
    for (family, group), cases in sorted(groups.items()):
        base = assessed[(cases["base"]["opaque_case_key"], variant)]
        safety = assessed[(cases[SAFETY_REPRESENTATION]["opaque_case_key"], variant)]
        for start in range(START_COUNT):
            if base.attempts[start].decision != safety.attempts[start].decision:
                disagreements.append(
                    {
                        "family_ordinal": family,
                        "latent_group_index": group,
                        "start_index": start,
                    }
                )
    return disagreements


def _variant_safety(
    assessed: Mapping[tuple[str, str], CaseVariantAssessment],
    raw_results: Mapping[tuple[str, str], Mapping[str, Any]],
    truth: Mapping[str, Any],
    variant: str,
) -> dict[str, Any]:
    records = [
        assessed[(case["opaque_case_key"], variant)] for case in truth["cases"]
    ]
    false_candidates = sum(
        attempt.accepted and (not attempt.canonical_valid or not attempt.gold_valid)
        for record in records
        for attempt in record.attempts
    )
    primary = _primary_disagreements(assessed, raw_results, truth, variant)
    orthogonal = _orthogonal_safety_disagreements(assessed, truth, variant)
    return {
        "false_candidate_count": false_candidates,
        "semantic_or_wire_drift_count": sum(
            record.semantic_or_wire_drift_count for record in records
        ),
        "gold_or_identity_leak_count": sum(
            record.identity_access_count for record in records
        ),
        "budget_overrun_count": sum(
            attempt.budget_overrun for record in records for attempt in record.attempts
        ),
        "primary_representation_disagreement_count": len(primary),
        "primary_representation_disagreements": primary,
        "calibration_audit_failure_count": sum(
            record.calibration_audit_failures
            + record.nonfinite_q_misclassification_count
            for record in records
        ),
        "orthogonal_safety_disagreement_count": len(orthogonal),
        "orthogonal_safety_disagreements": orthogonal,
    }


_HARD_SAFETY_COUNTS = (
    "false_candidate_count",
    "semantic_or_wire_drift_count",
    "gold_or_identity_leak_count",
    "budget_overrun_count",
    "primary_representation_disagreement_count",
    "calibration_audit_failure_count",
)


def _pair_safety_passes(control: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    return all(control[key] == 0 and candidate[key] == 0 for key in _HARD_SAFETY_COUNTS)


def _common_noninferiority(prefix_rows: Sequence[Mapping[str, Any]]) -> bool:
    return all(
        row["recall_lower"] >= RECALL_NONINFERIORITY
        and all(
            family["recall_delta"] >= RECALL_NONINFERIORITY
            for family in row["families"]
        )
        for row in prefix_rows
    )


def _positive_family_count(prefix32: Mapping[str, Any], path: Path) -> int:
    if path == "recall":
        return sum(family["recall_delta"] > 0.0 for family in prefix32["families"])
    return sum(
        family["recall_delta"] >= RECALL_NONINFERIORITY
        and family["ert_reduction"] > 0.0
        for family in prefix32["families"]
    )


def _evaluate_paths(
    prefix_rows: Sequence[Mapping[str, Any]],
    *,
    hard_safety_passed: bool,
) -> dict[str, Any]:
    by_prefix = {row["prefix"]: row for row in prefix_rows}
    prefix32 = by_prefix[32]
    common = hard_safety_passed and _common_noninferiority(prefix_rows)
    recall_positive = _positive_family_count(prefix32, "recall")
    efficiency_positive = _positive_family_count(prefix32, "efficiency")
    recall_core = (
        prefix32["recall_delta"] >= RECALL_GAIN
        and prefix32["recall_lower"] >= 0.0
        and prefix32["ert_ratio"] <= RECALL_PATH_MAX_RATIO
    )
    efficiency_core = (
        prefix32["recall_lower"] >= RECALL_NONINFERIORITY
        and prefix32["ert_reduction_lower"] >= ERT_REDUCTION
    )
    recall_passed = (
        common and recall_core and recall_positive >= MINIMUM_POSITIVE_FAMILIES
    )
    efficiency_passed = (
        common
        and efficiency_core
        and efficiency_positive >= MINIMUM_POSITIVE_FAMILIES
    )
    return {
        "common_noninferiority_passed": _common_noninferiority(prefix_rows),
        "hard_safety_passed": hard_safety_passed,
        "recall": {
            "core_passed": recall_core,
            "positive_family_count": recall_positive,
            "passed": recall_passed,
        },
        "efficiency": {
            "core_passed": efficiency_core,
            "positive_family_count": efficiency_positive,
            "passed": efficiency_passed,
        },
    }


def _select_development_champion(candidate_rows: Mapping[str, Mapping[str, Any]]) -> tuple[str | None, str | None]:
    recall = [
        (variant, row)
        for variant, row in candidate_rows.items()
        if row["paths"]["recall"]["passed"]
    ]
    if recall:
        recall.sort(
            key=lambda item: (
                -item[1]["prefixes"][-1]["recall_lower"],
                item[1]["prefixes"][-1]["candidate_ert"],
                SIMPLICITY_ORDER[item[0]],
            )
        )
        return recall[0][0], "recall"
    efficiency = [
        (variant, row)
        for variant, row in candidate_rows.items()
        if row["paths"]["efficiency"]["passed"]
    ]
    if efficiency:
        efficiency.sort(
            key=lambda item: (
                -item[1]["prefixes"][-1]["ert_reduction_lower"],
                -item[1]["prefixes"][-1]["recall_delta"],
                SIMPLICITY_ORDER[item[0]],
            )
        )
        return efficiency[0][0], "efficiency"
    return None, None


def assess(
    raw_document: Any,
    assessor_truth: Any,
    bootstrap_bytes: bytes,
) -> dict[str, Any]:
    """Assess one sealed candidate output against physically separate Gold.

    Only this assessor process receives ``assessor_truth``.  All returned
    extended-real values are the JSON-safe strings ``+Inf``/``-Inf``.
    """

    candidate, truth = validate_topology(raw_document, assessor_truth)
    stage: Stage = truth["stage"]
    table = parse_bootstrap_index_bytes(
        bootstrap_bytes,
        expected_stage=stage,
        expected_sha256=truth["bootstrap_sha256"],
    )
    candidate_cases = {case["opaque_case_key"]: case for case in candidate["cases"]}
    raw_results = _variant_results_by_case(candidate)
    assessed: dict[tuple[str, str], CaseVariantAssessment] = {}
    expected_variants = _expected_variants(stage, truth)
    for truth_case in truth["cases"]:
        opaque = truth_case["opaque_case_key"]
        candidate_case = candidate_cases[opaque]
        for variant in expected_variants:
            assessed[(opaque, variant)] = _assess_case_variant(
                candidate_case,
                truth_case,
                raw_results[(opaque, variant)],
            )

    safety = {
        variant: _variant_safety(assessed, raw_results, truth, variant)
        for variant in sorted(expected_variants, key=ALL_VARIANTS.index)
    }
    tested_candidates = [variant for variant in CANDIDATES if variant in expected_variants]
    candidate_rows: dict[str, dict[str, Any]] = {}
    for variant in tested_candidates:
        prefix_rows = [
            _prefix_statistics(assessed, truth, variant, prefix, table)
            for prefix in PREFIXES
        ]
        pair_safety = _pair_safety_passes(safety[CONTROL], safety[variant])
        candidate_rows[variant] = {
            "prefixes": prefix_rows,
            "paths": _evaluate_paths(prefix_rows, hard_safety_passed=pair_safety),
        }

    selected_variant: str | None
    selected_path: str | None
    if stage == "development":
        selected_variant, selected_path = _select_development_champion(candidate_rows)
        stage_passed = selected_variant is not None
    else:
        locked = truth["locked_decision"]
        selected_variant = locked["candidate_id"]
        selected_path = locked["development_path"]
        stage_passed = candidate_rows[selected_variant]["paths"][selected_path]["passed"]

    # Orthogonal Safety is deliberately outside selection, but every observed
    # disagreement blocks a later product connection.
    orthogonal_total = sum(
        row["orthogonal_safety_disagreement_count"] for row in safety.values()
    )
    result = {
        "schema_version": ASSESSMENT_SCHEMA,
        "card_sha256": CARD_SHA256,
        "stage": stage,
        "bootstrap_sha256": table.sha256,
        "bootstrap_replicates": REPLICATE_COUNT,
        "safety": safety,
        "candidates": candidate_rows,
        "selected_variant": selected_variant,
        "selected_path": selected_path,
        "stage_passed": stage_passed,
        "orthogonal_safety_disagreement_count": orthogonal_total,
        "product_connection_allowed": stage_passed and orthogonal_total == 0,
        "report_only_times": candidate["report_only_times"],
    }
    # Round-trip through strict JSON makes tagged extended values part of the
    # function contract and proves no nonstandard numeric literal escaped.
    return strict_json_loads(strict_json_dumps(result))


if __name__ == "__main__":
    raise SystemExit(
        "assessor.py is a library; the C3 assessor process must call assess() once"
    )
