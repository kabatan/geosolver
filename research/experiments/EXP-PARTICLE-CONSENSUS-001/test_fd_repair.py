from __future__ import annotations

from dataclasses import dataclass
import time

import numpy as np

import real_adapter as adapter


@dataclass(frozen=True)
class Observation:
    residual: np.ndarray
    finite: bool
    semantics_valid: bool


class SmoothCase:
    dimension = 2
    residual_dimension = 2
    lower = np.array([-10.0, -10.0])
    upper = np.array([10.0, 10.0])

    def evaluate(self, point):
        x = np.asarray(point, dtype=float)
        residual = np.array([x[0] - 1.0, x[1] + 0.5])
        return Observation(residual, bool(np.all(np.isfinite(residual))), True)


class OpaqueProgram:
    construction = ()
    constraints = (("x0 - 1", 0), ("x1 + 0.5", 0))

    def relation_rows(self, _point):
        return (None, None)


@dataclass(frozen=True)
class Prefix:
    points: tuple[np.ndarray, ...]
    sources: tuple[str, ...]
    scale_exponents: tuple[int | None, ...]
    sha256: str
    activation: dict[str, object]


def _prefix(anchor: np.ndarray | None = None) -> Prefix:
    if anchor is None:
        points = tuple(np.array([3.0 + 0.05 * i, -3.0 + 0.03 * i]) for i in range(16))
    else:
        points = tuple(np.asarray(anchor, dtype=float).copy() for _ in range(16))
    return Prefix(points, tuple("baseline" for _ in points), tuple(0 for _ in points), "original", {})


def test_fully_opaque_ad_uses_charged_fd_only_for_smooth_parity() -> None:
    case = SmoothCase()
    before = _prefix()
    after = adapter._candidate_prefix(case, OpaqueProgram(), before, time.monotonic() + 10.0)
    assert after.activation["particle_consensus_status"] == "eligible"
    assert after.activation["particle_groups"] == 1
    assert after.activation["particle_full_fd_fallback_used"] is True
    assert after.activation["particle_max_charged_fd_relation_rows"] == 2
    side = [i for i in range(len(after.points)) if i % adapter.SIDE_PERIOD == 0]
    safe = sum(np.linalg.norm(case.evaluate(after.points[i]).residual, ord=np.inf) <= 1e-8 for i in side)
    assert safe > 0
    for index in range(len(after.points)):
        if index % adapter.SIDE_PERIOD:
            assert np.array_equal(after.points[index], before.points[index])


def test_nonsmooth_source_capability_is_exact_prefix_fallback() -> None:
    class NonsmoothProgram(OpaqueProgram):
        constraints = (("abs(x0) - 1", 0), ("x1 + 0.5", 0))

    before = _prefix()
    after = adapter._candidate_prefix(SmoothCase(), NonsmoothProgram(), before, time.monotonic() + 10.0)
    assert str(after.activation["particle_consensus_status"]).startswith("fallback:")
    assert all(np.array_equal(left, right) for left, right in zip(after.points, before.points, strict=True))


def test_semantic_branch_parity_unknown_is_exact_prefix_fallback() -> None:
    class BranchCase(SmoothCase):
        def evaluate(self, point):
            raw = super().evaluate(point)
            return Observation(raw.residual, raw.finite, bool(np.asarray(point)[0] <= 0.0))

    before = _prefix(np.array([0.0, -3.0]))
    after = adapter._candidate_prefix(BranchCase(), OpaqueProgram(), before, time.monotonic() + 10.0)
    assert str(after.activation["particle_consensus_status"]).startswith("fallback:")
    assert all(np.array_equal(left, right) for left, right in zip(after.points, before.points, strict=True))


def test_present_but_parity_failed_ad_is_not_reinterpreted_as_opaque() -> None:
    @dataclass(frozen=True)
    class WrongDual:
        value: float
        derivative: np.ndarray

    class ParityFailedProgram(OpaqueProgram):
        def relation_rows(self, point):
            x = np.asarray(point, dtype=float)
            return (
                WrongDual(x[0] + 100.0, np.array([1.0, 0.0])),
                WrongDual(x[1] - 100.0, np.array([0.0, 1.0])),
            )

    before = _prefix()
    after = adapter._candidate_prefix(SmoothCase(), ParityFailedProgram(), before, time.monotonic() + 10.0)
    assert str(after.activation["particle_consensus_status"]).startswith("fallback:")
    assert all(np.array_equal(left, right) for left, right in zip(after.points, before.points, strict=True))


def test_mixed_pass_and_failed_ad_parity_is_not_partially_fd_repaired() -> None:
    @dataclass(frozen=True)
    class Dual:
        value: float
        derivative: np.ndarray

    class MixedParityProgram(OpaqueProgram):
        def relation_rows(self, point):
            x = np.asarray(point, dtype=float)
            return (
                Dual(x[0] - 1.0, np.array([1.0, 0.0])),
                Dual(x[1] - 100.0, np.array([0.0, 1.0])),
            )

    before = _prefix()
    after = adapter._candidate_prefix(SmoothCase(), MixedParityProgram(), before, time.monotonic() + 10.0)
    assert str(after.activation["particle_consensus_status"]).startswith("fallback:")
    assert all(np.array_equal(left, right) for left, right in zip(after.points, before.points, strict=True))


def test_mixed_supported_and_truly_unsupported_rows_are_exact_prefix_fallback() -> None:
    @dataclass(frozen=True)
    class Dual:
        value: float
        derivative: np.ndarray

    class MixedProgram(OpaqueProgram):
        def relation_rows(self, point):
            x = np.asarray(point, dtype=float)
            return (Dual(x[0] - 1.0, np.array([1.0, 0.0])), None)

    before = _prefix()
    after = adapter._candidate_prefix(
        SmoothCase(), MixedProgram(), before, time.monotonic() + 10.0
    )
    assert str(after.activation["particle_consensus_status"]).startswith("fallback:")
    assert all(
        np.array_equal(left, right)
        for left, right in zip(after.points, before.points, strict=True)
    )


def test_full_ad_semantic_invalid_state_is_exact_prefix_fallback() -> None:
    @dataclass(frozen=True)
    class Dual:
        value: float
        derivative: np.ndarray

    class FullProgram(OpaqueProgram):
        def relation_rows(self, point):
            x = np.asarray(point, dtype=float)
            return (
                Dual(x[0] - 1.0, np.array([1.0, 0.0])),
                Dual(x[1] + 0.5, np.array([0.0, 1.0])),
            )

    class InvalidCase(SmoothCase):
        def evaluate(self, point):
            raw = super().evaluate(point)
            return Observation(raw.residual, raw.finite, False)

    before = _prefix()
    after = adapter._candidate_prefix(
        InvalidCase(), FullProgram(), before, time.monotonic() + 10.0
    )
    assert str(after.activation["particle_consensus_status"]).startswith("fallback:")
    assert all(
        np.array_equal(left, right)
        for left, right in zip(after.points, before.points, strict=True)
    )


def test_valid_selector_token_change_is_exact_prefix_fallback() -> None:
    @dataclass(frozen=True)
    class TokenObservation:
        residual: np.ndarray
        finite: bool
        semantics_valid: bool
        branch_token: int

    class SelectorCase(SmoothCase):
        def evaluate(self, point):
            raw = super().evaluate(point)
            token = int(np.asarray(point, dtype=float)[0] >= 3.02)
            return TokenObservation(raw.residual, raw.finite, True, token)

    before = _prefix()
    after = adapter._candidate_prefix(
        SelectorCase(), OpaqueProgram(), before, time.monotonic() + 10.0
    )
    assert str(after.activation["particle_consensus_status"]).startswith("fallback:")
    assert all(
        np.array_equal(left, right)
        for left, right in zip(after.points, before.points, strict=True)
    )


def test_nonsmooth_full_ad_is_exact_prefix_fallback() -> None:
    @dataclass(frozen=True)
    class Dual:
        value: float
        derivative: np.ndarray

    class NonsmoothFullProgram(OpaqueProgram):
        constraints = (("abs(x0) - 1", 0), ("x1 + 0.5", 0))

        def relation_rows(self, point):
            x = np.asarray(point, dtype=float)
            return (
                Dual(abs(x[0]) - 1.0, np.array([1.0, 0.0])),
                Dual(x[1] + 0.5, np.array([0.0, 1.0])),
            )

    before = _prefix()
    after = adapter._candidate_prefix(
        SmoothCase(), NonsmoothFullProgram(), before, time.monotonic() + 10.0
    )
    assert str(after.activation["particle_consensus_status"]).startswith("fallback:")
    assert all(
        np.array_equal(left, right)
        for left, right in zip(after.points, before.points, strict=True)
    )


def test_full_fd_without_a_bounded_side_sample_is_exact_prefix_fallback() -> None:
    class FixedCoordinateCase(SmoothCase):
        lower = np.array([3.0, -10.0])
        upper = np.array([3.0, 10.0])

    before = _prefix(np.array([3.0, -3.0]))
    after = adapter._candidate_prefix(
        FixedCoordinateCase(), OpaqueProgram(), before, time.monotonic() + 10.0
    )
    assert str(after.activation["particle_consensus_status"]).startswith("fallback:")
    assert all(np.array_equal(left, right) for left, right in zip(after.points, before.points, strict=True))


def test_missing_source_metadata_is_exact_prefix_fallback() -> None:
    class UnknownProgram:
        def relation_rows(self, _point):
            return (None, None)

    before = _prefix()
    after = adapter._candidate_prefix(SmoothCase(), UnknownProgram(), before, time.monotonic() + 10.0)
    assert str(after.activation["particle_consensus_status"]).startswith("fallback:")
    assert all(np.array_equal(left, right) for left, right in zip(after.points, before.points, strict=True))
