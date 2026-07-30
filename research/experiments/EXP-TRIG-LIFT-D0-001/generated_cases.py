from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math

import candidate


@dataclass(frozen=True)
class GeneratedCase:
    family: str
    category: str
    block: candidate.TrigBlock
    expect_proposal: bool
    expect_applicable: bool
    replay_mode: str = "accept"


def _phase(
    *,
    unit: str = "radians",
    multiplier: int | Fraction = 1,
    offset: int | Fraction = 0,
    phase_id: str = "phase-0",
    source_operator: str | None = None,
) -> candidate.PhaseSpec:
    operator = source_operator or ("SinCos" if unit == "radians" else "PointOnCircle")
    return candidate.PhaseSpec(
        "theta", unit, Fraction(multiplier), Fraction(offset), operator, phase_id
    )


def _block(
    equations,
    *,
    phase: candidate.PhaseSpec | None = None,
    cosine_phase: candidate.PhaseSpec | None | object = ...,
    lower: float = -math.pi,
    upper: float = math.pi,
    lower_closed: bool = True,
    upper_closed: bool = True,
    semantic_kind: str = "explicit_sin_cos_pair",
    raw_angle_escape: bool = False,
    required_branch: str | None = None,
    required_ordinal: int | None = None,
) -> candidate.TrigBlock:
    actual_phase = _phase() if phase is None else phase
    actual_cosine = actual_phase if cosine_phase is ... else cosine_phase
    return candidate.TrigBlock(
        "theta",
        actual_phase,
        actual_cosine,
        tuple(equations),
        lower,
        upper,
        lower_closed,
        upper_closed,
        semantic_kind,
        raw_angle_escape,
        required_branch,
        required_ordinal,
    )


def cases() -> tuple[GeneratedCase, ...]:
    distance_to_one = candidate.sound_distance_equality_square(
        candidate.DistanceOperand({(0, 0): 2.0, (1, 0): -2.0}), math.sqrt(2.0)
    )
    return (
        GeneratedCase(
            "radian_quadrant_pair",
            "positive",
            _block(({(1, 0): 1.0},)),
            True,
            True,
        ),
        GeneratedCase(
            "point_on_circle_antipodal_pole",
            "positive",
            _block(
                ({(1, 0): 1.0, (0, 0): 1.0},),
                phase=_phase(unit="turns", phase_id="circle-t"),
                lower=0.0,
                upper=1.0,
                upper_closed=False,
                semantic_kind="point_on_circle_angle_pair",
            ),
            True,
            True,
        ),
        GeneratedCase(
            "rational_harmonic_sheet_reconstruction",
            "positive",
            _block(
                ({(1, 0): 1.0},),
                phase=_phase(multiplier=2, phase_id="double-angle"),
                lower=0.0,
                upper=2.0 * math.pi,
                upper_closed=False,
            ),
            True,
            True,
        ),
        GeneratedCase(
            "nonlinear_polynomial_on_unit_circle",
            "positive",
            _block(({(2, 0): 1.0, (0, 2): -1.0},), upper_closed=False),
            True,
            True,
        ),
        GeneratedCase(
            "proved_distance_to_positive_literal_square",
            "positive",
            _block((distance_to_one,)),
            True,
            True,
        ),
        GeneratedCase(
            "negative_multiplier_rational_phase_offset",
            "positive",
            _block(
                ({(1, 0): 1.0},),
                phase=_phase(multiplier=-2, offset=Fraction(1, 3), phase_id="reflected"),
            ),
            True,
            True,
        ),
        GeneratedCase(
            "mixed_radian_turn_phase",
            "negative",
            _block(
                ({(1, 0): 1.0},),
                phase=_phase(unit="radians"),
                cosine_phase=_phase(unit="turns"),
            ),
            False,
            False,
        ),
        GeneratedCase(
            "raw_angle_escape",
            "negative",
            _block(({(1, 0): 1.0},), raw_angle_escape=True),
            False,
            False,
        ),
        GeneratedCase(
            "unit_circle_inconsistent_polynomial",
            "negative",
            _block(({(2, 0): 1.0, (0, 2): 1.0, (0, 0): 1.0},)),
            False,
            True,
        ),
        GeneratedCase(
            "positive_dimensional_circle_identity",
            "negative",
            _block(({(2, 0): 1.0, (0, 2): 1.0, (0, 0): -1.0},)),
            False,
            False,
        ),
        GeneratedCase(
            "untyped_trig_operator",
            "negative",
            _block(
                ({(1, 0): 1.0},),
                phase=_phase(source_operator="OpaqueSinCos"),
            ),
            False,
            False,
        ),
        GeneratedCase(
            "strict_lower_endpoint_root",
            "near_miss",
            _block(
                ({(0, 1): 1.0},),
                lower=0.0,
                upper=0.2,
                lower_closed=False,
            ),
            False,
            True,
        ),
        GeneratedCase(
            "canonical_branch_veto",
            "near_miss",
            _block(
                ({(1, 0): 1.0},),
                lower=0.0,
                upper=math.pi,
                required_branch="counterclockwise",
            ),
            False,
            True,
            "reject_branch",
        ),
        GeneratedCase(
            "canonical_ordinal_veto",
            "near_miss",
            _block(
                ({(1, 0): 1.0},),
                lower=0.0,
                upper=math.pi,
                required_ordinal=1,
            ),
            False,
            True,
            "reject_ordinal",
        ),
        GeneratedCase(
            "finite_but_excessive_sheet_ledger",
            "near_miss",
            _block(({(1, 0): 1.0},), lower=-100.0 * math.pi, upper=100.0 * math.pi),
            False,
            False,
        ),
        GeneratedCase(
            "missing_explicit_cosine_pair",
            "near_miss",
            _block(({(1, 0): 1.0},), cosine_phase=None),
            False,
            False,
        ),
        GeneratedCase(
            "canonical_residual_veto",
            "near_miss",
            _block(({(1, 0): 1.0},)),
            False,
            True,
            "reject_residual",
        ),
    )
