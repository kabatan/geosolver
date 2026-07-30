import random

import sympy as sp

import run_repair_a as campaign
from candidate_repair_a import Source, solve


def test_minimized_representation_repairs():
    x = sp.symbols("x", real=True)
    repeated = solve(Source((x,), ((x - 1) ** 2,), (), (), x, {x: 1.0}))
    assert repeated.status == "EXACT_CONFIGURATIONS_READY"
    assert repeated.branch_states_generated == 2
    assert len(repeated.configurations) == 1

    variables = sp.symbols("q0:6", real=True)
    repeated_six = solve(Source(
        tuple(variables),
        tuple((variable - index) ** 2 for index, variable in enumerate(variables, 1)),
        (), (), sum(variables),
        {variable: float(index) for index, variable in enumerate(variables, 1)},
    ))
    assert not repeated_six.fallback_required
    assert repeated_six.branch_states_generated == 7
    assert len(repeated_six.configurations) == 1

    for transform in campaign.TRANSFORMS:
        case = campaign._leading_zero_split(random.Random(12345))
        source = campaign._transform(case.source, transform)
        result = solve(source)
        false, descriptors = campaign._groebner_oracle(source, result)
        assert not result.fallback_required
        assert false == 0
        assert len(descriptors) == 1

    strict = campaign._strict_boundary(random.Random(12345))
    assert solve(strict.source).fallback_required

    before = campaign._branch_cap_before(random.Random(12345))
    over = campaign._branch_cap_over(random.Random(12345))
    assert not solve(before.source).fallback_required
    assert solve(over.source).fallback_required
