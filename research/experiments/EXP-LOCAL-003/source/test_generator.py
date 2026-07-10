from __future__ import annotations

import copy
import math
import struct
from collections import Counter, defaultdict
from typing import Any

import pytest
from jsonschema import Draft202012Validator

import generator
from geotarget import canonical_bytes, canonical_hash, validate_document


@pytest.fixture(scope="module")
def documents() -> dict[str, dict[str, object]]:
    return generator.build_development_documents()


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


def _to_base(point: list[float], mapping: dict[str, Any]) -> list[float]:
    permutation = mapping["base_from_candidate_permutation"]
    signs = mapping["base_from_candidate_signs"]
    return [
        signs[index] * point[candidate] for index, candidate in enumerate(permutation)
    ]


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
    }
    assert _keys(documents["candidate"]).isdisjoint(forbidden)
    assert forbidden - _keys(documents["assessor"])
    assert {"family_id", "representation", "gold", "tolerances"} <= _keys(
        documents["assessor"]
    )
    assert {"calibration_key_hex", "start_key_hex", "source_ordinal"} <= _keys(
        documents["generator_private"]
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
            base = generator._family_case(family_ordinal, group)
            representation = generator._representation(
                base, group, generator.SAFETY_REPRESENTATION
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
    assert configurations == [[2.0, 1.75]]
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
