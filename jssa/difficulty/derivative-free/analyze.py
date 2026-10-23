"""Offline grading; this is the only experiment stage that reads references."""
import csv
import hashlib
import json
import math
import sys
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import beta
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parent))
from probe_basins import reference_values, answer_float
from experiment import ARMS,clean,dump
from campaign import verify

def write_csv(name,rows):
    if not rows: return
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    assert (OUT/name).stat().st_size<5_000_000

def score(candidate,ev,refs):
    if candidate is None: return {'hit':False,'coarse':False,'value':None,'res':None,'audit_ok':True,'reason':'no_feasible_candidate'}
    x=candidate['x']; r=ev.evaluate_float_residual(x); hard=ev.evaluate_float_hard_feasibility(x,include_margins=False); guard=ev.evaluate_guard(x)[0]
    res=float(r.residual_norm_float)
    feasible=bool(hard.hard_feasible and guard and candidate['inside'] and r.is_finite)
    audit=bool(feasible and math.isclose(res,candidate['res'],rel_tol=1e-9,abs_tol=1e-12))
    value=answer_float(ev,x) if feasible and res<=1e-4 else None
    match=value is not None and math.isfinite(value) and any(abs(value-ref)<=1e-6*max(1.,abs(ref)) for ref in refs)
    hit=bool(feasible and res<=1e-8 and match)
    reason='hit' if hit else 'stuck' if res>1e-8 else 'wrong_answer' if feasible else 'wrong_branch'
    return {'hit':hit,'coarse':bool(feasible and res<=1e-4),'value':value,'res':res,'audit_ok':audit,'reason':reason}

def main():
    verify()
    selection=json.loads((OUT/'selection.json').read_text()); rows=[]; missing=[]; raw_manifest={}
    for case in selection:
        cid=case['id']; inp=json.loads((OUT/'inputs'/f'{cid}.json').read_text())
        b=load_problem_bundle(GeometryProblem.model_validate(inp['dsl']).engine_document()); ev=build_ir_evaluator(b)
        refs=reference_values(json.loads((OUT/'grading'/f'{cid}.json').read_text())['answer'])
        cache={}
        def grade(c):
            key=json.dumps(c,sort_keys=True)
            if key not in cache: cache[key]=score(c,ev,refs)
            return cache[key]
        for start in inp['starts']:
            seed,k=start['seed'],start['k']; path=OUT/'runs'/cid/f'{seed}-{k}.json'
            saved=json.loads(path.read_text()) if path.exists() else {}
            if path.exists(): raw_manifest[str(path.relative_to(OUT))]=hashlib.sha256(path.read_bytes()).hexdigest()
            if saved:
                assert saved['x0']==start['x'] and saved['input_sha256']==case['input_sha256']
            arms={r['arm']:r for r in saved.get('arms',[])}
            for arm in ARMS:
                r=arms.get(arm,{})
                if not r: missing.append([cid,seed,k,arm])
                s=grade(r.get('best'))
                rows.append({'id':cid,'group':case['group'],'seed':seed,'k':k,'arm':arm,'hit':int(s['hit']),'coarse':int(s['coarse']),'res':s['res'],'value':s['value'],'reason':s['reason'] if r else 'missing','audit_ok':s['audit_ok'],'status':r.get('status','missing'),'evals':r.get('evals',0),'seconds':r.get('seconds',0),'cpu_seconds':r.get('cpu_seconds',0),'invalid':r.get('invalid',0),'infeasible':r.get('infeasible',0),'outside':r.get('outside',0),'hit200':int(grade(r.get('snapshots',{}).get('200'))['hit']),'hit800':int(grade(r.get('snapshots',{}).get('800'))['hit']),'raw':str(path.relative_to(OUT))})
    write_csv('per-start.csv',clean(rows))
    problems=[]
    for c in selection:
        for arm in ARMS:
            rs=[r for r in rows if r['id']==c['id'] and r['arm']==arm]; h=sum(r['hit'] for r in rs); n=len(rs)
            lo=0. if h==0 else float(beta.ppf(.025,h,n-h+1)); hi=1. if h==n else float(beta.ppf(.975,h+1,n-h))
            problems.append({'id':c['id'],'group':c['group'],'arm':arm,'hits':h,'n':n,'p':h/n,'ci95_low':lo,'ci95_high':hi,'coarse':sum(r['coarse'] for r in rs),'hits_seed32001':sum(r['hit'] for r in rs if r['seed']==32001),'hits_seed32002':sum(r['hit'] for r in rs if r['seed']==32002),'time_caps':sum(r['status']=='time_cap' for r in rs),'missing':sum(r['status']=='missing' for r in rs),'mean_evals':float(np.mean([r['evals'] for r in rs]))})
    write_csv('per-problem.csv',problems)
    lookup={(r['id'],r['arm']):r for r in problems}
    matrix=[]
    for c in selection:
        matrix.append({'id':c['id'],'group':c['group'],'d':c['n_vars'],'historical_method':c['historical_method'],**{a:lookup[(c['id'],a)]['p'] for a in ARMS}})
    write_csv('success-matrix.csv',matrix)
    summaries=[]
    for group in ['hard','control']:
        for seed in [0,32001,32002]:
            for arm in ARMS:
                rs=[r for r in rows if r['group']==group and r['arm']==arm and (seed==0 or seed==r['seed'])]
                summaries.append({'group':group,'seed':seed,'arm':arm,'hits':sum(r['hit'] for r in rs),'n':len(rs),'p':float(np.mean([r['hit'] for r in rs])),'coarse':sum(r['coarse'] for r in rs),'mean_evals':float(np.mean([r['evals'] for r in rs])),'time_caps':sum(r['status']=='time_cap' for r in rs),'cpu_seconds':sum(r['cpu_seconds'] for r in rs),'statuses':dict(Counter(r['status'] for r in rs))})
    dump(OUT/'group-summary.json',summaries)
    comparisons=[('N','L'),('Nfine','N'),('Ls','Lu'),('Ls','Lrestart'),('Nlp','L'),('N','Lnp'),('Lnp','L'),('Nu','Lu'),('Nrs','Lrs'),('Lu','L'),('Lrs','L'),('Lrs','Lu'),('Nu','N'),('Nrs','Nu')]
    paired=[]; rowmap={(r['id'],r['seed'],r['k'],r['arm']):r for r in rows}
    rng=np.random.default_rng(32932)
    for group in ['hard','control']:
        ids=[r['id'] for r in selection if r['group']==group]
        for a,b in comparisons:
            diffs=np.array([lookup[(cid,a)]['p']-lookup[(cid,b)]['p'] for cid in ids])
            bs=np.mean(rng.choice(diffs,(4000,len(ids)),replace=True),axis=1)
            rescue=loss=0
            for cid in ids:
                for seed in [32001,32002]:
                    for k in range(8):
                        aa=rowmap[(cid,seed,k,a)]['hit']; bb=rowmap[(cid,seed,k,b)]['hit']
                        rescue+=aa>bb; loss+=aa<bb
            paired.append({'group':group,'a':a,'b':b,'difference':float(np.mean(diffs)),'bootstrap95_low':float(np.quantile(bs,.025)),'bootstrap95_high':float(np.quantile(bs,.975)),'improved_problems':int(sum(diffs>0)),'worsened_problems':int(sum(diffs<0)),'rescued_starts':int(rescue),'lost_starts':int(loss)})
    write_csv('paired-effects.csv',paired)
    def p(a,seed=0): return next(r['p'] for r in summaries if r['group']=='hard' and r['seed']==seed and r['arm']==a)
    delta=p('N')-p('L'); gate=delta>=.1 and all(p('N',s)>p('L',s) for s in [32001,32002])
    h1=gate and p('Nfine')<=p('N')-.1 and p('Ls')>=p('Lu')+.1 and p('Ls')>=p('Lrestart')+.05 and sum(lookup[(cid,'Nfine')]['p']<lookup[(cid,'N')]['p'] for cid in [r['id'] for r in selection if r['group']=='hard'])>=4 and sum(lookup[(cid,'Ls')]['p']>lookup[(cid,'Lu')]['p'] for cid in [r['id'] for r in selection if r['group']=='hard'])>=4 and all(p('Nfine',s)<p('N',s) and p('Ls',s)>p('Lu',s) and p('Ls',s)>p('Lrestart',s) for s in [32001,32002])
    h2=gate and abs(p('Nlp')-p('L'))<=delta/2 and abs(p('N')-p('Lnp'))<=delta/2 and p('Lnp')>=p('L')+.05 and all(p('Lnp',s)>p('L',s) for s in [32001,32002])
    h3=gate and any(abs(p(na)-p(la))<=delta/2 and p(la)>=p('L')+.1 and all(p(la,s)>p('L',s) for s in [32001,32002]) for na,la in [('Nu','Lu'),('Nrs','Lrs')])
    summary={'complete':not missing,'missing':missing,'planned_trials':len(rows),'observed_trials':len(rows)-len(missing),'candidate_audit_failures':sum(not r['audit_ok'] for r in rows),'G0':gate,'H1':h1,'H2':h2,'H3':h3,'hard_baseline_difference':delta,'interpretation': 'registered criteria, not proof of absence; if G0 fails mechanism attribution is not identified','max_actual_evals':max(r['evals'] for r in rows),'total_search_evals':sum(r['evals'] for r in rows),'total_search_cpu_seconds':sum(r['cpu_seconds'] for r in rows),'total_search_wall_seconds_summed':sum(r['seconds'] for r in rows),'status_counts':dict(Counter(r['status'] for r in rows)),'single_case_zero16_upper95':1-.05**(1/16)}
    dump(OUT/'summary.json',summary); dump(OUT/'raw-manifest.json',raw_manifest)
    print(json.dumps(summary,ensure_ascii=False))
    print(json.dumps([r for r in summaries if r['seed']==0],ensure_ascii=False))

if __name__=='__main__': main()
