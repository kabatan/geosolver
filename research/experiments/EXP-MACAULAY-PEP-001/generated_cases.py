"""Truth-free generated mechanism families for the disposable D0."""

from __future__ import annotations

from dataclasses import dataclass

from candidate import PolynomialBlock


@dataclass(frozen=True)
class GeneratedCase:
    family: str
    category: str
    block: PolynomialBlock
    expect_proposal: bool


def cases() -> tuple[GeneratedCase, ...]:
    return (
        GeneratedCase(
            "univariate_repeated_plus_simple",
            "positive",
            PolynomialBlock(
                1, ({(3,): 1.0, (1,): -3.0, (0,): 2.0},),
                (-3.0,), (3.0,), rank_signal="stable_rank_deficient",
            ),
            True,
        ),
        GeneratedCase(
            "separable_double_root",
            "positive",
            PolynomialBlock(
                2,
                ({(2, 0): 1.0}, {(0, 1): 1.0, (0, 0): -1.0}),
                (-2.0, -2.0), (2.0, 2.0),
                rank_signal="stable_rank_deficient",
            ),
            True,
        ),
        GeneratedCase(
            "nilpotent_cusp_block",
            "positive",
            PolynomialBlock(
                2,
                ({(0, 1): 1.0, (2, 0): -1.0}, {(0, 2): 1.0}),
                (-2.0, -2.0), (2.0, 2.0),
                rank_signal="stable_rank_deficient",
            ),
            True,
        ),
        GeneratedCase(
            "positive_dimensional_common_factor",
            "negative",
            PolynomialBlock(
                2,
                ({(1, 1): 1.0}, {(2, 0): 1.0}),
                (-2.0, -2.0), (2.0, 2.0),
                rank_signal="stable_rank_deficient",
            ),
            False,
        ),
        GeneratedCase(
            "complex_only_univariate",
            "negative",
            PolynomialBlock(
                1, ({(2,): 1.0, (0,): 1.0},),
                (-2.0,), (2.0,), rank_signal="near_multiple",
            ),
            False,
        ),
        GeneratedCase(
            "inconsistent_parallel_quadratics",
            "negative",
            PolynomialBlock(
                2,
                ({(2, 0): 1.0}, {(2, 0): 1.0, (0, 0): 1.0}),
                (-2.0, -2.0), (2.0, 2.0),
                rank_signal="stable_rank_deficient",
            ),
            False,
        ),
        GeneratedCase(
            "near_colliding_distinct_roots",
            "near_miss",
            PolynomialBlock(
                2,
                (
                    {(2, 0): 1.0, (1, 0): -1.0e-4},
                    {(0, 1): 1.0, (0, 0): -1.0},
                ),
                (-2.0, -2.0), (2.0, 2.0), rank_signal="near_multiple",
            ),
            True,
        ),
        GeneratedCase(
            "regular_rank_polynomial",
            "near_miss",
            PolynomialBlock(
                2,
                ({(1, 0): 1.0, (0, 0): -1.0}, {(0, 1): 1.0, (0, 0): -2.0}),
                (-3.0, -3.0), (3.0, 3.0), rank_signal="regular",
            ),
            False,
        ),
        GeneratedCase(
            "degree_four_polynomial",
            "near_miss",
            PolynomialBlock(
                1, ({(4,): 1.0, (0,): -1.0},),
                (-2.0,), (2.0,), rank_signal="near_multiple",
            ),
            False,
        ),
        GeneratedCase(
            "opaque_transcendental_block",
            "near_miss",
            PolynomialBlock(
                1, ({(1,): 1.0},), (-2.0,), (2.0,),
                semantic_kind="opaque_transcendental", rank_signal="near_multiple",
            ),
            False,
        ),
    )
