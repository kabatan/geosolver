"""Synthetic regression checks only; never loads benchmark problems."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), '/tmp/q6-tools/exact_comparison/benchmarks/exact_comparison', '/tmp/exstrong-clean/src']
sys.dont_write_bytecode = True
import sympy as sp
from strong_translate import translate, ConversionError
from run_strong import identity, prepare, lift_candidate


def main():
    checks = []
    def ok(name, condition):
        assert condition, name
        checks.append(name)

    dsl = {'variables': ['x'], 'constructions': [],
           'conditions': [{'left': 'x', 'operator': '>', 'right': 0},
                          {'left': 'x**2', 'operator': '=', 'right': 4}], 'target': 'x'}
    system, target = translate(dsl)
    eq, factors, used = prepare(system, target)
    ok('strict_inequality_becomes_saturation', sp.Symbol('v_x') in factors)
    algebraic = dict(dsl, conditions=[{'left': 'x', 'operator': '=', 'right': 'cos(pi/7)'}])
    system2, _ = translate(algebraic)
    ok('trig_minimal_polynomial', any('8*_constant**3' in c['minimal_polynomial'] for c in system2.constants))
    for expr in ('pi*x', 'Area(Circle(Point(0,0),x))'):
        try:
            translate(dict(dsl, target=expr))
        except ConversionError as exc:
            ok('reject_pi:' + expr, exc.code == 'NONALGEBRAIC_PI')
        else:
            raise AssertionError(expr)
    line = dict(dsl, constructions=[{'name': 'L', 'expression': 'Line(Point(0,0),Point(x,0))'}], conditions=[])
    s, t = translate(line)
    ok('line_direction_nonzero', sp.Symbol('v_x') in prepare(s, t)[1])
    bounded = dict(dsl, conditions=[{'predicate':'Bound(x,(0,1),inclusive=False)'}])
    bs, bt = translate(bounded)
    ok('Bound_open_endpoints_nonzero', set(prepare(bs, bt)[1]) == {sp.Symbol('v_x'), sp.Symbol('v_x')-1})
    tangent = dict(variables=['x'], constructions=[{'name':'P','expression':'Intersect(Line(Point(-2,1),Point(2,1)),Circle(Point(0,0),1))'}], conditions=[], target='P.x')
    ts, tt = translate(tangent)
    ok('tangent_intersection_not_saturated_away', any(sol.get(tt) == 0 for sol in sp.solve(ts.eqs, ts.variables, dict=True)))
    # A fibre sampled at five rational coordinates may miss a valid diagram.
    # It must remain unresolved, never be universally rejected.
    free = dict(dsl, variables=['x','y'], conditions=[], target='x')
    fs, ft = translate(free)
    x, y = sp.symbols('v_x v_y')
    class Bundle:
        var_names = ('x', 'y')
    # Missing DSL coordinate is deliberately left out of the polynomial ring.
    r = lift_candidate(sp.Integer(1), ft, [ft-x], [ft-x], [], [x,ft], fs,
                       {'dsl': free}, Bundle(), None)
    ok('unresolved_fibre_not_excluded', r['state'] == 'unresolved')
    ident = identity()
    ok('frozen_verifier_identity', ident['source_hash'].startswith('sha256:d8fd9bb8'))
    with tempfile.TemporaryDirectory(prefix='exstrong-synthetic-') as temp:
        directory = Path(temp)
        fixtures = [dict(id='synthetic-finite', dsl=dsl),
                    dict(id='synthetic-zero', dsl=dict(variables=[], constructions=[], conditions=[], target='sqrt(2)+cos(pi/7)'))]
        for fixture in fixtures:
            fixture['dsl']['id'] = fixture['id']
        source = directory/'fixtures.jsonl'
        source.write_text(''.join(json.dumps(c)+'\n' for c in fixtures))
        for fixture in fixtures:
            output = directory/(fixture['id']+'.json')
            subprocess.run([sys.executable, str(HERE/'run_strong.py'), fixture['id'],
                            '--stage-b', '--cases', str(source), '--out', str(output)],
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), check=True, timeout=40)
            result = json.loads(output.read_text())
            if result['status'] == 'error':
                print(result)
            if fixture['id'] == 'synthetic-finite':
                ok('finite_exact_pipeline_and_negative_branch', result['status'] == 'verified_complete' and result['answers'] == ['2'])
            else:
                ok('R4_zero_unknowns_no_algebra_solver', result['status'] == 'direct_verified' and result['algebra_solver_calls'] == 0)
    (HERE/'smoke-checks.json').write_text(json.dumps({'passed': checks, 'count': len(checks)}, ensure_ascii=False, indent=2)+'\n')
    print('passed', len(checks))


if __name__ == '__main__':
    main()
