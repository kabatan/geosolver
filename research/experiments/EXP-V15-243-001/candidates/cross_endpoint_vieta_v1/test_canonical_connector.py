from __future__ import annotations

import copy
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace

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
        "id": "synthetic-custody-id",
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "construction": [],
        "constraints": [],
        "guards": [],
        "answer": "x",
    }
    source_artifact_sha = _write_json(source_path, source)
    projection = dict(source)
    projection.pop("id")
    projection_payload = json.dumps(projection, indent=2, sort_keys=True).encode() + b"\n"
    projection_sha = hashlib.sha256(projection_payload).hexdigest()
    endpoint = [1.0, 2.0]
    bits = [struct.pack(">d", value).hex() for value in endpoint]
    endpoint_sha = connector._endpoint_sha256(bits)
    plan_path = tmp_path / "PLAN.json"
    plan_sha = _write_json(
        plan_path,
        {
            "schema_version": "geotarget.exp008-single-raw-endpoint-hp-plan/v1",
            "source_sha256": source_artifact_sha,
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
                "source_raw_sha256": source_artifact_sha,
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
            "source_sha256": source_artifact_sha,
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
            source_sha256=source_artifact_sha,
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

    subset_sha = connector.subset_sha256(projection_sha, [endpoint_sha, "f" * 64])
    # A second, distinct endpoint is required by the private schema.  It can
    # reuse the original artifacts only after binding a matching PLAN, so the
    # unit directly exercises _rung for the custody contract instead.
    return source_artifact_sha, projection_sha, endpoint_sha, bits, rung, subset_sha


def test_original_result_plan_lane_provenance_and_numeric_parity(tmp_path):
    source_artifact_sha, projection_sha, endpoint_sha, bits, rung, _ = _private_subset(tmp_path)
    value = rung(768)
    validated = connector._rung(
        value,
        precision_bits=768,
        dimension=2,
        artifact_source_sha256=source_artifact_sha,
        source_projection_sha256=projection_sha,
        endpoint_bits=bits,
        endpoint_sha256=endpoint_sha,
    )
    assert validated["numeric_guard_branch_parity"] is True


def test_numeric_guard_parity_failure_is_not_rescued_by_exact_route(tmp_path):
    source_artifact_sha, projection_sha, endpoint_sha, bits, rung, _ = _private_subset(tmp_path, guard_ok=False)
    with pytest.raises(connector.ConnectorFailure, match="numeric replay lane"):
        connector._rung(
            rung(1024),
            precision_bits=1024,
            dimension=2,
            artifact_source_sha256=source_artifact_sha,
            source_projection_sha256=projection_sha,
            endpoint_bits=bits,
            endpoint_sha256=endpoint_sha,
        )


def test_v4_dual_raw_and_projection_sha_binding(tmp_path):
    raw_sha, projection_sha, _endpoint_sha, _bits, _rung_factory, _subset = _private_subset(
        tmp_path
    )
    binding, observed_raw_sha, projection_payload, projection = connector._source(
        {"path": str(tmp_path / "source.json"), "sha256": raw_sha}, projection_sha
    )
    assert binding["sha256"] == raw_sha
    assert observed_raw_sha == raw_sha
    assert hashlib.sha256(projection_payload).hexdigest() == projection_sha
    assert "id" not in projection
    assert raw_sha != projection_sha


def test_v4_crossed_id_mutation_cannot_reuse_original_hp_artifacts(tmp_path):
    raw_sha, projection_sha, endpoint_sha, bits, rung, _subset = _private_subset(tmp_path)
    source_path = tmp_path / "source.json"
    source = json.loads(source_path.read_text())
    source["id"] = "different-custody-id"
    mutated_raw_sha = _write_json(source_path, source)
    assert mutated_raw_sha != raw_sha
    _binding, observed, _payload, _projection = connector._source(
        {"path": str(source_path), "sha256": mutated_raw_sha}, projection_sha
    )
    assert observed == mutated_raw_sha
    with pytest.raises(connector.ConnectorFailure, match="authority binding"):
        connector._rung(
            rung(768),
            precision_bits=768,
            dimension=2,
            artifact_source_sha256=mutated_raw_sha,
            source_projection_sha256=projection_sha,
            endpoint_bits=bits,
            endpoint_sha256=endpoint_sha,
        )


def test_v4_duplicate_top_level_id_is_rejected(tmp_path):
    source_path = tmp_path / "duplicate-id.json"
    payload = (
        b'{"id":"first","id":"second","task":"solve",'
        b'"variables":{"names":["x"]},"construction":[],"constraints":[],'
        b'"guards":[],"answer":"x"}'
    )
    source_path.write_bytes(payload)
    with pytest.raises(connector.ConnectorFailure, match="duplicate JSON key"):
        connector._source(
            {"path": str(source_path), "sha256": hashlib.sha256(payload).hexdigest()},
            "0" * 64,
        )


def _accepted_record(endpoint_sha: str, coefficients: list[int], root_index: int):
    descriptor = {
        "coefficients_high_to_low": coefficients,
        "isolating_interval": {
            "left": str(root_index),
            "right": str(root_index),
            "multiplicity": 1,
            "real_root_index": root_index,
        },
    }
    identity = hashlib.sha256(
        json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    proof = {
        "schema_version": "geotarget.cross-endpoint-vieta-canonical-factor-proof/v1",
        "status": "CANONICAL_FACTOR_ACCEPTED",
        "observed_endpoint_float64_sha256": endpoint_sha,
        "descriptor_identity_sha256": identity,
        "factor_local_real_root_ordinal": root_index,
        "source_raw_answer_exact": True,
        "target_link_exact": True,
        "root_ordinal_attestation_complete": True,
        "attested_real_root_index": root_index,
        "multiplicity": 1,
        "truth_used": False,
        "post_process_used": False,
        "target_set_completeness_claim": False,
    }
    return {
        "status": "CANONICAL_FACTOR_ACCEPTED",
        "descriptor": descriptor,
        "descriptor_identity_sha256": identity,
        "proof_record": proof,
        "proof_record_sha256": hashlib.sha256(
            json.dumps(proof, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "observed_endpoint_float64_sha256": endpoint_sha,
        "unobserved_root_emitted": False,
        "target_set_completeness_claim": False,
    }


def test_materialized_union_keeps_fallback_and_partial_siblings():
    endpoint_shas = ["a" * 64, "b" * 64, "c" * 64]
    first = _accepted_record(endpoint_shas[0], [1, -2], 0)
    sibling = _accepted_record(endpoint_shas[2], [1, 0, -2], 1)
    duplicate = dict(first)
    duplicate["observed_endpoint_float64_sha256"] = endpoint_shas[1]
    duplicate_proof = dict(duplicate["proof_record"])
    duplicate_proof["observed_endpoint_float64_sha256"] = endpoint_shas[1]
    duplicate["proof_record"] = duplicate_proof
    duplicate["proof_record_sha256"] = hashlib.sha256(
        json.dumps(duplicate_proof, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    fallback = {"status": "UNCHANGED", "records": ()}
    union = connector.union_observed_factor_records(
        fallback_result=fallback,
        accepted_records=[first, duplicate, sibling],
        observed_endpoint_sha256=endpoint_shas,
    )
    assert union["fallback_result"] is fallback
    assert union["canonical_emitted_endpoint_count"] == 2
    assert union["descriptor_identity_dedup_count"] == 1
    assert union["unobserved_root_emit_count"] == 0
    assert [item["descriptor"] for item in union["accepted_factor_records"]] == [
        first["descriptor"],
        sibling["descriptor"],
    ]


def test_materialized_union_rejects_mutated_proof():
    endpoint_sha = "d" * 64
    record = _accepted_record(endpoint_sha, [1, -3], 0)
    record["proof_record"] = dict(record["proof_record"])
    record["proof_record"]["target_link_exact"] = False
    record["proof_record_sha256"] = hashlib.sha256(
        json.dumps(record["proof_record"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(connector.ConnectorFailure, match="record binding"):
        connector.union_observed_factor_records(
            fallback_result=object(),
            accepted_records=[record],
            observed_endpoint_sha256=[endpoint_sha],
        )


def _rehash_record(record, *, descriptor_changed: bool):
    if descriptor_changed:
        identity = hashlib.sha256(
            json.dumps(
                record["descriptor"], sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        record["descriptor_identity_sha256"] = identity
        record["proof_record"]["descriptor_identity_sha256"] = identity
    record["proof_record_sha256"] = hashlib.sha256(
        json.dumps(
            record["proof_record"], sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


@pytest.mark.parametrize(
    "mutation,descriptor_changed",
    [
        ("descriptor_ordinal", True),
        ("proof_factor_ordinal", False),
        ("proof_attested_ordinal", False),
        ("descriptor_multiplicity", True),
        ("proof_multiplicity", False),
    ],
)
def test_materialized_union_rejects_each_recomputed_semantic_mutation(
    mutation, descriptor_changed
):
    endpoint_sha = "e" * 64
    record = copy.deepcopy(_accepted_record(endpoint_sha, [1, -5], 0))
    if mutation == "descriptor_ordinal":
        record["descriptor"]["isolating_interval"]["real_root_index"] = 7
    elif mutation == "proof_factor_ordinal":
        record["proof_record"]["factor_local_real_root_ordinal"] = 7
    elif mutation == "proof_attested_ordinal":
        record["proof_record"]["attested_real_root_index"] = 7
    elif mutation == "descriptor_multiplicity":
        record["descriptor"]["isolating_interval"]["multiplicity"] = 9
    else:
        record["proof_record"]["multiplicity"] = 9
    _rehash_record(record, descriptor_changed=descriptor_changed)
    with pytest.raises(connector.ConnectorFailure, match="record binding"):
        connector.union_observed_factor_records(
            fallback_result=object(),
            accepted_records=[record],
            observed_endpoint_sha256=[endpoint_sha],
        )


@pytest.mark.parametrize("layer", ["record", "descriptor", "interval", "proof"])
def test_materialized_union_requires_exact_key_sets(layer):
    endpoint_sha = "f" * 64
    record = copy.deepcopy(_accepted_record(endpoint_sha, [1, -7], 0))
    target = {
        "record": record,
        "descriptor": record["descriptor"],
        "interval": record["descriptor"]["isolating_interval"],
        "proof": record["proof_record"],
    }[layer]
    target["attacker_extension"] = True
    _rehash_record(record, descriptor_changed=layer in {"descriptor", "interval"})
    with pytest.raises(connector.ConnectorFailure):
        connector.union_observed_factor_records(
            fallback_result=object(),
            accepted_records=[record],
            observed_endpoint_sha256=[endpoint_sha],
        )


def test_frozen_file_and_tree_closure_reject_stale_mutations(tmp_path, monkeypatch):
    frozen_file = tmp_path / "Project.toml"
    frozen_file.write_text("[deps]\n")
    frozen_tree = tmp_path / "Nemo"
    frozen_tree.mkdir()
    (frozen_tree / "source.jl").write_text("module Nemo end\n")
    monkeypatch.setattr(
        connector,
        "FROZEN_DEPENDENCIES",
        {frozen_file: hashlib.sha256(frozen_file.read_bytes()).hexdigest()},
    )
    monkeypatch.setattr(
        connector,
        "FROZEN_DIRECTORY_TREES",
        {frozen_tree: connector._directory_tree_sha256(frozen_tree)},
    )
    connector.verify_frozen_dependencies()
    frozen_file.write_text("[deps]\nNemo = \"changed\"\n")
    with pytest.raises(connector.ConnectorFailure, match="closure changed"):
        connector.verify_frozen_dependencies()
    frozen_file.write_text("[deps]\n")
    (frozen_tree / "source.jl").write_text("module DriftedNemo end\n")
    with pytest.raises(connector.ConnectorFailure, match="closure changed"):
        connector.verify_frozen_dependencies()


def test_qqbar_uses_absolute_frozen_julia_project_and_depot(monkeypatch):
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["environment"] = kwargs["env"]
        return SimpleNamespace(returncode=0, stdout='{"status":"FAKE"}\n', stderr="")

    monkeypatch.setattr(connector, "verify_frozen_dependencies", lambda: {})
    monkeypatch.setattr(connector.subprocess, "run", fake_run)
    exact = SimpleNamespace(_extended_worker_source=lambda: "# generated-only fake\n")
    assert connector._run_frozen_qqbar(exact, {}, timeout_seconds=1.0) == {
        "status": "FAKE"
    }
    assert observed["command"][0] == str(connector.JULIA)
    assert Path(observed["command"][0]).is_absolute()
    assert observed["command"][2] == f"--project={connector.JULIA_PROJECT}"
    assert observed["environment"]["JULIA_DEPOT_PATH"] == str(connector.JULIA_DEPOT)
    assert observed["environment"]["JULIA_PROJECT"] == str(connector.JULIA_PROJECT)
