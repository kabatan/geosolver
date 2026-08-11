#!/usr/bin/env python3
"""Reproduce the repeated-factor exactification regression.

Run this with the fixed external runtime on ``PYTHONPATH``.  The checks use
only the exactification API and do not alter any DSL case.
"""

from mpmath import mp

from geosolver._internal.pipeline.exact.identify_answer import identify_answer
from geosolver._internal.pipeline.exact.verify_identified_answer import (
    verify_identified_answer,
)
from geosolver._internal.solver.exact.polynomial_search import (
    canonicalize_polynomial,
    find_minimal_polynomial,
)


NEAR_72 = (
    "71.999999999999999999999999999999999999999999999999999999999999999999999999999999999999999148320685140076024224056123646876301130960353060742"
)


def main() -> None:
    with mp.workdps(220):
        value = mp.mpf(NEAR_72)
        assert canonicalize_polynomial([1, -144, 5184], value) == [1, -72]

        verified, residual = verify_identified_answer(
            coefficients=[1, -144, 5184],
            numeric_value=value,
            precision_dps=180,
        )
        assert not verified
        assert residual > mp.mpf("1e-100")

        polynomial = find_minimal_polynomial(
            value,
            precision=180,
            max_degree=8,
            max_coeff=10**8,
            max_steps=20_000,
        )
        assert polynomial is None or polynomial != [1, -144, 5184]

        exact = identify_answer(
            answer_hp=mp.mpf(72),
            tier="strict",
            input_precision_dps=180,
        )
        assert exact.exact_status == "identified"
        assert exact.selected_exact_value == "72"
        assert exact.minimal_polynomial == (1, -72)

    print("exactification repeated-factor regression: PASS")


if __name__ == "__main__":
    main()
