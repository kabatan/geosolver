"""Supplementary source coverage and descriptive checks, not preregistered tests."""
from pathlib import Path
from collections import defaultdict, Counter
import json, math, re
import numpy as np
from explore import ROOT, OUT, read, table, inputs, savejson, savecsv, med, col, q


def main():
    prec=table('jssa/strategy/astra-consult-18/q21b-number-theory/precision.csv')
    values=defaultdict(list)
    for r in prec: values[(r['id'],r['answer_index'])].append(r)
    rev=[]; first=[]
    for (id,ai),g in values.items():
        g.sort(key=lambda r:int(r['precision']))
        first.append(dict(id=id,answer_index=ai,first_success=min([int(r['precision']) for r in g if r['status']=='correct'],default=None)))
        for a,b in zip(g,g[1:]):
            if a['status']=='correct' and b['status']!='correct': rev.append(dict(id=id,answer_index=ai,precision_a=a['precision'],precision_b=b['precision'],status_b=b['status']))
    savecsv('precision-reversals.csv',rev)
    ms=table('jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv')
    valid=[r for r in ms if r['msolve_class']=='answer_set_matches']
    mss=[]
    for label,lo,hi in [('roots<=2',0,2),('roots3..16',2,16),('roots>16',16,np.inf)]:
        g=[r for r in valid if lo<float(r['real_solutions'] or 0)<=hi]
        mss.append(dict(group=label,n=len(g),msolve_s=med(g,'msolve_s'),geo_median_s=med(g,'geo_median_s'),max_degree_median=med(g,'max_degree')))
    savecsv('msolve-descriptive.csv',mss)
    refine=[]
    for path in sorted((ROOT/'jssa/difficulty/multiplicity/runs').glob('*__O.json')):
        j=json.loads(read(path.relative_to(ROOT))); hist=[h for o in j['outputs'] for h in o.get('history',[])]
        stages=[]
        for h in hist:
            parts=h.split(':',2)
            if len(parts)<3: continue
            try: residual=float(parts[2]); precision=int(parts[0])
            except ValueError: continue
            stages.append((precision,parts[1],residual))
        refine.append(dict(id=j['id'],index=j['index'],passed=j['passed'],seconds=j['seconds'],history_records=len(hist),outputs=len(j['outputs']),zero_history_residual=sum(x[2]==0 for x in stages),max_logged_precision=max([x[0] for x in stages],default=None)))
    savecsv('refinement-history-audit.csv',refine)
    dose=[]
    for path in sorted((ROOT/'benchmarks/extra-variables/dsl').glob('*.json')):
        j=json.loads(read(path.relative_to(ROOT)))
        dose.append(dict(id=path.name.rsplit('.k',1)[0],k=int(path.stem.rsplit('.k',1)[1]),n_vars=len(j['variables']),conditions=len(j['conditions'])))
    savecsv('dose-input-inventory.csv',dose)
    gs=table('jssa/results/gmb-success-definition/per-trial.csv')
    c=table('jssa/difficulty/common-start/summary.csv')
    f0=table('jssa/difficulty/start-feasibility-1023/per-problem.csv')
    f1=table('jssa/difficulty/start-feasibility-1023/per-problem-seed1.csv')
    target='HMMT-2024-FEB-GEO-04'
    evidence=dict(precision=dict(values=len(values),problems=len(set(r['id'] for r in prec)),calls=len(prec),nonmonotone_values=len(set((r['id'],r['answer_index']) for r in rev)),nonmonotone_problems=len(set(r['id'] for r in rev)),first_success_counts=dict(Counter(r['first_success'] for r in first))),
                  msolve=mss,refinement=dict(candidates=len(refine),problems=len(set(r['id'] for r in refine)),history_record_counts=q(col(refine,'history_records')),with_zero_log=sum(r['zero_history_residual']>0 for r in refine),note='These are precision-stage history strings, not every local-search iterate. Residual 0 is not proof of exactness.'),
                  dose=dict(inputs=len(dose),problems=len(set(r['id'] for r in dose)),has_raw_extra60=(ROOT/'jssa/difficulty/minima/raw-extra60').exists(),has_basins_extra60=(ROOT/'jssa/difficulty/minima/basins-extra60.csv').exists(),common_start_inputs=len(c),common_start_median_pE=med(c,'pE'),common_start_median_pY=med(c,'pY'),note='Original dose-response raw times absent in this checkout. Common-start E/Y has a different protocol.'),
                  gmb=dict(rows=len(gs),problems=len(set(r['case_id'] for r in gs)),columns=list(gs[0]),has_timing=False,has_local_evaluation=(ROOT/'benchmarks/local-evaluation').exists()),
                  feasibility_example_seed0=[r for r in f0 if r['id']==target],feasibility_example_seed1=[r for r in f1 if r['id']==target])
    savejson('supplement-summary.json',evidence); savejson('input-manifest-supplement.json',inputs)
    print(json.dumps(evidence,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
