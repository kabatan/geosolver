"""Verify source identities, saved-table arithmetic, and the local invariance check."""
from __future__ import annotations
import csv
import hashlib
import json
from collections import Counter

import numpy as np
from experiment import OUT, ROOT, all_cases, context, dump, norm, radial, smb, vector_function


def jacobian(fun, x, hscale=1e-6):
    cols=[]
    for j in range(len(x)):
        h=hscale*max(1., abs(x[j]))
        xp,xm=x.copy(),x.copy()
        xp[j]+=h;xm[j]-=h
        cols.append((fun(xp)-fun(xm))/(2*h))
    return np.column_stack(cols)


def main():
    env=json.loads((OUT/'environment.json').read_text())
    for key,path in [('case_file_sha256',ROOT/'benchmarks/cases.jsonl'),('backend_sha256',ROOT/'src/geosolver/engine/standard/search/scipy_multistart_backend.py'),('protocol_sha256',OUT/'protocol.md')]:
        assert hashlib.sha256(path.read_bytes()).hexdigest()==env[key], key
    selected=json.loads((OUT/'selected.json').read_text())
    assert len(selected)==12 and len({r['id'] for r in selected})==12
    cases=all_cases()
    checks=[]
    all_interventions=[]
    for sel in selected:
        d=json.loads((OUT/'interventions'/f"{sel['id']}.json").read_text())
        assert len(d['rows'])==40
        for row in d['rows']:
            assert set(row)-{'k','start'}=={'base','sharpen','flatten'}
            for mode in ('base','sharpen','flatten'):
                r80,r320=row[mode]['80'],row[mode]['320']
                if r80['status']!=0:
                    assert r320.get('reused_terminated')
                    assert r80['cls']==r320['cls']
                else:
                    assert not r320.get('reused_terminated')
        all_interventions.append(d)
    summary=list(csv.DictReader((OUT/'intervention-summary.csv').open()))
    lookup={d['id']:d for d in all_interventions}
    for r in summary:
        d=lookup[r['id']]
        assert int(r['hits'])==sum(row[r['mode']][r['cap']]['cls']=='hit' for row in d['rows'])
    for cid in ('AIME-2023-I-12','HMMT-2024-FEB-GEO-04'):
        d=lookup[cid]
        b,ev,box=context(cases[cid])
        fn,tel=vector_function(b,ev)
        hit=next(r['sharpen']['320'] for r in d['rows'] if r['sharpen']['320']['cls']=='hit')
        x=np.array(hit['x'])
        J=jacobian(fn,x)
        eq=J[:len(b.spec.constraints)]
        sv=np.linalg.svd(eq,compute_uv=False)
        check={'id':cid,'x':x.tolist(),'augmented_residual':norm(fn(x)),
               'equality_jacobian_singular_values':sv.tolist(),
               'equality_condition_number':float(sv[0]/sv[-1]),'a':d['a']}
        for mode in ('sharpen','flatten'):
            T=jacobian(lambda v:radial(fn(v),d['a'],mode),x)
            check[f'{mode}_relative_J_difference']=float(np.linalg.norm(T-J)/np.linalg.norm(J))
        checks.append(check)
    primary_calls=sum(1+int(not row[mode]['320'].get('reused_terminated')) for d in all_interventions for row in d['rows'] for mode in ('base','sharpen','flatten'))
    reps=[json.loads(p.read_text()) for p in (OUT/'replication').glob('*.json')]
    for d in reps:
        assert len(d['rows'])==100
    counts={mode:dict(Counter(row[mode]['cls'] for d in reps for row in d['rows'])) for mode in ('base','sharpen','flatten','scale10')}
    features=[json.loads(p.read_text()) for p in (OUT/'features').glob('*.json')]
    report={'source_hashes_unchanged':True,'primary_cases':len(selected),'primary_local_solve_calls':primary_calls,
            'primary_runs_at_80':12*40*3,'additional_runs_at_320':primary_calls-12*40*3,
            'replication_local_solve_calls':sum(len(d['rows'])*4 for d in reps),
            'feature_seconds':sum(d['seconds'] for d in features),
            'primary_intervention_seconds':sum(d['elapsed'] for d in all_interventions),
            'replication_seconds':sum(d['elapsed'] for d in reps),
            'replication_class_counts':counts,'local_checks':checks,
            'artifact_bytes_before_final_report':sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())}
    if (OUT/'hard-penalty-results.json').exists():
        hard=json.loads((OUT/'hard-penalty-results.json').read_text())
        report['additional_nohard_local_solve_calls']=sum(len(d['rows']) for d in hard)
        report['additional_nohard_seconds']=sum(d['seconds'] for d in hard)
        report['total_local_solve_calls']=primary_calls+sum(len(d['rows'])*4 for d in reps)+sum(len(d['rows']) for d in hard)
    dump(OUT/'audit.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
