"""Exact rational identities on explicitly derived real charts.

This is a verifier/generator for hand-derived certificates, NOT a fresh-DSL
automatic prover. See certificate-derivations.md for implications from the DSL.
Only H/certificates/ is written; no external CAS or numerical search is used.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import signal
import time

import sympy as sp

HERE = Path(__file__).resolve().parent


def timeout(signum, frame):
    raise TimeoutError('60 second certificate limit')


def systems():
    x, y, t, T = sp.symbols('x y t T')
    F = [x*x+y*y-400,
         (1-t)*(x*x+y*y)+11*t*x-20*((1-t)*x+11*t),
         t*T-1]
    yield dict(id='AIME-2011-II-04', variables=[x,y,t,T], F=F,
               s=20-x, N=1, P=20*T-31,
               C=[-T*(1-t), T, 31*(20-x)],
               nonzero_reason='0 < x < 11 implies 20-x > 0; the internal angle condition implies t=20/31 > 0.')

    b, d, k, T = sp.symbols('b d k T')
    F = [180**2+d*d-k-360*d*T, 180**2+b*b-k-360*b*T, b+d-280]
    yield dict(id='aime-2003-1-12', variables=[b,d,k,T], F=F,
               s=d-b, N=1, P=9*T-7,
               C=[-sp.Rational(1,40), sp.Rational(1,40), (d-b)/40],
               nonzero_reason='AD != BC is an explicit DSL guard; b=BC,d=AD.')

    p, q, c, T = sp.symbols('p q c T')
    A = p*p+4-4*p*c
    B = q*q+81-18*q*c
    F = [p*p-2*q, q*q-9*p, T*T*p*p*B-q*q*A]
    h1 = (p*p+2*q)*(q*q-18*q*c)+324*p*c
    h2 = -(q*q+9*p)*(p*p-4*p*c)-72*q*c
    K = p*p*B*(q*T+p)
    V = q*q*T*T+p*q*T+p*p
    yield dict(id='JMO-2013-PRE-05', variables=[p,q,c,T], F=F,
               s=q**3*K, N=1, P=9*T**3-2,
               C=[9*p*K-9*V*h1, -2*q*K-9*V*h2, 9*V*q*q],
               auxiliary=dict(A=A, B=B, h1=h1, h2=h2, K=K, V=V),
               nonzero_reason='p,q,T are positive; B=QR^2>0 since 0<theta<pi; hence s>0.')

    k, a, y, T = sp.symbols('k a y T')
    yield dict(id='HMMT-2023-FEB-GEO-01', variables=[k,a,y,T],
               F=[k*a*a-2*a*y-80, a*y-23, 2*T-3*k*a*a, k*k-3],
               s=sp.Integer(1), N=0, P=T-189,
               C=[sp.Rational(3,2), sp.Integer(3), sp.Rational(1,2), sp.Integer(0)],
               nonzero_reason='s=1; k=sqrt(3)>0, a is the hexagon side. This case was outside the old 63.')


def main():
    signal.signal(signal.SIGALRM, timeout)
    outdir = HERE/'certificates'
    outdir.mkdir(exist_ok=True)
    prior = {r['id']: r for r in csv.DictReader((HERE/'sources/prior-batch-summary.csv').open())}
    old_nd = {'AIME-2009-I-12','HMMT-2008-FEB-GEO-09','JMO-2013-PRE-08','aime-2000-2-6'}
    results=[]
    for item in systems():
        signal.alarm(60)
        started=time.perf_counter()
        residual=sp.expand(item['s']**item['N']*item['P']-sum(c*f for c,f in zip(item['C'],item['F'])))
        assert residual == 0, (item['id'],residual)
        terms=sum(len(sp.Poly(sp.expand(c),*item['variables']).terms()) for c in item['C'] if c!=0)
        old=prior.get(item['id'],{}).get('status','outside_old_63')
        is_new=old not in ('identity_P','identity_E','identity_E_large','outside_old_63') and item['id'] not in old_nd
        record=dict(id=item['id'],system_kind='derived real chart; not original fresh ideal',
            variables=list(map(str,item['variables'])),F=list(map(str,item['F'])),s=str(item['s']),N=item['N'],
            P=str(item['P']),C=list(map(str,item['C'])),
            auxiliary={k:str(v) for k,v in item.get('auxiliary',{}).items()},
            residual=str(residual),exact_check='sympy.expand over QQ',cofactor_terms=terms,
            nonzero_reason=item['nonzero_reason'],prior_status=old,
            new_among_old_63=is_new,seconds=time.perf_counter()-started)
        text=json.dumps(record,ensure_ascii=False,indent=2)+'\n'
        assert len(text.encode()) < 2_000_000
        (outdir/(item['id']+'.json')).write_text(text)
        results.append({k:record[k] for k in ('id','prior_status','new_among_old_63','cofactor_terms','seconds')})
        signal.alarm(0)
    assert sum(r['new_among_old_63'] for r in results)==3
    (outdir/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    main()
