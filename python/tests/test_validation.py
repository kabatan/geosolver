from __future__ import annotations

import base64
import hashlib
from copy import deepcopy
from pathlib import Path

import pytest
from test_model import build_problem

from geotarget import ProtocolValidationError, parse_json, validate_document
from geotarget.validation import SCHEMA_FILES, schema_directory


def valid_problem() -> dict[str, object]:
    return build_problem().to_dict()


def test_invalid_reference_is_rejected() -> None:
    document = valid_problem()
    document["target"] = "missing"
    with pytest.raises(ProtocolValidationError, match="unknown node reference"):
        validate_document(document)


def test_duplicate_node_is_rejected() -> None:
    document = valid_problem()
    nodes = document["graph"]
    assert isinstance(nodes, list)
    nodes.append(deepcopy(nodes[0]))
    with pytest.raises(ProtocolValidationError, match="duplicate value"):
        validate_document(document)


def test_unknown_plugin_and_schema_version_are_rejected() -> None:
    document = valid_problem()
    nodes = document["graph"]
    assert isinstance(nodes, list)
    call = nodes[-1]
    assert isinstance(call, dict)
    call["operation"] = "33333333-3333-4333-8333-333333333333/not_locked::combine"
    with pytest.raises(ProtocolValidationError, match="unlocked plugin"):
        validate_document(document)

    document = valid_problem()
    document["schema_version"] = "geotarget.problem/v999"
    with pytest.raises(ProtocolValidationError, match="unsupported schema version"):
        validate_document(document)


def test_unknown_variable_non_topological_edge_and_overlapping_roles_are_rejected() -> None:
    document = valid_problem()
    graph = document["graph"]
    assert isinstance(graph, list)
    reference = graph[0]
    assert isinstance(reference, dict)
    reference["variable"] = "missing_variable"
    with pytest.raises(ProtocolValidationError, match="unknown variable reference"):
        validate_document(document)

    document = valid_problem()
    graph = document["graph"]
    assert isinstance(graph, list)
    graph[-1], graph[-2] = graph[-2], graph[-1]
    with pytest.raises(ProtocolValidationError, match="non-topological"):
        validate_document(document)

    document = valid_problem()
    relations = document["relations"]
    assert isinstance(relations, list)
    relation = relations[0]
    assert isinstance(relation, dict)
    document["target"] = relation["node"]
    with pytest.raises(ProtocolValidationError, match="semantic role"):
        validate_document(document)


def test_variable_bounds_match_base_constructor_invariants() -> None:
    document = valid_problem()
    variables = document["variables"]
    assert isinstance(variables, list)
    variable = variables[0]
    assert isinstance(variable, dict)
    variable["lower"] = 5.0
    variable["upper"] = 4.0
    variable["origin"] = 0.0
    with pytest.raises(ProtocolValidationError, match="strictly below"):
        validate_document(document)


def test_wire_shape_has_only_four_node_kinds() -> None:
    document = valid_problem()
    nodes = document["graph"]
    assert isinstance(nodes, list)
    invalid = deepcopy(nodes[0])
    assert isinstance(invalid, dict)
    invalid["id"] = "bad_node"
    invalid["kind"] = "geometry_special_case"
    nodes.append(invalid)
    with pytest.raises(ProtocolValidationError):
        validate_document(document)


def test_strict_json_rejects_duplicates_and_non_finite_numbers() -> None:
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        parse_json('{"a":1,"a":2}')
    with pytest.raises(ValueError, match="non-finite"):
        parse_json('{"a":NaN}')


def test_bundled_schemas_are_byte_identical_to_canonical_sources() -> None:
    bundled = schema_directory()
    repository = Path(__file__).resolve().parents[2] / "schemas"
    for filename in SCHEMA_FILES.values():
        assert (bundled / filename).read_bytes() == (repository / filename).read_bytes()


def valid_manifest() -> dict[str, object]:
    return {
        "schema_version": "geotarget.plugin/v1",
        "plugin_id": "22222222-2222-4222-8222-222222222222/custom",
        "version": "1.0.0",
        "core_abi": "1.0.0",
        "content_hash": "sha256:" + "a" * 64,
        "types": [
            {
                "id": "22222222-2222-4222-8222-222222222222/custom::Point",
                "literal_codec": True,
                "documentation": "point",
            }
        ],
        "primitives": [
            {
                "id": "22222222-2222-4222-8222-222222222222/custom::distance",
                "signatures": [
                    {
                        "arguments": [
                            "22222222-2222-4222-8222-222222222222/custom::Point",
                            "22222222-2222-4222-8222-222222222222/custom::Point",
                        ],
                        "keywords": {},
                        "output": "22222222-2222-4222-8222-222222222222/custom::Real",
                        "variadic": False,
                    }
                ],
                "kernel": {
                    "capabilities": ["C0", "C2"],
                    "smoothness": "smooth_c1",
                    "derivative_mode": "none",
                    "generic_numeric": True,
                    "deterministic": True,
                },
                "documentation": "distance",
            }
        ],
        "relations": [],
        "guards": [],
        "domains": [],
        "branches": [],
        "selectors": [],
    }


def valid_options() -> dict[str, object]:
    return {
        "schema_version": "geotarget.solve-options/v1",
        "wall_time_seconds": 180,
        "seed": 42,
        "preset": "default",
        "answer_level": "exact_if_available",
    }


def test_valid_plugin_manifest_and_solve_options() -> None:
    manifest = valid_manifest()
    assert validate_document(manifest) == "geotarget.plugin/v1"
    options = valid_options()
    assert validate_document(options) == "geotarget.solve-options/v1"

    digest = "sha256:" + "1" * 64
    options["seed"] = "18446744073709551615"
    options["checkpoint"] = {
        "path": "checkpoint/run-1.json",
        "environment_lock": {
            "problem_hash": digest,
            "plugin_locks": [
                {
                    "plugin_id": "22222222-2222-4222-8222-222222222222/custom",
                    "version": "1.0.0",
                    "core_abi": "1.0.0",
                    "content_hash": digest,
                }
            ],
            "policy_hash": digest,
            "environment_hash": digest,
        },
    }
    assert validate_document(options) == "geotarget.solve-options/v1"


def test_plugin_kernel_and_version_invariants() -> None:
    manifest = valid_manifest()
    manifest["version"] = "0.0.0"
    with pytest.raises(ProtocolValidationError, match=r"0\.0\.0"):
        validate_document(manifest)

    manifest = valid_manifest()
    primitives = manifest["primitives"]
    assert isinstance(primitives, list)
    primitive = primitives[0]
    assert isinstance(primitive, dict)
    kernel = primitive["kernel"]
    assert isinstance(kernel, dict)
    kernel["derivative_mode"] = "autodiff"
    with pytest.raises(ProtocolValidationError, match="requires capability C1"):
        validate_document(manifest)


def valid_result() -> dict[str, object]:
    problem_digest = "sha256:" + "b" * 64
    payload = b"x"
    artifact_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    artifact: dict[str, object] = {
        "scheme": "interval_krawczyk",
        "media_type": "application/octet-stream",
        "payload_base64": base64.b64encode(payload).decode("ascii"),
        "digest": artifact_digest,
    }
    identity_hash = "sha256:" + hashlib.sha256(b"-2,0,1|7|5|3|2|2").hexdigest()
    return {
        "schema_version": "geotarget.solve-result/v1",
        "exact_answers": [
            {
                "identity": {
                    "coefficients": ["-2", "0", "1"],
                    "isolating_interval": {
                        "lower": {"numerator": "7", "denominator": "5"},
                        "upper": {"numerator": "3", "denominator": "2"},
                    },
                    "real_root_index": 2,
                },
                "approximation": 1.41421356237,
                "branch_signature": [{"choice_node": "choices", "key": "left"}],
                "configuration_certificate": {
                    "problem_hash": problem_digest,
                    "configuration_hash": "sha256:" + "c" * 64,
                    "artifact": artifact,
                },
                "target_certificate": {
                    "problem_hash": problem_digest,
                    "identity_hash": identity_hash,
                    "artifact": artifact,
                },
            }
        ],
        "provisional_answers": [
            {
                "target": {"lower": "3.14158", "upper": "3.1416"},
                "canonical_residual_bound": 1e-50,
                "branch_signature": [{"choice_node": "choices", "key": "right"}],
                "guard_enclosures": [
                    {
                        "node": "positive_guard",
                        "enclosure": {"lower": "0.1", "upper": "0.2"},
                        "strict": True,
                    }
                ],
                "validation": {
                    "problem_hash": problem_digest,
                    "configuration_hash": "sha256:" + "d" * 64,
                    "method": "independent_hp",
                    "precision_bits": 256,
                    "independent": True,
                    "artifact": artifact,
                },
                "exact_failure": "non_algebraic",
                "exact_failure_detail": "transcendental target",
            }
        ],
        "search_status": "deadline_reached",
        "target_image_status": "finite_observed",
        "coverage": {
            "independent_waves": 3,
            "proposed_tasks": 10,
            "completed_tasks": 8,
            "pending_tasks": 2,
            "explored_shells": [0, 1],
            "last_new_target_seconds": 12.5,
        },
        "environment_lock": {
            "problem_hash": problem_digest,
            "policy_hash": "sha256:" + "e" * 64,
            "environment_hash": "sha256:" + "f" * 64,
            "plugin_locks": [
                {
                    "plugin_id": "22222222-2222-4222-8222-222222222222/custom",
                    "version": "1.0.0",
                    "core_abi": "1.0.0",
                    "content_hash": "sha256:" + "a" * 64,
                }
            ],
        },
        "evidence_log": {
            "content_hash": "sha256:" + "9" * 64,
            "location": "evidence/run-1.jsonl",
        },
    }


def test_result_keeps_configuration_and_target_certificates_separate() -> None:
    result = valid_result()
    assert validate_document(result) == "geotarget.solve-result/v1"

    exact = result["exact_answers"]
    assert isinstance(exact, list)
    first = exact[0]
    assert isinstance(first, dict)
    del first["configuration_certificate"]
    with pytest.raises(ProtocolValidationError):
        validate_document(result)

    result = valid_result()
    exact = result["exact_answers"]
    assert isinstance(exact, list)
    first = exact[0]
    assert isinstance(first, dict)
    identity = first["identity"]
    assert isinstance(identity, dict)
    identity["real_root_index"] = 0
    with pytest.raises(ProtocolValidationError):
        validate_document(result)


def test_certified_empty_result_cannot_contain_answers() -> None:
    result = valid_result()
    result["search_status"] = "empty_certified"
    result["target_image_status"] = "empty_certified"
    with pytest.raises(ProtocolValidationError, match="cannot contain"):
        validate_document(result)


def test_artifact_and_certificate_cross_links_are_verified() -> None:
    result = valid_result()
    exact = result["exact_answers"]
    assert isinstance(exact, list)
    answer = exact[0]
    assert isinstance(answer, dict)
    target_certificate = answer["target_certificate"]
    assert isinstance(target_certificate, dict)
    target_certificate["identity_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ProtocolValidationError, match="identity hash mismatch"):
        validate_document(result)

    result = valid_result()
    exact = result["exact_answers"]
    assert isinstance(exact, list)
    answer = exact[0]
    assert isinstance(answer, dict)
    configuration = answer["configuration_certificate"]
    assert isinstance(configuration, dict)
    artifact = configuration["artifact"]
    assert isinstance(artifact, dict)
    artifact["digest"] = "sha256:" + "0" * 64
    with pytest.raises(ProtocolValidationError, match="does not match payload"):
        validate_document(result)


def test_canonical_rationals_guard_branch_and_coverage_invariants() -> None:
    result = valid_result()
    exact = result["exact_answers"]
    assert isinstance(exact, list)
    answer = exact[0]
    assert isinstance(answer, dict)
    identity = answer["identity"]
    assert isinstance(identity, dict)
    interval = identity["isolating_interval"]
    assert isinstance(interval, dict)
    lower = interval["lower"]
    assert isinstance(lower, dict)
    lower["numerator"] = "14"
    lower["denominator"] = "10"
    with pytest.raises(ProtocolValidationError, match="must be reduced"):
        validate_document(result)

    result = valid_result()
    provisional = result["provisional_answers"]
    assert isinstance(provisional, list)
    answer = provisional[0]
    assert isinstance(answer, dict)
    guards = answer["guard_enclosures"]
    assert isinstance(guards, list)
    guard = guards[0]
    assert isinstance(guard, dict)
    guard["enclosure"] = {"lower": "0", "upper": "0.2"}
    with pytest.raises(ProtocolValidationError, match="not separated"):
        validate_document(result)

    result = valid_result()
    exact = result["exact_answers"]
    assert isinstance(exact, list)
    answer = exact[0]
    assert isinstance(answer, dict)
    signature = answer["branch_signature"]
    assert isinstance(signature, list)
    signature.append(deepcopy(signature[0]))
    with pytest.raises(ProtocolValidationError, match="duplicate choice node"):
        validate_document(result)

    result = valid_result()
    coverage = result["coverage"]
    assert isinstance(coverage, dict)
    coverage["completed_tasks"] = 9
    coverage["pending_tasks"] = 2
    with pytest.raises(ProtocolValidationError, match="exceeds proposed"):
        validate_document(result)


def test_result_dedup_environment_and_evidence_invariants() -> None:
    result = valid_result()
    exact = result["exact_answers"]
    assert isinstance(exact, list)
    exact.append(deepcopy(exact[0]))
    with pytest.raises(ProtocolValidationError, match="duplicate exact identity"):
        validate_document(result)

    result = valid_result()
    provisional = result["provisional_answers"]
    assert isinstance(provisional, list)
    answer = provisional[0]
    assert isinstance(answer, dict)
    guards = answer["guard_enclosures"]
    assert isinstance(guards, list)
    guards.append(deepcopy(guards[0]))
    with pytest.raises(ProtocolValidationError, match="duplicate guard node"):
        validate_document(result)

    result = valid_result()
    environment = result["environment_lock"]
    assert isinstance(environment, dict)
    locks = environment["plugin_locks"]
    assert isinstance(locks, list)
    locks.append(deepcopy(locks[0]))
    with pytest.raises(ProtocolValidationError, match="duplicate value"):
        validate_document(result)

    result = valid_result()
    evidence = result["evidence_log"]
    assert isinstance(evidence, dict)
    evidence["location"] = "   "
    with pytest.raises(ProtocolValidationError, match="location"):
        validate_document(result)


def test_result_rejects_bad_base64_and_certificate_problem_mismatch() -> None:
    result = valid_result()
    exact = result["exact_answers"]
    assert isinstance(exact, list)
    answer = exact[0]
    assert isinstance(answer, dict)
    target = answer["target_certificate"]
    assert isinstance(target, dict)
    artifact = target["artifact"]
    assert isinstance(artifact, dict)
    artifact["payload_base64"] = "***"
    with pytest.raises(ProtocolValidationError, match="strict base64"):
        validate_document(result)

    result = valid_result()
    exact = result["exact_answers"]
    assert isinstance(exact, list)
    answer = exact[0]
    assert isinstance(answer, dict)
    target = answer["target_certificate"]
    assert isinstance(target, dict)
    target["problem_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ProtocolValidationError, match="problems differ"):
        validate_document(result)


def test_exact_failure_includes_guard_not_separated() -> None:
    result = valid_result()
    provisional = result["provisional_answers"]
    assert isinstance(provisional, list)
    answer = provisional[0]
    assert isinstance(answer, dict)
    answer["exact_failure"] = "guard_not_separated"
    assert validate_document(result) == "geotarget.solve-result/v1"
