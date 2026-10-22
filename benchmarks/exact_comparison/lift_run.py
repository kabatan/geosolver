"""usage: lift_run.py CASE GEOSOLVER_RESULT.json OUT.json"""
import json, sys, time
sys.path.insert(0, '.')
import sympy as sp
from run_exact import load_case, build, verifier_for
from algebraize import translate
from lift_check import lift

cid, res, out = sys.argv[1:4]
case = load_case(cid)
r = json.load(open(res))
r = r.get('solver_result') or r  # research_runner raw record or plain solver output
recs = ((r.get('diagnostics') or {}).get('pipeline_summary') or {}).get('exact_candidate_records', [])
bundle, _ = verifier_for(case)
rec = {'id': cid}
if not recs:
    rec['status'] = 'no_geosolver_configuration'
else:
    x = recs[0]['candidate']['x_hp']
    vals = {sp.Symbol('v_' + n): sp.Float(v, 60) for n, v in zip(bundle.var_names, x)}
    # fixed variables appear as constructions in the bundle spec
    for c in bundle.spec.construction:
        if sp.Symbol('v_' + c.name) not in vals and c.name in case['dsl']['variables']:
            vals[sp.Symbol('v_' + c.name)] = sp.Float(sp.sympify(c.expression), 60)
    s, _ = translate(case['dsl'], mode='fresh')
    eqs, used, _ = build(s, rabinowitsch=False)
    t = time.monotonic()
    rec['status'] = 'satisfied' if lift(s, eqs, vals) else 'NOT_satisfied'
    rec['seconds'] = time.monotonic() - t
json.dump(rec, open(out, 'w'))
