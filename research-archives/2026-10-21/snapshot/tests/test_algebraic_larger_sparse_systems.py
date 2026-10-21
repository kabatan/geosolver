"""Sparse coupled systems preserve every branch under the bounded variable gate."""

import pytest

from geosolver.engine.standard.search.algebraic_branches import discover_polynomial_branches


def reciprocal_family(count, reverse=False, repeated=False):
    names = [f"coordinate_{i}" for i in range(count)]
    parameter = names[-1]
    equations = [f"({i + 2})*({v}*{parameter}-1)" for i, v in enumerate(names[:-1])]
    equations.append(f"{parameter}**2-2")
    if repeated:
        equations = [f"({e})**2" for e in equations]
    if reverse:
        names.reverse()
        equations.reverse()
    return {
        "variables": names,
        "construction": [],
        "constraints": equations,
        "targets": [0] * len(equations),
    }


@pytest.mark.parametrize("count,reverse", [(4, False), (5, True), (6, False), (7, True)])
def test_coupled_reciprocal_family_preserves_both_roots(count, reverse):
    payload = reciprocal_family(count, reverse=reverse)
    data = discover_polynomial_branches(payload)
    assert data is not None
    parameter = f"coordinate_{count - 1}"
    expected = [
        [sign * (2**0.5 if name == parameter else 2**-0.5) for name in payload["variables"]]
        for sign in (-1, 1)
    ]
    assert sorted(tuple(map(float, p)) for p in data["points"]) == pytest.approx(
        sorted(map(tuple, expected))
    )


def test_squarefree_consequences_preserve_both_repeated_coupled_roots():
    data = discover_polynomial_branches(reciprocal_family(4, repeated=True))
    assert data is not None
    assert len(data["points"]) == 2


def test_eight_coupled_variables_remain_outside_optional_budget_gate():
    assert discover_polynomial_branches(reciprocal_family(8)) is None


def test_positive_dimensional_seven_variable_system_declines_without_fixing_gauge():
    payload = reciprocal_family(7)
    payload["constraints"].pop()
    payload["targets"].pop()
    assert discover_polynomial_branches(payload) is None


def test_root_product_overflow_does_not_return_a_truncated_subset():
    names = [f"q{i}" for i in range(7)]
    equations = [f"{v}**2-2" for v in names]
    equations.append("+".join(f"{v}**2" for v in names) + "-14")
    payload = {
        "variables": names,
        "construction": [],
        "constraints": equations,
        "targets": [0] * len(equations),
    }
    assert discover_polynomial_branches(payload) is None
