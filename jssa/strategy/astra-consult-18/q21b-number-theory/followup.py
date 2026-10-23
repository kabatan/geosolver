"""Post-observation diagnostics, as fixed in followup-protocol.md."""
from collections import Counter, defaultdict
import json
import math
import time

import numpy as np
from mpmath import mp
import sympy as sp

from analyze import OUT, ROOT, X, GRID, limit, BudgetExpired, primitive, reconstruct, csave, jsave, loadcsv, digest
from geosolver.exact.polynomial_search_helpers import scale_candidates_for_value
from geosolver.engine.standard.exact_assembly.verify_identified_answer import verify_identified_answer


def scaled_height(v):
    with mp.workdps(180):
        result=[]
        for s in scale_candidates_for_value(mp.mpf(v['value_180'])):
            k=int(mp.nint(mp.log10(s)))
            coeff=primitive(sum(sp.Integer(a)*(X*(sp.Rational(10)**k))**(v['degree']-i) for i,a in enumerate(v['coefficients'])))
            result.append({'exponent':k,'height':max(map(abs,coeff))})
    return result


def bound_experiment(values):
    rows=[]
    for v in values:
        if v.get('degree',0)<3:
            continue
        height=min(h['height'] for h in scaled_height(v))
        for p in [20,40,60,80,100]:
            for b in [1000,10000,1000000,100000000]:
                r={'id':v['id'],'answer_index':v['answer_index'],'degree':v['degree'],'height':v['height'],
                   'min_scaled_height':height,'eligible':height<b,'precision':p,'coefficient_bound':b,
                   **reconstruct(v['value_180'],p,v['coefficients'],max_coeff=b)}
                rows.append(r)
        print('bound',v['id'],dict(Counter(r['status'] for r in rows if r['id']==v['id'])),flush=True)
    csave('bound-experiment.csv',rows)
    jsave('bound-experiment.json',rows)
    contrasts=[]
    groups=defaultdict(list)
    for r in rows:
        groups[r['id'],r['precision']].append(r)
    for group in groups.values():
        for a in group:
            for b in group:
                if a['eligible'] and b['eligible'] and a['coefficient_bound']<b['coefficient_bound'] and a['status']=='correct' and b['status']=='wrong':
                    contrasts.append({'id':a['id'],'precision':a['precision'],'low_B':a['coefficient_bound'],
                                      'high_B':b['coefficient_bound'],'wrong_polynomial':b['got']})
    csave('bound-reversals.csv',contrasts)


def direct_oracle(values):
    rows=[]
    for v in values:
        if 'coefficients' not in v:
            continue
        p=max(15,math.ceil(v['heuristic_digits'])+10)
        start=time.monotonic()
        got=None
        try:
            with limit(2),mp.workdps(p+40):
                a=mp.mpf(mp.nstr(mp.mpf(v['value_180']),p))
                reverse=abs(a)>1
                if a==0:
                    got=[1,0];status='zero_special'
                else:
                    z=1/a if reverse else a
                    rel=mp.pslq([z**i for i in range(v['degree']+1)],tol=mp.power(10,-p+5),
                                maxcoeff=v['height']+1,maxsteps=20000)
                    if rel:
                        poly=list(reversed(rel))
                        if reverse:poly=list(reversed(poly))
                        got=primitive(sum(sp.Integer(c)*X**(len(poly)-i-1) for i,c in enumerate(poly)))
                    status='correct' if got==v['coefficients'] else ('none' if got is None else 'wrong')
        except BudgetExpired:
            status='timeout'
        except Exception as e:
            status='error:'+repr(e)
        rows.append({'id':v['id'],'answer_index':v['answer_index'],'degree':v['degree'],'height':v['height'],
                     'precision':p,'status':status,'got':got,'seconds':time.monotonic()-start})
    csave('oracle-diagnostic.csv',rows)
    jsave('oracle-summary.json',{'counts':dict(Counter(r['status'] for r in rows)),
                               'max_precision':max(r['precision'] for r in rows),
                               'failures':[r for r in rows if r['status'] not in ['correct','zero_special']]})
    print('oracle',dict(Counter(r['status'] for r in rows)),flush=True)


def final_verifier(values):
    index={(v['id'],v['answer_index']):v for v in values}
    primary=[json.loads(l) for l in (OUT/'precision.jsonl').read_text().splitlines()]
    work=[]
    for r in primary:
        if r['precision']==80 and r['status']=='wrong':
            work.append({**r,'kind':'primary','value':index[r['id'],r['answer_index']]['value_180']})
    for r in json.loads((OUT/'recoding-replay.json').read_text()):
        if r['origin']=='oracle' and r['status']=='wrong':
            with mp.workdps(180):
                v=mp.mpf(index[r['id'],r['answer_index']]['value_180'])+mp.mpf(1)/r['q']
                work.append({**r,'kind':'recoded','value':mp.nstr(v,180)})
    rows=[]
    for r in work:
        try:
            with limit(2),mp.workdps(max(80,r['precision']+40)):
                a=mp.mpf(mp.nstr(mp.mpf(r['value']),r['precision']))
                accepted,residual=verify_identified_answer(coefficients=r['got'],numeric_value=a,precision_dps=r['precision'])
            result={'accepted':bool(accepted),'polynomial_residual':str(residual)}
        except BudgetExpired:
            result={'accepted':None,'error':'timeout'}
        rows.append({'id':r['id'],'kind':r['kind'],'precision':r['precision'],'q':r.get('q',1),'got':r['got'],**result})
    csave('final-verifier.csv',rows)
    print('final verifier',Counter(str(r['accepted']) for r in rows),flush=True)


def summarize(values):
    rows=[json.loads(l) for l in (OUT/'precision.jsonl').read_text().splitlines()]
    byval=defaultdict(dict)
    for r in rows:byval[r['id'],r['answer_index']][r['precision']]=r
    vrows=[]
    for v in values:
        if 'coefficients' not in v:continue
        hist=byval[v['id'],v['answer_index']]
        success=[p for p in GRID if hist[p]['status']=='correct']
        stable=[p for p in GRID if all(hist[q]['status']=='correct' for q in GRID if q>=p)]
        reversed_success=[(a,b) for a,b in zip(GRID,GRID[1:]) if hist[a]['status']=='correct' and hist[b]['status']!='correct']
        vrows.append({**v,'first_correct_grid':min(success) if success else '',
                      'stable_correct_grid':min(stable) if stable else '',
                      'nonmonotone':bool(reversed_success),'reversals':reversed_success,
                      'min_scaled_height':min(r['height'] for r in scaled_height(v))})
    csave('precision-per-value.csv',vrows)
    probs=loadcsv(OUT/'answer-census.csv'); prrows=[]
    saved_by_id=defaultdict(list)
    for c in loadcsv(OUT/'saved-candidates.csv'):
        saved_by_id[c['id']].append(c)
    for r in probs:
        vs=[v for v in vrows if v['id']==r['id']]
        if r['has_pi']=='False':
            stored=saved_by_id[r['id']]
            r['saved_hp_count']=len(stored)
            r['saved_80digit_count']=sum(float(c.get('relative_digits') or '-inf')>=80 for c in stored)
            r['saved_has_80digits']=r['saved_80digit_count']>0
            good=[p for p in GRID if all(byval[v['id'],v['answer_index']][p]['status']=='correct' for v in vs)]
            stable=[p for p in GRID if all(q in good for q in GRID if q>=p)]
            r['first_correct_grid']=min(good) if good else ''
            r['stable_correct_grid']=min(stable) if stable else ''
        else:
            r['first_correct_grid']='';r['stable_correct_grid']=''
            r['saved_hp_count']='';r['saved_80digit_count']='';r['saved_has_80digits']=''
        prrows.append(r)
    csave('problem-summary.csv',prrows)
    tables=[]
    algebraic=[r for r in probs if r['has_pi']=='False']
    for p in GRID:
        sub=[r for r in rows if r['precision']==p]
        n_problem=sum(all(byval[v['id'],v['answer_index']][p]['status']=='correct' for v in vrows if v['id']==r['id']) for r in algebraic)
        tables.append({'precision':p,'correct_values':sum(r['status']=='correct' for r in sub),
                       'wrong_values':sum(r['status']=='wrong' for r in sub),'none_values':sum(r['status']=='none' for r in sub),
                       'correct_problems':n_problem,'problems':len(algebraic)})
    csave('precision-summary.csv',tables)
    rng=np.random.default_rng(21023)
    human=[];human_contrasts=[]
    for contest in sorted({r['contest'] for r in prrows if r['human']}):
        cs=[r for r in prrows if r['human'] and r['contest']==contest]
        median=float(np.median([float(r['human']) for r in cs]))
        for group in ['lower','higher']:
            chosen=[r for r in cs if (float(r['human'])>=median)==(group=='higher')]
            alg=[r for r in chosen if r['has_pi']=='False']
            def med(key):return float(np.median([float(r[key]) for r in alg if r[key]!='']))
            human.append({'contest':contest,'group':group,'human_threshold':median,'n':len(chosen),'n_algebraic':len(alg),
                          'rational':sum(r['degree']=='1' for r in alg),'quadratic':sum(r['degree']=='2' for r in alg),
                          'cubic_quartic':sum(r['degree'] in ['3','4'] for r in alg),'pi':len(chosen)-len(alg),
                          'human_median':float(np.median([float(r['human']) for r in chosen])),
                          'E_median':med('heuristic_digits'),'H_median':med('height'),
                          'precision_median':med('stable_correct_grid'),'radical_depth_median':med('radical_depth')})
        for key in ['heuristic_digits','stable_correct_grid']:
            a=np.array([float(r[key]) for r in cs if r['has_pi']=='False' and r[key]!='' and float(r['human'])<median])
            b=np.array([float(r[key]) for r in cs if r['has_pi']=='False' and r[key]!='' and float(r['human'])>=median])
            diffs=np.median(rng.choice(b,(2000,len(b))),axis=1)-np.median(rng.choice(a,(2000,len(a))),axis=1)
            human_contrasts.append({'contest':contest,'quantity':key,'lower_n':len(a),'higher_n':len(b),
                    'higher_minus_lower_median':float(np.median(b)-np.median(a)),
                    'bootstrap_ci025':float(np.quantile(diffs,.025)),'bootstrap_ci975':float(np.quantile(diffs,.975))})
    csave('human-strata.csv',human);csave('human-contrasts.csv',human_contrasts)
    summary={'total_problems':len(probs),'algebraic_problems':len(algebraic),'algebraic_values':len(vrows),
             'P1_problems_with_success_by80':sum(r['first_correct_grid']!='' and int(r['first_correct_grid'])<=80 for r in prrows),
             'stable_grid_distribution_problems':dict(Counter(r['stable_correct_grid'] for r in prrows if r['has_pi']=='False')),
             'nonmonotone_values':[{'id':v['id'],'reversals':v['reversals']} for v in vrows if v['nonmonotone']],
             'max_kll_absolute_digits':max(v['kll_absolute_digits'] for v in vrows),
             'E_quantiles':np.quantile([v['heuristic_digits'] for v in vrows],[0,.5,.9,.95,1]).tolist(),
             'K_quantiles':np.quantile([v['kll_absolute_digits'] for v in vrows],[0,.5,.9,.95,1]).tolist(),
             'human_total':sum(bool(r['human']) for r in prrows),'human_tables':human,'human_contrasts':human_contrasts,
             'max_input_precision_needed_on_grid':max(v['stable_correct_grid'] for v in vrows if v['stable_correct_grid']!=''),
             'protocol_hash':digest(OUT/'protocol.md'),'followup_protocol_hash':digest(OUT/'followup-protocol.md')}
    jsave('summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    start=time.monotonic()
    vals=json.loads((OUT/'values.json').read_text())
    bound_experiment(vals)
    direct_oracle(vals)
    final_verifier(vals)
    summarize(vals)
    jsave('followup-timing.json',{'seconds':time.monotonic()-start})
