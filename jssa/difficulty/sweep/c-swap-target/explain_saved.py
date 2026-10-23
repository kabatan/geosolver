"""Post-hoc arithmetic on saved figures, without search or re-identification.

Target values are evaluated on the original run's verified coordinates. This is
not a new solver trial, a full answer-set reference, or a change to the scorer.
"""
from __future__ import annotations

import argparse
import json

from common import BASE, RAW, KINDS, read, save, sha, verify_source


def coefficient_example():
    """Exact substitution in the already selected AIME-2019-I-12 input."""
    import sympy as s
    expected = read(BASE / 'inputs/AIME-2019-I-12/original.json')
    assert expected['variables'] == ['x']
    assert [c['expression'] for c in expected['constructions']] == [
        'Point(x, 11)', 'Point(x**2-11**2-19*x, 2*11*x-19*11)',
        'Point(F.x**2-F.y**2-19*F.x, 2*F.x*F.y-19*F.y)']
    assert expected['conditions'][0] == {
        'left': 'Dot(Vector(Z, F), Vector(F, G))', 'operator': '=', 'right': 0}
    x, t = s.symbols('x t', real=True)
    z = s.Matrix([x, 11])
    f = s.Matrix([x*x-121-19*x, 22*x-209])
    g = s.Matrix([f[0]**2-f[1]**2-19*f[0], 2*f[0]*f[1]-19*f[1]])
    equation = s.factor((f-z).dot(g-f))
    x0 = 9 + s.sqrt(221)
    assert s.simplify(equation.subs(x, x0)) == 0
    z, f, g = [s.simplify(v.subs(x, x0)) for v in [z, f, g]]
    u, v = f-g, z-g
    values = {'original': x0, 'length': s.sqrt(s.simplify(u.dot(u))),
              'area': s.simplify(s.Abs(s.det(s.Matrix.hstack(u, v))) / 2),
              'ratio': s.sqrt(s.simplify(u.dot(u) / v.dot(v)))}
    result = {'id': expected['id'], 'input_sha256': sha(BASE / 'inputs/AIME-2019-I-12/original.json'),
              'condition_factorization': str(equation), 'positive_root': str(x0), 'targets': {}}
    for kind, value in values.items():
        poly = s.Poly(s.minpoly(value, t), t)
        result['targets'][kind] = {'value': str(value), 'decimal': str(s.N(value, 40)),
            'degree': poly.degree(), 'minimal_polynomial': [str(c) for c in poly.all_coeffs()],
            'max_abs_coefficient': str(max(abs(c) for c in poly.all_coeffs()))}
    from geosolver.engine.standard.exact_assembly.identify_answer import TIER_CONFIGS
    from dataclasses import asdict
    result['frozen_identification_limits'] = {k: asdict(v) for k, v in TIER_CONFIGS.items()}
    result['interpretation_limit'] = 'Bounds apply to the polynomial search, not a proof that every fallback must fail. Actual failure is established by the saved run records.'
    return result


def continuous_examples():
    """Explicit exact families in two selected inputs; no numerical trials."""
    import sympy as s
    a = read(BASE / 'inputs/AIME-2012-I-14/original.json')
    assert a['variables'] == ['x', 'y', 'u', 'v']
    assert [c['left'] for c in a['conditions'][:3]] == [
        '2*x+u', '2*y+v', 'x**2+y**2+u**2+y**2+x**2+v**2']
    assert [c['right'] for c in a['conditions'][:3]] == [0, 0, 250]
    theta = s.symbols('theta', positive=True)
    radius = s.sqrt(s.Rational(125, 3))
    x, y = -radius*s.cos(theta), -radius*s.sin(theta)
    u, v = -2*x, -2*y
    assert s.trigsimp(x*x+y*y+u*u+y*y+x*x+v*v) == 250
    assert s.trigsimp((u-x)**2+(v-y)**2) == 375
    area = s.trigsimp((u-x)*(v-y)/2)
    assert s.trigsimp(area-s.Rational(375, 4)*s.sin(2*theta)) == 0
    b = read(BASE / 'inputs/HMMT-2011-FEB-GUTS-01/original.json')
    assert b['variables'] == ['b', 'x', 'y', 'u', 'v']
    assert [c['left'] for c in b['conditions'][:3]] == [
        'Area(A,B,C)', 'Parallel(Line(D,E),Line(B,C))', 'Distance(D,E)/Distance(B,C)']
    assert [c['right'] for c in b['conditions'][:3]] == [1, 0, '1/3']
    t = s.symbols('t', positive=True)
    A, B, C = s.Matrix([t, 1]), s.Matrix([0, 0]), s.Matrix([2, 0])
    D, E = s.Rational(2, 3)*A+s.Rational(1, 3)*B, s.Rational(2, 3)*A+s.Rational(1, 3)*C
    F = s.Matrix([t, s.Rational(1, 3)])
    assert s.det(s.Matrix.hstack(B-A, C-A))/2 == 1
    assert D[1] == E[1] == s.Rational(2, 3)
    assert (E-D).dot(E-D)/(C-B).dot(C-B) == s.Rational(1, 9)
    assert s.det(s.Matrix.hstack(B-F, C-F))/2 == s.Rational(1, 3)
    return {'analysis_only': True, 'scope': 'At least these two selected problems. This is not an exhaustive uniqueness proof for the other 18.', 'examples': [
        {'id': a['id'], 'input_sha256': sha(BASE / 'inputs/AIME-2012-I-14/original.json'),
         'family': 'r=sqrt(125/3), x=-r*cos(theta), y=-r*sin(theta), u=-2*x, v=-2*y; 0<theta<pi/2',
         'checks': ['2*x+u=0', '2*y+v=0', '6*(x^2+y^2)=250', 'u>x and v>y'],
         'target_values': {'original': '375', 'length': '5*sqrt(15)',
                           'area': '(375/4)*sin(2*theta)', 'angle': 'theta', 'ratio': '1/cos(theta)'},
         'nonconstant_targets': ['area', 'angle', 'ratio']},
        {'id': b['id'], 'input_sha256': sha(BASE / 'inputs/HMMT-2011-FEB-GUTS-01/original.json'),
         'family': 'b=2, x=t, y=1, u=v=1/3; t>0. Then F=(t,1/3).',
         'checks': ['Area(A,B,C)=1', 'D.y=E.y=2/3, so DE parallel BC', 'DE/BC=1/3', 'all interval and positivity conditions hold'],
         'target_values': {'original': '1/3', 'length': 'sqrt(t^2+1)', 'area': 't/3',
                           'angle': 'acos((t^2+1/3)/sqrt((t^2+1)*(t^2+1/9)))',
                           'ratio': 'sqrt((t^2+1)/(t^2+1/9))'},
         'nonconstant_targets': ['length', 'area', 'angle', 'ratio']}]}


def equilateral_example():
    import sympy as s
    dsl = read(BASE / 'inputs/AIME-2014-II-10/original.json')
    assert dsl['target'] == 'Area(Z, W1, W2)'
    assert dsl['constructions'][0]['expression'] == 'Point(2014, 0)'
    assert [(c['left'], c['right']) for c in dsl['conditions'] if c['operator'] == '='] == [
        ('x**2-y**2+2014*x+2014**2', 0), ('2*x*y+2014*y', 0),
        ('u**2-v**2+2014*u+2014**2', 0), ('2*u*v+2014*v', 0)]
    Z = s.Matrix([2014, 0])
    W1 = s.Matrix([-1007, 1007*s.sqrt(3)])
    W2 = s.Matrix([-1007, -1007*s.sqrt(3)])
    for point in [W1, W2]:
        x, y = point
        assert x*x-y*y+2014*x+2014**2 == 0
        assert 2*x*y+2014*y == 0
    area = s.Abs(s.det(s.Matrix.hstack(W1-Z, W2-Z)))/2
    length = s.sqrt((W2-Z).dot(W2-Z))
    assert area == 3042147*s.sqrt(3)
    assert length == 2014*s.sqrt(3)
    t = s.Symbol('t')
    targets = {}
    for kind, value in [('original', area), ('area', area), ('length', length), ('ratio', s.Integer(1))]:
        poly = s.Poly(s.minpoly(value, t), t)
        targets[kind] = {'value': str(value), 'decimal': str(s.N(value, 40)),
            'degree': poly.degree(), 'minimal_polynomial': [str(c) for c in poly.all_coeffs()],
            'max_abs_coefficient': str(max(abs(c) for c in poly.all_coeffs()))}
    targets['angle'] = {'value': 'pi/3', 'decimal': str(s.N(s.pi/3, 40)),
                        'public_format': 'affine_pi'}
    return {'id': dsl['id'], 'input_sha256': sha(BASE / 'inputs/AIME-2014-II-10/original.json'),
            'derivation': 'y>0 and v<0 imply x=u=-1007 and y=-v=1007*sqrt(3); the triangle is equilateral.',
            'targets': targets}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--partial', action='store_true')
    opts = parser.parse_args()
    verify_source()
    output = RAW / 'analysis-preview' if opts.partial else BASE
    stats = read(output / 'analysis-summary.json')
    assert opts.partial or stats['complete']
    runs = read(output / 'per-run.json')
    selection = read(BASE / 'selection.json')
    cases = {c['id']: c for c in selection['cases']}
    by_key = {(r['id'], r['seed'], r['kind']): r for r in runs}
    from mpmath import mp
    from geosolver.problem.models import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    measurements = []
    for original in runs:
        if original['kind'] != 'original' or not original['artifact_path']:
            continue
        artifact = read(original['artifact_path'])
        summary = artifact['diagnostics']['pipeline_summary']
        verified = [v for v in summary.get('verification_records', [])
                    if v.get('verified') and v.get('values')]
        if not verified:
            continue
        # First saved verified figure; selection does not depend on swapped outcomes.
        witness = verified[0]
        for kind in KINDS:
            target = by_key.get((original['id'], original['seed'], kind))
            if target is None:
                continue
            dsl = read(BASE / cases[original['id']]['variants'][kind]['path'])
            evaluator = build_ir_evaluator(load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document()))
            row = {'id': original['id'], 'seed': original['seed'], 'kind': kind,
                   'source_run': original['index'], 'source_receipt_sha256': original['receipt_sha256'],
                   'source_candidate_uid': witness['candidate_uid'],
                   'source_verification_revision': witness.get('revision'),
                   'source_precision_dps': witness.get('precision_dps'),
                   'source_values': witness['values'], 'target': dsl['target'],
                   'target_run': target['index'], 'target_run_solved': target['public_solved']}
            with mp.workdps(100), high_precision_mode():
                values = tuple(mp.mpf(x) for x in witness['values'])
                evaluated = evaluator.evaluate_answer_hp(values, precision=100)
                row['evaluation_status'] = evaluated.evaluation_status.value
                row['target_on_saved_figure'] = mp.nstr(evaluated.answer_hp, 70) if evaluated.answer_hp is not None else None
                observed = [mp.mpf(x) for x in target['verified_target_values'] if x != 'None']
                if evaluated.answer_hp is not None and observed:
                    row['nearest_relative_target_difference_32_digit_saved_values'] = mp.nstr(min(abs(x-evaluated.answer_hp) / max(mp.mpf(1), abs(x), abs(evaluated.answer_hp)) for x in observed), 12)
            measurements.append(row)
    examples = [coefficient_example(), equilateral_example()]
    # Check the hand-derived values against frozen target evaluation on saved figures.
    with mp.workdps(80):
        for example in examples:
            for row in measurements:
                if row['id'] == example['id'] and row['kind'] in example['targets']:
                    expected = mp.mpf(example['targets'][row['kind']]['decimal'])
                    actual = mp.mpf(row['target_on_saved_figure'])
                    assert abs(actual - expected) / max(1, abs(expected)) < mp.mpf('1e-35')
    save(output / 'saved-figure-targets.json', {'analysis_only': True,
        'note': '100-digit target evaluation at a saved verified original figure. No new solve, refinement, acceptance decision, or complete answer-set claim.',
        'script_sha256': sha(__file__), 'measurements': measurements})
    save(output / 'coefficient-examples.json', {'analysis_only': True, 'examples': examples})
    save(output / 'nonunique-targets.json', continuous_examples())
    print(json.dumps({'measurements': len(measurements),
                      'targets_evaluable_on_saved_original': sum(r['evaluation_status'] == 'ok' for r in measurements),
                      'unsolved_but_evaluable': sum(not r['target_run_solved'] and r['evaluation_status'] == 'ok' for r in measurements)}))


if __name__ == '__main__':
    main()
