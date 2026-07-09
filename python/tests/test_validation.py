from __future__ import annotations

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


def test_valid_plugin_manifest_and_solve_options() -> None:
    manifest: dict[str, object] = {
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
                    "derivative_modes": ["autodiff"],
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
    assert validate_document(manifest) == "geotarget.plugin/v1"

    options: dict[str, object] = {
        "schema_version": "geotarget.solve-options/v1",
        "wall_time_seconds": 180,
        "seed": 42,
        "preset": "default",
        "answer_level": "exact_if_available",
    }
    assert validate_document(options) == "geotarget.solve-options/v1"


def valid_result() -> dict[str, object]:
    digest = "sha256:" + "b" * 64
    artifact: dict[str, object] = {
        "scheme": "interval_krawczyk",
        "media_type": "application/octet-stream",
        "payload_base64": "eA==",
        "digest": digest,
    }
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
                    "real_root_index": 1,
                },
                "approximation": 1.41421356237,
                "branch_signature": [{"choice_node": "choices", "key": "left"}],
                "configuration_certificate": {
                    "problem_hash": digest,
                    "configuration_hash": digest,
                    "artifact": artifact,
                },
                "target_certificate": {"identity_hash": digest, "artifact": artifact},
            }
        ],
        "provisional_answers": [
            {
                "target": {"lower": "3.14158", "upper": "3.14160"},
                "canonical_residual_bound": "1e-50",
                "branch_signature": [{"choice_node": "choices", "key": "right"}],
                "validation": {
                    "method": "independent_hp",
                    "precision_bits": 256,
                    "strict_guards_separated": True,
                    "artifact": artifact,
                },
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
        "resume_identity": {
            "graph_hash": digest,
            "policy_hash": digest,
            "environment_hash": digest,
            "plugin_locks": [
                {
                    "plugin_id": "22222222-2222-4222-8222-222222222222/custom",
                    "version": "1.0.0",
                    "core_abi": "1.0.0",
                    "content_hash": digest,
                }
            ],
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
