"""Post-hoc check of the exact, undamped GN radial-step formula.

This does not assert equality to the damped, diagonally scaled LM trajectory.
For R'=g(R)R, g=1+||R||^2/a^2, full-column-rank J, define
eta=||P_col(J) R||^2 / ||R||^2 and k=(1+3t^2)/(1+t^2).
The new GN step is k/[1+(k^2-1)eta] times the original GN step.
"""
from __future__ import annotations
import json
from collections import Counter

import numpy as np
from experiment import OUT, all_cases, context, dump, norm, vector_function
from audit import jacobian


def main():
    cases=all_cases()
    rows=[]
    for cid in ('AIME-2023-I-12','HMMT-2024-FEB-GEO-04'):
        data=json.loads((OUT/'replication'/f'{cid}.json').read_text())
        b,ev,box=context(cases[cid])
        fn,tel=vector_function(b,ev)
        a=data['a']
        for rec in data['rows']:
            x=np.array(rec['start'])
            r=fn(x)
            J=jacobian(fn,x,hscale=1e-5)
            delta,_,rank,sv=np.linalg.lstsq(J,-r,rcond=1e-10)
            if rank<len(x) or norm(delta)<1e-12:
                rows.append({'id':cid,'k':rec['k'],'rank':int(rank),'skipped':True})
                continue
            t2=(norm(r)/a)**2
            g=1+t2
            kappa=(1+3*t2)/(1+t2)
            eta=(norm(J@delta)/norm(r))**2
            predicted=kappa/(1+(kappa*kappa-1)*eta)
            Jnew=g*J+2/a**2*np.outer(r,r@J)
            dnew=np.linalg.lstsq(Jnew,-g*r,rcond=1e-10)[0]
            measured=float(np.dot(dnew,delta)/np.dot(delta,delta))
            rows.append({'id':cid,'k':rec['k'],'rank':int(rank),'eta':eta,
                         'predicted_step_factor':predicted,'measured_step_factor':measured,
                         'relative_formula_error':norm(dnew-predicted*delta)/max(norm(dnew),1e-30),
                         'initial_hard_penalty':float(r[-1]),
                         'base_hit':rec['base']['cls']=='hit',
                         'sharpen_hit':rec['sharpen']['cls']=='hit'})
    summary=[]
    for cid in ('AIME-2023-I-12','HMMT-2024-FEB-GEO-04'):
        for group in ('all','initial_hard_10000','initial_hard_not_10000'):
            rr=[r for r in rows if r['id']==cid and not r.get('skipped') and
                (group=='all' or ((r['initial_hard_penalty']==10000)==(group=='initial_hard_10000')))]
            if not rr:
                continue
            summary.append({'id':cid,'group':group,'n':len(rr),
                            'median_eta':float(np.median([r['eta'] for r in rr])),
                            'median_GN_step_factor':float(np.median([r['predicted_step_factor'] for r in rr])),
                            'max_formula_relative_error':max(r['relative_formula_error'] for r in rr),
                            'base_hits':sum(r['base_hit'] for r in rr),
                            'sharpen_hits':sum(r['sharpen_hit'] for r in rr),
                            'gain':sum(r['sharpen_hit'] and not r['base_hit'] for r in rr),
                            'loss':sum(r['base_hit'] and not r['sharpen_hit'] for r in rr)})
    dump(OUT/'mechanism-rows.json',rows)
    dump(OUT/'mechanism-summary.json',{'posthoc':True,'rows':summary,'skipped':sum(r.get('skipped',False) for r in rows)})
    print(json.dumps(summary,indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
