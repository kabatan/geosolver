from __future__ import annotations

from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from interval_rescue import Problem, Var, discover  # noqa: E402


def _point(problem: Problem) -> tuple[float, float]:
    result = discover(problem)
    assert result.applicability.applicable
    assert len(result.proposals) == 1
    proposal = result.proposals[0]
    assert proposal.authority is False
    assert proposal.requires_canonical_source_replay
    return proposal.point


def _close(left: tuple[float, float], right: tuple[float, float]) -> None:
    assert max(abs(a - b) for a, b in zip(left, right, strict=True)) < 1.0e-10


def _base() -> Problem:
    x, y = Var(0), Var(1)
    return Problem((x + y - 3.0, x - y - 1.0), ((1.5, 2.5), (0.5, 1.5)))


def test_variable_and_residual_permutation_are_proposal_invariant() -> None:
    baseline = _point(_base())
    y, x = Var(0), Var(1)
    variable_permuted = Problem(
        (x + y - 3.0, x - y - 1.0),
        ((0.5, 1.5), (1.5, 2.5)),
    )
    transformed = _point(variable_permuted)
    _close(baseline, (transformed[1], transformed[0]))

    x, y = Var(0), Var(1)
    residual_permuted = Problem(
        (x - y - 1.0, x + y - 3.0),
        ((1.5, 2.5), (0.5, 1.5)),
    )
    _close(baseline, _point(residual_permuted))


def test_affine_coordinate_reflection_and_residual_scaling_are_invariant() -> None:
    baseline = _point(_base())
    u, v = Var(0), Var(1)
    x = -2.0 * u + 4.0
    y = 0.5 * v + 0.5
    transformed = Problem(
        (-3.0 * (x + y - 3.0), 0.25 * (x - y - 1.0)),
        ((0.75, 1.25), (0.0, 2.0)),
    )
    point = _point(transformed)
    _close(baseline, (-2.0 * point[0] + 4.0, 0.5 * point[1] + 0.5))


def test_dag_reorder_and_cse_are_proposal_invariant() -> None:
    baseline = _point(_base())
    x, y = Var(0), Var(1)
    reordered = Problem(
        ((y - 3.0) + x, (-y - 1.0) + x),
        ((1.5, 2.5), (0.5, 1.5)),
    )
    _close(baseline, _point(reordered))

    shared_sum = x + y
    twice_x = x + x
    cse = Problem(
        (shared_sum - 3.0, (twice_x - shared_sum) - 1.0),
        ((1.5, 2.5), (0.5, 1.5)),
    )
    _close(baseline, _point(cse))
