"""Exact positive configurations derived without GeoSolver search.

These are test fixtures, never initial guesses supplied to a campaign run.
Each assignment is rechecked against every repaired condition and its independent
reference. It demonstrates nonempty input geometry, not completeness of search.
"""

WITNESSES = {
    "JMO-2009-PRE-02": {"t": "acos(1/3)"},
    "AIME-2008-I-02": {"h": "25"},
    "AIME-2010-I-13": {"h": "63*sqrt(6)", "nx": "63", "ny": "-63*sqrt(3)"},
    "AIME-2013-I-12": {"r": "2+sqrt(3)"},
    "HMMT-2008-FEB-GEO-05": {
        "x": "(5-sqrt(5))/4",
        "y": "sqrt(10+2*sqrt(5))/4",
        "e": "sqrt((5-sqrt(5))/2)/(1+sqrt((5-sqrt(5))/2))",
    },
    "HMMT-2009-FEB-GEO-01": {"f": "5/2", "g": "11/2"},
    "HMMT-2009-FEB-GEO-04": {"x": "(1+sqrt(5))/2", "u": "(sqrt(5)-1)/2"},
    "HMMT-2010-FEB-GEO-02": {"w": "sqrt(5)"},
    "HMMT-2020-FEB-GEO-04": {"e": "1", "h": "(3+sqrt(5))/2"},
    "JMO-2008-PRE-02": {"e": "1/4"},
    "JMO-2011-PRE-04": {"h": "sqrt(39)/2"},
    "JMO-2011-PRE-06": {"c": "3+6*sqrt(5)/5", "a": "6+12*sqrt(5)/5", "r": "2+2*sqrt(5)/5"},
    "JMO-2012-PRE-01": {"s": "10"},
    "JMO-2017-PRE-04": {"h": "sqrt(15)", "ox": "-2", "oy": "4*sqrt(15)/5", "r": "4*sqrt(15)/5"},
    "HMMT-2020-FEB-GEO-06": {"ax": "1", "ay": "2*sqrt(6)"},
    "HMMT-2017-FEB-GEO-07": {"t": "acos(-8/15)"},
    "JMO-2020-PRE-06": {"t": "atan((sqrt(17)-1)/(sqrt(17)+1))"},
    "JMO-2023-PRE-06": {
        "s": "2*sqrt(37)/3**(1/4)",
        "phi": "acos(-3*sqrt(3)/(2*sqrt(37)))",
        "cx": "7*3**(1/4)",
        "cy": "11/3**(1/4)",
        "W": "14*3**(1/4)",
        "H": "22/3**(1/4)",
    },
}

BRANCH_WITNESSES = {
    identifier: [{"a": "1", "bx": "2/3", "cx": "1/2"}, {"a": "1", "bx": "-2", "cx": "-1/2"}]
    for identifier in ("HMMT-2011-FEB-ALGGEO-18", "HMMT-2011-collinear-circumcircle")
}


def check_witness(identifier, dsl, assignments):
    import sympy as sp
    from mpmath import mp

    from benchmarks.repairs.corpus97.records import repaired_rows
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.problem.models import GeometryProblem

    with mp.workdps(120), high_precision_mode():
        point = [mp.mpf(str(sp.N(assignments[v], 130))) for v in dsl["variables"]]
        evaluator = build_ir_evaluator(
            load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
        )
        residual = evaluator.evaluate_hp_residual(point, precision=100)
        feasibility = evaluator.evaluate_hp_hard_feasibility(point, precision=100)
        answer = evaluator.evaluate_answer_hp(point, precision=100)
        reference_values = repaired_rows(include_removed=True)[identifier]["answer"]
        references = [mp.mpf(str(sp.N(value, 120))) for value in reference_values]
        return residual, feasibility, answer, references
