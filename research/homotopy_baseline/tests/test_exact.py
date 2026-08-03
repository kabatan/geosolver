from __future__ import annotations

from research.homotopy_baseline.compiler import compile_problem
from research.homotopy_baseline.exact import (
    descriptors_from_candidates,
    elimination_polynomial,
    exact_degree,
)


def test_exact_elimination_and_root_index_for_sqrt_two():
    problem = {
        "task": "solve",
        "id": "sqrt-two",
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": "x**2", "value": 2}],
        "guards": ["AssumeGt(x, 0)"],
        "answer": "x",
        "post_process": "",
    }
    compilation = compile_problem(problem)
    polynomial = elimination_polynomial(compilation)
    assert polynomial.all_coeffs() == [1, 0, -2]
    assert exact_degree(compilation) == 2
    answers, _ = descriptors_from_candidates(
        compilation,
        [
            {
                "certified": True,
                "real": True,
                "coordinates": [
                    {"re": "1.4142135623730951", "im": "0"},
                    {"re": "1.4142135623730951", "im": "0"},
                ],
            }
        ],
    )
    assert answers[0]["minimal_polynomial_high_to_low"] == [1, 0, -2]
    assert answers[0]["selected_real_root_index"] == 1
