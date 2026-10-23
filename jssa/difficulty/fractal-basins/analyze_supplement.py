"""Separate, explicitly post-registration analyses; no solver execution."""
from collections import Counter
import json
import math
from pathlib import Path
import sys
import dataio
from experiment import OUT, IDS, EPS, SUPPLEMENT_MODES, check_lock, save, utc, label
from analyze import bootstrap, robust_fit, csvwrite, canonical_answers, full_roots
import numpy as np


def dense():
    stats=[];curves=[]
    inputs={r['id']:r for r in json.loads((OUT/'inputs.json').read_text())}
    for cid in ['AIME-2023-I-05','AIME-2025-I-02']:
        rows=[];verified=[]
        for p in sorted((OUT/'dense').glob(cid+'-*.json')):
            d=json.loads(p.read_text());rows+=d['rows'];verified+=d['verified']
        rows.sort(key=lambda r:r['i'])
        if len(rows)!=1024:
            print('incomplete',cid,len(rows));continue
        aa=np.array([[r['base']['label'] for _ in EPS] for r in rows])
        bb=np.array([[v['r']['label'] for v in r['variants']] for r in rows])
        coverage=np.char.startswith(aa,'R')&np.char.startswith(bb,'R')
        change=aa!=bb; roots=change&coverage
        ua=np.array([r['base']['label'] for r in rows]);ub=np.array([r['ulp']['r']['label'] for r in rows])
        u=ua!=ub;ur=u&np.char.startswith(ua,'R')&np.char.startswith(ub,'R')
        mask=(np.asarray(EPS)>=1e-12)&(np.asarray(EPS)<=1e-3)
        inp=inputs[cid];diff=0;total=0;old={r['i']:r for r in rows}
        for r in verified:
            a=old[r['i']]
            diff+=r['base']['label']!=a['base']['label'];total+=1
            for v in r['variants']:
                v0=next(v0 for v0 in a['variants'] if v0['eps']==v['eps'])
                diff+=v['r']['label']!=v0['r']['label'];total+=1
        tol={str(t):sum(label(r['base'],inp,t)!=r['base']['label'] for r in rows)+
             sum(label(v['r'],inp,t)!=v['r']['label'] for r in rows for v in r['variants'])
             for t in (1e-6,1e-5,1e-4)}
        s={'id':cid,'n':1024,'alpha_raw':bootstrap(change,EPS,rows,mask),
           'alpha_root_raw':bootstrap(roots,EPS,rows,mask),
           'outcome_scaling':robust_fit(change,u,EPS,rows),
           'root_scaling':robust_fit(roots,ur,EPS,rows),
           'root_coverage_min':float(coverage.mean(axis=0).min()),
           'ulp_changes':int(u.sum()),'ulp_root_changes':int(ur.sum()),
           'repeat_changes':sum(r['base']['label']!=r['repeat']['label'] for r in rows if 'repeat' in r),
           'cap320_label_changes':diff,'cap320_labels':total,'cap320_rate':diff/total,
           'label_tolerance_differences':tol}
        reasons=list(s['root_scaling']['reasons'])
        if s['root_coverage_min']<.9:reasons.append('root_coverage_below_90pct')
        if s['cap320_rate']>.02:reasons.append('cap_dependent')
        if any(tol.values()):reasons.append('root_tolerance_dependent')
        s['exploratory_scaling_pass']=not reasons;s['reasons']=reasons
        for j,e in enumerate(EPS):
            curves.append({'id':cid,'epsilon':e,'n':1024,'changes':int(change[:,j].sum()),
               'f':float(change[:,j].mean()),'root_changes':int(roots[:,j].sum()),
               'f_root':float(roots[:,j].mean()),'root_coverage':float(coverage[:,j].mean()),
               'f_seed340601':float(change[:512,j].mean()),'f_seed340602':float(change[512:,j].mean())})
        stats.append(s)
    save('dense-summary.json',{'utc':utc(),'kind':'exploratory; excluded from primary P1','problems':stats})
    csvwrite('dense-uncertainty.csv',curves)
    print(json.dumps(stats,indent=2))


def full_mp():
    rows=[]; inputs={r['id']:r for r in json.loads((OUT/'inputs.json').read_text())}
    for cid in IDS:
        for seed in (340301,340302):
            native_path=OUT/f'full/{cid}-{seed}-native.json'
            native=dataio.read(native_path);nk,na,nn,_,nd=full_roots(native_path,inputs[cid])
            nk=[k for k in nk if k.startswith('R')]
            for mode in SUPPLEMENT_MODES:
                p=OUT/f'full-mp/{cid}-{seed}-{mode}.json'
                if not dataio.exists(p):continue
                d=dataio.read(p);keys,acc,n,_,digest=full_roots(p,inputs[cid])
                known=[k for k in keys if k.startswith('R')]
                rows.append({'id':cid,'seed':seed,'mode':mode,'status':d['status'],
                   'seconds':d['elapsed_seconds'],'termination':d['termination_reason'],
                   'intervention_calls':d['intervention_calls'],'candidate_count':n,
                   'answers':'|'.join(canonical_answers(d)),
                   'answer_changed':canonical_answers(d)!=canonical_answers(native),
                   'candidate_roots':'|'.join(known),'root_set_changed':known!=nk,
                   'accepted_roots':'|'.join(acc),'accepted_roots_changed':acc!=na,
                   'source_coordinates_changed':digest!=nd,
                   'float_count_changed':d['counters'].get('evaluate_float_residual')!=native['counters'].get('evaluate_float_residual'),
                   'float_calls':d['counters'].get('evaluate_float_residual',0),
                   'error':str(d.get('error') or '')})
    summary={'utc':utc(),'n_runs':len(rows),'errors':sum(r['status']!='completed' for r in rows)}
    for col in ['answer_changed','root_set_changed','accepted_roots_changed','source_coordinates_changed','float_count_changed']:
        summary[col+'_runs']=sum(r[col] for r in rows)
        summary[col+'_pairs']=len({(r['id'],r['seed']) for r in rows if r[col]})
    summary['total_seconds']=sum(r['seconds'] for r in rows)
    csvwrite('full-mp-runs.csv',rows);save('full-mp-summary.json',summary)
    print(json.dumps(summary,indent=2))


def audit():
    data=json.loads((OUT/'rounding-audit-with-mp.json').read_text())['rows']
    bykey={(r['id'],r['mode']):r for r in data};rows=[]
    for r in data:
        native=bykey[r['id'],'native'];pairs=[]
        for p,q in zip(native['probes'],r['probes']):
            pairs += [(a,b) for a,b in zip(p['vector'],q['vector']) if a is not None and b is not None]
        rows.append({'id':r['id'],'mode':r['mode'],'probes':4,'calls':r['calls'],
                     'vector_components':len(pairs),'changed_components':sum(a!=b for a,b in pairs),
                     'max_scaled_component_delta':max([abs(a-b)/max(1,abs(a)) for a,b in pairs] or [0]),
                     'changed_norms':sum(p['norm']!=q['norm'] for p,q in zip(native['probes'],r['probes']))})
    csvwrite('rounding-audit.csv',rows)
    re=[];inputs={r['id']:r for r in json.loads((OUT/'inputs.json').read_text())}
    for cid,seed,mode in json.loads((OUT/'recheck-jobs.json').read_text()):
        p=OUT/f'full-recheck/{cid}-{seed}-{mode}.json'
        if not dataio.exists(p):continue
        old=OUT/f'full/{cid}-{seed}-{mode}.json'
        a=dataio.read(old);b=dataio.read(p)
        aa=full_roots(old,inputs[cid]);bb=full_roots(p,inputs[cid])
        re.append({'id':cid,'seed':seed,'mode':mode,
                   'answer_same_as_original':canonical_answers(a)==canonical_answers(b),
                   'classes_same_as_original':aa[0]==bb[0],
                   'source_digest_same_as_original':aa[-1]==bb[-1]})
    save('recheck-summary.json',re)
    print('audit rows',len(rows),'rechecks',re)


if __name__=='__main__':
    check_lock()
    {'dense':dense,'full-mp':full_mp,'audit':audit}[sys.argv[1]]()
