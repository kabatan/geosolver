"""Final independent consistency checks for the delivered evidence, no search."""
import ast
import collections
import csv
import json
import math
import os
from pathlib import Path
import re
import sys

for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
import numpy
import scipy
import sympy as sp
import mpmath

HERE=Path(__file__).resolve().parent


def main():
    for p in HERE.glob('*.py'):
        ast.parse(p.read_text(),filename=str(p))
    def invalid_constant(value):
        raise ValueError(value)
    for p in HERE.rglob('*.json'):
        json.loads(p.read_text(),parse_constant=invalid_constant)
    for p in HERE.glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if not target.startswith(('http:','https:','#')):
                assert (p.parent/target).exists(),(p.name,target)
    comparison=list(csv.DictReader((HERE/'sources/comparison-cases.csv').open()))
    expected={r['id'] for r in comparison if r['msolve_class'] in ('positive_dimensional','free_parameter')}
    rows=list(csv.DictReader((HERE/'classification.csv').open()))
    assert len(rows)==68 and {r['id'] for r in rows}==expected
    counts=collections.Counter(r['evidence_code'] for r in rows)
    assert counts=={'G':16,'GAUGE':13,'AUX':1,'L0':36,'R0':2}
    number_samples=0
    for r in rows:
        if r['evidence_code']!='G':continue
        d=json.loads((HERE/'diagnostic'/f"{r['id']}.json").read_text())
        assert d['rank_stable'] and d['rank_threshold_stable']
        assert any(g['all_four_accepted'] and g['shape_moves'] for g in d['directions'])
        for q in d['samples']:
            assert q['accepted'] and q['state']['hard_feasible']
            assert q['state']['residual']<=1e-8 and q['coordinate_error']<=1e-8
            assert q['target_relative_change']<=1e-7
            number_samples+=1
    assert number_samples==72

    certificates=[]
    for p in sorted((HERE/'certificates').glob('*.json')):
        if p.name=='summary.json':continue
        c=json.loads(p.read_text())
        F=list(map(sp.sympify,c['F'])); C=list(map(sp.sympify,c['C']))
        s=sp.sympify(c['s']); P=sp.sympify(c['P'])
        assert sp.expand(s**c['N']*P-sum(a*b for a,b in zip(C,F)))==0
        d=json.loads((HERE/'diagnostic'/f"{c['id']}.json").read_text())
        points=[{'figure':d['figure'],'x':d['x'],'state':d['base_state']}]+[q for q in d['samples'] if q['accepted']]
        maximum=0.0; min_s=math.inf
        for q in points:
            g=q['figure']; T=q['state']['answer']
            if c['id']=='AIME-2011-II-04':
                values=dict(x=q['x'][0],y=q['x'][1],t=q['x'][2],T=T)
            elif c['id']=='aime-2003-1-12':
                values=dict(b=math.dist(g['B'],g['C']),d=math.dist(g['D'],g['A']),k=math.dist(g['B'],g['D'])**2,T=T)
            elif c['id']=='JMO-2013-PRE-05':
                values=dict(p=q['x'][1],q=q['x'][2],c=math.cos(q['x'][0]),T=T)
            else:
                values=dict(k=math.sqrt(3),a=q['x'][0],y=q['x'][2],T=T)
            substitution={sp.Symbol(k):v for k,v in values.items()}
            min_s=min(min_s,abs(float(s.subs(substitution))))
            for f in F:
                scale=max(1.0,sum(abs(float(term.subs(substitution))) for term in sp.Add.make_args(sp.expand(f))))
                maximum=max(maximum,abs(float(f.subs(substitution)))/scale)
        assert min_s>0 and maximum<1e-8
        certificates.append(dict(id=c['id'],exact_identity_zero=True,numeric_chart_points=len(points),
            maximum_relative_chart_residual=maximum,min_abs_s_on_tested_points=min_s))
    assert len(certificates)==4
    maximum_file=max(p.stat().st_size for p in HERE.rglob('*') if p.is_file())
    assert maximum_file<2_000_000
    result=dict(status='passed',classification_counts=counts,accepted_genuine_continuation_points=number_samples,
        certificates=certificates,local_markdown_links='all exist',python_syntax='valid',json_files='valid finite JSON',
        max_file_bytes=maximum_file,
        versions=dict(python=sys.version.split()[0],numpy=numpy.__version__,scipy=scipy.__version__,
            sympy=sp.__version__,mpmath=mpmath.__version__),
        limitations=['No new global component decomposition.',
            'Trapezoid second-direction shape change is below the numerical threshold; dimension two also uses analytic reasoning.',
            'Derived chart implication is explained mathematically, not fully machine-checked from fresh DSL generators.'])
    (HERE/'verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
