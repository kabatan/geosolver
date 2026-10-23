"""Post-registration endpoint audit; NO optimization or answer-guided proposals.

Motivated by reading the feasible-margin penalty and the first saved endpoints.
This is exploratory mechanistic evidence, separate from registered H1/H2/H3.
"""
import csv
import json
import math
from collections import Counter
from pathlib import Path
import numpy as np
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.search import scipy_multistart_backend as smb
from experiment import OUT,clean,dump

def main():
    selected=json.loads((OUT/'selection.json').read_text()); rows=[]; natives=Counter(); native_time=Counter(); evals=0
    for c in selected:
        inp=json.loads((OUT/'inputs'/f'{c["id"]}.json').read_text())
        bundle=load_problem_bundle(GeometryProblem.model_validate(inp['dsl']).engine_document()); ev=build_ir_evaluator(bundle)
        tele=smb._SearchTelemetry()
        def vector(x):
            return smb._evaluate_augmented_residual_vector(bundle=bundle,evaluator=ev,values=np.array(x),n_constraints=len(bundle.spec.constraints),telemetry=tele)
        for path in (OUT/'runs'/c['id']).glob('*.json'):
            raw=json.loads(path.read_text())
            for a in raw['arms']:
                nr=a.get('native_result')
                if isinstance(nr,dict):
                    reason=nr.get('stop_reason','unknown'); natives[(a['arm'],reason)]+=1
                    if 'allowed time' in reason: native_time[a['arm']]+=1
                if a['arm'] not in ['L','Lnp'] or a.get('best') is None: continue
                best=a['best']; x=np.asarray(best['x']); v=vector(x)
                h=ev.evaluate_float_hard_feasibility(x,include_margins=False)
                row={'id':c['id'],'group':c['group'],'seed':raw['seed'],'k':raw['k'],'arm':a['arm'],'res':best['res'],'guard_row':float(v[-2]),'hard_row':float(v[-1]),'margin':None if h.min_margin is None else float(h.min_margin),'total_cost_at_saved_point':float(np.dot(v,v)),'eq_grad_norm':None,'pen_grad_norm':None,'total_grad_norm':None,'cos_eq_pen':None,'gradient_consistent':None}
                # Examine all near-root L/Lnp endpoints, not a hand-picked case.
                if best['res']<=1e-4:
                    estimates=[]
                    for step_factor in [1e-5,1e-6]:
                        cols=[]
                        for j in range(len(x)):
                            step=step_factor*max(1.,abs(x[j])); xp=x.copy(); xm=x.copy(); xp[j]+=step; xm[j]-=step
                            cols.append((vector(xp)-vector(xm))/(2*step))
                        jac=np.column_stack(cols); ge=2*jac[:-2].T@v[:-2]; gp=2*jac[-2:].T@v[-2:]
                        estimates.append((ge,gp))
                    ge,gp=estimates[-1]; ne=float(np.linalg.norm(ge)); npg=float(np.linalg.norm(gp)); total=float(np.linalg.norm(ge+gp))
                    row.update(eq_grad_norm=ne,pen_grad_norm=npg,total_grad_norm=total,cos_eq_pen=float(np.dot(ge,gp)/(ne*npg)) if ne*npg else None,gradient_consistent=bool(np.linalg.norm(estimates[0][1]-gp)<=.01*max(npg,1e-20)))
                rows.append(row)
        evals+=tele.evaluation_count
    with (OUT/'margin-diagnostic.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(clean(rows))
    dump(OUT/'diagnostic-summary.json',{'posthoc':True,'optimization_calls':0,'diagnostic_residual_evals':evals,'native_time_stops':dict(native_time),'native_stop_reasons':[{'arm':a,'reason':reason,'n':n} for (a,reason),n in sorted(natives.items())],'audited_endpoints':len(rows),'hard_L_near_roots':sum(r['group']=='hard' and r['arm']=='L' and r['res']<=1e-4 for r in rows),'hard_Lnp_near_roots':sum(r['group']=='hard' and r['arm']=='Lnp' and r['res']<=1e-4 for r in rows)})
    print(json.dumps({'diagnostic_endpoints':len(rows),'residual_evaluations':evals,'native_time_stops':dict(native_time)}))

if __name__=='__main__': main()
