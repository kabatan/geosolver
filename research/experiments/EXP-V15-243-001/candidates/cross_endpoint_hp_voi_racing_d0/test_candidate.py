from __future__ import annotations

import candidate
import generated_cases


def _trace(result):
    return tuple((row.endpoint_key, row.rung, row.status, row.censored) for row in result.attempts)


def test_equal_budget_loss_false_extra_and_insurance() -> None:
    for family in generated_cases.FAMILIES:
        for seed in range(8):
            case = generated_cases.make_case(family, seed)
            control = candidate.run_racing(
                case.endpoints, generated_cases.Backend(case), candidate.Arm.CONTROL
            )
            racing = candidate.run_racing(
                case.endpoints, generated_cases.Backend(case), candidate.Arm.CANDIDATE
            )
            assert set(control.descriptors).issubset(racing.descriptors)
            assert set(racing.descriptors).issubset(case.expected_descriptors)
            assert racing.charged_callbacks == control.charged_callbacks
            assert racing.charged_wall_seconds == control.charged_wall_seconds
            assert racing.first_probe_insurance_holds
            assert racing.untried_dispatches == 12
            assert racing.revisit_dispatches == 4


def test_endpoint_permutation_and_censor_prefix_metamorphic() -> None:
    case = generated_cases.make_case("misleading_cheap_rung", 11)
    full = candidate.run_racing(
        case.endpoints, generated_cases.Backend(case), candidate.Arm.CANDIDATE
    )
    for salt in range(8):
        transformed = generated_cases.permuted(case, salt)
        result = candidate.run_racing(
            transformed.endpoints,
            generated_cases.Backend(transformed),
            candidate.Arm.CANDIDATE,
        )
        assert result.descriptors == full.descriptors
        assert _trace(result) == _trace(full)
    for cap in range(1, 16):
        prefix = candidate.run_racing(
            case.endpoints,
            generated_cases.Backend(case),
            candidate.Arm.CANDIDATE,
            maximum_dispatches=cap,
        )
        assert _trace(prefix) == _trace(full)[:cap]
        assert set(prefix.descriptors).issubset(full.descriptors)


def test_malformed_and_opaque_fail_closed_without_descriptor() -> None:
    case = generated_cases.make_case("all_fail_opaque", 3)

    def malformed(*_args):
        return object()

    result = candidate.run_racing(case.endpoints, malformed, candidate.Arm.CANDIDATE)
    assert not result.descriptors
    assert result.invalid_outcomes == 16
    assert result.status == "FAIL_CLOSED"
    assert result.first_probe_insurance_holds


def test_mechanism_manifest_excludes_forbidden_routing() -> None:
    manifest = candidate.configuration_manifest()
    assert manifest["untried_insurance_work_fraction_minimum"] == 0.75
    assert manifest["truth_case_family_id_previous_case_outcome_routing"] is False
    assert manifest["pslq_grid_or_path_reordering"] is False
