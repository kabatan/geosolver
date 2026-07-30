from __future__ import annotations

import numpy as np

from real_seam_patch import transform_augmented_residual


def test_lift_matches_transformed_normal_rhs_and_scale() -> None:
    J = np.array([[5.0, 0.2], [0.0, 1.0], [2.0, -0.5]])
    r = np.array([12.0, -1.0, 5.0])
    transformed = transform_augmented_residual(J, r, 1e-3)
    assert transformed.activated
    assert transformed.direction_change > 1e-5
    scaled = transform_augmented_residual(3.0 * J, 3.0 * r, 9e-3)
    assert scaled.activated
    np.testing.assert_allclose(scaled.residual, 3.0 * transformed.residual, rtol=2e-12, atol=2e-12)


def test_rank_and_ambiguous_frame_fail_closed() -> None:
    rank = transform_augmented_residual(
        np.array([[1.0, 0.0], [0.0, 0.0]]), np.array([2.0, 0.0]), 1e-16
    )
    assert not rank.activated
    repeated = transform_augmented_residual(np.eye(2), np.array([2.0, 3.0]), 1e-3)
    assert not repeated.activated
    assert repeated.reason == "eigenframe"


def test_real_candidate_and_quarter_lane_adapter_load() -> None:
    import real_adapter
    import real_candidate

    assert real_candidate.REFERENCE_NAME == real_adapter.CANDIDATE
    manifest = real_adapter.configuration_manifest()
    assert manifest["baseline_minimum_share"] == 0.75
    assert manifest["case_family_truth_target_or_outcome_routing"] is False


def test_smooth_source_scan_repairs_thin_ad_capability_mismatch() -> None:
    import real_candidate

    class SmoothUnsupported:
        construction = (("q", "Distance(P, Q)"),)
        constraints = (("q*q", "radius*radius"),)

        def relation_rows(self, _start):
            return (None,)

    class NonsmoothUnsupported:
        construction = ()
        constraints = (("abs(x)", "1"),)

        def relation_rows(self, _start):
            return (None,)

    assert real_candidate._source_smooth_at_start(SmoothUnsupported(), [0.0])
    assert not real_candidate._source_smooth_at_start(NonsmoothUnsupported(), [0.0])
