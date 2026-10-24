"""BASE1 + raw/T1 switch, matching the fixed S7 stage-(1) residual definition."""
import ast
from functools import wraps
from mpmath import mp
from geosolver.engine.standard.evaluation.high_precision_expressions import build_solution_context_high_precision
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.problem.ir.compiler import safe_eval_expr_hp


def key(s):
    return ast.dump(ast.parse(str(s), mode='eval'), include_attributes=False)


def mapped_rows(bundle, item, tangencies):
    equalities = list(zip(bundle.spec.constraints, bundle.targets, strict=True))
    result = {}
    for row in tangencies:
        condition = item['dsl']['conditions'][row['index']]
        found = [i for i, (lhs, rhs) in enumerate(equalities)
                 if key(lhs) == key(condition['left']) and key(rhs) == key(condition['right'])]
        assert len(found) == 1, (condition, found)
        result[found[0]] = row
    return result


def t1(bundle, point, row, dps):
    # The formulas and the circle/circle branch are fixed by S7 stage (1).
    # Arithmetic follows the refinement stage precision, rather than 200 dps.
    with mp.workdps(int(dps)), high_precision_mode():
        ctx = build_solution_context_high_precision(bundle.spec, list(bundle.var_names),
            list(point), bundle.base_context, int(dps), expressions=[row['left'], row['right']])
        a, b = [getattr(v, 'circle', v) for v in
                [safe_eval_expr_hp(row['left'], ctx), safe_eval_expr_hp(row['right'], ctx)]]
        if hasattr(a, 'radius') and hasattr(b, 'radius'):
            d = a.center.distance_to(b.center)
            return d-(a.radius+b.radius) if row['branch'] == 'outer' else d-abs(a.radius-b.radius)
        line, circle = (a, b) if hasattr(a, 'a') else (b, a)
        delta = line.a*circle.center.x+line.b*circle.center.y+line.c
        return delta**2-circle.radius**2


def install(bundle, item, tangencies):
    import os
    import geosolver.engine.standard.refinement.mpmath_refiner as refiner
    assert os.environ.get('GEOSOLVER_ABLATE_NO_RESIDUAL_REWRITE') == '1'
    assert os.environ.get('GEOSOLVER_S7_RAW_T1') == '1'
    rows = mapped_rows(bundle, item, tangencies)
    original = refiner.MpmathRefiner._residual_vector_for_stage

    @wraps(original)
    def raw(self, bundle, evaluator, point, dps, integer_closures=(), smooth_zero_constraints=False):
        values = original(self, bundle, evaluator, point, dps,
                          integer_closures=integer_closures, smooth_zero_constraints=smooth_zero_constraints)
        if values is not None:
            values = list(values)
            for i, row in rows.items():
                values[i] = t1(bundle, point, row, dps)
        return values

    refiner.MpmathRefiner._residual_vector_for_stage = raw
    if rows:
        # Frozen symbolic plans can describe contact/T2 or unsigned residuals.
        # Use the solver's existing finite differences for the replaced rows.
        refiner.derivative_plan = lambda bundle: None
    return dict(tangency_rows=sorted(rows), no_distance_coordinate_rewrite=True,
                no_radius_auxiliary_rewrite=True, circle_branch='fixed stage-(1) reference',
                analytic_plan='finite differences when T1 rows exist; otherwise unchanged')
