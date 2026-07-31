from __future__ import annotations

from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import struct

import mpmath
import pytest
import sympy

import canonical_connector as connector


class FakeExact:
    sp = sympy
    mp = mpmath

    @staticmethod
    def _mp_poly_value(polynomial, value):
        total = mpmath.mpf("0")
        for coefficient in polynomial.all_coeffs():
            total = total * value + int(coefficient)
        return total

    @staticmethod
    def _interval_descriptor(polynomial, approximation):
        matches = []
        for root_index, (interval, multiplicity) in enumerate(
            polynomial.intervals(eps=sympy.Rational(1, 10**100))
        ):
            left, right = (sympy.Rational(item) for item in interval)
            left_mp = mpmath.mpf(int(left.p)) / int(left.q)
            right_mp = mpmath.mpf(int(right.p)) / int(right.q)
            if left_mp - mpmath.mpf("1e-120") <= approximation <= right_mp + mpmath.mpf(
                "1e-120"
            ):
                matches.append((left, right, root_index, multiplicity))
        if len(matches) != 1:
            raise ValueError("not one real root")
        left, right, root_index, multiplicity = matches[0]
        return {
            "left": str(left),
            "right": str(right),
            "multiplicity": multiplicity,
            "real_root_index": root_index,
        }

    @staticmethod
    def _qqbar_descriptor(proposal):
        return {
            "coefficients_high_to_low": proposal["coefficients_high_to_low"],
            "isolating_interval": proposal["polynomial_metadata"][
                "isolating_interval"
            ],
        }


def _reducible_endpoints():
    with localcontext() as context:
        context.prec = 150
        values = sorted(
            (
                -Decimal(3).sqrt(),
                -Decimal(2).sqrt(),
                Decimal(2).sqrt(),
                Decimal(3).sqrt(),
            )
        )
    return tuple(
        {
            "low": {"raw_answer_decimal": format(value, "f")},
            "high": {"raw_answer_decimal": format(value, "f")},
        }
        for value in values
    )


def test_reducible_vieta_uses_only_factor_local_minimal_descriptors():
    targets = connector.prepare_factorized_targets(
        exact=FakeExact,
        endpoints=_reducible_endpoints(),
        coefficients=(1, 0, -5, 0, 6),
        subset_root_ordinals=(0, 1, 2, 3),
    )
    assert all(item["status"] == "FACTOR_READY" for item in targets)
    assert all(
        len(item["target_proposal"]["coefficients_high_to_low"]) == 3
        for item in targets
    )
    assert all(
        item["target_proposal"]["coefficients_high_to_low"]
        in ([1, 0, -2], [1, 0, -3])
        for item in targets
    )
    assert [item["factor_local_real_root_ordinal"] for item in targets] == [0, 0, 1, 1]
    assert all(item["product_global_root_ordinal_used"] is False for item in targets)
    assert all(item["unobserved_root_emitted"] is False for item in targets)


def test_factor_selection_failure_is_endpoint_local(monkeypatch):
    endpoints = _reducible_endpoints()
    original = connector._matching_factor
    rejected_target = endpoints[1]["low"]["raw_answer_decimal"]

    def selective(exact, factors, target):
        if target == rejected_target:
            raise connector.ConnectorFailure("synthetic close-root ambiguity")
        return original(exact, factors, target)

    monkeypatch.setattr(connector, "_matching_factor", selective)
    targets = connector.prepare_factorized_targets(
        exact=FakeExact,
        endpoints=endpoints,
        coefficients=(1, 0, -5, 0, 6),
        subset_root_ordinals=(0, 1, 2, 3),
    )
    assert targets[1]["status"] == "FACTOR_REJECTED"
    assert sum(item["status"] == "FACTOR_READY" for item in targets) == 3


def _write_json(path: Path, value: object) -> str:
    payload = json.dumps(value, indent=2, sort_keys=True).encode() + b"\n"
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _artifact_binding(path: Path, digest: str):
    return {"path": str(path), "sha256": digest}


def _private_subset(tmp_path: Path, *, guard_ok: bool = True):
    source_path = tmp_path / "source.json"
    source = {
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "construction": [],
        "constraints": [],
        "guards": [],
        "answer": "x",
    }
    source_sha = _write_json(source_path, source)
    endpoint = [1.0, 2.0]
    bits = [struct.pack(">d", value).hex() for value in endpoint]
    endpoint_sha = connector._endpoint_sha256(bits)
    plan_path = tmp_path / "PLAN.json"
    plan_sha = _write_json(
        plan_path,
        {
            "schema_version": "geotarget.exp008-single-raw-endpoint-hp-plan/v1",
            "source_sha256": source_sha,
            "endpoint_float64_sha256": endpoint_sha,
            "endpoint": endpoint,
            "truth_read": False,
            "case_or_family_identity_read": False,
            "source_or_problem_modified": False,
            "bounds_or_gauge_added": False,
            "endpoint_unchanged_before_refinement": True,
        },
    )
    lanes = [
        {
            "bits": precision,
            "point": ["1", "2"],
            "answer": "1",
            "finite": True,
            "hard_feasible": True,
            "guard_ok": guard_ok,
            "guard_violations": [] if guard_ok else ["synthetic"],
            "raw_hard_feasible_without_intrinsic_domains": True,
            "intrinsic_domain_ok": True,
            "intrinsic_domain_violations": [],
        }
        for precision in (768, 1024)
    ]
    lane_path = tmp_path / "authority.json"
    lane_sha = _write_json(
        lane_path,
        {
            "schema_version": "geotarget.exp008-target-first-fallback-composition/v1",
            "status": "TARGET_AUTHORITY_READY",
            "authority_pass": True,
            "final_result": {
                "status": "TARGET_AUTHORITY_READY",
                "source_raw_sha256": source_sha,
                "endpoint_float64_sha256": endpoint_sha,
                "authority_pass": True,
                "input_contract": {
                    "source_bytes_and_digest": True,
                    "bare_float64_endpoint": True,
                    "truth": False,
                    "known_target_count": False,
                    "case_id": False,
                    "family": False,
                },
                "problem_transformations": {
                    "source_mutated": False,
                    "bounds_added": False,
                    "coordinate_fixing_or_gauge": False,
                    "symmetry_reduction": False,
                    "constraint_or_answer_changed": False,
                },
                "float64_replay": {
                    "semantic_valid": True,
                    "hard_feasible": True,
                    "guard_ok": True,
                    "intrinsic_domain_ok": True,
                },
                "original_numerical_replay": {
                    "numeric_v3_ready": True,
                    "lanes": lanes,
                },
                "authority_scope": {"original_dsl_hp_replay": True},
            },
        },
    )
    result_path = tmp_path / "RESULT.json"
    result_sha = _write_json(
        result_path,
        {
            "schema_version": "geotarget.exp008-single-raw-endpoint-hp-result/v1",
            "status": "COMPLETE",
            "process_classification": "SUCCESS",
            "artifact_accepted": True,
            "authority_pass": True,
            "source_sha256": source_sha,
            "endpoint_float64_sha256": endpoint_sha,
            "artifact_sha256": lane_sha,
            "truth_read": False,
            "case_or_family_identity_read": False,
            "source_or_problem_modified": False,
            "bounds_or_gauge_added": False,
            "endpoint_unchanged_before_refinement": True,
            "transitive_implementation_current_at_result_write": True,
        },
    )
    bindings = {
        "result_artifact": _artifact_binding(result_path, result_sha),
        "plan_artifact": _artifact_binding(plan_path, plan_sha),
        "lane_artifact": _artifact_binding(lane_path, lane_sha),
    }

    def rung(precision):
        provenance = connector._hp_provenance_sha256(
            result_sha256=result_sha,
            plan_sha256=plan_sha,
            lane_sha256=lane_sha,
            source_sha256=source_sha,
            endpoint_bits=bits,
            endpoint_sha256=endpoint_sha,
            precision_bits=precision,
        )
        return {
            "precision_bits": precision,
            "provenance_sha256": provenance,
            "raw_answer_decimal": "1",
            "full_tuple_decimal": ["1", "2"],
            **bindings,
        }

    subset_sha = connector.subset_sha256(source_sha, [endpoint_sha, "f" * 64])
    # A second, distinct endpoint is required by the private schema.  It can
    # reuse the original artifacts only after binding a matching PLAN, so the
    # unit directly exercises _rung for the custody contract instead.
    return source_sha, endpoint_sha, bits, rung, subset_sha


def test_original_result_plan_lane_provenance_and_numeric_parity(tmp_path):
    source_sha, endpoint_sha, bits, rung, _ = _private_subset(tmp_path)
    value = rung(768)
    validated = connector._rung(
        value,
        precision_bits=768,
        dimension=2,
        source_sha256=source_sha,
        endpoint_bits=bits,
        endpoint_sha256=endpoint_sha,
    )
    assert validated["numeric_guard_branch_parity"] is True


def test_numeric_guard_parity_failure_is_not_rescued_by_exact_route(tmp_path):
    source_sha, endpoint_sha, bits, rung, _ = _private_subset(tmp_path, guard_ok=False)
    with pytest.raises(connector.ConnectorFailure, match="numeric replay lane"):
        connector._rung(
            rung(1024),
            precision_bits=1024,
            dimension=2,
            source_sha256=source_sha,
            endpoint_bits=bits,
            endpoint_sha256=endpoint_sha,
        )
