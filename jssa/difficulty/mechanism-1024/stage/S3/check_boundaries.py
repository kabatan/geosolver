"""Small residual/Jacobian probes only; no optimizer or answer evaluation."""
import ast
import inspect
import json
import os
from functools import partial

from mpmath import mp

from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement import analytic_jacobian as analytic
from geosolver.engine.standard.refinement import mpmath_refiner as refiner
from geosolver.engine.standard.refinement.s3_tangency import distance_radius_sources, tangency_mode
from geosolver.runtime.ablation import ablated
from geosolver.runtime.integrity import verify_engine_lock


def forbidden(*args, **kwargs):
    raise AssertionError('No optimization or answer evaluation in stage 1')


refiner.MpmathRefiner.refine_candidates = forbidden
refiner.MpmathRefiner._refine_single_candidate = forbidden
refiner.MpmathRefiner._run_stage = forbidden
refiner.MpmathRefiner._evaluate_answer = forbidden
mp.findroot = forbidden


def bundle_and_vector(document, point):
    bundle = load_problem_bundle(document)
    evaluator = build_ir_evaluator(bundle)
    type(evaluator).evaluate_answer_hp = forbidden
    obj = refiner.MpmathRefiner()
    raw = obj._residual_vector_for_stage(bundle, evaluator, point, 80)
    vector = obj._residual_vector_for_stage(bundle, evaluator, point, 80,
                                           smooth_zero_constraints=True)
    assert raw is not None and vector is not None
    return bundle, raw, vector


def document(names, construction, constraints, targets=None):
    value = {'task': 'solve', 'variables': {'names': names},
             'construction': [{'name': name, 'expr': expr} for name, expr in construction],
             'constraints': constraints, 'answer': names[0]}
    if targets is not None:
        value['v'] = targets
    return value


def main():
    # Extract and evaluate the actual adoption predicate, without entering Newton.
    tree = ast.parse(inspect.getsource(refiner._run_findroot_closure))
    gates = [node for node in ast.walk(tree) if isinstance(node, ast.If)
             and 'requires_smoothing' in ast.unparse(node.test)]
    assert len(gates) == 1
    gate = compile(ast.Expression(gates[0].test), '<actual-adoption-predicate>', 'eval')
    results = {'optimization_executed': False, 'answer_evaluation_executed': False,
               'distance_radius_orders': [], 'derivative_adoption': [], 'auxiliaries': []}
    with mp.workdps(80), high_precision_mode():
        point = [mp.mpf(4), mp.mpf(3)]
        construction = [('P', 'Point(0,0)'), ('Q', 'Point(1,0)'),
                        ('L', 'Line(P,Q)'), ('O', 'Point(x,y)'), ('C', 'Circle(O,2)')]
        for reversed_args in (False, True):
            distance = 'Distance(L,O)' if reversed_args else 'Distance(O,L)'
            for reversed_equality in (False, True):
                lhs, rhs = ('2', distance) if reversed_equality else (distance, '2')
                doc = document(['x', 'y'], construction,
                               [lhs, 'Distance(P,O)'], [rhs, '2'])
                values = {}
                for mode in ('T0', 'T1', 'T2'):
                    os.environ['GEOSOLVER_S3_TANGENCY_MODE'] = mode
                    bundle, raw, vector = bundle_and_vector(doc, point)
                    expected = raw[0] if mode == 'T0' else mp.mpf(5 if mode == 'T1' else 4)
                    assert vector[0]._mpf_ == expected._mpf_
                    assert vector[1:] == raw[1:]
                    payload = (tuple(bundle.var_names), tuple(construction),
                               tuple(bundle.spec.constraints), tuple(map(str, bundle.targets)), 'T1')
                    assert analytic.compile_jacobian(payload) is None
                    values[mode] = str(vector[0])
                results['distance_radius_orders'].append({
                    'reversed_arguments': reversed_args, 'reversed_equality': reversed_equality,
                    'residuals': values, 'T1_analytic_disabled': True})
        tangent_doc = document(['x', 'y'], construction,
                               ['IsTangent(L,C)', 'Distance(P,O)'], ['0', '2'])
        os.environ['GEOSOLVER_S3_TANGENCY_MODE'] = 'T2'
        bundle, _, _ = bundle_and_vector(tangent_doc, point)
        payload = (tuple(bundle.var_names), tuple(construction),
                   tuple(bundle.spec.constraints), tuple(map(str, bundle.targets)))
        p2 = analytic.compile_jacobian(payload)
        p1 = analytic.compile_jacobian((*payload, 'T1'))
        assert p1 is not None and p2 is not None
        assert p1['requires_smoothing'] and p2['requires_smoothing']
        assert analytic.evaluate_jacobian(p1, point, 80)[0] == [mp.mpf(0), mp.mpf(6)]
        assert analytic.evaluate_jacobian(p2, point, 80)[0] == [mp.mpf(1), mp.mpf(0)]
        results['T1_T2_contact_line_analytic_rows'] = {'T1': ['0', '6'], 'T2': ['1', '0']}
        circle_payload = (('x', 'y'), (('C1', 'Circle(Point(0,0),2)'),
            ('C2', 'Circle(Point(x,y),3)')), ('IsTangent(C1,C2)',), ('0',), 'T1')
        assert analytic.compile_jacobian(circle_payload) is None
        results['T1_circle_circle_analytic_disabled'] = True
        # Verify payload/cache separation as used by the symbolic-worker boundary.
        original_plan = analytic._plan
        keys = []
        analytic._plan = lambda key: keys.append(key) or {'dummy': True}
        try:
            for mode in ('T0', 'T1', 'T2'):
                os.environ['GEOSOLVER_S3_TANGENCY_MODE'] = mode
                analytic.derivative_plan(bundle)
            assert keys[0] == keys[2] == payload
            assert keys[1] == (*payload, 'T1')
        finally:
            analytic._plan = original_plan
        results['symbolic_payload_cache_separation'] = True
        ordinary = analytic.compile_jacobian((('x', 'y'), (), ('x-1', 'y-2'), ('0', '0')))
        assert ordinary is not None and not ordinary['requires_smoothing']
        for mode in ('T0', 'T1', 'T2'):
            os.environ['GEOSOLVER_S3_TANGENCY_MODE'] = mode
            for requires_smoothing in (False, True):
                for smooth in (False, True):
                    plan = {'rows': 2, 'requires_smoothing': requires_smoothing}
                    residual_fn = partial(lambda: None, smooth_zero_constraints=smooth)
                    rejected = eval(gate, dict(plan=plan, initial_residuals=[0, 0],
                        residual_fn=residual_fn, partial=partial, isinstance=isinstance,
                        ablated=ablated, tangency_mode=tangency_mode))
                    expected = requires_smoothing and (not smooth or mode == 'T0')
                    assert rejected == expected
                    results['derivative_adoption'].append({'mode': mode,
                        'requires_smoothing': requires_smoothing, 'smooth': smooth,
                        'rejected': rejected})
            coord = document(['x', 'y'], [], ['Distance(Point(x,y),Point(0,0))'])
            _, raw, vector = bundle_and_vector(coord, [mp.mpf(3), mp.mpf(4)])
            assert raw == [mp.mpf(5)] and vector == [mp.mpf(3), mp.mpf(4)]
            radius = document(['r'], [('B', 'Point(2,0)'), ('P', 'Point(0,2)'),
                ('Q', 'Point(-2,0)'), ('G', 'Circumcircle(B,P,Q)'),
                ('O', 'Point(B.x-2*r,B.y+r)'), ('D', 'Circle(O,r)')],
                ['Distance(O,Center(G))'], ['Radius(G)-r'])
            _, raw, vector = bundle_and_vector(radius, [mp.mpf('0.3')])
            assert len(vector) == len(raw) + 1 and vector[:-1] == raw
            assert mp.almosteq(vector[-1], mp.mpf('-2.8'))
            results['auxiliaries'].append({'mode': mode, 'coordinate_rows': ['3', '4'],
                'positive_radius_auxiliary_rows': 1, 'auxiliary_value': str(vector[-1])})
        # Independently enumerate Distance=center,line matches without requiring incidence.
        from pathlib import Path
        from geosolver.problem.models import GeometryProblem
        manifest = json.loads(Path('/tmp/mechanism-S1-1m9aomj8/manifest.json').read_text())
        matches = {}
        for task in manifest['inputs']:
            problem = GeometryProblem.model_validate_json(Path(task['input_copy']).read_text())
            bundle = load_problem_bundle(problem.engine_document())
            found = distance_radius_sources(tuple((c.name, c.expr) for c in bundle.spec.construction),
                tuple(zip(bundle.spec.constraints, map(str, bundle.targets), strict=True)))
            matches[task['case_id']] = list(found)
        assert not any(matches.values())
        results['S1_distance_center_line_radius_indices'] = matches
    os.environ.pop('GEOSOLVER_S3_TANGENCY_MODE')
    assert tangency_mode() == 'T2'
    os.environ['GEOSOLVER_S3_TANGENCY_MODE'] = 'invalid'
    try:
        tangency_mode()
    except ValueError:
        results['invalid_mode_rejected'] = True
    else:
        raise AssertionError('invalid mode accepted')
    os.environ.pop('GEOSOLVER_S3_TANGENCY_MODE')
    ok, source_hash = verify_engine_lock()
    assert ok, source_hash
    results['engine_lock_valid'] = True
    results['source_hash'] = source_hash
    print(json.dumps(results, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
