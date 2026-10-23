"""Independent algebraic/data checks. No search or optimization is run here."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import os
from pathlib import Path
from fractions import Fraction
import sys

for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='1'
sys.dont_write_bytecode=True
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]


def read(name):
    return json.loads((HERE/name).read_text())


def main():
    rows=read('measurements.json')
    summary=read('summary.json')
    regular=[r for r in rows if r['status']=='regular_stable']
    assert len(rows)==323 and len({r['id'] for r in rows})==323
    assert len(regular)==summary['n_regular']==218
    assert sum(summary['counts'].values())==323
    errors=[]
    for r in regular:
        A=np.asarray(r['row_weights'])[:,None]*np.asarray(r['jacobian'])
        g=np.asarray(r['gradient'])
        P=np.linalg.pinv(A,rcond=1e-12)
        # Different formula from measure.metric: explicit Moore-Penrose inverse.
        kx=np.linalg.norm(P,2)
        kt=np.linalg.norm(g@P)/max(1,abs(r['target']))
        q=np.linalg.norm(g@P)/(np.linalg.norm(g)*kx)
        e=max(abs(kx/r['main']['kx']-1),abs(kt/r['main']['ktau']-1),abs(q/r['main']['q']-1))
        assert e<1e-9,(r['id'],e)
        assert 1/r['main']['cond']-1e-10<=q<=1+1e-10
        if r['n_vars']==1:
            assert abs(q-1)<1e-10
        assert r['hard'] and r['guard'] and r['raw_residual_max']<=1e-8
        errors.append(e)
    count=sum(r['main']['q']<=.01 for r in regular)
    required=max(10,math.ceil(.1*len(regular)))
    assert count==summary['q_le_001']==0
    assert required==summary['separation_prevalence_required']==22
    assert summary['separation_prevalence_gate_passed'] is False
    assert summary['strong_claim_gate_passed'] is False
    assert read('selected-controls.json')==[r['id'] for r in regular if r['main']['q']>.01][:3]

    # Closed forms follow directly from the three geometries, independently of
    # the solver evaluator, the residual finite differences, and SciPy's solves.
    targets={r['id']:r['target'] for r in regular}
    for cid,t in [('AIME-2006-I-01',84),('AIME-2006-I-07',408),('AIME-2006-II-01',46)]:
        assert abs(targets[cid]-t)/t<1e-8
    r=Fraction(11,5)
    N=16*(2*r-1)*(r-1)
    dN=64*r-48
    L=7-3*r
    value=N/L**2
    derivative=dN/L**2+6*N/L**3
    assert value==408 and derivative==6700
    exact={
        ('AIME-2006-I-01','AB'):Fraction(21,62),
        ('AIME-2006-I-01','BC'):Fraction(13,31),
        ('AIME-2006-I-01','CD'):Fraction(15,62),
        ('AIME-2006-I-07','area_ratio'):r*derivative/value,
        ('AIME-2006-I-07','illustrative_angle'):Fraction(0),
        ('AIME-2006-II-01','area'):Fraction(1,2),
    }
    exact_checks=[]
    for s in read('input-sensitivities.json'):
        theory=exact[s['id'],s['parameter']]
        error=abs(s['relative_target_gain']-float(theory))/max(1,abs(float(theory)))
        assert error<1e-8,(s['id'],s['parameter'],error)
        assert all(f['check_pass'] for f in s['fits'])
        exact_checks.append({'id':s['id'],'parameter':s['parameter'],
                             'exact_relative_target_gain':str(theory),
                             'measured_relative_target_gain':s['relative_target_gain'],
                             'normalized_error':error})
    runs=read('perturbation-runs.json')
    assert len(runs)==24 and all(r['ok'] and r['hard'] and r['guard'] and r['raw_residual_max']<=1e-8 for r in runs)
    for t in read('integer-triangles.json'):
        m=t['m'];a=m*m+1;c=2*(m*m-1);h=2*m
        assert a*a-(c*c//4)==h*h
        assert abs(float(t['relative_height_condition_theory'])-float(Fraction(a*a,h*h)))<1e-10
        assert float(t['relative_difference'])<1e-10

    locked=read('measurement-lock.json')['hashes']
    changed=[p for p,v in locked.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=v]
    assert not changed,changed
    for item in rows:
        if 'raw_sha256' in item:
            rawpath=ROOT/'jssa/difficulty/minima/raw-323'/(item['id']+'.json')
            assert hashlib.sha256(rawpath.read_bytes()).hexdigest()==item['raw_sha256']
    perturb_lock=read('perturbation-lock.json')['hashes']
    assert all(hashlib.sha256((HERE/p).read_bytes()).hexdigest()==v for p,v in perturb_lock.items())
    result={'passed':True,'n_metrics_independently_recomputed':len(errors),
            'max_metric_relative_error':max(errors),'n_exact_target_checks':3,
            'exact_sensitivity_checks':exact_checks,'n_accepted_perturbation_runs':len(runs),
            'n_source_hashes_checked':len(locked),'all_locked_sources_unchanged':not changed,
            'n_saved_raw_hashes_checked':sum('raw_sha256' in r for r in rows),
            'all_locked_perturbation_files_unchanged':True}
    (HERE/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
