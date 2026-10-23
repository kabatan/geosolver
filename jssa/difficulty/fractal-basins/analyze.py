"""Analyze Q34 saved records without running the solver."""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import dataio

from experiment import OUT, IDS, EPS, MODES, check_lock, clean, label, save, sha, utc
import numpy as np


def csvwrite(name, rows):
    if not rows:
        return
    with (OUT / name).open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def wilson(k, n, z=1.959963984540054):
    p = k/n
    mid = (p + z*z/(2*n)) / (1+z*z/n)
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)) / (1+z*z/n)
    return max(0, mid-half), min(1, mid+half)


def fit(eps, f):
    eps, f = np.asarray(eps), np.asarray(f)
    ok = (f > 0) & (f < 1)
    if ok.sum() < 3:
        return None
    x, y = np.log10(eps[ok]), np.log10(f[ok])
    a, b = np.polyfit(x, y, 1)
    den = float(np.sum((y-y.mean())**2))
    r2 = 1 - np.sum((y-a*x-b)**2)/den if den > 1e-28 else 0.0
    return {'alpha': float(a), 'intercept': float(b), 'r2': float(r2),
            'scales': eps[ok].tolist(), 'n_scales': int(ok.sum())}


def bootstrap(events, eps, rows, mask, seed=340400):
    fitted = fit(np.asarray(eps)[mask], events[:, mask].mean(axis=0))
    if fitted is None:
        return None
    groups = [[i for i,r in enumerate(rows) if (r['rep'],r['patch']) == (a,b)]
              for a in range(2) for b in range(2)]
    rng = np.random.default_rng(seed)
    alphas = []
    for _ in range(400):
        ii = np.concatenate([rng.choice(g, len(g), replace=True) for g in groups if g])
        f = fit(np.asarray(eps)[mask], events[ii][:,mask].mean(axis=0))
        if f is not None:
            alphas.append(f['alpha'])
    fitted['ci95'] = np.quantile(alphas, [.025, .975]).tolist() if alphas else None
    fitted['bootstrap_valid'] = len(alphas)
    fitted['replicate_alpha'] = []
    for rep in range(2):
        g = [i for i,r in enumerate(rows) if r['rep']==rep]
        ff = fit(np.asarray(eps)[mask], events[g][:,mask].mean(axis=0)) if g else None
        fitted['replicate_alpha'].append(None if ff is None else ff['alpha'])
    return fitted


def robust_fit(events, ulp, eps, rows):
    n = len(rows)
    rates = events.mean(axis=0)
    low = np.asarray(eps) <= 1e-12
    floor_count = max(int(events[:,low].sum(axis=0).max()), int(ulp.sum()))
    floor_upper = wilson(floor_count,n)[1]
    eligible = ((np.asarray(eps)>=1e-10) & (rates > 3*floor_upper) &
                (events.sum(axis=0)>=5) & (rates<=.8))
    runs = []
    for start in range(len(eps)):
        if eligible[start] and (start==0 or not eligible[start-1]):
            end = start
            while end < len(eps) and eligible[end]:
                end += 1
            if end-start >= 4:
                runs.append((start,end))
    info = {'floor_count': floor_count, 'floor_rate': floor_count/n,
            'floor_upper95': floor_upper, 'eligible_scales': np.asarray(eps)[eligible].tolist(),
            'fit': None, 'pass': False, 'reasons': []}
    if not runs:
        info['reasons'].append('fewer_than_4_consecutive_scales_above_noise_floor')
        return info
    start,end = sorted(runs,key=lambda p:(-(p[1]-p[0]),p[0]))[0]
    mask = np.zeros(len(eps),bool); mask[start:end] = True
    f = bootstrap(events,eps,rows,mask)
    info['fit'] = f
    if f is None:
        info['reasons'].append('not_identifiable'); return info
    ci = f['ci95']
    if ci is None or not (0 < ci[0] <= ci[1] < 1):
        info['reasons'].append('CI_not_inside_0_1')
    if f['r2'] < .95:
        info['reasons'].append('R2_below_095')
    aa = f['replicate_alpha']
    if any(v is None for v in aa) or abs(aa[0]-aa[1]) > .2:
        info['reasons'].append('seed_slopes_not_stable')
    info['pass'] = not info['reasons']
    return info


def loadrows(cid):
    rows = []
    for p in sorted((OUT/'measure').glob(cid+'-*.json')):
        rows.extend(json.loads(p.read_text())['rows'])
    return sorted(rows,key=lambda r:r['i'])


def event(a,b,kind):
    both = a.startswith('R') and b.startswith('R')
    return (a != b) if kind=='outcome' else (both and a != b)


def analyze_local():
    inputs = json.loads((OUT/'inputs.json').read_text())
    summary, curves, flat, tol_rows = [], [], [], []
    for inp in inputs:
        cid = inp['id']; rows = loadrows(cid)
        if len(rows) != 256:
            print('incomplete',cid,len(rows)); continue
        n=len(rows); rawmask = (np.asarray(EPS)>=1e-12)&(np.asarray(EPS)<=1e-3)
        aa=np.array([[r['base']['label'] for _ in EPS] for r in rows])
        bb=np.array([[v['r']['label'] for v in r['variants']] for r in rows])
        root=np.char.startswith(aa,'R')&np.char.startswith(bb,'R')
        outcomes = aa != bb; roots = outcomes & root
        ua=np.array([r['base']['label'] for r in rows]); ub=np.array([r['ulp']['r']['label'] for r in rows])
        u=ua!=ub; ur=u&np.char.startswith(ua,'R')&np.char.startswith(ub,'R')
        stats = {'id':cid,'n':n,'alpha_raw':bootstrap(outcomes,EPS,rows,rawmask),
                 'alpha_root_raw':bootstrap(roots,EPS,rows,rawmask),
                 'outcome_scaling':robust_fit(outcomes,u,EPS,rows),
                 'root_scaling':robust_fit(roots,ur,EPS,rows),
                 'ulp_changes':int(u.sum()),'ulp_root_changes':int(ur.sum()),
                 'repeat_n':sum('repeat' in r for r in rows),
                 'repeat_changes':sum(r['base']['label']!=r['repeat']['label'] for r in rows if 'repeat' in r),
                 'base_labels':dict(Counter(ua)), 'root_coverage_min':float(root.mean(axis=0).min()),
                 'same_bits':sum(v['same_bits'] for r in rows for v in r['variants'])}
        verify_path=OUT/f'verify/{cid}.json'
        diff,total,nfev_cap=0,0,0
        if verify_path.exists():
            original={r['i']:r for r in rows}
            for r in json.loads(verify_path.read_text())['rows']:
                old=original[r['i']]
                diff+=label(r['base'],inp)!=label(old['base'],inp);total+=1
                for v in r['variants']:
                    v0=next(v0 for v0 in old['variants'] if v0['eps']==v['eps'])
                    diff+=label(v['r'],inp)!=label(v0['r'],inp);total+=1
        stats['cap320_label_changes']=diff; stats['cap320_labels']=total
        stats['cap320_change_rate']=diff/total if total else None
        reasons=list(stats['root_scaling']['reasons'])
        rootfit=stats['root_scaling']['fit']
        if rootfit:
            sel=[EPS.index(e) for e in rootfit['scales']]
            if min(root.mean(axis=0)[sel])<.9:
                reasons.append('root_pair_coverage_below_90pct')
            # Preregistered same-scale outcome criterion, evaluated on root-fit scales.
            mask=np.zeros(len(EPS),bool);mask[sel]=True
            f=bootstrap(outcomes,EPS,rows,mask)
            if f is None or f['ci95'] is None or not (0<f['ci95'][0]<=f['ci95'][1]<1) or f['r2']<.95:
                reasons.append('outcome_fit_fails_on_root_scales')
        if total!=160 or diff/total>.02:
            reasons.append('cap320_not_verified_or_not_stable')
        stats['fractal_consistent']=not reasons
        stats['fractal_reasons']=reasons
        for tol in (1e-6,1e-5,1e-4):
            a=np.array([label(r['base'],inp,tol) for r in rows])
            b=np.array([[label(v['r'],inp,tol) for v in r['variants']] for r in rows])
            tol_rows.append({'id':cid,'tolerance':tol,'different_from_primary':int((b!=bb).sum()+(a!=ua).sum()),
                             'ulp_changes':sum(label(r['base'],inp,tol)!=label(r['ulp']['r'],inp,tol) for r in rows)})
        recs=[r['base'] for r in rows]+[v['r'] for r in rows for v in r['variants']]+[r['ulp']['r'] for r in rows]+[r['repeat'] for r in rows if 'repeat' in r]
        stats['local_calls']=len(recs);stats['local_seconds']=sum(r['sec'] for r in recs)
        stats['all_labels']=dict(Counter(r['label'] for r in recs))
        stats['status0_count']=sum(r.get('status')==0 for r in recs)
        for j,e in enumerate(EPS):
            k=int(outcomes[:,j].sum()); kr=int(roots[:,j].sum());cov=int(root[:,j].sum())
            lo,hi=wilson(k,n)
            # Compare reference target values only when both endpoints are known roots.
            target_changes=0
            for i in range(n):
                if root[i,j]:
                    av=inp['roots'][int(aa[i,j][1:])]['answer'];bv=inp['roots'][int(bb[i,j][1:])]['answer']
                    target_changes+=abs(av-bv)>1e-6*max(1,abs(av),abs(bv))
            actual=[r['variants'][j]['actual_eps'] for r in rows]
            curves.append({'id':cid,'epsilon':e,'n':n,'changes':k,'f':k/n,'wilson_low':lo,'wilson_high':hi,
                           'root_changes':kr,'f_root':kr/n,'root_pair_count':cov,'root_pair_coverage':cov/n,
                           'conditional_root_f':kr/cov if cov else '', 'target_changes_between_roots':target_changes,
                           'f_rep0':float(outcomes[:128,j].mean()),'f_rep1':float(outcomes[128:,j].mean()),
                           'actual_epsilon_min':min(actual),'actual_epsilon_max':max(actual)})
        raw=stats['alpha_raw']; rr=stats['alpha_root_raw']
        flat.append({'id':cid,'n':n,'alpha_raw':raw['alpha'] if raw else '',
                     'alpha_raw_low':raw['ci95'][0] if raw and raw['ci95'] else '',
                     'alpha_raw_high':raw['ci95'][1] if raw and raw['ci95'] else '',
                     'R2_raw':raw['r2'] if raw else '',
                     'alpha_root_raw':rr['alpha'] if rr else '',
                     'alpha_root_raw_low':rr['ci95'][0] if rr and rr['ci95'] else '',
                     'alpha_root_raw_high':rr['ci95'][1] if rr and rr['ci95'] else '',
                     'R2_root_raw':rr['r2'] if rr else '',
                     'noise_floor':stats['outcome_scaling']['floor_rate'],
                     'ulp_changes':stats['ulp_changes'],'ulp_root_changes':stats['ulp_root_changes'],
                     'repeat_changes':stats['repeat_changes'],'cap320_change_rate':stats['cap320_change_rate'],
                     'root_coverage_min':stats['root_coverage_min'],
                     'fractal_consistent':stats['fractal_consistent'],'reason':';'.join(reasons)})
        summary.append(stats)
    save('local-summary.json',{'utc':utc(),'problems':summary,
        'P1_count':sum(s['fractal_consistent'] for s in summary),
        'P2_count':sum(s['alpha_raw'] is not None and s['alpha_raw']['alpha']<.25 for s in summary),
        'P4_count':sum(s['ulp_changes']>0 for s in summary)})
    csvwrite('per-problem.csv',flat);csvwrite('uncertainty.csv',curves);csvwrite('label-tolerance.csv',tol_rows)
    print(json.dumps(clean(flat),ensure_ascii=False,indent=2))


def canonical_answers(d):
    # Descriptor canonicalization uses the frozen exact-answer model, not decimals.
    from geosolver.runtime.protocol import WorkerArtifact
    payload={k:v for k,v in d.items() if k in WorkerArtifact.model_fields}
    a=WorkerArtifact.model_validate(payload)
    return sorted(str(v.canonical_key()) for v in a.answers)


def full_roots(path, inp):
    records=[]
    for p in dataio.paths(path.parent/'candidates',path.stem+'-[0-9][0-9].json'):
        records.extend(dataio.read(p))
    keys=set(); accepted=set(); finite=0
    for r in records:
        x=r.get('x_hp') or r.get('x_float')
        if x is None:
            continue
        try:
            xx=np.asarray([float(v) for v in x]);finite+=1
            distances=np.max(np.abs((xx-np.array([v['center'] for v in inp['roots']]))/
                np.diff(np.asarray(inp['box']),axis=1).ravel()),axis=1)
            nearest=int(np.argmin(distances));key=f'R{nearest}' if distances[nearest]<=1e-5 else 'other'
        except (ValueError,TypeError):
            key='unparsed'
        keys.add(key)
        if r.get('accepted'):
            accepted.add(key)
    source_rows=sorted((r.get('candidate_uid',''),r.get('source',{}).get('x_float',[]))
                       for r in records if r.get('source'))
    fingerprint=hashlib.sha256(json.dumps(source_rows,sort_keys=True).encode()).hexdigest()
    return sorted(keys),sorted(accepted),len(records),finite,fingerprint


def analyze_full():
    inputs={i['id']:i for i in json.loads((OUT/'inputs.json').read_text())}
    flat=[]; bykey={}; comparisons=[]; recheck=[]
    for cid in IDS:
        for seed in (340301,340302):
            for mode in MODES:
                path=OUT/f'full/{cid}-{seed}-{mode}.json'
                if not dataio.exists(path):
                    continue
                d=dataio.read(path); keys,accepted,n,nparsed,digest=full_roots(path,inputs[cid])
                ans=canonical_answers(d)
                row={'id':cid,'seed':seed,'mode':mode,'status':d['status'],
                     'termination':d.get('termination_reason'),'answers':'|'.join(ans),
                     'candidate_roots':'|'.join(k for k in keys if k.startswith('R')),
                     'candidate_classes':'|'.join(keys),'accepted_roots':'|'.join(accepted),
                     'source_coordinate_sha256':digest,
                     'candidate_count':n,'candidate_coordinates_parsed':nparsed,
                     'seconds':d['elapsed_seconds'],'intervention_calls':d['intervention_calls'],
                     'float_calls':d.get('counters',{}).get('evaluate_float_residual',0),
                     'error':str(d.get('error') or '')}
                flat.append(row);bykey[cid,seed,mode]=row
    for cid in IDS:
        for seed in (340301,340302):
            if not all((cid,seed,mode) in bykey for mode in MODES):
                continue
            native=bykey[cid,seed,'native']; repeat=bykey[cid,seed,'native-repeat']
            aa=[];rr=[];acc=[];trace=[];counts=[];classes=[]
            for mode in MODES[2:]:
                r=bykey[cid,seed,mode]
                if r['answers']!=native['answers']:
                    aa.append(mode)
                if r['candidate_roots']!=native['candidate_roots']:
                    rr.append(mode)
                if r['accepted_roots']!=native['accepted_roots']:
                    acc.append(mode)
                if r['source_coordinate_sha256']!=native['source_coordinate_sha256']:
                    trace.append(mode)
                if r['float_calls']!=native['float_calls']:
                    counts.append(mode)
                if r['candidate_classes']!=native['candidate_classes']:
                    classes.append(mode)
            c={'id':cid,'seed':seed,'answer_change_modes':'|'.join(aa),'root_change_modes':'|'.join(rr),
               'accepted_root_change_modes':'|'.join(acc),
               'source_coordinate_change_modes':'|'.join(trace),
               'float_count_change_modes':'|'.join(counts),
               'candidate_class_change_modes':'|'.join(classes),
               'native_repeat_answer_change':native['answers']!=repeat['answers'],
               'native_repeat_root_change':native['candidate_roots']!=repeat['candidate_roots'],
               'native_repeat_source_coordinate_change':native['source_coordinate_sha256']!=repeat['source_coordinate_sha256'],
               'native_repeat_float_count_change':native['float_calls']!=repeat['float_calls'],
               'all_completed':all(bykey[cid,seed,m]['status']=='completed' for m in MODES)}
            comparisons.append(c)
            for mode in sorted(set(aa+rr)):
                if len(recheck)<12:
                    recheck.append((cid,seed,mode))
    recheckjobs=sorted({(cid,seed,m) for cid,seed,mode in recheck for m in ('native',mode)})
    if not (OUT/'recheck-jobs.json').exists() and len(comparisons)==24:
        save('recheck-jobs.json',recheckjobs)
    csvwrite('full-runs.csv',flat);csvwrite('full-comparisons.csv',comparisons)
    summary={'utc':utc(),'n_runs':len(flat),'n_pairs':len(comparisons),
             'answer_change_pairs':sum(bool(c['answer_change_modes']) for c in comparisons),
             'root_change_pairs':sum(bool(c['root_change_modes']) for c in comparisons),
             'accepted_root_change_pairs':sum(bool(c['accepted_root_change_modes']) for c in comparisons),
             'source_coordinate_change_pairs':sum(bool(c['source_coordinate_change_modes']) for c in comparisons),
             'float_count_change_pairs':sum(bool(c['float_count_change_modes']) for c in comparisons),
             'native_repeat_answer_change_pairs':sum(c['native_repeat_answer_change'] for c in comparisons),
             'native_repeat_root_change_pairs':sum(c['native_repeat_root_change'] for c in comparisons),
             'native_repeat_source_coordinate_change_pairs':sum(c['native_repeat_source_coordinate_change'] for c in comparisons),
             'native_repeat_float_count_change_pairs':sum(c['native_repeat_float_count_change'] for c in comparisons),
             'errors':sum(r['status']!='completed' for r in flat),
             'total_seconds':sum(r['seconds'] for r in flat),'comparisons':comparisons}
    save('full-summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


def controls():
    rng=np.random.default_rng(340500)
    x=rng.uniform(.01,.99,400000)
    def cantor(y):
        z=y.copy();labels=np.full(z.shape,-1,dtype=np.int16)
        for i in range(40):
            middle=(z>=1/3)&(z<2/3)&(labels<0)
            labels[middle]=i%2
            z=np.remainder(z*3,1)
        return labels
    cs=cantor(x); s=x>=.5
    rows=[]
    for e in EPS:
        rows.append({'epsilon':e,'smooth':float(np.mean(s!=((x+e)>=.5))),
                     'cantor':float(np.mean(cs!=cantor(x+e)))})
    chosen=[r for r in rows if 1e-5<=r['epsilon']<=1e-2]
    sf=fit([r['epsilon'] for r in chosen],[r['smooth'] for r in chosen])
    cf=fit([r['epsilon'] for r in chosen],[r['cantor'] for r in chosen])
    expected=1-math.log(2)/math.log(3)
    save('controls.json',{'utc':utc(),'n':len(x),'rows':rows,'smooth_fit':sf,'cantor_fit':cf,
                          'expected_smooth_alpha':1.0,'expected_cantor_alpha':expected,
                          'pass':abs(sf['alpha']-1)<.12 and abs(cf['alpha']-expected)<.10})
    print('controls',sf,cf,expected)


if __name__=='__main__':
    check_lock()
    mode=sys.argv[1] if len(sys.argv)>1 else 'local'
    if mode=='local':analyze_local()
    elif mode=='full':analyze_full()
    elif mode=='controls':controls()
