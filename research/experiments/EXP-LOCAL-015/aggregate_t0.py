#!/usr/bin/env python3
"""Independent, stdlib-only aggregation for EXP-LOCAL-015 T0.

The experiment card is the contract.  The runner must emit 63 one-case JSON
shards with this deliberately small schema::

    {
      "schema_version": "geotarget.exp-local-015-t0-raw/v1",
      "experiment_id": "EXP-LOCAL-015",
      "nonpromotional_t0": true,
      "case_count": 63,
      "case_index": 1,
      "corpus_checksum": "...",
      "preregistration": {"path": "...", "sha256": "..."},
      "revision": {"git_head": "...", "git_dirty": false},
      "runtime_contract": {
        "julia_version": "...",
        "active_project_path": "research/experiments/EXP-LOCAL-002/Project.toml",
        "project_sha256": "...",
        "manifest_sha256": "..."
      },
      "case": {
        "representation_class_id": "base-fixture-identity",
        "representation": "base|signed_permutation|orthogonal",
        "stratum_id": "assessor-side parameterized stratum"
      },
      "arm_order": [<the eight frozen arm names below>],
      "shared_prefilter_physical_evaluations": 16,
      "thread_contract": {
        "assigned_cpu": 0,
        "blas_threads": 1,
        "julia_threads": 1,
        "openblas_env_threads": 1,
        "omp_env_threads": 1,
        "mkl_env_threads": 1,
        "solver_worker_count": 1,
        "within_case_parallelism": false
      },
      "rows": [<exactly 16 starts x eight arms>]
    }

Every row must contain ``arm``, ``start_index`` (1..16), ``candidate_input``,
``truth_free_replay_digest`` (the canonical JSON SHA-256 of recursively
type-normalized candidate_input),
``status``, ``reason``, a bool-valued ``activation_observables`` object,
``emission_kind`` (none/bracket_seed/refinement_seed), rescue precision
callback counts, shared-prefilter counts, rescue/shared/total callback/work
ledgers, independently observed rescue/shared precision ledgers,
``emitted_seed_coordinates`` (all bracket or refinement starts), full
``emitted_brackets``, ``mechanism_diagnostics``, ``exception``,
``budget_exhausted``, and::

    "assessor": {
      "valid_refinement_seed": bool,
      "matched_isolated_root_classes": [str, ...],
      "safety_control": bool
    }

Precision callback counts use keys ``float64``, ``128``, ``256`` and ``512``.
The aggregator independently charges weights 1, 3, 5 and 10, respectively.
``requested_precision_counts`` describes rescue work;
``shared_requested_precision_counts`` is exactly the common Float64
``anchor + h/h2 +/-`` stencil.  ``charged_*``, ``observed_*`` and
``reported_*`` must all equal both the requested and physically observed rescue
reconstructions, shared requested/observed fields must agree, and totals must
equal both reconstructions of shared plus rescue.
Only rescue weighted work has the frozen 600-unit mechanism cap.  Candidate
input is paired across arms at each shard/start and may contain only public
numerical data; assessor/case/family/root/target/truth metadata is rejected by
audit.  Digest normalization converts every value into a fully type-tagged AST
before key-sorted canonical JSON: null, bool, integer, string, Float64, list and
dict are disjoint nodes, and Float64 payloads are 16 lowercase IEEE-754 hex
digits.  Thus Python/Julia exponent formatting is irrelevant, ``-0.0`` and
subnormals remain distinguishable, and user strings or dictionaries cannot
collide with an internal Float64 marker.

``mechanism_diagnostics`` is always an object.  ADAPTED and COMBINED rows must
state that confirmation is on the same source model and never claim that the
refined endpoint itself received high-precision confirmation.  A seed-ready
adaptive attempt additionally retains selected/confirmation precision and
rank, true rank/correction stability, and string-valued residual, Jacobian and
correction disagreement/tolerance pairs.  COMBINED retains the complete list
of adaptive-attempt diagnostic objects; unknown attempts may carry null metric
values.  These are causal seed diagnostics, not answer verification.

This scorer never promotes production and never emits a bounded-mechanism
negative classification.  T0 emits proposed ``RefinementSeed`` objects, not
answers.  An unsupported seed on a positive stratum is therefore a performance
measurement, not an invalid run or an answer-level safety claim.  A valid T0
can only provide an INCONCLUSIVE signal for a later E4-attached T1, while
structural/accounting failures or a candidate-arm safety-control emission are
INVALID_RUN and an inactive mechanism is MECHANISM_UNEXERCISED.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence


EXPERIMENT_ID = "EXP-LOCAL-015"
RAW_SCHEMA = "geotarget.exp-local-015-t0-raw/v1"
OUTPUT_SCHEMA = "geotarget.exp-local-015-t0-aggregate/v1"
CASE_COUNT = 63
REPRESENTATION_CLASS_COUNT = 21
START_COUNT = 16
WEIGHTED_WORK_CAP = 600
REPRESENTATIONS = ("base", "signed_permutation", "orthogonal")
TOP_LEVEL_FIELDS = frozenset(
    (
        "arm_order",
        "case",
        "case_count",
        "case_index",
        "corpus_checksum",
        "experiment_id",
        "nonpromotional_t0",
        "preregistration",
        "revision",
        "rows",
        "runtime_contract",
        "schema_version",
        "shared_prefilter_physical_evaluations",
        "thread_contract",
    )
)
CASE_FIELDS = frozenset(("representation", "representation_class_id", "stratum_id"))
REVISION_FIELDS = frozenset(("git_dirty", "git_head"))
PREREGISTRATION_FIELDS = frozenset(("path", "sha256"))
THREAD_CONTRACT_FIELDS = frozenset(
    (
        "assigned_cpu",
        "blas_threads",
        "julia_threads",
        "mkl_env_threads",
        "omp_env_threads",
        "openblas_env_threads",
        "solver_worker_count",
        "within_case_parallelism",
    )
)
RUNTIME_CONTRACT_FIELDS = frozenset(
    ("active_project_path", "julia_version", "manifest_sha256", "project_sha256")
)
FORMAL_PROJECT_PATH = "research/experiments/EXP-LOCAL-002/Project.toml"
FORMAL_JULIA_VERSION = "1.12.6"
FORMAL_PYTHON_VERSION = (3, 12, 11)

E4 = "E4-ENDPOINT-NO-RESCUE"
FLOAT_DIAGNOSTIC = "FLOAT64-H-H2-DIAGNOSTIC-ONLY"
REFERENCE = "REFERENCE-512-CPQR-H-H2"
ADAPTED = "GEOTARGET-ADAPTED-128-256-512-CPQR"
WEAK = "WEAK-BRACKET"
ISOTROPIC = "ISOTROPIC-BRACKET"
WEAK_NO_EMIT = "WEAK-NO-EMIT"
COMBINED = "WEAK-THEN-ADAPTIVE"
ARMS = (
    E4,
    FLOAT_DIAGNOSTIC,
    REFERENCE,
    ADAPTED,
    WEAK,
    ISOTROPIC,
    WEAK_NO_EMIT,
    COMBINED,
)
CANDIDATE_ARMS = (ADAPTED, WEAK, COMBINED)
EXACT_REPRESENTATION_ARMS = tuple(arm for arm in ARMS if arm != ISOTROPIC)
ROOT_RECALL_EXCLUDED_ARMS = frozenset((WEAK, ISOTROPIC, WEAK_NO_EMIT))
ACTIVATION_FIELDS = {
    E4: frozenset(("mechanism_activated",)),
    FLOAT_DIAGNOSTIC: frozenset(("rank_or_condition_trigger",)),
    REFERENCE: frozenset(("factorization_performed",)),
    ADAPTED: frozenset(
        ("tier_started", "newton_step_accepted", "cross_tier_confirmed")
    ),
    WEAK: frozenset(("rank_evidence_activated", "strict_bracket_detected")),
    ISOTROPIC: frozenset(("rank_evidence_activated", "strict_bracket_detected")),
    WEAK_NO_EMIT: frozenset(("rank_evidence_activated", "strict_bracket_detected")),
    COMBINED: frozenset(
        ("adaptive_attempt_started", "cross_tier_confirmed", "strict_bracket_detected")
    ),
}

PRECISION_WEIGHTS = {"float64": 1, "128": 3, "256": 5, "512": 10}
EMISSION_KINDS = ("none", "bracket_seed", "refinement_seed")
BRACKET_ARMS = frozenset((WEAK, ISOTROPIC))
BRACKET_UNIT_TOLERANCE = 1.0e-12
BRACKET_MIDPOINT_TOLERANCE = 1.0e-12
ALLOWED_EMISSIONS = {
    E4: frozenset(("none",)),
    FLOAT_DIAGNOSTIC: frozenset(("none",)),
    REFERENCE: frozenset(("none", "refinement_seed")),
    ADAPTED: frozenset(("none", "refinement_seed")),
    WEAK: frozenset(("none", "bracket_seed")),
    ISOTROPIC: frozenset(("none", "bracket_seed")),
    WEAK_NO_EMIT: frozenset(("none",)),
    COMBINED: frozenset(("none", "refinement_seed")),
}

# The card says which contrasts have causal meaning.  Reference/adapted is
# deliberately absent because their stencil and precision schedule both differ.
CONTRASTS = (
    ("adapted_vs_float_diagnostic", ADAPTED, FLOAT_DIAGNOSTIC),
    ("adapted_vs_zero_rescue", ADAPTED, E4),
    ("weak_direction_vs_isotropic", WEAK, ISOTROPIC),
    ("weak_emission_vs_no_emit", WEAK, WEAK_NO_EMIT),
    ("weak_vs_zero_rescue", WEAK, E4),
    ("combined_vs_adapted", COMBINED, ADAPTED),
    ("combined_vs_weak", COMBINED, WEAK),
    ("combined_vs_no_emit", COMBINED, WEAK_NO_EMIT),
    ("combined_vs_zero_rescue", COMBINED, E4),
)

_TRUTH_TOKENS = (
    "assessor",
    "case_id",
    "checksum",
    "classification",
    "descriptor",
    "family",
    "fixture",
    "gold",
    "known_root",
    "manifold",
    "plugin",
    "primitive",
    "replay",
    "representation",
    "root",
    "stratum",
    "target",
    "truth",
    "witness",
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _normalize_digest_value(value: Any) -> Any:
    """Return the cross-language, type-preserving candidate digest payload."""

    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, str):
        return ["string", value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("candidate digest Float64 values must be finite")
        bits = struct.unpack(">Q", struct.pack(">d", value))[0]
        return ["float64", f"{bits:016x}"]
    if isinstance(value, list):
        return ["list", [_normalize_digest_value(child) for child in value]]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("candidate digest object keys must be strings")
        return [
            "dict",
            [[key, _normalize_digest_value(value[key])] for key in sorted(value)],
        ]
    raise TypeError(f"unsupported candidate digest type: {type(value).__name__}")


def candidate_input_digest(value: Any) -> str:
    normalized = _normalize_digest_value(value)
    return hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and not set(value) - set("0123456789abcdef")
    )


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _truth_leaks(value: Any, path: str = "candidate_input") -> list[str]:
    leaks: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in _TRUTH_TOKENS):
                leaks.append(f"{path}.{key}")
            leaks.extend(_truth_leaks(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            leaks.extend(_truth_leaks(child, f"{path}[{index}]"))
    return leaks


def _precision_ledger(document: Any) -> tuple[dict[str, int], int, int]:
    if not isinstance(document, dict) or set(document) - set(PRECISION_WEIGHTS):
        raise ValueError("requested_precision_counts has an unknown precision tier")
    counts: dict[str, int] = {}
    for tier, value in document.items():
        counts[str(tier)] = _integer(value, f"precision count {tier}")
    callbacks = sum(counts.values())
    weighted = sum(counts[tier] * PRECISION_WEIGHTS[tier] for tier in counts)
    return counts, callbacks, weighted


def _activation(document: Any, arm: str) -> tuple[dict[str, bool], bool]:
    if not isinstance(document, dict) or not document:
        raise ValueError("activation_observables must be a nonempty object")
    values = {
        _text(key, "activation observable name"): _boolean(
            value, f"activation observable {key}"
        )
        for key, value in document.items()
    }
    expected = ACTIVATION_FIELDS[arm]
    if set(values) != expected:
        raise ValueError(
            f"{arm} activation_observables must be exactly {sorted(expected)}"
        )
    if arm in (WEAK, ISOTROPIC, WEAK_NO_EMIT):
        if values["strict_bracket_detected"] and not values["rank_evidence_activated"]:
            raise ValueError("a strict bracket requires activated rank evidence")
        return values, values["strict_bracket_detected"]
    return values, any(values.values())


def _emitted_coordinates(value: Any, dimension: int) -> list[list[float]]:
    if not isinstance(value, list):
        raise ValueError("emitted_seed_coordinates must be a list")
    result: list[list[float]] = []
    for coordinates in value:
        if not isinstance(coordinates, list) or len(coordinates) != dimension:
            raise ValueError("an emitted seed has the wrong dimension")
        if any(
            isinstance(coordinate, bool)
            or not isinstance(coordinate, (int, float))
            or not math.isfinite(coordinate)
            for coordinate in coordinates
        ):
            raise ValueError("emitted seed coordinates must be finite numbers")
        result.append([float(coordinate) for coordinate in coordinates])
    return result


def _finite_vector(value: Any, dimension: int, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != dimension:
        raise ValueError(f"{label} must be a dimension-{dimension} list")
    if any(
        isinstance(coordinate, bool)
        or not isinstance(coordinate, (int, float))
        or not math.isfinite(coordinate)
        for coordinate in value
    ):
        raise ValueError(f"{label} must contain finite numbers")
    return [float(coordinate) for coordinate in value]


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number")
    return result


def _validate_brackets(
    document: Any,
    *,
    arm: str,
    dimension: int,
    endpoint: list[float],
    emitted_coordinates: list[list[float]],
) -> list[dict[str, Any]]:
    if not isinstance(document, list):
        raise ValueError("emitted_brackets must be a list")
    if arm not in BRACKET_ARMS:
        if document:
            raise ValueError(f"{arm} may not report emitted brackets")
        return []
    if len(document) != len(emitted_coordinates):
        raise ValueError(
            "emitted bracket count must equal emitted_seed_coordinates count"
        )

    required = {
        "lower_parameter",
        "upper_parameter",
        "lower_projected_residual",
        "upper_projected_residual",
        "midpoint_coordinates",
        "unit_direction",
    }
    brackets: list[dict[str, Any]] = []
    for index, raw in enumerate(document):
        if not isinstance(raw, dict) or set(raw) != required:
            raise ValueError("an emitted bracket has an invalid field set")
        lower = _finite_number(raw["lower_parameter"], "lower_parameter")
        upper = _finite_number(raw["upper_parameter"], "upper_parameter")
        if not lower < upper:
            raise ValueError("an emitted bracket must satisfy lower < upper")
        lower_residual = _finite_number(
            raw["lower_projected_residual"], "lower_projected_residual"
        )
        upper_residual = _finite_number(
            raw["upper_projected_residual"], "upper_projected_residual"
        )
        opposite = (lower_residual < 0.0 < upper_residual) or (
            upper_residual < 0.0 < lower_residual
        )
        if not opposite:
            raise ValueError(
                "emitted bracket projected residuals must have opposite sign"
            )
        midpoint = _finite_vector(
            raw["midpoint_coordinates"], dimension, "midpoint_coordinates"
        )
        direction = _finite_vector(raw["unit_direction"], dimension, "unit_direction")
        direction_norm = math.sqrt(sum(value * value for value in direction))
        if not math.isclose(
            direction_norm,
            1.0,
            rel_tol=BRACKET_UNIT_TOLERANCE,
            abs_tol=BRACKET_UNIT_TOLERANCE,
        ):
            raise ValueError("emitted bracket direction must have unit norm")
        parameter_midpoint = (lower + upper) / 2.0
        expected_midpoint = [
            coordinate + parameter_midpoint * component
            for coordinate, component in zip(endpoint, direction, strict=True)
        ]
        if any(
            not math.isclose(
                observed,
                expected,
                rel_tol=BRACKET_MIDPOINT_TOLERANCE,
                abs_tol=BRACKET_MIDPOINT_TOLERANCE,
            )
            for observed, expected in zip(midpoint, expected_midpoint, strict=True)
        ):
            raise ValueError("emitted bracket midpoint is inconsistent")
        if any(
            not math.isclose(
                observed,
                expected,
                rel_tol=BRACKET_MIDPOINT_TOLERANCE,
                abs_tol=BRACKET_MIDPOINT_TOLERANCE,
            )
            for observed, expected in zip(
                midpoint, emitted_coordinates[index], strict=True
            )
        ):
            raise ValueError(
                "emitted bracket midpoint disagrees with emitted_seed_coordinates"
            )
        brackets.append(
            {
                "lower_parameter": lower,
                "lower_projected_residual": lower_residual,
                "midpoint_coordinates": midpoint,
                "unit_direction": direction,
                "upper_parameter": upper,
                "upper_projected_residual": upper_residual,
            }
        )
    return brackets


def _validate_assessor(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("assessor must be an object")
    required = {
        "valid_refinement_seed",
        "matched_isolated_root_classes",
        "safety_control",
    }
    if set(document) != required:
        missing = sorted(required - set(document))
        extra = sorted(set(document) - required)
        raise ValueError(f"assessor contract differs: missing={missing} extra={extra}")
    raw_matches = document["matched_isolated_root_classes"]
    if not isinstance(raw_matches, list):
        raise ValueError("matched_isolated_root_classes must be a list")
    matched = [_text(value, "matched isolated-root class") for value in raw_matches]
    if len(set(matched)) != len(matched):
        raise ValueError("matched_isolated_root_classes must be unique")
    return {
        "valid_refinement_seed": _boolean(
            document["valid_refinement_seed"], "valid_refinement_seed"
        ),
        "matched_isolated_root_classes": sorted(matched),
        "safety_control": _boolean(document["safety_control"], "safety_control"),
    }


_ADAPTIVE_BASE_DIAGNOSTICS = {
    "confirmation_site",
    "cross_tier_confirmed",
    "refined_endpoint_high_precision_confirmed",
    "same_source_model_confirmed",
}
_ADAPTIVE_INTEGER_DIAGNOSTICS = {
    "selected_precision_bits",
    "confirmation_precision_bits",
    "selected_numerical_rank",
    "confirmation_numerical_rank",
}
_ADAPTIVE_STABILITY_DIAGNOSTICS = {"rank_stable", "correction_stable"}
_ADAPTIVE_CROSS_TIER_DIAGNOSTICS = {
    "cross_tier_residual_disagreement",
    "cross_tier_residual_tolerance",
    "cross_tier_jacobian_disagreement",
    "cross_tier_jacobian_tolerance",
    "cross_tier_correction_disagreement",
    "cross_tier_correction_tolerance",
}
_ADAPTIVE_SUCCESS_DIAGNOSTICS = (
    _ADAPTIVE_INTEGER_DIAGNOSTICS
    | _ADAPTIVE_STABILITY_DIAGNOSTICS
    | _ADAPTIVE_CROSS_TIER_DIAGNOSTICS
)


def _validate_adaptive_diagnostic(
    document: Any,
    *,
    label: str,
    expected_confirmed: bool | None,
    require_success_evidence: bool,
    dimension: int,
) -> tuple[dict[str, Any], bool]:
    if not isinstance(document, dict) or any(
        not isinstance(key, str) for key in document
    ):
        raise ValueError(f"{label} must be an object with string keys")
    missing = _ADAPTIVE_BASE_DIAGNOSTICS - set(document)
    if missing:
        raise ValueError(f"{label} is missing causal fields: {sorted(missing)}")
    if _text(document["confirmation_site"], f"{label}.confirmation_site") != (
        "same_source_model"
    ):
        raise ValueError(f"{label} confirmation_site must be same_source_model")
    same_source = _boolean(
        document["same_source_model_confirmed"],
        f"{label}.same_source_model_confirmed",
    )
    cross_tier = _boolean(
        document["cross_tier_confirmed"], f"{label}.cross_tier_confirmed"
    )
    if cross_tier != same_source:
        raise ValueError(f"{label} cross-tier and same-source confirmation disagree")
    endpoint_confirmed = _boolean(
        document["refined_endpoint_high_precision_confirmed"],
        f"{label}.refined_endpoint_high_precision_confirmed",
    )
    if endpoint_confirmed:
        raise ValueError(
            f"{label} may not claim refined-endpoint high-precision confirmation"
        )
    if expected_confirmed is not None and same_source != expected_confirmed:
        raise ValueError(f"{label} confirmation does not match row status")

    if same_source and require_success_evidence:
        missing = _ADAPTIVE_SUCCESS_DIAGNOSTICS - set(document)
        if missing:
            raise ValueError(f"{label} is missing success evidence: {sorted(missing)}")
        selected_bits = _integer(
            document["selected_precision_bits"],
            f"{label}.selected_precision_bits",
            minimum=1,
        )
        confirmation_bits = _integer(
            document["confirmation_precision_bits"],
            f"{label}.confirmation_precision_bits",
            minimum=1,
        )
        if confirmation_bits <= selected_bits:
            raise ValueError(f"{label} confirmation precision must exceed selection")
        selected_rank = _integer(
            document["selected_numerical_rank"],
            f"{label}.selected_numerical_rank",
        )
        confirmation_rank = _integer(
            document["confirmation_numerical_rank"],
            f"{label}.confirmation_numerical_rank",
        )
        if selected_rank > dimension or confirmation_rank > dimension:
            raise ValueError(f"{label} numerical rank exceeds problem dimension")
        if selected_rank != confirmation_rank:
            raise ValueError(f"{label} selected and confirmation ranks differ")
        for key in _ADAPTIVE_STABILITY_DIAGNOSTICS:
            if _boolean(document[key], f"{label}.{key}") is not True:
                raise ValueError(f"{label}.{key} must be true for a confirmed seed")
        for key in _ADAPTIVE_CROSS_TIER_DIAGNOSTICS:
            _text(document[key], f"{label}.{key}")
    elif require_success_evidence:
        # Unknown attempts may retain typed partial telemetry; the source adapter
        # currently emits null metrics and false stability flags.
        for key in _ADAPTIVE_INTEGER_DIAGNOSTICS:
            if key in document and document[key] is not None:
                _integer(document[key], f"{label}.{key}")
        for key in _ADAPTIVE_STABILITY_DIAGNOSTICS:
            if key in document and document[key] is not None:
                _boolean(document[key], f"{label}.{key}")
        for key in _ADAPTIVE_CROSS_TIER_DIAGNOSTICS:
            if key in document and document[key] is not None:
                _text(document[key], f"{label}.{key}")
    return dict(document), same_source


def _validate_mechanism_diagnostics(
    document: Any,
    *,
    arm: str,
    status: str,
    exception: Any,
    dimension: int,
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("mechanism_diagnostics must be an object")
    if exception is not None:
        # The runner deliberately emits an empty object after catching an arm
        # exception; the exception accounting makes the campaign invalid.
        return dict(document)
    if arm == ADAPTED:
        validated, _ = _validate_adaptive_diagnostic(
            document,
            label="mechanism_diagnostics",
            expected_confirmed=status == "seed_ready",
            require_success_evidence=True,
            dimension=dimension,
        )
        return validated
    if arm == COMBINED:
        validated, confirmed = _validate_adaptive_diagnostic(
            document,
            label="mechanism_diagnostics",
            expected_confirmed=status == "seed_ready",
            require_success_evidence=False,
            dimension=dimension,
        )
        attempts = document.get("adaptive_attempt_observables")
        if not isinstance(attempts, list):
            raise ValueError(
                "combined mechanism_diagnostics.adaptive_attempt_observables must be a list"
            )
        attempt_count = _integer(
            document.get("adaptive_attempt_count"),
            "mechanism_diagnostics.adaptive_attempt_count",
        )
        if attempt_count != len(attempts):
            raise ValueError("combined adaptive attempt count disagrees with its list")
        attempt_started = _boolean(
            document.get("adaptive_attempt_started"),
            "mechanism_diagnostics.adaptive_attempt_started",
        )
        if attempt_started != bool(attempts):
            raise ValueError(
                "combined adaptive_attempt_started disagrees with its list"
            )
        confirmed_attempts = 0
        validated_attempts: list[dict[str, Any]] = []
        for index, attempt in enumerate(attempts):
            validated_attempt, attempt_confirmed = _validate_adaptive_diagnostic(
                attempt,
                label=f"mechanism_diagnostics.adaptive_attempt_observables[{index}]",
                expected_confirmed=None,
                require_success_evidence=True,
                dimension=dimension,
            )
            confirmed_attempts += attempt_confirmed
            validated_attempts.append(validated_attempt)
        if confirmed and confirmed_attempts != 1:
            raise ValueError(
                "combined seed_ready must retain one confirmed adaptive attempt"
            )
        if not confirmed and confirmed_attempts:
            raise ValueError(
                "combined unknown row may not retain a confirmed adaptive attempt"
            )
        validated["adaptive_attempt_observables"] = validated_attempts
        return validated
    return dict(document)


def _validate_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("raw row must be an object")
    required = {
        "activation_observables",
        "arm",
        "assessor",
        "budget_exhausted",
        "candidate_input",
        "charged_callback_count",
        "charged_weighted_work",
        "emission_kind",
        "emitted_brackets",
        "emitted_seed_coordinates",
        "exception",
        "mechanism_diagnostics",
        "observed_callback_count",
        "observed_precision_counts",
        "observed_weighted_work",
        "reason",
        "reported_callback_count",
        "reported_weighted_work",
        "requested_precision_counts",
        "shared_callback_count",
        "shared_observed_callback_count",
        "shared_observed_precision_counts",
        "shared_observed_weighted_work",
        "shared_requested_precision_counts",
        "shared_weighted_work",
        "start_index",
        "status",
        "total_callback_count",
        "total_weighted_work",
        "truth_free_replay_digest",
    }
    if set(row) != required:
        missing = sorted(required - set(row))
        extra = sorted(set(row) - required)
        raise ValueError(f"raw row contract differs: missing={missing} extra={extra}")
    arm = _text(row["arm"], "arm")
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm}")
    start = _integer(row["start_index"], "start_index", minimum=1)
    if start > START_COUNT:
        raise ValueError("start_index exceeds the frozen 16 starts")
    status = _text(row["status"], "status")
    exception = row["exception"]
    candidate_input = row["candidate_input"]
    if not isinstance(candidate_input, dict):
        raise ValueError("candidate_input must be an object")
    dimension = _integer(
        candidate_input.get("dimension"), "candidate_input.dimension", minimum=1
    )
    endpoint = _finite_vector(
        candidate_input.get("endpoint"), dimension, "candidate_input.endpoint"
    )
    digest = row["truth_free_replay_digest"]
    if not _is_sha256(digest):
        raise ValueError("truth_free_replay_digest is malformed")
    counts, computed_callbacks, computed_work = _precision_ledger(
        row["requested_precision_counts"]
    )
    observed_counts, computed_observed_callbacks, computed_observed_work = (
        _precision_ledger(row["observed_precision_counts"])
    )
    shared_counts, computed_shared_callbacks, computed_shared_work = _precision_ledger(
        row["shared_requested_precision_counts"]
    )
    (
        shared_observed_counts,
        computed_shared_observed_callbacks,
        computed_shared_observed_work,
    ) = _precision_ledger(row["shared_observed_precision_counts"])
    expected_shared_counts = {"float64": 1 + 4 * dimension}
    if shared_counts != expected_shared_counts:
        raise ValueError(
            "shared_requested_precision_counts must be the complete Float64 1+4n stencil"
        )
    observables, activated = _activation(row["activation_observables"], arm)
    emission = row["emission_kind"]
    if emission not in EMISSION_KINDS or emission not in ALLOWED_EMISSIONS[arm]:
        raise ValueError(f"{arm} has an impossible emission kind {emission}")
    emitted_coordinates = _emitted_coordinates(
        row["emitted_seed_coordinates"], dimension
    )
    if (emission == "none") != (not emitted_coordinates):
        raise ValueError("emission kind and emitted seed coordinates disagree")
    emitted_brackets = _validate_brackets(
        row["emitted_brackets"],
        arm=arm,
        dimension=dimension,
        endpoint=endpoint,
        emitted_coordinates=emitted_coordinates,
    )
    if (emission == "bracket_seed") != bool(emitted_brackets):
        raise ValueError("bracket emission kind and emitted_brackets disagree")
    if arm in BRACKET_ARMS and activated != bool(emitted_brackets):
        raise ValueError(
            f"{arm} strict_bracket_detected must equal emitted bracket presence"
        )
    mechanism_diagnostics = _validate_mechanism_diagnostics(
        row["mechanism_diagnostics"],
        arm=arm,
        status=status,
        exception=exception,
        dimension=dimension,
    )
    assessor = _validate_assessor(row["assessor"])
    if arm in ROOT_RECALL_EXCLUDED_ARMS and assessor["matched_isolated_root_classes"]:
        raise ValueError(f"{arm} may not claim isolated-root recall authority")
    return {
        "activation_observables": observables,
        "activated": activated,
        "arm": arm,
        "assessor": assessor,
        "budget_exhausted": _boolean(row["budget_exhausted"], "budget_exhausted"),
        "candidate_input": candidate_input,
        "candidate_input_canonical": canonical_json(candidate_input),
        "charged_callback_count": _integer(
            row["charged_callback_count"], "charged_callback_count"
        ),
        "charged_weighted_work": _integer(
            row["charged_weighted_work"], "charged_weighted_work"
        ),
        "computed_callback_count": computed_callbacks,
        "computed_observed_callback_count": computed_observed_callbacks,
        "computed_observed_weighted_work": computed_observed_work,
        "computed_shared_callback_count": computed_shared_callbacks,
        "computed_shared_observed_callback_count": computed_shared_observed_callbacks,
        "computed_shared_observed_weighted_work": computed_shared_observed_work,
        "computed_shared_weighted_work": computed_shared_work,
        "computed_weighted_work": computed_work,
        "emission_kind": emission,
        "emitted_brackets": emitted_brackets,
        "emitted_seed_coordinates": emitted_coordinates,
        "exception": exception,
        "mechanism_diagnostics": mechanism_diagnostics,
        "observed_callback_count": _integer(
            row["observed_callback_count"], "observed_callback_count"
        ),
        "observed_precision_counts": observed_counts,
        "observed_weighted_work": _integer(
            row["observed_weighted_work"], "observed_weighted_work"
        ),
        "precision_counts": counts,
        "reason": _text(row["reason"], "reason"),
        "reported_callback_count": _integer(
            row["reported_callback_count"], "reported_callback_count"
        ),
        "reported_weighted_work": _integer(
            row["reported_weighted_work"], "reported_weighted_work"
        ),
        "shared_callback_count": _integer(
            row["shared_callback_count"], "shared_callback_count"
        ),
        "shared_observed_callback_count": _integer(
            row["shared_observed_callback_count"], "shared_observed_callback_count"
        ),
        "shared_observed_precision_counts": shared_observed_counts,
        "shared_observed_weighted_work": _integer(
            row["shared_observed_weighted_work"],
            "shared_observed_weighted_work",
        ),
        "shared_precision_counts": shared_counts,
        "shared_weighted_work": _integer(
            row["shared_weighted_work"], "shared_weighted_work"
        ),
        "start_index": start,
        "status": status,
        "total_callback_count": _integer(
            row["total_callback_count"], "total_callback_count"
        ),
        "total_weighted_work": _integer(
            row["total_weighted_work"], "total_weighted_work"
        ),
        "truth_free_replay_digest": digest,
        "truth_leaks": _truth_leaks(candidate_input),
    }


def _validate_shard(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("raw shard must be an object")
    if set(document) != TOP_LEVEL_FIELDS:
        missing = sorted(TOP_LEVEL_FIELDS - set(document))
        extra = sorted(set(document) - TOP_LEVEL_FIELDS)
        raise ValueError(
            f"raw shard top-level contract differs: missing={missing} extra={extra}"
        )
    if document.get("schema_version") != RAW_SCHEMA:
        raise ValueError("unexpected EXP-LOCAL-015 raw schema")
    if document.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("unexpected experiment id")
    if document.get("nonpromotional_t0") is not True:
        raise ValueError("T0 shard must be explicitly nonpromotional")
    if document.get("case_count") != CASE_COUNT:
        raise ValueError("raw shard case_count must be 63")
    case_index = _integer(document.get("case_index"), "case_index", minimum=1)
    if case_index > CASE_COUNT:
        raise ValueError("case_index exceeds 63")
    if tuple(document.get("arm_order", ())) != ARMS:
        raise ValueError("frozen arm order differs")
    if document.get("shared_prefilter_physical_evaluations") != START_COUNT:
        raise ValueError("shared prefilter must be physically evaluated once per start")
    corpus_checksum = document.get("corpus_checksum")
    if not _is_sha256(corpus_checksum):
        raise ValueError("corpus_checksum must be a lowercase SHA-256")
    preregistration = document.get("preregistration")
    if not isinstance(preregistration, dict) or set(preregistration) != (
        PREREGISTRATION_FIELDS
    ):
        raise ValueError("preregistration must have exactly path and sha256")
    preregistration_path = _text(preregistration["path"], "preregistration.path")
    preregistration_sha = preregistration["sha256"]
    if not _is_sha256(preregistration_sha):
        raise ValueError("preregistration.sha256 must be a lowercase SHA-256")
    revision = document.get("revision")
    if (
        not isinstance(revision, dict)
        or set(revision) != REVISION_FIELDS
        or revision.get("git_dirty") is not False
    ):
        raise ValueError("raw shard must record a clean revision")
    git_head = _text(revision.get("git_head"), "revision.git_head")
    case = document.get("case")
    if not isinstance(case, dict) or set(case) != CASE_FIELDS:
        raise ValueError("raw shard case must have the exact frozen field set")
    class_id = _text(case.get("representation_class_id"), "representation_class_id")
    representation = case.get("representation")
    if representation not in REPRESENTATIONS:
        raise ValueError("unknown representation")
    stratum = _text(case.get("stratum_id"), "stratum_id")
    runtime_contract = document.get("runtime_contract")
    if not isinstance(runtime_contract, dict) or set(runtime_contract) != (
        RUNTIME_CONTRACT_FIELDS
    ):
        raise ValueError("runtime_contract has an unexpected field set")
    active_project_path = _text(
        runtime_contract["active_project_path"],
        "runtime_contract.active_project_path",
    )
    if active_project_path != FORMAL_PROJECT_PATH:
        raise ValueError("runtime_contract must use the formal EXP-LOCAL-002 project")
    julia_version = _text(
        runtime_contract["julia_version"], "runtime_contract.julia_version"
    )
    if julia_version != FORMAL_JULIA_VERSION:
        raise ValueError(f"runtime_contract Julia must equal {FORMAL_JULIA_VERSION}")
    project_sha = runtime_contract["project_sha256"]
    manifest_sha = runtime_contract["manifest_sha256"]
    if not _is_sha256(project_sha) or not _is_sha256(manifest_sha):
        raise ValueError(
            "runtime project and manifest hashes must be lowercase SHA-256"
        )
    thread_contract = document.get("thread_contract")
    if not isinstance(thread_contract, dict) or set(thread_contract) != (
        THREAD_CONTRACT_FIELDS
    ):
        raise ValueError("thread_contract has an unexpected field set")
    assigned_cpu = _integer(
        thread_contract["assigned_cpu"], "thread_contract.assigned_cpu", minimum=-1
    )
    for key in (
        "blas_threads",
        "julia_threads",
        "mkl_env_threads",
        "omp_env_threads",
        "openblas_env_threads",
        "solver_worker_count",
    ):
        if _integer(thread_contract[key], f"thread_contract.{key}", minimum=1) != 1:
            raise ValueError(f"thread_contract.{key} must equal one")
    if _boolean(
        thread_contract["within_case_parallelism"],
        "thread_contract.within_case_parallelism",
    ):
        raise ValueError("within-case parallelism is forbidden in T0")
    rows = document.get("rows")
    if not isinstance(rows, list) or len(rows) != START_COUNT * len(ARMS):
        raise ValueError("each shard must contain 16 starts x eight frozen arms")
    validated = [_validate_row(row) for row in rows]
    keys = [(row["arm"], row["start_index"]) for row in validated]
    wanted = {(arm, start) for arm in ARMS for start in range(1, START_COUNT + 1)}
    if len(set(keys)) != len(keys) or set(keys) != wanted:
        raise ValueError("raw shard arm/start rows are missing or duplicated")
    return {
        "case_index": case_index,
        "class_id": class_id,
        "corpus_checksum": corpus_checksum,
        "git_head": git_head,
        "preregistration": {
            "path": preregistration_path,
            "sha256": preregistration_sha,
        },
        "representation": representation,
        "rows": validated,
        "runtime_contract": {
            "active_project_path": active_project_path,
            "julia_version": julia_version,
            "manifest_sha256": manifest_sha,
            "project_sha256": project_sha,
        },
        "stratum": stratum,
        "thread_contract": {
            "assigned_cpu": assigned_cpu,
            "blas_threads": 1,
            "julia_threads": 1,
            "mkl_env_threads": 1,
            "omp_env_threads": 1,
            "openblas_env_threads": 1,
            "solver_worker_count": 1,
            "within_case_parallelism": False,
        },
    }


def _unsupported_seed(row: dict[str, Any]) -> bool:
    emitted = row["emission_kind"] != "none"
    return emitted and not row["assessor"]["valid_refinement_seed"]


def _safety_emission(row: dict[str, Any]) -> bool:
    return row["emission_kind"] != "none" and row["assessor"]["safety_control"]


def _mechanism_outcome_signature(row: dict[str, Any]) -> Any:
    diagnostics = row["mechanism_diagnostics"]
    if row["arm"] not in (ADAPTED, COMBINED):
        return None
    if not diagnostics:
        return {}
    categorical_keys = (
        "confirmation_site",
        "cross_tier_confirmed",
        "refined_endpoint_high_precision_confirmed",
        "same_source_model_confirmed",
        "selected_precision_bits",
        "confirmation_precision_bits",
        "selected_numerical_rank",
        "confirmation_numerical_rank",
        "rank_stable",
        "correction_stable",
    )
    signature = {
        key: diagnostics[key] for key in categorical_keys if key in diagnostics
    }
    if row["arm"] == COMBINED:
        signature["adaptive_attempt_count"] = diagnostics["adaptive_attempt_count"]
        signature["adaptive_attempts"] = [
            {key: attempt[key] for key in categorical_keys if key in attempt}
            for attempt in diagnostics["adaptive_attempt_observables"]
        ]
    return signature


def _outcome_signature(row: dict[str, Any]) -> dict[str, Any]:
    assessor = row["assessor"]
    return {
        "activated": row["activated"],
        "activation_observables": dict(sorted(row["activation_observables"].items())),
        "emission_kind": row["emission_kind"],
        "emitted_bracket_count": len(row["emitted_brackets"]),
        "emitted_seed_count": len(row["emitted_seed_coordinates"]),
        "safety_emission": _safety_emission(row),
        "unsupported_seed": _unsupported_seed(row),
        "matched_isolated_root_classes": assessor["matched_isolated_root_classes"],
        "mechanism_causal_signature": _mechanism_outcome_signature(row),
        "rescue_observed_weighted_work": row["observed_weighted_work"],
        "shared_weighted_work": row["shared_weighted_work"],
        "total_weighted_work": row["total_weighted_work"],
        "precision_counts": dict(sorted(row["precision_counts"].items())),
        "reason": row["reason"],
        "status": row["status"],
        "valid_refinement_seed": assessor["valid_refinement_seed"],
    }


def _paired_key(row: dict[str, Any]) -> tuple[str, str, int]:
    return row["class_id"], row["representation"], row["start_index"]


def _class_tokens(row: dict[str, Any]) -> set[str]:
    if row["arm"] in ROOT_RECALL_EXCLUDED_ARMS:
        return set()
    return {
        f"{row['class_id']}::{matched}"
        for matched in row["assessor"]["matched_isolated_root_classes"]
    }


def _contrast(
    name: str,
    candidate: str,
    control: str,
    rows_by_arm: dict[str, dict[tuple[str, str, int], dict[str, Any]]],
) -> dict[str, Any]:
    candidate_rows = rows_by_arm[candidate]
    control_rows = rows_by_arm[control]
    if set(candidate_rows) != set(control_rows):
        raise ValueError("candidate/control pairing differs")
    candidate_only_activation = 0
    control_only_activation = 0
    candidate_only_valid = 0
    control_only_valid = 0
    stratum_activation: Counter[str] = Counter()
    stratum_valid: Counter[str] = Counter()
    for key in sorted(candidate_rows):
        left, right = candidate_rows[key], control_rows[key]
        candidate_only_activation += left["activated"] and not right["activated"]
        control_only_activation += right["activated"] and not left["activated"]
        left_valid = left["assessor"]["valid_refinement_seed"]
        right_valid = right["assessor"]["valid_refinement_seed"]
        candidate_only_valid += left_valid and not right_valid
        control_only_valid += right_valid and not left_valid
        stratum = left["stratum"]
        stratum_activation[stratum] += int(left["activated"]) - int(right["activated"])
        stratum_valid[stratum] += int(left_valid) - int(right_valid)
    candidate_classes = set().union(
        *(_class_tokens(row) for row in candidate_rows.values())
    )
    control_classes = set().union(
        *(_class_tokens(row) for row in control_rows.values())
    )
    candidate_work = sum(row["total_weighted_work"] for row in candidate_rows.values())
    control_work = sum(row["total_weighted_work"] for row in control_rows.values())
    return {
        "candidate": candidate,
        "candidate_activation_count": sum(
            row["activated"] for row in candidate_rows.values()
        ),
        "candidate_matched_classes": sorted(candidate_classes),
        "candidate_only_activation_trials": candidate_only_activation,
        "candidate_only_matched_classes": sorted(candidate_classes - control_classes),
        "candidate_only_valid_seed_trials": candidate_only_valid,
        "candidate_total_case_weighted_work": candidate_work,
        "control": control,
        "control_activation_count": sum(
            row["activated"] for row in control_rows.values()
        ),
        "control_matched_classes": sorted(control_classes),
        "control_only_activation_trials": control_only_activation,
        "control_only_matched_classes": sorted(control_classes - candidate_classes),
        "control_only_valid_seed_trials": control_only_valid,
        "control_total_case_weighted_work": control_work,
        "name": name,
        "stratum_activation_delta": dict(sorted(stratum_activation.items())),
        "stratum_valid_seed_delta": dict(sorted(stratum_valid.items())),
    }


def aggregate_documents(documents: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if len(documents) != CASE_COUNT:
        raise ValueError(f"expected 63 one-case shards, got {len(documents)}")
    shards = [_validate_shard(document) for document in documents]
    indices = [shard["case_index"] for shard in shards]
    if sorted(indices) != list(range(1, CASE_COUNT + 1)):
        raise ValueError("case indices must be exactly 1..63 with no duplicate")
    revisions = {shard["git_head"] for shard in shards}
    if len(revisions) != 1:
        raise ValueError("all T0 shards must come from one clean revision")
    corpus_checksums = {shard["corpus_checksum"] for shard in shards}
    if len(corpus_checksums) != 1:
        raise ValueError("all T0 shards must use one corpus checksum")
    preregistrations = {canonical_json(shard["preregistration"]) for shard in shards}
    if len(preregistrations) != 1:
        raise ValueError("all T0 shards must use one preregistration")
    runtime_contracts = {canonical_json(shard["runtime_contract"]) for shard in shards}
    if len(runtime_contracts) != 1:
        raise ValueError("all T0 shards must use one Julia runtime contract")
    by_class: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for shard in shards:
        by_class[shard["class_id"]].append(shard)
    if len(by_class) != REPRESENTATION_CLASS_COUNT:
        raise ValueError("63 shards must form exactly 21 representation classes")
    for class_id, members in by_class.items():
        if len(members) != len(REPRESENTATIONS) or {
            member["representation"] for member in members
        } != set(REPRESENTATIONS):
            raise ValueError(
                f"representation class {class_id} lacks base/signed/orthogonal closure"
            )
        if len({member["stratum"] for member in members}) != 1:
            raise ValueError(f"representation class {class_id} changes stratum")

    accounting = Counter(
        {
            "assessor_consistency_mismatches": 0,
            "callback_charge_mismatches": 0,
            "exception_rows": 0,
            "paired_candidate_input_mismatches": 0,
            "precision_count_mismatches": 0,
            "replay_digest_mismatches": 0,
            "shared_callback_mismatches": 0,
            "shared_ledger_pairing_mismatches": 0,
            "shared_observed_callback_mismatches": 0,
            "shared_observed_weighted_work_mismatches": 0,
            "shared_precision_count_mismatches": 0,
            "shared_weighted_work_mismatches": 0,
            "total_callback_mismatches": 0,
            "total_weighted_work_mismatches": 0,
            "truth_leak_fields": 0,
            "weighted_work_cap_violations": 0,
            "weighted_work_mismatches": 0,
        }
    )
    all_rows: list[dict[str, Any]] = []
    for shard in shards:
        for row in shard["rows"]:
            row.update(
                class_id=shard["class_id"],
                representation=shard["representation"],
                stratum=shard["stratum"],
            )
            all_rows.append(row)
            callbacks = (
                row["computed_callback_count"],
                row["computed_observed_callback_count"],
                row["charged_callback_count"],
                row["observed_callback_count"],
                row["reported_callback_count"],
            )
            accounting["callback_charge_mismatches"] += len(set(callbacks)) != 1
            works = (
                row["computed_weighted_work"],
                row["computed_observed_weighted_work"],
                row["charged_weighted_work"],
                row["observed_weighted_work"],
                row["reported_weighted_work"],
            )
            accounting["weighted_work_mismatches"] += len(set(works)) != 1
            accounting["weighted_work_cap_violations"] += any(
                work > WEIGHTED_WORK_CAP for work in works
            )
            accounting["precision_count_mismatches"] += (
                row["precision_counts"] != row["observed_precision_counts"]
            )
            accounting["shared_callback_mismatches"] += (
                row["shared_callback_count"] != row["computed_shared_callback_count"]
            )
            accounting["shared_weighted_work_mismatches"] += (
                row["shared_weighted_work"] != row["computed_shared_weighted_work"]
            )
            accounting["shared_observed_callback_mismatches"] += (
                len(
                    {
                        row["computed_shared_callback_count"],
                        row["computed_shared_observed_callback_count"],
                        row["shared_callback_count"],
                        row["shared_observed_callback_count"],
                    }
                )
                != 1
            )
            accounting["shared_observed_weighted_work_mismatches"] += (
                len(
                    {
                        row["computed_shared_weighted_work"],
                        row["computed_shared_observed_weighted_work"],
                        row["shared_weighted_work"],
                        row["shared_observed_weighted_work"],
                    }
                )
                != 1
            )
            accounting["shared_precision_count_mismatches"] += (
                row["shared_precision_counts"]
                != row["shared_observed_precision_counts"]
            )
            accounting["total_callback_mismatches"] += row["total_callback_count"] != (
                row["computed_shared_callback_count"] + row["computed_callback_count"]
            ) or row["total_callback_count"] != (
                row["computed_shared_observed_callback_count"]
                + row["computed_observed_callback_count"]
            )
            accounting["total_weighted_work_mismatches"] += row[
                "total_weighted_work"
            ] != (
                row["computed_shared_weighted_work"] + row["computed_weighted_work"]
            ) or row["total_weighted_work"] != (
                row["computed_shared_observed_weighted_work"]
                + row["computed_observed_weighted_work"]
            )
            accounting["replay_digest_mismatches"] += row[
                "truth_free_replay_digest"
            ] != candidate_input_digest(row["candidate_input"])
            accounting["truth_leak_fields"] += len(row["truth_leaks"])
            accounting["exception_rows"] += row["exception"] is not None
            assessor = row["assessor"]
            emitted = row["emission_kind"] != "none"
            accounting["assessor_consistency_mismatches"] += (
                assessor["valid_refinement_seed"] and not emitted
            ) or (
                bool(assessor["matched_isolated_root_classes"])
                and not (assessor["valid_refinement_seed"] or row["arm"] == E4)
            )
        inputs_by_start: defaultdict[int, set[str]] = defaultdict(set)
        for row in shard["rows"]:
            inputs_by_start[row["start_index"]].add(row["candidate_input_canonical"])
        accounting["paired_candidate_input_mismatches"] += sum(
            len(values) != 1 for values in inputs_by_start.values()
        )
        shared_ledgers_by_start: defaultdict[int, set[str]] = defaultdict(set)
        for row in shard["rows"]:
            shared_ledgers_by_start[row["start_index"]].add(
                canonical_json(
                    {
                        "callback_count": row["shared_callback_count"],
                        "observed_callback_count": row[
                            "shared_observed_callback_count"
                        ],
                        "observed_precision_counts": row[
                            "shared_observed_precision_counts"
                        ],
                        "observed_weighted_work": row["shared_observed_weighted_work"],
                        "precision_counts": row["shared_precision_counts"],
                        "weighted_work": row["shared_weighted_work"],
                    }
                )
            )
        accounting["shared_ledger_pairing_mismatches"] += sum(
            len(values) != 1 for values in shared_ledgers_by_start.values()
        )

    rows_by_arm: dict[str, dict[tuple[str, str, int], dict[str, Any]]] = {
        arm: {} for arm in ARMS
    }
    for row in all_rows:
        key = _paired_key(row)
        if key in rows_by_arm[row["arm"]]:
            raise ValueError("duplicate class/representation/start arm row")
        rows_by_arm[row["arm"]][key] = row
    expected_trials = REPRESENTATION_CLASS_COUNT * len(REPRESENTATIONS) * START_COUNT
    if any(len(rows) != expected_trials for rows in rows_by_arm.values()):
        raise ValueError("one or more frozen arms lacks 1,008 trials")

    unsupported_seed_rows = [row for row in all_rows if _unsupported_seed(row)]
    candidate_safety_emission_rows = [
        row
        for row in all_rows
        if row["arm"] in CANDIDATE_ARMS and _safety_emission(row)
    ]
    control_safety_emission_rows = [
        row
        for row in all_rows
        if row["arm"] not in CANDIDATE_ARMS and _safety_emission(row)
    ]
    representation_disagreements: list[dict[str, Any]] = []
    for class_id in sorted(by_class):
        for arm in EXACT_REPRESENTATION_ARMS:
            for start in range(1, START_COUNT + 1):
                signatures = {
                    representation: _outcome_signature(
                        rows_by_arm[arm][class_id, representation, start]
                    )
                    for representation in REPRESENTATIONS
                }
                if len({canonical_json(value) for value in signatures.values()}) != 1:
                    representation_disagreements.append(
                        {
                            "arm": arm,
                            "representation_class_id": class_id,
                            "signatures": signatures,
                            "start_index": start,
                        }
                    )

    arm_metrics: dict[str, Any] = {}
    for arm in ARMS:
        rows = list(rows_by_arm[arm].values())
        matched = set().union(*(_class_tokens(row) for row in rows))
        total_work = sum(row["total_weighted_work"] for row in rows)
        activations = sum(row["activated"] for row in rows)
        valid_seeds = sum(row["assessor"]["valid_refinement_seed"] for row in rows)
        arm_metrics[arm] = {
            "activation_count": activations,
            "activation_rate": activations / len(rows),
            "budget_exhausted_rows": sum(row["budget_exhausted"] for row in rows),
            "safety_emission_count": sum(_safety_emission(row) for row in rows),
            "matched_isolated_root_class_count": len(matched),
            "matched_isolated_root_classes": sorted(matched),
            "matched_root_classes_per_600_work": (
                600 * len(matched) / total_work if total_work else None
            ),
            "reason_counts": dict(
                sorted(Counter(row["reason"] for row in rows).items())
            ),
            "status_counts": dict(
                sorted(Counter(row["status"] for row in rows).items())
            ),
            "total_case_weighted_work": total_work,
            "trial_count": len(rows),
            "unsupported_seed_count": sum(_unsupported_seed(row) for row in rows),
            "unsupported_seed_rate": sum(_unsupported_seed(row) for row in rows)
            / len(rows),
            "valid_refinement_seed_count": valid_seeds,
            "valid_refinement_seed_rate": valid_seeds / len(rows),
        }

    isotropic_by_representation: dict[str, Any] = {}
    for representation in REPRESENTATIONS:
        rows = [
            row
            for row in rows_by_arm[ISOTROPIC].values()
            if row["representation"] == representation
        ]
        isotropic_by_representation[representation] = {
            "activation_count": sum(row["activated"] for row in rows),
            "total_case_weighted_work": sum(row["total_weighted_work"] for row in rows),
            "trial_count": len(rows),
            "valid_refinement_seed_count": sum(
                row["assessor"]["valid_refinement_seed"] for row in rows
            ),
        }
    isotropic_activation_counts = [
        value["activation_count"] for value in isotropic_by_representation.values()
    ]
    isotropic_valid_counts = [
        value["valid_refinement_seed_count"]
        for value in isotropic_by_representation.values()
    ]
    isotropic_work = [
        value["total_case_weighted_work"]
        for value in isotropic_by_representation.values()
    ]
    isotropic_representation_diagnostic = {
        "activation_count_spread": max(isotropic_activation_counts)
        - min(isotropic_activation_counts),
        "by_representation": isotropic_by_representation,
        "exact_per_start_gate": False,
        "promotion_authority": False,
        "reason": "fixed coordinate draws test an invariant law, not covariant per-start draws",
        "total_case_weighted_work_spread": max(isotropic_work) - min(isotropic_work),
        "valid_refinement_seed_count_spread": max(isotropic_valid_counts)
        - min(isotropic_valid_counts),
    }

    contrasts = {
        name: _contrast(name, candidate, control, rows_by_arm)
        for name, candidate, control in CONTRASTS
    }
    critical_accounting = sum(accounting.values())
    structural_conformance_zero = (
        critical_accounting == 0 and not representation_disagreements
    )
    conformance_zero = (
        structural_conformance_zero and not candidate_safety_emission_rows
    )
    candidate_decisions: dict[str, Any] = {}
    for arm in CANDIDATE_ARMS:
        arm_safety_emissions = sum(
            _safety_emission(row) for row in rows_by_arm[arm].values()
        )
        if not structural_conformance_zero or arm_safety_emissions:
            classification = "INVALID_RUN"
        elif arm_metrics[arm]["activation_count"] == 0:
            classification = "MECHANISM_UNEXERCISED"
        else:
            # Only an audited, separately bounded campaign may declare a bounded
            # mechanism negative.  This one-replicate open-development T0 cannot.
            classification = "INCONCLUSIVE"
        relevant = [value for value in contrasts.values() if value["candidate"] == arm]
        candidate_decisions[arm] = {
            "activation_count": arm_metrics[arm]["activation_count"],
            "causal_classification": classification,
            "direct_bounded_mechanism_negative_authority": False,
            "nonpromotional_t0": True,
            "positive_activation_contrasts": [
                value["name"]
                for value in relevant
                if value["candidate_only_activation_trials"]
                > value["control_only_activation_trials"]
            ],
            "safety_emission_count": arm_safety_emissions,
            "unsupported_seed_count": arm_metrics[arm]["unsupported_seed_count"],
            "valid_refinement_seed_count": arm_metrics[arm][
                "valid_refinement_seed_count"
            ],
        }

    return {
        "accounting": dict(sorted(accounting.items())),
        "arm_metrics": arm_metrics,
        "candidate_decisions": candidate_decisions,
        "case_count": CASE_COUNT,
        "candidate_safety_emission_count": len(candidate_safety_emission_rows),
        "corpus_checksum": corpus_checksums.pop(),
        "contrasts": contrasts,
        "experiment_id": EXPERIMENT_ID,
        "exact_representation_gate_arms": list(EXACT_REPRESENTATION_ARMS),
        "isotropic_representation_diagnostic": isotropic_representation_diagnostic,
        "nonpromotional_t0": True,
        "preregistration": json.loads(preregistrations.pop()),
        "reference_classification": "BUDGET_OR_PARAMETER_LIMITED",
        "representation_class_count": REPRESENTATION_CLASS_COUNT,
        "representation_disagreement_count": len(representation_disagreements),
        "representation_disagreements": representation_disagreements,
        "revision": revisions.pop(),
        "runtime_contract": {
            "aggregate_python_version": sys.version,
            "solver_julia": json.loads(runtime_contracts.pop()),
        },
        "control_safety_emission_count": len(control_safety_emission_rows),
        "schema_version": OUTPUT_SCHEMA,
        "t0_conformance_zero": conformance_zero,
        "trial_count": len(all_rows),
        "thread_contract": {
            "assigned_cpu_counts": dict(
                sorted(
                    Counter(
                        str(shard["thread_contract"]["assigned_cpu"])
                        for shard in shards
                    ).items()
                )
            ),
            "blas_threads": 1,
            "julia_threads": 1,
            "mkl_env_threads": 1,
            "omp_env_threads": 1,
            "openblas_env_threads": 1,
            "solver_worker_count": 1,
            "within_case_parallelism": False,
        },
        "unsupported_seed_count": len(unsupported_seed_rows),
        "weak_only_brackets_are_activation_not_root_authority": True,
    }


def aggregate(paths: Sequence[Path]) -> dict[str, Any]:
    if len(paths) != CASE_COUNT:
        raise ValueError(f"expected 63 one-case shard paths, got {len(paths)}")
    documents = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    return aggregate_documents(documents)


def main(argv: Sequence[str] | None = None) -> None:
    if tuple(sys.version_info[:3]) != FORMAL_PYTHON_VERSION:
        wanted = ".".join(str(value) for value in FORMAL_PYTHON_VERSION)
        observed = ".".join(str(value) for value in sys.version_info[:3])
        raise SystemExit(
            f"formal EXP-LOCAL-015 aggregation requires Python {wanted}, got {observed}"
        )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("shards", nargs="+", type=Path)
    arguments = parser.parse_args(argv)
    result = aggregate(arguments.shards)
    arguments.output.write_text(canonical_json(result) + "\n", encoding="utf-8")
    print(f"output={arguments.output}")


if __name__ == "__main__":
    main()
