"""Disposable config-first repair for one exact-coordinate failure seam.

The current refiner is allowed to propose exact *coordinates* while its target
PSLQ is ignored.  Canonical replay then evaluates the untouched raw answer at
those exact coordinates.  The target descriptor is derived from that exact
value; numeric target lanes are only a final consistency check.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from mpmath import mp
import sympy as sp


SCHEMA = "geotarget.v15-243-config-first-source-derived-target/v1"
ROOT_POLICY = "ZERO_BASED_STRICTLY_INCREASING_REAL_ROOTS_V1"


class FailClosed(ValueError):
    pass


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def activation_ready(aggregate: Mapping[str, Any]) -> bool:
    """The benchmark owner supplies counts only; no row may enter this lane."""
    count = aggregate.get("complete_coordinate_witness_attempt_count")
    clusters = aggregate.get("anonymous_structure_cluster_hashes")
    return bool(
        aggregate.get("aggregate_only") is True
        and aggregate.get("individual_rows_shared") is False
        and isinstance(count, int)
        and not isinstance(count, bool)
        and count >= 10
        and isinstance(clusters, list)
        and len(set(clusters)) >= 2
        and all(
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
            for value in clusters
        )
    )


def _valid_refinement_replay(proposal: Mapping[str, Any]) -> bool:
    float_replay = proposal.get("float_source_replay")
    lane_replay = proposal.get("lane_source_replay")
    expected_lanes = {"155", "232", "320"}
    return bool(
        isinstance(float_replay, Mapping)
        and float_replay.get("evaluation_defined") is True
        and float_replay.get("guard_ok") is True
        and float_replay.get("hard_feasible") is True
        and float_replay.get("residual_is_authority") is False
        and isinstance(lane_replay, Mapping)
        and set(lane_replay) == expected_lanes
        and all(
            isinstance(lane_replay[key], Mapping)
            and lane_replay[key].get("guard_ok") is True
            and lane_replay[key].get("hard_feasible") is True
            and lane_replay[key].get("residual_reached") is True
            and lane_replay[key].get("answer_defined") is True
            for key in expected_lanes
        )
    )


def _descriptor_shape(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    polynomial = value.get("coefficients_high_to_low")
    metadata = value.get("polynomial_metadata")
    interval = metadata.get("isolating_interval") if isinstance(metadata, Mapping) else None
    return bool(
        value.get("status") == "ALGEBRAIC_PROPOSAL"
        and value.get("numeric_lanes_used_only_for_proposal") is True
        and isinstance(polynomial, list)
        and len(polynomial) >= 2
        and all(isinstance(item, int) and not isinstance(item, bool) for item in polynomial)
        and isinstance(metadata, Mapping)
        and metadata.get("square_free") is True
        and metadata.get("irreducible_over_Q") is True
        and isinstance(interval, Mapping)
        and isinstance(interval.get("left"), str)
        and isinstance(interval.get("right"), str)
        and interval.get("multiplicity") == 1
        and isinstance(interval.get("real_root_index"), int)
        and not isinstance(interval.get("real_root_index"), bool)
        and interval.get("real_root_index") >= 0
    )


def configuration_contract(proposal: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """Accept every current gate except the target relation/PSLQ gate."""
    descriptors = proposal.get("configuration_algebraic_proposals")
    lanes_a = proposal.get("coordinates_768bit_minimum")
    lanes_b = proposal.get("coordinates_1024bit_minimum")
    if (
        proposal.get("status") != "NUMERIC_ONLY"
        or proposal.get("independent_precision_lanes") is not True
        or proposal.get("numeric_gate_1e_100") is not True
        or proposal.get("configuration_fully_recognized") is not True
        or not _valid_refinement_replay(proposal)
        or not isinstance(descriptors, list)
        or not descriptors
        or not all(_descriptor_shape(item) for item in descriptors)
        or not isinstance(lanes_a, list)
        or not isinstance(lanes_b, list)
        or len(lanes_a) != len(descriptors)
        or len(lanes_b) != len(descriptors)
        or not all(isinstance(value, str) for value in (*lanes_a, *lanes_b))
        or not isinstance(proposal.get("answer_768bit_minimum"), str)
        or not isinstance(proposal.get("answer_1024bit_minimum"), str)
    ):
        raise FailClosed("configuration-first refinement contract is incomplete")
    # Target PSLQ coefficients, residual and polynomial metadata are never read.
    exact_descriptors = [dict(item) for item in descriptors]
    commitment = _digest(
        {
            "coordinate_descriptors": exact_descriptors,
            "coordinate_lane_a": list(lanes_a),
            "coordinate_lane_b": list(lanes_b),
        }
    )
    return exact_descriptors, commitment


def exact_value_commitment(value: sp.Expr) -> str:
    return hashlib.sha256(sp.srepr(value).encode()).hexdigest()


def _require_exact_real_scalar(value: object) -> sp.Expr:
    if not isinstance(value, sp.Expr) or isinstance(value, sp.MatrixBase):
        raise FailClosed("raw answer is undefined or non-scalar")
    if value.has(sp.Float) or value.free_symbols:
        raise FailClosed("raw answer is not an exact closed expression")
    if value.is_algebraic is not True or value.is_real is not True:
        raise FailClosed("raw answer is not proved real algebraic")
    return value


def _primitive_positive(poly: sp.Poly) -> sp.Poly:
    _content, primitive = sp.Poly(poly, domain=sp.ZZ).primitive()
    if primitive.LC() < 0:
        primitive = -primitive
    return sp.Poly(primitive, poly.gens[0], domain=sp.ZZ)


def _exact_equal(left: sp.Expr, right: sp.Expr) -> bool:
    difference = sp.simplify(left - right)
    if difference == 0 or difference.is_zero is True:
        return True
    if difference.is_zero is False:
        return False
    answer = difference.equals(0)
    if answer is None:
        raise FailClosed("exact root identity is undecidable")
    return bool(answer)


def derive_descriptor(raw_answer: object) -> dict[str, Any]:
    value = _require_exact_real_scalar(raw_answer)
    variable = sp.Symbol("config_first_target")
    polynomial = _primitive_positive(sp.Poly(sp.minpoly(value, variable), variable))
    if polynomial.is_sqf is not True or polynomial.is_irreducible is not True:
        raise FailClosed("derived polynomial is not a square-free minimal polynomial")
    roots = sp.real_roots(polynomial.as_expr(), variable)
    matches = [index for index, root in enumerate(roots) if _exact_equal(root, value)]
    if len(matches) != 1:
        raise FailClosed("exact raw answer does not select one real-root ordinal")
    ordinal = matches[0]
    intervals = polynomial.intervals(eps=sp.Rational(1, 10**100))
    if len(intervals) != len(roots):
        raise FailClosed("real-root isolator count is inconsistent")
    interval, multiplicity = intervals[ordinal]
    left, right = (sp.Rational(item) for item in interval)
    if multiplicity != 1:
        raise FailClosed("derived root is not simple")
    descriptor = {
        "minimal_polynomial_high_to_low": [int(item) for item in polynomial.all_coeffs()],
        "selected_real_root_index": ordinal,
        "isolating_interval": {
            "left": str(left),
            "right": str(right),
            "multiplicity": 1,
            "real_root_index": ordinal,
        },
        "proposal_relation_low_to_high": [int(item) for item in reversed(polynomial.all_coeffs())],
        "confirmation_relation_low_to_high": [int(item) for item in reversed(polynomial.all_coeffs())],
        "root_ordinal_policy": ROOT_POLICY,
    }
    descriptor["descriptor_sha256"] = _digest(descriptor)
    return descriptor


def _source_replay_contract(
    replay: Mapping[str, Any],
    *,
    coordinate_commitment: str,
) -> sp.Expr:
    required_true = (
        "source_bytes_unchanged",
        "source_sha_matches",
        "coordinate_descriptors_exact",
        "coordinate_ordinals_attested",
        "constraints_exact",
        "guards_exact",
        "bounds_exact",
        "branches_selectors_phases_exact",
        "raw_answer_from_canonical_dag",
        "raw_answer_defined",
        "raw_answer_scalar",
        "post_process_absent",
    )
    if (
        replay.get("status") != "CONFIGURATION_EXACT_REPLAY_ACCEPTED"
        or replay.get("backend") != "FLINT_QQBAR_VIA_NEMO"
        or replay.get("truth_used") is not False
        or replay.get("routing_used") is not False
        or replay.get("target_completeness_claim") is not False
        or replay.get("numeric_target_used_only_for_consistency") is not True
        or replay.get("coordinate_witness_sha256") != coordinate_commitment
        or not all(replay.get(key) is True for key in required_true)
        or not isinstance(replay.get("source_sha256"), str)
        or replay.get("source_sha256") != replay.get("replayed_source_sha256")
    ):
        raise FailClosed("canonical configuration replay obligations are incomplete")
    raw = _require_exact_real_scalar(replay.get("raw_answer_exact"))
    if replay.get("raw_answer_exact_sha256") != exact_value_commitment(raw):
        raise FailClosed("exact raw answer changed after canonical replay")
    return raw


def _numeric_consistent(raw: sp.Expr, lanes: Sequence[str]) -> bool:
    if len(lanes) < 2 or not all(isinstance(value, str) for value in lanes):
        return False
    with mp.workdps(180):
        try:
            numeric = [mp.mpf(value) for value in lanes]
            exact_numeric = mp.mpf(str(sp.N(raw, 175)))
        except (ValueError, TypeError):
            return False
        if not all(mp.isfinite(value) for value in (*numeric, exact_numeric)):
            return False
        tolerance = mp.mpf("1e-90") * max(mp.mpf(1), abs(exact_numeric))
        return max(abs(value - exact_numeric) for value in numeric) <= tolerance


def build_repair(
    *,
    aggregate_gate: Mapping[str, Any],
    refinement_proposal: Mapping[str, Any],
    exact_source_replay: Mapping[str, Any],
) -> dict[str, Any]:
    if not activation_ready(aggregate_gate):
        raise FailClosed("aggregate reopen gate is not established")
    descriptors, coordinate_commitment = configuration_contract(refinement_proposal)
    raw = _source_replay_contract(
        exact_source_replay,
        coordinate_commitment=coordinate_commitment,
    )
    descriptor = derive_descriptor(raw)
    numeric_lanes = (
        refinement_proposal["answer_768bit_minimum"],
        refinement_proposal["answer_1024bit_minimum"],
    )
    if not _numeric_consistent(raw, numeric_lanes):
        raise FailClosed("numeric target is inconsistent with exact source-derived answer")
    source_sha = exact_source_replay["source_sha256"]
    result = {
        "schema_version": SCHEMA,
        "status": "CONFIG_FIRST_SOURCE_DERIVED_TARGET_READY",
        "authority_pass": True,
        "truth_used": False,
        "routing_used": False,
        "source_sha256": source_sha,
        "coordinate_witness_sha256": coordinate_commitment,
        "coordinate_descriptor_count": len(descriptors),
        "canonical_source_replay_complete": True,
        "raw_answer_exact_sha256": exact_value_commitment(raw),
        "target_descriptor": descriptor,
        "target_descriptor_derived_from_exact_raw_answer": True,
        "target_pslq_used": False,
        "numeric_target_is_authority": False,
        "numeric_target_consistency_only": True,
        "target_set_completeness_claim": False,
    }
    result["authority_payload_sha256"] = _digest(result)
    return result


def repair_or_exact_outer_fallback(
    exact_outer_bytes: bytes,
    *,
    aggregate_gate: Mapping[str, Any],
    refinement_proposal: Mapping[str, Any],
    exact_source_replay: Mapping[str, Any],
) -> bytes:
    """Return the original object unchanged at every rejected seam."""
    try:
        repaired = build_repair(
            aggregate_gate=aggregate_gate,
            refinement_proposal=refinement_proposal,
            exact_source_replay=exact_source_replay,
        )
    except Exception:
        return exact_outer_bytes
    return _canonical_json(repaired) + b"\n"


def consume_repair(payload: bytes) -> bool:
    """Strict final seam catches descriptor/root/ordinal mutation."""
    try:
        value = json.loads(payload)
        descriptor = value["target_descriptor"]
        descriptor_digest = descriptor.pop("descriptor_sha256")
        authority_digest = value.pop("authority_payload_sha256")
        valid = bool(
            value.get("schema_version") == SCHEMA
            and value.get("status") == "CONFIG_FIRST_SOURCE_DERIVED_TARGET_READY"
            and value.get("authority_pass") is True
            and value.get("truth_used") is False
            and value.get("routing_used") is False
            and value.get("target_descriptor_derived_from_exact_raw_answer") is True
            and value.get("target_pslq_used") is False
            and value.get("numeric_target_is_authority") is False
            and value.get("numeric_target_consistency_only") is True
            and value.get("target_set_completeness_claim") is False
            and descriptor.get("selected_real_root_index")
            == descriptor.get("isolating_interval", {}).get("real_root_index")
            and descriptor.get("proposal_relation_low_to_high")
            == list(reversed(descriptor.get("minimal_polynomial_high_to_low", [])))
            and descriptor.get("confirmation_relation_low_to_high")
            == list(reversed(descriptor.get("minimal_polynomial_high_to_low", [])))
            and descriptor.get("root_ordinal_policy") == ROOT_POLICY
            and descriptor_digest == _digest(descriptor)
        )
        descriptor["descriptor_sha256"] = descriptor_digest
        value["authority_payload_sha256"] = authority_digest
        return valid and authority_digest == _digest(
            {key: item for key, item in value.items() if key != "authority_payload_sha256"}
        )
    except Exception:
        return False
