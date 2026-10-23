"""Validate measurement semantics, finite differences, and an analytic example.

This script never runs a geometry optimizer. Writes stay in A/.
"""
from __future__ import annotations
import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode=True
from measure_attraction import GeometryProbe, HERE, ROOT, measure
import numpy as np


def main():
    cases={c['id']:c for c in map(json.loads,(ROOT/'benchmarks/cases.jsonl').read_text().splitlines())}
    with (HERE/'attraction.csv').open() as f:
        features=list(csv.DictReader(f))
    assert len(features)==292
    mismatch=[];valid_mismatch=[];nonfinite=[];name_only=[]
    for r in features:
        probe=GeometryProbe(cases[r['id']]['dsl'])
        z=np.linspace(.337,.613,len(probe.var_names))
        f,_=probe.evaluate(z)
        native=np.asarray(probe.evaluator.evaluate_float_residual((probe.lower+probe.width*z).tolist()).residual_vector)
        fv=bool(np.isfinite(f).all());nv=bool(np.isfinite(native).all())
        if fv!=nv:valid_mismatch.append(r['id'])
        if fv and nv and not np.allclose(f,native,rtol=1e-12,atol=1e-12):mismatch.append(r['id'])
        if not nv:nonfinite.append(r['id'])
        if not np.allclose(f,native,rtol=1e-12,atol=1e-12,equal_nan=True):name_only.append(r['id'])
    assert not mismatch and not valid_mismatch
    report={'residual_validation':{
        'n':len(features),'validity_mismatches':valid_mismatch,'finite_vector_mismatches':mismatch,
        'native_nonfinite_at_test_point':nonfinite,
        'invalid_vector_nan_pattern_differences':name_only,
        'note':'Native evaluation can mark the entire vector NaN; partial evaluation preserves some finite entries. Both are rejected by the metric.'}}
    selected=sorted(features,key=lambda r:hashlib.sha256(('derivative-audit:'+r['id']).encode()).hexdigest())[:20]
    checked=[]
    for r in selected:
        s=measure(r['id'],cases[r['id']]['dsl'],h=1e-6)
        checked.append({'id':r['id'],'A_h1e5':float(r['A']) if r['A'] else None,
                        'A_h1e6':s.get('A'),'status_h1e5':r['status'],'status_h1e6':s['status']})
    report['derivative_check']=checked
    diffs=[abs(r['A_h1e5']-r['A_h1e6']) for r in checked if r['A_h1e5'] is not None and r['A_h1e6'] is not None]
    report['derivative_max_abs_diff']=max(diffs)
    report['toy_example']=[]
    for a in [-8,-2,0,2,8]:
        # r_a(x)=exp(a*x)*x*(x-1); its interior stationary point is b.
        # Under continuous negative-gradient flow of r_a^2 and x~U(0,1),
        # 0 is reached below b, 1 above b. This is NOT an LM experiment.
        b=.5 if a==0 else (a-2+np.sqrt(a*a+4))/(2*a)
        assert abs((2*b-1)+a*b*(b-1))<1e-12
        report['toy_example'].append({'alpha':a,'separator':b,'p_gradient_flow':1-b,'f_ghost':1.})
    report['matplotlib_available']=importlib.util.find_spec('matplotlib') is not None
    (HERE/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    (HERE/'residual-validation.json').write_text(json.dumps(report['residual_validation'],indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
