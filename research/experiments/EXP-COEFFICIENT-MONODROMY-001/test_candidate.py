from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import candidate  # noqa: E402


def _quadratic() -> candidate.PolynomialSource:
    return candidate.PolynomialSource(
        (Fraction(1), Fraction(0), Fraction(-1)), True
    )


def test_baseline_floor() -> None:
    for total in range(1, 1000):
        baseline, side = candidate.split_work(total)
        assert baseline + side == total
        assert baseline / total >= 0.75


def test_safe_route_eligibility_fails_closed() -> None:
    assert not candidate.eligible(
        candidate.PolynomialSource((Fraction(1), Fraction(0)), True)
    )[0]
    assert not candidate.eligible(
        candidate.PolynomialSource((Fraction(1), Fraction(0), Fraction(0)), False)
    )[0]
    assert not candidate.eligible(
        candidate.PolynomialSource(
            (Fraction(1), Fraction(0), Fraction(-1)),
            True,
            Fraction(1),
            Fraction(-1),
        )
    )[0]


def test_coefficient_loop_discovers_other_quadratic_sheet() -> None:
    result = candidate.discover(_quadratic(), accepted_start=1.0, side_work_cap=4000)
    assert result.eligible
    assert result.status == "UNKNOWN"
    assert result.loops_completed >= 1
    assert any(abs(value + 1.0) < 1.0e-6 for value in result.proposals)


def test_invalid_start_and_zero_side_work_fail_closed() -> None:
    invalid = candidate.discover(_quadratic(), accepted_start=0.0, side_work_cap=4000)
    assert invalid.proposals == ()
    assert invalid.reason == "START_REPLAY_FAILED"
    empty = candidate.discover(_quadratic(), accepted_start=1.0, side_work_cap=0)
    assert empty.proposals == ()
    assert empty.reason == "NO_SIDE_WORK"


def test_candidate_has_no_answer_or_case_routing_surface() -> None:
    source = (HERE / "candidate.py").read_text(encoding="utf-8")
    for forbidden in (
        "case_id",
        "gold_targets",
        "known_target_count",
        "expected_answer",
        "family_name",
    ):
        assert forbidden not in source
    assert "UNKNOWN_STATUS" in source
