"""Assemble fixed-case comparison and exact checks from preserved raw results."""
import csv
import hashlib
import json
import math
import signal
from collections import Counter
from pathlib import Path

import sympy as sp

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
IDS=['AIME-2006-I-01','AIME-2025-I-06','AIME-2025-II-06',
     'HMMT-2010-FEB-GEO-02','HMMT-2014-FEB-GEO-08','JMO-2008-PRE-02']

def expire(*_): raise TimeoutError('summary exact check exceeded 30 seconds')
signal.signal(signal.SIGALRM,expire)
signal.alarm(30)
audits={(x['id'],x['mode']):x for x in json.loads((OUT/'exact-audit.json').read_text())}
hc=list(csv.DictReader((OUT/'hc-summary.csv').open()))
old=list(csv.DictReader((ROOT/'jssa/difficulty/minima/basins-323.csv').open()))
exactold=list(csv.DictReader((ROOT/'jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv').open()))

# Exact counts follow from the saved triangular rational Groebner bases.
# The only non-shape case has a squarefree degree-six eliminant and two lifts.
h,e,s3=sp.symbols('v_h v_e s3')
g2=audits[('AIME-2025-II-06','fresh')]
polys=[sp.sympify(x) for x in g2['groebner_basis']]
P=polys[-1]
e_of_h=sp.solve(polys[-2],e)[0]
s_squared=-polys[2].subs(s3,0)
assert sp.rem(s_squared-e_of_h**2*(h-12)**2,P,h)==0
assert sp.gcd(P,sp.diff(P,h))==1
assert sp.gcd(P,s_squared)==1
degree=sp.degree(P,h)
real_h=sum(1 for _ in sp.Poly(P,h).intervals())
assert degree==6 and real_h==4

tf=sp.Symbol('v_t')
f=json.loads((OUT/'inputs/HMMT-2014-FEB-GEO-08__fresh.json').read_text())
i=json.loads((OUT/'inputs/HMMT-2014-FEB-GEO-08__inline.json').read_text())
ratio=sp.cancel(sp.sympify(i['equations'][0])/sp.sympify(f['equations'][0]))
assert sp.expand(ratio-(tf-1)**2)==0
assert audits[('HMMT-2014-FEB-GEO-08','fresh')]['groebner_basis']==audits[('HMMT-2014-FEB-GEO-08','inline')]['groebner_basis']
counts={
 'AIME-2006-I-01':(2,2,2,'squarefree quadratic; other coordinates uniquely determined by its root'),
 'AIME-2025-I-06':(4,4,4,'squarefree quartic; other coordinates uniquely polynomial in s'),
 'AIME-2025-II-06':(12,8,6,'squarefree sextic; 2 nonzero square-root lifts per h; 4 real h'),
 'HMMT-2010-FEB-GEO-02':(4,4,4,'(w^2-5)(29w^2-5); all other coordinates polynomial in w'),
 'HMMT-2014-FEB-GEO-08':(1,1,1,'(73t-82)^2; zz linear in t; unique double root'),
 'JMO-2008-PRE-02':(1,1,1,'linear Groebner basis')}
checks={'AIME-2025-II-06':{'P':str(P),'e_of_h':str(e_of_h),
 's_squared':str(s_squared),'s_squared_equals_e2_hminus12_squared_mod_P':True,
 'gcd_P_derivative':'1','gcd_P_s_squared':'1','degree_h':int(degree),'real_h':real_h},
 'HMMT-2014-FEB-GEO-08':{'inline_first_equation_divided_by_fresh':str(ratio),
 'same_rational_groebner_basis':True}}
(OUT/'exact-count-checks.json').write_text(json.dumps(checks,indent=2)+'\n')

def wilson(k,n):
    z=1.959963984540054
    p=k/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den
    radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [center-radius,center+radius]

rows=[]
for cid in IDS:
    local=json.loads((OUT/'local-runs'/f'{cid}.json').read_text())
    archived=json.loads((ROOT/'jssa/difficulty/minima/raw-323'/f'{cid}.json').read_text())
    a=audits[(cid,'fresh')]
    pre=next(x for x in json.loads((OUT/'prepared.json').read_text()) if x['id']==cid and x['mode']=='fresh')
    r={'id':cid,'dsl_nvars':len(local['variables']),'polynomial_nvars':pre['nvars'],
       'total_degree_product':pre['total_degree_product'],
       'algebraic_length':a['quotient_dimension_with_multiplicity'],
       'exact_distinct_complex':counts[cid][0],'exact_distinct_real':counts[cid][1],
       'exact_projected_complex':counts[cid][2],'count_reason':counts[cid][3],
       'local_hits':local['n_hit'],'local_n':local['n'],'local_p':local['p'],
       'local_wilson95_low':wilson(local['n_hit'],local['n'])[0],
       'local_wilson95_high':wilson(local['n_hit'],local['n'])[1],
       'local_seconds':local['seconds'],'archived_p':archived['p_any'],
       'archived_n':archived['starts_done']}
    for method in ['total_degree','polyhedral']:
        entries=[x for x in hc if x['id']==cid and x['mode']=='fresh' and x['method']==method]
        assert len(entries)==2
        for field in ['tracked','at_infinity','failed','n_hit_clusters','n_hc_distinct']:
            r[f'{method}_{field}']='|'.join(x[field] for x in entries)
    rows.append(r)
with (OUT/'comparison.csv').open('w') as f:
    w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
metadata={'hc_jobs':len(hc),'tracked_paths':sum(int(x['tracked']) for x in hc),
 'failed_paths':sum(int(x['failed']) for x in hc),
 'infinity_paths':sum(int(x['at_infinity']) for x in hc),
 'local_starts':sum(r['local_n'] for r in rows),
 'local_seconds':sum(r['local_seconds'] for r in rows),
 'summary_sha256':hashlib.sha256((OUT/'comparison.csv').read_bytes()).hexdigest()}
(OUT/'measurement-summary.json').write_text(json.dumps(metadata,indent=2)+'\n')
signal.alarm(0)
print(json.dumps(metadata,indent=2))
