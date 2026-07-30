"""Strict consumer boundary for the frozen degree-eight exact fallback.

This is a candidate-private copy of the reviewed champion-v5 consumption
checks.  The exact child remains a pinned, trusted process, but no child
terminal becomes authority unless the complete numeric-plus-exact ledger is
well typed and tied to the untouched source.
"""

from __future__ import annotations

from fractions import Fraction
import hashlib
import math
import os
from pathlib import Path
from typing import Mapping


HERE = Path(__file__).resolve().parent
ROOT = Path(
    os.environ.get(
        "GEOTARGET_CURRENT_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
EXACT_REFINER = (
    ROOT / "research/experiments/EXP-REAL61-001/refine_proposals_worker.py"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matches_sha256(path: Path, expected: str) -> bool:
    try:
        return sha256(path) == expected
    except OSError:
        return False


def isolator_metadata(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    left = value.get("left")
    right = value.get("right")
    multiplicity = value.get("multiplicity")
    root_index = value.get("real_root_index")
    if (
        not isinstance(left, str)
        or not isinstance(right, str)
        or not isinstance(multiplicity, int)
        or isinstance(multiplicity, bool)
        or multiplicity != 1
        or not isinstance(root_index, int)
        or isinstance(root_index, bool)
        or root_index < 0
    ):
        return None
    try:
        if Fraction(left) > Fraction(right):
            return None
    except (ValueError, ZeroDivisionError):
        return None
    return dict(value)


def coordinate_descriptor_metadata(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    polynomial = value.get("coefficients_high_to_low")
    metadata = value.get("polynomial_metadata")
    return bool(
        value.get("status") == "ALGEBRAIC_PROPOSAL"
        and value.get("numeric_lanes_used_only_for_proposal") is True
        and isinstance(polynomial, list)
        and len(polynomial) >= 2
        and all(
            isinstance(coefficient, int)
            and not isinstance(coefficient, bool)
            for coefficient in polynomial
        )
        and isinstance(metadata, Mapping)
        and metadata.get("square_free") is True
        and metadata.get("irreducible_over_Q") is True
        and isolator_metadata(metadata.get("isolating_interval")) is not None
    )


def exact_descriptor(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    polynomial = value.get("minimal_polynomial_high_to_low")
    root_index = value.get("selected_real_root_index")
    isolator = value.get("isolating_interval")
    if (
        not isinstance(polynomial, list)
        or len(polynomial) < 2
        or not all(
            isinstance(coefficient, int)
            and not isinstance(coefficient, bool)
            for coefficient in polynomial
        )
        or not isinstance(root_index, int)
        or isinstance(root_index, bool)
        or root_index < 0
        or isolator_metadata(isolator) is None
        or isolator.get("real_root_index") != root_index
        or value.get("proposal_relation_low_to_high")
        != list(reversed(polynomial))
        or value.get("confirmation_relation_low_to_high")
        != list(reversed(polynomial))
        or not isinstance(value.get("target_768"), str)
        or not isinstance(value.get("target_1024"), str)
    ):
        return None
    return dict(value)


def descriptor_identity(value: object) -> tuple[tuple[int, ...], int] | None:
    """Return the exact algebraic identity, ignoring noncanonical isolators.

    A primitive minimal polynomial and its zero-based ordinal among all real
    roots uniquely identify the real algebraic value.  Numeric target strings
    and rational isolator widths may legitimately differ across independent
    refinement runs, so they are deliberately not equality keys.
    """

    descriptor = exact_descriptor(value)
    if descriptor is None:
        return None
    return (
        tuple(descriptor["minimal_polynomial_high_to_low"]),
        int(descriptor["selected_real_root_index"]),
    )


def _root_attestation_matches(value: object, root_index: object) -> bool:
    return bool(
        isinstance(root_index, int)
        and not isinstance(root_index, bool)
        and root_index >= 0
        and isinstance(value, Mapping)
        and isinstance(value.get("claimed_real_root_index"), int)
        and not isinstance(value.get("claimed_real_root_index"), bool)
        and value.get("claimed_real_root_index") == root_index
        and isinstance(value.get("attested_real_root_index"), int)
        and not isinstance(value.get("attested_real_root_index"), bool)
        and value.get("attested_real_root_index") == root_index
        and isinstance(value.get("real_root_count"), int)
        and not isinstance(value.get("real_root_count"), bool)
        and value.get("real_root_count") > root_index
        and isinstance(value.get("multiplicity"), int)
        and not isinstance(value.get("multiplicity"), bool)
        and value.get("multiplicity") == 1
        and value.get("interval_unique") is True
        and value.get("index_match") is True
    )


def nested_exact_authority_matches_source(
    fallback: Mapping[str, object],
    descriptor: Mapping[str, object],
    source_document: Mapping[str, object],
    source_sha256: str,
) -> bool:
    """Recheck the audited child authority ledger at the outer seam."""

    exact = fallback.get("exact_coordinate_authority")
    numeric = fallback.get("numeric_source_replay")
    variables = source_document.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    constraints = source_document.get("constraints")
    guards = source_document.get("guards") or []
    bounds = source_document.get("bounds")
    if (
        not isinstance(exact, Mapping)
        or not isinstance(names, list)
        or not isinstance(constraints, list)
        or not isinstance(guards, list)
        or fallback.get("independent_coordinate_lanes") != [768, 1024]
        or fallback.get("exact_replay_backend") != "FLINT_QQBAR_VIA_NEMO"
        or fallback.get("numeric_guard_branch_replay_is_authority") is not True
        or fallback.get("numeric_target_nearness_is_authority") is not False
        or fallback.get("numeric_float_residual_is_authority") is not False
        or not isinstance(numeric, Mapping)
        or numeric.get("schema_version")
        != "geotarget.v15-243-frozen-numeric-source-replay/v1"
        or numeric.get("refiner_sha256") != sha256(EXACT_REFINER)
        or numeric.get("source_sha256") != source_sha256
        or numeric.get("proposal_status") != "PSLQ_PROPOSAL"
        or not isinstance(numeric.get("float_source_replay"), Mapping)
        or numeric.get("float_source_replay").get("evaluation_defined")
        is not True
        or numeric.get("float_source_replay").get("guard_ok") is not True
        or numeric.get("float_source_replay").get("hard_feasible") is not True
        or numeric.get("float_source_replay").get("residual_is_authority")
        is not False
        or not isinstance(
            numeric.get("float_source_replay").get("residual_inf"),
            (int, float),
        )
        or isinstance(
            numeric.get("float_source_replay").get("residual_inf"), bool
        )
        or not math.isfinite(
            float(numeric.get("float_source_replay").get("residual_inf"))
        )
        or float(numeric.get("float_source_replay").get("residual_inf")) < 0.0
        or numeric.get("precision_lanes_decimal_digits") != [155, 232, 320]
        or not isinstance(numeric.get("lane_methods"), Mapping)
        or set(numeric.get("lane_methods")) != {"155", "232", "320"}
        or not isinstance(numeric.get("lane_working_decimal_digits"), Mapping)
        or set(numeric.get("lane_working_decimal_digits"))
        != {"155", "232", "320"}
        or any(
            not isinstance(numeric.get("lane_working_decimal_digits")[key], int)
            or isinstance(
                numeric.get("lane_working_decimal_digits")[key], bool
            )
            or numeric.get("lane_working_decimal_digits")[key] < int(key)
            for key in ("155", "232", "320")
        )
        or not isinstance(numeric.get("lane_source_replay"), Mapping)
        or set(numeric.get("lane_source_replay")) != {"155", "232", "320"}
        or any(
            not isinstance(numeric.get("lane_source_replay")[key], Mapping)
            or numeric.get("lane_source_replay")[key]
            != {
                "replay_decimal_digits": int(key),
                "guard_replay_decimal_digits": int(key),
                "hard_feasibility_replay_decimal_digits": int(key),
                "residual_replay_decimal_digits": int(key),
                "answer_replay_decimal_digits": int(key),
                "residual_threshold": {
                    "155": "1e-100",
                    "232": "1e-150",
                    "320": "1e-200",
                }[key],
                "guard_ok": True,
                "hard_feasible": True,
                "residual_reached": True,
                "answer_defined": True,
            }
            for key in ("155", "232", "320")
        )
        or numeric.get("float_endpoint_source_replay_required") is not True
        or numeric.get("all_precision_lanes_guard_and_hard_feasible")
        is not True
        or numeric.get("all_precision_lanes_source_residual_reached")
        is not True
        or numeric.get(
            "coordinates_linked_to_exact_roots_by_independent_lanes"
        )
        is not True
        or numeric.get("branch_and_guard_parity_is_not_inferred_from_qqbar")
        is not True
        or exact.get("schema_version")
        != "geotarget.v15-243-exact-coordinate-replay/v1"
        or exact.get("backend") != "FLINT_QQBAR_VIA_NEMO"
        or exact.get("status") != "EXACT_TARGET_AUTHORITY_READY"
        or exact.get("authority_pass") is not True
        or exact.get("truth_used") is not False
        or exact.get("case_family_or_target_count_routing") is not False
        or exact.get("numeric_nearness_is_authority") is not False
        or exact.get("source_replay_required") is not True
        or exact.get("source_raw_answer_exact") is not True
        or exact.get("target_link_exact") is not True
        or exact.get("post_process_used") is not False
        or exact.get("target_set_completeness_claim") is not False
        or exact.get("root_ordinal_attestation_complete") is not True
        or exact.get("root_ordinal_policy")
        != "ZERO_BASED_STRICTLY_INCREASING_REAL_QQBAR_V1"
        or exact.get("root_ordinal_attestation_backend")
        != "NEMO_QQBAR_SORTED_REAL_ROOTS"
        or exact.get("source_guard_margin_policy")
        != (
            "exact algebraic guard leg; frozen numeric parity separately "
            "required"
        )
        or exact.get("combined_numeric_and_exact_authority_required")
        is not True
        or exact.get("standalone_operational_v15_parity_claim") is not False
        or exact.get("source_guard_default_margin_exact_rational")
        != "1/10^40"
        or exact.get("source_guard_logical_not_fails_closed") is not True
        or exact.get("source_hard_feasibility_exact_subset") is not True
        or exact.get("source_hard_margin_exact_rationals")
        != {
            "line_distinct": "1/10^12",
            "triangle_nondegenerate": "1/10^14",
            "intersection_exclude_distinct": "1/10^12",
        }
        or exact.get("source_constraints_exact") != len(constraints)
        or exact.get("source_guards_exact") != len(guards)
        or exact.get("source_bounds_exact")
        != (0 if bounds is None else len(names))
    ):
        return False

    coordinate_descriptors = exact.get("coordinate_descriptors")
    coordinate_attestations = exact.get("coordinate_root_attestations")
    target = exact.get("exact_target_descriptor")
    target_isolator = (
        target.get("isolating_interval")
        if isinstance(target, Mapping)
        else None
    )
    if (
        not isinstance(coordinate_descriptors, list)
        or len(coordinate_descriptors) != len(names)
        or not isinstance(coordinate_attestations, list)
        or len(coordinate_attestations) != len(names)
        or not all(
            coordinate_descriptor_metadata(item)
            for item in coordinate_descriptors
        )
        or any(
            not isinstance(item.get("polynomial_metadata"), Mapping)
            or not isinstance(
                item.get("polynomial_metadata").get("isolating_interval"),
                Mapping,
            )
            or not _root_attestation_matches(
                attestation,
                item.get("polynomial_metadata")
                .get("isolating_interval")
                .get("real_root_index"),
            )
            for item, attestation in zip(
                coordinate_descriptors,
                coordinate_attestations,
                strict=True,
            )
        )
        or not isinstance(target, Mapping)
        or not isinstance(target_isolator, Mapping)
        or not _root_attestation_matches(
            target_attestation := exact.get("target_root_attestation"),
            target_isolator.get("real_root_index"),
        )
        or not isinstance(target_attestation, Mapping)
        or target_isolator.get("real_root_index")
        != descriptor.get("selected_real_root_index")
        or target.get("coefficients_high_to_low")
        != descriptor.get("minimal_polynomial_high_to_low")
        or target.get("isolating_interval")
        != descriptor.get("isolating_interval")
    ):
        return False
    return True
