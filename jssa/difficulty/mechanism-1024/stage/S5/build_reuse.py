"""Extract S4.12 numerical implementation verbatim; no S4 measurements rerun."""
import ast
import textwrap
from pathlib import Path

OUT=Path(__file__).resolve().parent
source=(OUT.parent/'S4/sigma_min.py').read_text()
start=source.index('    def spectrum(jac):')
end=source.index('    results, csv_rows =',start)
spectrum=textwrap.dedent(source[start:end])
start=source.index('            bundle = s4.load_problem_bundle')
end=source.index('            results.append(entry)',start)
body=textwrap.dedent(source[start:end])
# The sole formatting change forces exponents for every reported sigma, including zero.
imports='''"""S4.12 measurement body extracted by build_reuse.py; S4 source hashes recorded."""
import json
from mpmath import mp
from geosolver.engine.standard.refinement.mpmath_refiner import _zero_constraint_plans, _smooth_zero_constraint_residuals
from geosolver.engine.standard.problem.positive_radius_contacts import positive_radius_contact_sources
from geosolver.engine.standard.evaluation.high_precision_expressions import evaluate_target_high_precision
from geosolver.engine.standard.evaluation.snapshots import evaluate_scalar_expression

def num(v):
    assert mp.isfinite(v)
    return mp.nstr(v,200,min_fixed=0,max_fixed=0) if v else '0.0e+0'

'''
fn='def measure(s4, item, reference, scales, initial_points, task):\n'
setup="manifest = {'step_exponents':[70,60], 'agreement_relative_tolerance':'1e-40'}\ncsv_rows=[]\n"
# Body was originally under mp.workdps(200), high_precision_mode().
fn+=textwrap.indent(setup,'    ')
fn+='    with mp.workdps(200), s4.high_precision_mode():\n'+textwrap.indent(body,'        ')
fn+='        return entry, csv_rows\n'
(OUT/'measure.py').write_text(imports+spectrum+'\n'+fn)

# Reuse the original 620-dps reference implementation. Tighten both acceptance gates
# to 300 digits, retaining the single closure, residual gate, and verifier.
s=(OUT.parent/'S4/worker.py').read_text()
a=s.index('def make_reference(');b=s.index('\ndef run(',a)
ref=s[a:b].replace("mp.mpf('1e-200')","mp.mpf('1e-300')").replace('200桁一致','300桁一致')
(OUT/'reference.py').write_text('"""S4 reference function; only 200 -> 300 digit acceptance changed."""\nfrom s4_helpers import *\n'+ref+'\n')
# Helper functions are directly imported from original S4 worker (no calls to run).
(OUT/'s4_helpers.py').write_text('''"""Import S4 expression helpers without running S4 or reading S3 outcomes."""
import importlib.util
from pathlib import Path
p=Path(__file__).resolve().parent.parent/'S4/worker.py'
spec=importlib.util.spec_from_file_location('s4_original_worker',p)
s4=importlib.util.module_from_spec(spec)
spec.loader.exec_module(s4)
for k,v in vars(s4).items():
    if not k.startswith('__'): globals()[k]=v
''')
print('Reused S4 reference and S4.12 measurement implementations')
