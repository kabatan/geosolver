"""Posthoc hand-formula verification and local NOMAD help capture; no search."""
import json
import math
import os
import subprocess
import sys
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from experiment import OUT, dump


def main():
    inp = json.loads((OUT/'inputs/HMMT-2014-FEB-GEO-08.json').read_text())
    b = load_problem_bundle(GeometryProblem.model_validate(inp['dsl']).engine_document())
    ev = build_ir_evaluator(b)
    root = 82/73  # Derived after initial saved endpoints; never a search input.
    checks = []
    for t in [root-.001, root, root+.001, root+.002]:
        center_y = (64-73*t)/16
        radius = math.sqrt(9/4+center_y**2)
        distance = abs(6-3*center_y)/5
        residual = abs(radius-distance)
        margin = 8*(t-1)/(3*t*t)
        r = ev.evaluate_float_residual([t])
        h = ev.evaluate_float_hard_feasibility([t], include_margins=False)
        assert math.isclose(residual, r.residual_norm_float, rel_tol=1e-8, abs_tol=5e-13)
        assert math.isclose(margin, float(h.min_margin), rel_tol=1e-12, abs_tol=1e-13)
        checks.append({'t': t, 'manual_residual': residual, 'frozen_residual': r.residual_norm_float, 'manual_margin': margin, 'frozen_margin': float(h.min_margin)})
    margin = 8*(root-1)/(3*root**2)
    margin_prime = 8*(2-root)/(3*root**3)
    radius = 15/8
    f_second = (9/4)/radius**3*(73/16)**2
    penalty_derivative = -2e-10*margin_prime/margin**3
    delta = (-penalty_derivative/f_second**2)**(1/3)
    dump(OUT/'case-formula-check.json', {'posthoc': True, 'optimization_calls': 0, 'formula_checks': checks, 'root_derived_post_registration': root, 'F_second_derivative_at_root': f_second, 'original_L_penalty_derivative_at_root': penalty_derivative, 'leading_Taylor_displacement': delta, 'leading_Taylor_residual': f_second*delta**2/2})
    help_text = subprocess.run([sys.executable, '-B', '-c', "import PyNomad; PyNomad.help('EPSILON')"], env=os.environ, capture_output=True, text=True, timeout=10, check=True).stdout
    assert '1E-13' in help_text
    dump(OUT/'native-epsilon-audit.json', {'posthoc': True, 'optimization_calls': 0, 'source': 'Installed PyNomadBBO 4.5.1 bundled help, PyNomad.help("EPSILON")', 'help': help_text, 'observed_example': {'id': 'HMMT-2014-FEB-GEO-08', 'seed': 32001, 'k': 0, 'native_f_best': 6.151365775542411e-14, 'smallest_callback_objective': 4.738095811983702e-29}, 'interpretation': 'The comparison epsilon is consistent with the observed native-return versus best-callback gap. No epsilon intervention or rebuild was performed, so this is not a separate causal test.'})
    print('4 hand-formula points verified; local comparison-epsilon help saved; optimization calls=0')


if __name__ == '__main__':
    main()
