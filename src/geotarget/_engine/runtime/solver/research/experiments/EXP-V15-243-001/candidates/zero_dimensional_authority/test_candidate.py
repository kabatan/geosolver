from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


CANDIDATE = _load("zero_dimensional_candidate_test", HERE / "candidate.py")
GENERATED = _load("zero_dimensional_generated_test", HERE / "generated_cases.py")
BRIDGE = _load("zero_dimensional_bridge_test", HERE / "bridge.py")

STORED_AUTHORITY = (
    HERE.parents[1]
    / "results/baseline-corrected-247-180s-seed0-v1/artifacts/"
    "039-OMC009_C/hp/0000-df3f619804a92fdb/authority.json"
)


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _authority_for(source_sha256: str, answer: str = "25"):
    document = json.loads(STORED_AUTHORITY.read_text())
    final = document["final_result"]
    final["source_raw_sha256"] = source_sha256
    for lane in final["original_numerical_replay"]["lanes"]:
        lane["answer"] = answer
    return document


def test_empty_tuple_is_accepted_and_exact_descriptor_survives() -> None:
    payload = GENERATED.generated_family()["rational_geometry_positive"]
    source_sha256 = _digest(payload)

    def backend(*_args, **_kwargs):
        return _authority_for(source_sha256)

    result = CANDIDATE.run_zero_dimensional_authority(
        payload, source_sha256, (), backend=backend
    )
    assert result["status"] == "EXACT_SYMBOLIC_TARGET_READY"
    assert result["eligible"] is True
    assert result["authority_pass"] is True
    assert result["endpoint_float64_sha256"] == (
        "df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119"
    )
    assert result["exact_target_descriptor"][
        "minimal_polynomial_high_to_low"
    ] == [1, -25]
    assert result["exact_target_descriptor"]["numeric_pslq_used"] is False
    assert result["numeric_pslq_descriptor_used"] is False
    assert result["exact_authority_kind"] == (
        "SOURCE_EXACT_SYMBOLIC_MINPOLY_ISOLATOR"
    )
    assert all(result["source_certificates"].values())
    assert all(
        value is False
        for key, value in result["routing_audit"].items()
        if key != "only_source_dimension_and_endpoint_dimension_used"
    )


def test_numerical_pslq_descriptor_is_never_exact_authority() -> None:
    payload = GENERATED.generated_family()["rational_geometry_positive"]
    source_sha256 = _digest(payload)
    authority = _authority_for(source_sha256)
    authority["final_result"]["target_authority"][
        "minimal_polynomial_high_to_low"
    ] = [1, 0, 0, 0, 0, 0, -123456789]
    authority["final_result"]["target_authority"][
        "selected_real_root_index"
    ] = 4

    result = CANDIDATE.run_zero_dimensional_authority(
        payload,
        source_sha256,
        (),
        backend=lambda *_args, **_kwargs: authority,
    )
    assert result["authority_pass"] is True
    assert result["exact_target_descriptor"][
        "minimal_polynomial_high_to_low"
    ] == [1, -25]
    assert result["exact_target_descriptor"]["selected_real_root_index"] == 0
    assert result["numeric_replay_audit"][
        "numerical_recognition_ignored"
    ] is True


def test_nonempty_endpoint_and_positive_dimension_are_ineligible() -> None:
    family = GENERATED.generated_family()
    zero = family["rational_geometry_positive"]
    nonzero = family["positive_dimension_near_miss"]

    def forbidden(*_args, **_kwargs):
        raise AssertionError("ineligible input must not reach authority")

    endpoint_result = CANDIDATE.run_zero_dimensional_authority(
        zero, _digest(zero), (0.0,), backend=forbidden
    )
    source_result = CANDIDATE.run_zero_dimensional_authority(
        nonzero, _digest(nonzero), (), backend=forbidden
    )
    assert endpoint_result["status"] == "INELIGIBLE_FAIL_CLOSED"
    assert source_result["status"] == "INELIGIBLE_FAIL_CLOSED"
    assert endpoint_result["exact_target_descriptor"] is None
    assert source_result["exact_target_descriptor"] is None


def test_digest_mismatch_fails_before_authority() -> None:
    payload = GENERATED.generated_family()["rational_geometry_positive"]

    def forbidden(*_args, **_kwargs):
        raise AssertionError("digest mismatch must not reach authority")

    result = CANDIDATE.run_zero_dimensional_authority(
        payload, "0" * 64, (), backend=forbidden
    )
    assert result["authority_pass"] is False
    assert result["failure_reasons"] == ["SOURCE_DIGEST_MISMATCH"]


def test_invalid_source_replay_fails_closed_even_with_descriptor() -> None:
    payload = GENERATED.generated_family()["rational_geometry_positive"]
    source_sha256 = _digest(payload)
    authority = _authority_for(source_sha256)
    replay = authority["final_result"]["float64_replay"]
    replay["semantic_valid"] = False
    replay["guard_ok"] = False
    replay["guard_violations"] = ["generated invalid guard"]

    result = CANDIDATE.run_zero_dimensional_authority(
        payload,
        source_sha256,
        (),
        backend=lambda *_args, **_kwargs: authority,
    )
    assert result["authority_pass"] is False
    assert result["exact_target_descriptor"] is None
    assert "FLOAT64_SOURCE_REPLAY_REJECTED" in result["failure_reasons"]


def test_transcendental_unrecognized_target_fails_closed() -> None:
    payload = GENERATED.generated_family()["transcendental_near_miss"]
    source_sha256 = _digest(payload)
    authority = _authority_for(source_sha256)
    authority["authority_pass"] = False
    authority["final_result"]["authority_pass"] = False
    authority["final_result"]["target_authority"] = {
        "status": "NO_ALGEBRAIC_RELATION_CONFIRMED",
        "target_relation_confirmed": False,
    }

    result = CANDIDATE.run_zero_dimensional_authority(
        payload,
        source_sha256,
        [],
        backend=lambda *_args, **_kwargs: authority,
    )
    assert result["authority_pass"] is False
    assert result["exact_target_descriptor"] is None
    assert result["failure_reasons"] == [
        "TARGET_NOT_CERTIFIED_ALGEBRAIC_FROM_SOURCE_AST"
    ]


def test_near_transcendental_family_is_statically_rejected() -> None:
    family = GENERATED.generated_family()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("uncertified target must not reach authority")

    for name in (
        "near_transcendental_shift_near_miss",
        "algebraic_argument_sine_near_miss",
        "inverse_trig_near_miss",
        "irrational_circle_phase_near_miss",
    ):
        payload = family[name]
        result = CANDIDATE.run_zero_dimensional_authority(
            payload, _digest(payload), (), backend=forbidden
        )
        assert result["authority_pass"] is False
        assert result["exact_target_descriptor"] is None
        assert result["failure_reasons"] == [
            "TARGET_NOT_CERTIFIED_ALGEBRAIC_FROM_SOURCE_AST"
        ]


def test_exact_source_condition_certificate_accepts_proved_conditions() -> None:
    payload = GENERATED.generated_family()["exact_conditions_positive"]
    assert CANDIDATE._exact_source_conditions_certificate(payload) == ()
    assert CANDIDATE.preflight_zero_dimensional_source(
        payload, _digest(payload)
    ) == ()


def test_extreme_numeric_guard_lexemes_are_preserved_exactly() -> None:
    payload = GENERATED.generated_family()["extreme_numeric_guards_positive"]
    source_sha256 = _digest(payload)
    assert CANDIDATE._exact_source_conditions_certificate(payload) == ()
    result = CANDIDATE.run_zero_dimensional_authority(
        payload,
        source_sha256,
        (),
        backend=lambda *_args, **_kwargs: _authority_for(source_sha256),
    )
    assert result["status"] == "EXACT_SYMBOLIC_TARGET_READY"
    assert result["authority_pass"] is True
    assert result["numeric_pslq_descriptor_used"] is False


def test_nested_assume_and_or_not_are_exact_and_fail_closed() -> None:
    family = GENERATED.generated_family()
    positive = family["nested_boolean_guards_positive"]
    assert CANDIDATE._exact_source_conditions_certificate(positive) == ()
    for name in (
        "nested_boolean_false_near_miss",
        "nested_boolean_unknown_under_not_near_miss",
    ):
        assert CANDIDATE._exact_source_conditions_certificate(
            family[name]
        ) == ("EXACT_GUARD_FALSE_OR_UNPROVED",)


def test_near_unsatisfied_equation_and_guard_fail_before_authority() -> None:
    family = GENERATED.generated_family()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("false exact condition must not reach authority")

    expected = {
        "near_unsatisfied_constraint": "EXACT_CONSTRAINT_FALSE",
        "near_unsatisfied_guard": "EXACT_GUARD_FALSE_OR_UNPROVED",
        "underflow_guard_near_miss": "EXACT_GUARD_FALSE_OR_UNPROVED",
        "extreme_open_bound_near_miss": "EXACT_GUARD_FALSE_OR_UNPROVED",
        "nested_boolean_false_near_miss": "EXACT_GUARD_FALSE_OR_UNPROVED",
        "nested_boolean_unknown_under_not_near_miss": (
            "EXACT_GUARD_FALSE_OR_UNPROVED"
        ),
        "unproved_geometry_guard": "EXACT_GUARD_FALSE_OR_UNPROVED",
    }
    for name, reason in expected.items():
        payload = family[name]
        result = CANDIDATE.run_zero_dimensional_authority(
            payload, _digest(payload), (), backend=forbidden
        )
        assert result["authority_pass"] is False
        assert result["exact_target_descriptor"] is None
        assert result["failure_reasons"] == [reason]


def test_unsupported_target_ast_fails_before_authority() -> None:
    payload = GENERATED.generated_family()["unsupported_target_near_miss"]

    def unsupported(*_args, **_kwargs):
        raise AssertionError("uncertified target must not reach authority")

    result = CANDIDATE.run_zero_dimensional_authority(
        payload, _digest(payload), (), backend=unsupported
    )
    assert result["authority_pass"] is False
    assert result["exact_target_descriptor"] is None
    assert result["failure_reasons"] == [
        "TARGET_NOT_CERTIFIED_ALGEBRAIC_FROM_SOURCE_AST"
    ]


def test_authority_exception_on_certified_target_fails_closed() -> None:
    payload = GENERATED.generated_family()["rational_geometry_positive"]

    def broken(*_args, **_kwargs):
        raise NotImplementedError("generated backend failure")

    result = CANDIDATE.run_zero_dimensional_authority(
        payload, _digest(payload), (), backend=broken
    )
    assert result["authority_pass"] is False
    assert result["exact_target_descriptor"] is None
    assert result["failure_reasons"] == [
        "AUTHORITY_EXCEPTION_NOTIMPLEMENTEDERROR"
    ]


def test_missing_high_precision_replay_is_rejected() -> None:
    payload = GENERATED.generated_family()["rational_geometry_positive"]
    source_sha256 = _digest(payload)
    authority = _authority_for(source_sha256)
    del authority["final_result"]["original_numerical_replay"]
    result = CANDIDATE.run_zero_dimensional_authority(
        payload,
        source_sha256,
        (),
        backend=lambda *_args, **_kwargs: authority,
    )
    assert result["authority_pass"] is False
    assert "HP_REPLAY_LANES_MISSING" in result["failure_reasons"]


def test_duplicate_high_precision_replay_lane_is_rejected() -> None:
    payload = GENERATED.generated_family()["rational_geometry_positive"]
    source_sha256 = _digest(payload)
    authority = _authority_for(source_sha256)
    lanes = authority["final_result"]["original_numerical_replay"]["lanes"]
    lanes.append(dict(lanes[-1]))
    result = CANDIDATE.run_zero_dimensional_authority(
        payload,
        source_sha256,
        (),
        backend=lambda *_args, **_kwargs: authority,
    )
    assert result["authority_pass"] is False
    assert result["failure_reasons"] == ["HP_REPLAY_LANES_MISSING"]


def test_both_stored_zero_dimensional_targets_have_algebraicity_certificate() -> None:
    inputs = (
        HERE.parents[1]
        / "results/baseline-corrected-247-180s-seed0-v1/inputs"
    )
    for name in ("039-OMC009_C.json", "087-OMC142_B.json"):
        assert CANDIDATE._target_is_certified_algebraic(
            (inputs / name).read_bytes()
        )


def test_stored_zero_dimensional_targets_get_direct_exact_descriptors() -> None:
    inputs = (
        HERE.parents[1]
        / "results/baseline-corrected-247-180s-seed0-v1/inputs"
    )
    expected = {
        "039-OMC009_C.json": ([29, -81], 0),
        "087-OMC142_B.json": ([16, -675], 0),
    }
    for name, (polynomial, root_index) in expected.items():
        descriptor, value, reasons = CANDIDATE._exact_symbolic_target(
            (inputs / name).read_bytes()
        )
        assert reasons == ()
        assert value is not None
        assert descriptor is not None
        assert descriptor["minimal_polynomial_high_to_low"] == polynomial
        assert descriptor["selected_real_root_index"] == root_index
        assert descriptor["numeric_pslq_used"] is False


def test_generated_nonrational_algebraic_target_has_exact_isolator() -> None:
    payload = GENERATED.generated_family()["algebraic_geometry_positive"]
    descriptor, value, reasons = CANDIDATE._exact_symbolic_target(payload)
    assert reasons == ()
    assert value is not None
    assert descriptor is not None
    assert descriptor["minimal_polynomial_high_to_low"] == [1, 0, -5]
    assert descriptor["selected_real_root_index"] == 1
    isolator = descriptor["isolating_interval"]
    assert isolator["real_root_index"] == 1
    assert isolator["multiplicity"] == 1


def test_generated_constant_target_has_direct_exact_descriptor() -> None:
    payload = GENERATED.generated_family()["constant_rational_positive"]
    descriptor, value, reasons = CANDIDATE._exact_symbolic_target(payload)
    assert reasons == ()
    assert value is not None
    assert descriptor is not None
    assert descriptor["minimal_polynomial_high_to_low"] == [3, -7]
    assert descriptor["selected_real_root_index"] == 0


def test_both_historical_zero_dimensional_sources_pass_exact_lane() -> None:
    baseline = (
        HERE.parents[1] / "results/baseline-corrected-247-180s-seed0-v1"
    )
    expected = {
        "039-OMC009_C": [29, -81],
        "087-OMC142_B": [16, -675],
    }
    for slug, polynomial in expected.items():
        source = (baseline / "inputs" / f"{slug}.json").read_bytes()
        authority = json.loads(
            (
                baseline
                / "artifacts"
                / slug
                / "hp/0000-df3f619804a92fdb/authority.json"
            ).read_text()
        )
        result = CANDIDATE.run_zero_dimensional_authority(
            source,
            _digest(source),
            (),
            backend=lambda *_args, _authority=authority, **_kwargs: _authority,
        )
        assert result["status"] == "EXACT_SYMBOLIC_TARGET_READY"
        assert result["authority_pass"] is True
        assert result["exact_target_descriptor"][
            "minimal_polynomial_high_to_low"
        ] == polynomial
        assert result["numeric_pslq_descriptor_used"] is False


def test_dispatcher_changes_only_empty_endpoint_route() -> None:
    assert BRIDGE.route_endpoint_text("[]") == "ZERO_DIMENSIONAL_DIRECT"
    assert BRIDGE.route_endpoint_text("[0]") == "UNCHANGED_H1"
    assert BRIDGE.route_endpoint_text("[-1.5,2]") == "UNCHANGED_H1"


def test_dispatcher_rejects_malformed_or_nonfinite_endpoints() -> None:
    for payload in ("{}", "[true]", "[NaN]", '"[]"'):
        try:
            BRIDGE.route_endpoint_text(payload)
        except ValueError:
            pass
        else:
            raise AssertionError(f"malformed endpoint accepted: {payload}")


def test_bridge_preflight_rejects_pi_before_direct_authority(tmp_path) -> None:
    payload = GENERATED.generated_family()["transcendental_near_miss"]
    source = tmp_path / "source.json"
    source.write_bytes(payload)
    assert BRIDGE._zero_dimensional_preflight(source, _digest(payload)) == (
        "TARGET_NOT_CERTIFIED_ALGEBRAIC_FROM_SOURCE_AST",
    )


def test_bridge_preflight_accepts_both_stored_zero_dimensional_sources() -> None:
    inputs = (
        HERE.parents[1]
        / "results/baseline-corrected-247-180s-seed0-v1/inputs"
    )
    for name in ("039-OMC009_C.json", "087-OMC142_B.json"):
        source = inputs / name
        assert BRIDGE._zero_dimensional_preflight(
            source, _digest(source.read_bytes())
        ) == ()


def test_bridge_requires_exact_candidate_digest_authority() -> None:
    observed = _digest((HERE / "candidate.py").read_bytes())
    assert BRIDGE._candidate_digest_failure(observed) is None
    assert BRIDGE._candidate_digest_failure(None) == (
        "CANDIDATE_DIGEST_AUTHORITY_MISSING"
    )
    assert BRIDGE._candidate_digest_failure("x" * 64) == (
        "CANDIDATE_DIGEST_AUTHORITY_MALFORMED"
    )
    assert BRIDGE._candidate_digest_failure("0" * 64) == (
        "CANDIDATE_DIGEST_MISMATCH"
    )
