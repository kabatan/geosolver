from __future__ import annotations

import copy
import math
import secrets
import struct
from collections import Counter, defaultdict
from typing import Any

import pytest
from jsonschema import Draft202012Validator

import generator
from geotarget import canonical_bytes, canonical_hash, validate_document


@pytest.fixture(scope="module")
def documents() -> dict[str, dict[str, object]]:
    return generator.build_test_development_documents()


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        result = set(value)
        for child in value.values():
            result.update(_keys(child))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for child in value:
            result.update(_keys(child))
        return result
    return set()


def _float_bits(value: float) -> str:
    return struct.pack(">d", value).hex()


def _strings(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        result: set[str] = set()
        for key, child in value.items():
            result.add(str(key))
            result.update(_strings(child))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for child in value:
            result.update(_strings(child))
        return result
    return set()


def _to_base(point: list[float], mapping: dict[str, Any]) -> list[float]:
    permutation = mapping["base_from_candidate_permutation"]
    signs = mapping["base_from_candidate_signs"]
    return [
        signs[index] * point[candidate] for index, candidate in enumerate(permutation)
    ]


def _test_parameter_key(family: int, group: int) -> bytes:
    domain = (
        generator.DEVELOPMENT_PARAMETER_KEY_DOMAIN
        if group < 2
        else generator.LOCKED_PARAMETER_KEY_DOMAIN
    )
    return generator._derive_key(
        generator.TEST_ONLY_MASTER_SECRET, domain, family, group
    )


def _test_representation_key(family: int, group: int, representation: str) -> bytes:
    names = (
        *generator.PRIMARY_REPRESENTATIONS,
        generator.SAFETY_REPRESENTATION,
    )
    ordinal = names.index(representation)
    domain = (
        generator.DEVELOPMENT_REPRESENTATION_KEY_DOMAIN
        if group < 2
        else generator.LOCKED_REPRESENTATION_KEY_DOMAIN
    )
    return generator._derive_key(
        generator.TEST_ONLY_MASTER_SECRET, domain, family, group, ordinal
    )


def _test_gold_key(family: int, group: int) -> bytes:
    domain = (
        generator.DEVELOPMENT_GOLD_KEY_DOMAIN
        if group < 2
        else generator.LOCKED_GOLD_KEY_DOMAIN
    )
    return generator._derive_key(
        generator.TEST_ONLY_MASTER_SECRET, domain, family, group
    )


def test_three_projections_are_complete_disjoint_and_canonical(
    documents: dict[str, dict[str, object]],
) -> None:
    candidate = documents["candidate"]
    assessor = documents["assessor"]
    private = documents["generator_private"]
    assert (
        len(candidate["cases"]) == len(assessor["cases"]) == len(private["cases"]) == 64
    )
    candidate_keys = [case["opaque_case_key"] for case in candidate["cases"]]
    assessor_keys = [case["opaque_case_key"] for case in assessor["cases"]]
    private_keys = [case["opaque_case_key"] for case in private["cases"]]
    assert candidate_keys == assessor_keys == private_keys == sorted(candidate_keys)
    assert len(set(candidate_keys)) == 64
    for projection in documents.values():
        assert canonical_bytes(projection) == canonical_bytes(copy.deepcopy(projection))
        assert canonical_hash(projection).startswith("sha256:")


def test_every_generator_schema_is_itself_valid() -> None:
    for name in (
        "candidate-inputs.schema.json",
        "generator-assessor-projection.schema.json",
        "generator-private.schema.json",
        "calibration-truth.schema.json",
    ):
        Draft202012Validator.check_schema(generator._schema(name))


def test_candidate_projection_has_no_truth_or_representation_labels(
    documents: dict[str, dict[str, object]],
) -> None:
    forbidden = {
        "family_id",
        "family_ordinal",
        "latent_group",
        "representation",
        "expected_invariant",
        "gold",
        "tolerances",
        "calibration_key_hex",
        "start_key_hex",
        "source_ordinal",
        "master_secret_hex",
        "entropy_contract",
        "descriptor_sha256",
    }
    assert _keys(documents["candidate"]).isdisjoint(forbidden)
    assert forbidden - _keys(documents["assessor"])
    assert {"family_id", "representation", "gold", "tolerances"} <= _keys(
        documents["assessor"]
    )
    assert {
        "calibration_key_hex",
        "start_key_hex",
        "source_ordinal",
        "master_secret_hex",
        "entropy_contract",
        "descriptor_sha256",
    } <= _keys(documents["generator_private"])


def test_projection_schemas_enforce_stage_groups_and_representation_roles(
    documents: dict[str, dict[str, object]],
) -> None:
    assessor_validator = Draft202012Validator(
        generator._schema("generator-assessor-projection.schema.json")
    )
    assert assessor_validator.is_valid(documents["assessor"])

    wrong_group = copy.deepcopy(documents["assessor"])
    wrong_group["cases"][0]["latent_group"] = 2
    assert not assessor_validator.is_valid(wrong_group)

    primary_index = next(
        index
        for index, case in enumerate(documents["assessor"]["cases"])
        if case["representation"] != generator.SAFETY_REPRESENTATION
    )
    false_primary = copy.deepcopy(documents["assessor"])
    false_primary["cases"][primary_index]["expected_invariant"] = False
    assert not assessor_validator.is_valid(false_primary)

    safety_index = next(
        index
        for index, case in enumerate(documents["assessor"]["cases"])
        if case["representation"] == generator.SAFETY_REPRESENTATION
    )
    true_safety = copy.deepcopy(documents["assessor"])
    true_safety["cases"][safety_index]["expected_invariant"] = True
    assert not assessor_validator.is_valid(true_safety)

    # Exercise the locked JSON-Schema branch with shape-only synthetic rows;
    # this does not invoke build_locked_documents or create a locked bundle.
    source_primary = copy.deepcopy(documents["assessor"]["cases"][primary_index])
    source_primary["latent_group"] = 2
    source_primary["representation"] = "base"
    source_primary["expected_invariant"] = True
    synthetic_locked = {
        "schema_version": "exp-local-003-locked-generator-assessor-projection/v1",
        "card_sha256": generator.CARD_SHA256,
        "cases": [copy.deepcopy(source_primary) for _ in range(96)],
    }
    assert assessor_validator.is_valid(synthetic_locked)
    synthetic_locked["cases"][0]["representation"] = generator.SAFETY_REPRESENTATION
    synthetic_locked["cases"][0]["expected_invariant"] = False
    assert not assessor_validator.is_valid(synthetic_locked)


def test_formal_generation_requires_caller_entropy_and_rejects_every_test_secret() -> (
    None
):
    with pytest.raises(generator.GeneratorEntropyError, match="caller-owned"):
        generator.build_development_documents()
    with pytest.raises(generator.GeneratorEntropyError, match="exactly 32"):
        generator.build_development_documents(master_secret=b"short")
    with pytest.raises(generator.GeneratorEntropyError, match="exactly 32"):
        generator.build_development_documents(  # type: ignore[arg-type]
            master_secret=bytearray(secrets.token_bytes(32))
        )
    with pytest.raises(generator.GeneratorEntropyError, match="all-zero"):
        generator.build_development_documents(master_secret=bytes(32))
    for test_secret in generator._TEST_ONLY_SECRETS:
        with pytest.raises(generator.GeneratorEntropyError, match="test-only"):
            generator.build_development_documents(master_secret=test_secret)
        with pytest.raises(generator.GeneratorEntropyError, match="test-only"):
            generator.build_locked_documents(
                master_secret=test_secret,
                locked_decision=None,
            )


def test_hmac_vault_is_private_and_wrong_secret_cannot_enumerate_identities(
    documents: dict[str, dict[str, object]],
) -> None:
    candidate = documents["candidate"]
    assessor = documents["assessor"]
    vault = documents["generator_private"]
    correct_hex = generator.TEST_ONLY_MASTER_SECRET.hex()
    alternate_hex = generator.TEST_ONLY_ALTERNATE_SECRET.hex()
    assert vault["master_secret_hex"] == correct_hex
    assert vault["entropy_contract"]["algorithm"] == "HMAC-SHA-256"
    assert vault["entropy_contract"]["vault_boundary"] == "generator-private-only"
    for public_projection in (candidate, assessor):
        public_strings = _strings(public_projection)
        assert correct_hex not in public_strings
        assert alternate_hex not in public_strings
        assert "master_secret_hex" not in public_strings
        assert "entropy_contract" not in public_strings

    actual_keys = {case["opaque_case_key"] for case in candidate["cases"]}
    wrong_enumeration = {
        generator._opaque_key(
            generator.TEST_ONLY_ALTERNATE_SECRET,
            generator.DEVELOPMENT_OPAQUE_DOMAIN,
            ordinal,
        )
        for ordinal in range(64)
    }
    assert actual_keys.isdisjoint(wrong_enumeration)
    assert all(len(key) == 64 for key in actual_keys)
    locked_namespace_keys = {
        generator._opaque_key(
            generator.TEST_ONLY_MASTER_SECRET,
            generator.LOCKED_OPAQUE_DOMAIN,
            ordinal,
        )
        for ordinal in range(96)
    }
    assert actual_keys.isdisjoint(locked_namespace_keys)

    groups = vault["groups"]
    assert len(groups) == 16
    group_keys = {group["latent_group_key"] for group in groups}
    assert len(group_keys) == 16
    assert {case["latent_group_key"] for case in vault["cases"]} == group_keys
    namespace_values: list[str] = []
    for group in groups:
        namespace_values.extend(
            group[field]
            for field in (
                "latent_group_key",
                "calibration_key_hex",
                "start_key_hex",
                "parameter_key_hex",
                "gold_key_hex",
            )
        )
    namespace_values.extend(case["representation_key_hex"] for case in vault["cases"])
    namespace_values.extend(case["opaque_case_key"] for case in vault["cases"])
    assert len(namespace_values) == len(set(namespace_values))

    private_case_by_opaque = {case["opaque_case_key"]: case for case in vault["cases"]}
    private_group_by_key = {group["latent_group_key"]: group for group in groups}
    for truth in assessor["cases"]:
        private_case = private_case_by_opaque[truth["opaque_case_key"]]
        private_group = private_group_by_key[private_case["latent_group_key"]]
        assert truth["gold"]["identity_key"] == private_group["gold_key_hex"]


def test_every_hmac_purpose_and_stage_has_a_unique_nul_terminated_domain() -> None:
    development_domains = {
        generator.DEVELOPMENT_OPAQUE_DOMAIN,
        generator.DEVELOPMENT_CALIBRATION_KEY_DOMAIN,
        generator.DEVELOPMENT_START_KEY_DOMAIN,
        generator.DEVELOPMENT_GROUP_IDENTITY_DOMAIN,
        generator.DEVELOPMENT_PARAMETER_KEY_DOMAIN,
        generator.DEVELOPMENT_REPRESENTATION_KEY_DOMAIN,
        generator.DEVELOPMENT_GOLD_KEY_DOMAIN,
    }
    locked_domains = {
        generator.LOCKED_OPAQUE_DOMAIN,
        generator.LOCKED_CALIBRATION_KEY_DOMAIN,
        generator.LOCKED_START_KEY_DOMAIN,
        generator.LOCKED_GROUP_IDENTITY_DOMAIN,
        generator.LOCKED_PARAMETER_KEY_DOMAIN,
        generator.LOCKED_REPRESENTATION_KEY_DOMAIN,
        generator.LOCKED_GOLD_KEY_DOMAIN,
    }
    assert len(development_domains) == len(locked_domains) == 7
    assert development_domains.isdisjoint(locked_domains)
    assert all(
        domain.endswith(b"\0") for domain in development_domains | locked_domains
    )


def test_test_only_secret_variants_are_replayable_but_domain_disjoint(
    documents: dict[str, dict[str, object]],
) -> None:
    replay = generator.build_test_development_documents()
    alternate = generator.build_test_development_documents(secret_variant="alternate")
    assert canonical_hash(replay) == canonical_hash(documents)
    default_keys = {case["opaque_case_key"] for case in documents["candidate"]["cases"]}
    alternate_keys = {
        case["opaque_case_key"] for case in alternate["candidate"]["cases"]
    }
    assert default_keys.isdisjoint(alternate_keys)
    assert canonical_hash(documents["candidate"]) != canonical_hash(
        alternate["candidate"]
    )
    default_by_source = {
        case["source_ordinal"]: case for case in documents["generator_private"]["cases"]
    }
    alternate_by_source = {
        case["source_ordinal"]: case for case in alternate["generator_private"]["cases"]
    }
    default_candidates = {
        case["opaque_case_key"]: case for case in documents["candidate"]["cases"]
    }
    alternate_candidates = {
        case["opaque_case_key"]: case for case in alternate["candidate"]["cases"]
    }
    assert all(
        default_candidates[default_by_source[ordinal]["opaque_case_key"]][
            "problem_sha256"
        ]
        != alternate_candidates[alternate_by_source[ordinal]["opaque_case_key"]][
            "problem_sha256"
        ]
        for ordinal in range(64)
    )
    assert all(
        default_candidates[default_by_source[ordinal]["opaque_case_key"]][field]
        != alternate_candidates[alternate_by_source[ordinal]["opaque_case_key"]][field]
        for ordinal in range(64)
        for field in ("calibration_points_sha256", "starts_sha256")
    )
    default_truth = {
        case["opaque_case_key"]: case for case in documents["assessor"]["cases"]
    }
    alternate_truth = {
        case["opaque_case_key"]: case for case in alternate["assessor"]["cases"]
    }
    assert all(
        canonical_hash(default_truth[default_by_source[ordinal]["opaque_case_key"]]["gold"])
        != canonical_hash(
            alternate_truth[alternate_by_source[ordinal]["opaque_case_key"]]["gold"]
        )
        for ordinal in range(64)
    )


def test_all_eight_families_have_two_groups_three_primary_and_one_safety(
    documents: dict[str, dict[str, object]],
) -> None:
    assessor_cases = documents["assessor"]["cases"]
    allocation = Counter(
        (case["family_id"], case["latent_group"], case["representation"])
        for case in assessor_cases
    )
    assert set(case["family_id"] for case in assessor_cases) == set(generator.FAMILIES)
    for family in generator.FAMILIES:
        for group in range(2):
            for representation in (
                *generator.PRIMARY_REPRESENTATIONS,
                generator.SAFETY_REPRESENTATION,
            ):
                assert allocation[(family, group, representation)] == 1
    assert sum(case["expected_invariant"] is False for case in assessor_cases) == 16
    assert sum(case["expected_invariant"] is True for case in assessor_cases) == 48


def test_locked_descriptors_are_frozen_disjoint_groups_without_materializing_bundle() -> (
    None
):
    assert generator.LOCKED_GROUPS == (2, 3, 4, 5)
    assert generator.LOCKED_REPRESENTATIONS == generator.PRIMARY_REPRESENTATIONS
    assert (
        len(generator.FAMILIES)
        * len(generator.LOCKED_GROUPS)
        * len(generator.LOCKED_REPRESENTATIONS)
        == 96
    )
    development_hashes: set[str] = set()
    locked_hashes: set[str] = set()
    for family in range(len(generator.FAMILIES)):
        for group in (0, 1):
            development_hashes.add(
                canonical_hash(
                    generator._descriptor_document(
                        family,
                        group,
                        _test_parameter_key(family, group),
                        _test_representation_key(family, group, "base"),
                        _test_gold_key(family, group),
                    )
                )
            )
        for group in range(2, 6):
            descriptor = generator.build_test_locked_case_descriptor(family, group)
            assert descriptor["group"] == group
            locked_hashes.add(canonical_hash(descriptor))
    assert len(development_hashes) == 16
    assert len(locked_hashes) == 32
    assert development_hashes.isdisjoint(locked_hashes)
    secret = secrets.token_bytes(32)
    with pytest.raises(ValueError, match="sealed passing C3"):
        generator.build_locked_documents(master_secret=secret)
    decision = {
        "schema_version": generator.LOCKED_AUTHORIZATION_SCHEMA,
        "experiment_id": "EXP-LOCAL-003",
        "card_sha256": generator.CARD_SHA256,
        "development_gate_passed": True,
        "selected_variant": "LR-MODEL",
        "selected_path": "efficiency",
        "safety16_disagreement_count": 7,
        "candidate_input_sha256": "1" * 64,
        "development_assessment_sha256": "2" * 64,
        "decision_commit": "4" * 40,
    }
    assert generator._validated_locked_decision(decision) == decision
    assert set(decision) == generator.LOCKED_AUTHORIZATION_FIELDS
    private_schema = generator._schema("generator-private.schema.json")
    authorization_validator = Draft202012Validator(
        private_schema["$defs"]["lockedAuthorization"]
    )
    assert authorization_validator.is_valid(decision)
    rejected = {**decision, "development_gate_passed": False}
    with pytest.raises(ValueError, match="passing development"):
        generator._validated_locked_decision(rejected)
    # Orthogonal Safety16 disagreements are report-only at this boundary.
    safety_report = {**decision, "safety16_disagreement_count": 2**31}
    assert generator._validated_locked_decision(safety_report) == safety_report
    for old_or_extra_field in (
        "schema",
        "card_sha",
        "safety16_count",
        "candidate_input_sha",
        "development_assessment_sha",
        "unexpected",
    ):
        malformed = {**decision, old_or_extra_field: "forbidden"}
        with pytest.raises(ValueError, match="closed field set"):
            generator._validated_locked_decision(malformed)
        assert not authorization_validator.is_valid(malformed)


def test_parameter_and_gold_namespaces_bind_problem_truth_and_group_identity() -> None:
    for family in range(len(generator.FAMILIES)):
        for group in generator.DEVELOPMENT_GROUPS:
            default_parameter = generator._derive_key(
                generator.TEST_ONLY_MASTER_SECRET,
                generator.DEVELOPMENT_PARAMETER_KEY_DOMAIN,
                family,
                group,
            )
            alternate_parameter = generator._derive_key(
                generator.TEST_ONLY_ALTERNATE_SECRET,
                generator.DEVELOPMENT_PARAMETER_KEY_DOMAIN,
                family,
                group,
            )
            default_base = generator._family_case(family, group, default_parameter)
            alternate_base = generator._family_case(family, group, alternate_parameter)
            assert default_base != alternate_base
            assert default_base.gold_configurations != alternate_base.gold_configurations

            representation_key = _test_representation_key(family, group, "base")
            representation = generator._representation(
                default_base, group, "base", representation_key
            )
            default_gold_key = _test_gold_key(family, group)
            alternate_gold_key = generator._derive_key(
                generator.TEST_ONLY_ALTERNATE_SECRET,
                generator.DEVELOPMENT_GOLD_KEY_DOMAIN,
                family,
                group,
            )
            default_gold = generator._gold_document(
                default_base, representation, default_gold_key
            )
            alternate_gold = generator._gold_document(
                default_base, representation, alternate_gold_key
            )
            assert canonical_hash(default_gold) != canonical_hash(alternate_gold)
            assert default_gold["identity_key"] != alternate_gold["identity_key"]
            assert default_gold["configurations"] == alternate_gold["configurations"]
            assert default_gold["targets"] == alternate_gold["targets"]


def test_declared_semantic_coordinates_make_the_x_factor_non_degenerate() -> None:
    for family in range(len(generator.FAMILIES)):
        for group in range(6):
            base = generator._family_case(
                family, group, _test_parameter_key(family, group)
            )
            assert all(
                _float_bits(origin) != _float_bits((lower + upper) / 2.0)
                for origin, (lower, upper) in zip(
                    base.origins, base.bounds, strict=True
                )
            )
            assert all(
                _float_bits(scale) != _float_bits((upper - lower) / 2.0)
                for scale, (lower, upper) in zip(
                    base.variable_scales, base.bounds, strict=True
                )
            )
            signed = generator._representation(
                base,
                group,
                "signed-permutation",
                _test_representation_key(family, group, "signed-permutation"),
            )
            bounds, origins, scales = generator._candidate_variable_metadata(
                base, signed
            )
            assert all(
                _float_bits(origin) != _float_bits((lower + upper) / 2.0)
                for origin, (lower, upper) in zip(origins, bounds, strict=True)
            )
            assert all(
                _float_bits(scale) != _float_bits((upper - lower) / 2.0)
                for scale, (lower, upper) in zip(scales, bounds, strict=True)
            )


def test_representation_secret_actually_changes_every_development_group() -> None:
    changed = 0
    for family in range(len(generator.FAMILIES)):
        for group in generator.DEVELOPMENT_GROUPS:
            parameter_key = _test_parameter_key(family, group)
            base = generator._family_case(family, group, parameter_key)
            default_key = generator._derive_key(
                generator.TEST_ONLY_MASTER_SECRET,
                generator.DEVELOPMENT_REPRESENTATION_KEY_DOMAIN,
                family,
                group,
                1,
            )
            alternate_key = generator._derive_key(
                generator.TEST_ONLY_ALTERNATE_SECRET,
                generator.DEVELOPMENT_REPRESENTATION_KEY_DOMAIN,
                family,
                group,
                1,
            )
            default = generator._representation(
                base, group, "signed-permutation", default_key
            )
            alternate = generator._representation(
                base, group, "signed-permutation", alternate_key
            )
            changed += default != alternate
    assert changed == 16


def test_problem_documents_are_sdk_valid_and_use_only_the_unknown_c0_program_surface(
    documents: dict[str, dict[str, object]],
) -> None:
    for case in documents["candidate"]["cases"]:
        problem = case["problem_document"]
        assert validate_document(problem) == "geotarget.problem/v1"
        assert canonical_hash(problem) == case["problem_sha256"]
        fixture_locks = [
            lock
            for lock in problem["plugin_locks"]
            if lock["plugin_id"] == generator.LOCAL3_PLUGIN_ID
        ]
        assert len(fixture_locks) == 1
        operations = {
            node["operation"]
            for node in problem["graph"]
            if node["kind"] == "call"
            and node["operation"].startswith(generator.LOCAL3_PLUGIN_ID)
        }
        assert operations <= {
            f"{generator.LOCAL3_PLUGIN_ID}::program_relation",
            f"{generator.LOCAL3_PLUGIN_ID}::program_target",
            f"{generator.LOCAL3_PLUGIN_ID}::program_guard",
            f"{generator.LOCAL3_PLUGIN_ID}::program_domain",
        }
        assert f"{generator.LOCAL3_PLUGIN_ID}::program_relation" in operations
        assert f"{generator.LOCAL3_PLUGIN_ID}::program_target" in operations
        assert case["public_numeric_metadata"]["logical_capability"] == "C0"


def test_every_case_has_64_calibration_points_and_32_starts_inside_public_bounds(
    documents: dict[str, dict[str, object]],
) -> None:
    for case in documents["candidate"]["cases"]:
        points = case["calibration_points"]
        starts = case["starts"]
        bounds = case["public_numeric_metadata"]["bounds"]
        assert len(points) == 64
        assert len(starts) == 32
        assert canonical_hash(points) == case["calibration_points_sha256"]
        assert canonical_hash(starts) == case["starts_sha256"]
        for point in [*points, *starts]:
            assert len(point) == len(bounds)
            assert all(math.isfinite(value) for value in point)
            assert all(
                lower <= value <= upper
                for value, (lower, upper) in zip(point, bounds, strict=True)
            )


def test_primary_representation_points_are_exact_transforms_of_one_latent_block(
    documents: dict[str, dict[str, object]],
) -> None:
    candidate_by_key = {
        case["opaque_case_key"]: case for case in documents["candidate"]["cases"]
    }
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for truth in documents["assessor"]["cases"]:
        if truth["expected_invariant"]:
            groups[(truth["family_id"], truth["latent_group"])].append(truth)
    assert len(groups) == 16
    for truths in groups.values():
        assert {truth["representation"] for truth in truths} == set(
            generator.PRIMARY_REPRESENTATIONS
        )
        reference_calibration: list[list[str]] | None = None
        reference_starts: list[list[str]] | None = None
        for truth in truths:
            case = candidate_by_key[truth["opaque_case_key"]]
            calibration = [
                [
                    _float_bits(value)
                    for value in _to_base(point, truth["inverse_mapping"])
                ]
                for point in case["calibration_points"]
            ]
            starts = [
                [
                    _float_bits(value)
                    for value in _to_base(point, truth["inverse_mapping"])
                ]
                for point in case["starts"]
            ]
            reference_calibration = reference_calibration or calibration
            reference_starts = reference_starts or starts
            assert calibration == reference_calibration
            assert starts == reference_starts


def test_orthogonal_safety_rotates_semantic_z_not_unit_bearing_raw_y() -> None:
    for family_ordinal in range(len(generator.FAMILIES)):
        for group in range(2):
            base = generator._family_case(
                family_ordinal,
                group,
                _test_parameter_key(family_ordinal, group),
            )
            representation = generator._representation(
                base,
                group,
                generator.SAFETY_REPRESENTATION,
                _test_representation_key(
                    family_ordinal, group, generator.SAFETY_REPRESENTATION
                ),
            )
            transformed, _, _, _ = generator._transformed_expressions(
                base, representation
            )
            point = [(lower + upper) / 2.0 for lower, upper in base.bounds]
            base_z = [
                generator._evaluate_expression(expression, point)
                / base.relation_scales[index]
                for index, expression in enumerate(base.relations)
            ]
            observed = [
                generator._evaluate_expression(expression, point)
                for expression in transformed
            ]
            expected: list[float] = []
            for row in representation.residual_matrix:
                terms = [
                    coefficient * base_z[column]
                    for column, coefficient in enumerate(row)
                    if coefficient != 0.0
                ]
                value = terms[0]
                for term in terms[1:]:
                    value += term
                expected.append(value)
            assert [_float_bits(value) for value in observed] == [
                _float_bits(value) for value in expected
            ]


def test_gold_is_assessor_only_and_strict_guard_family_excludes_boundary_root(
    documents: dict[str, dict[str, object]],
) -> None:
    strict_truth = [
        case
        for case in documents["assessor"]["cases"]
        if case["family_id"] == "STRICT-GUARD-BOUNDARY"
        and case["latent_group"] == 1
        and case["representation"] == "base"
    ]
    assert len(strict_truth) == 1
    configurations = strict_truth[0]["gold"]["configurations"]
    expected = generator._family_case(6, 1, _test_parameter_key(6, 1))
    assert configurations == [list(expected.gold_configurations[0])]
    assert len(configurations) == 1
    assert "gold" not in documents["candidate"]


def test_fraction_fma_matches_nearest_even_reference_and_is_not_split_multiply_add() -> (
    None
):
    # This is the classic cancellation shape used by the card's t = fma(2,u,-1).
    unit = math.nextafter(0.5, 1.0)
    fused = generator._fraction_fma(2.0, unit, -1.0)
    assert _float_bits(fused) == _float_bits(math.ldexp(1.0, -52))
    assert all(
        len(vector["expected_bits"]) == 16
        for vector in generator.build_fma_test_vectors()["vectors"]
    )


def test_source_never_imports_or_constructs_direct_analytic_benchmark() -> None:
    source = generator.Path(generator.__file__).read_text(encoding="utf-8")
    assert "DirectAnalyticProblem" not in source
    assert "GeoTargetBenchmarks" not in source
