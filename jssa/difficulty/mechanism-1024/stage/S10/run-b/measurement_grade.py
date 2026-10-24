"""S6 independent exact-set grading adapted to 12 S8 configurations, partial machines."""
import csv
import json
import statistics as st
from collections import Counter
from pathlib import Path
from measurement_common import HERE, load, save, sha, utc, progress
from measurement_exact import answer_key, serial


def grade_one(job,r,refs,source):
    interrupted=r['state'].startswith('interrupted') or r['state']=='not_started'
    ref=refs['cases'][job['case_id']];result=None;keys=None;error=None
    p=Path(r.get('result_path','/nonexistent'))
    if p.is_file() and not interrupted:
        assert r.get('files',{}).get('result.json',{}).get('sha256')==sha(p),'result changed'
        try:
            result=load(p);keys=serial(answer_key(a) for a in result['answers'])
        except Exception as e:error=f'{type(e).__name__}: {e}'
    if interrupted:ok=None;cost=None;reason=r['state']
    elif not ref['available']:ok=None;cost=None;reason='reference_missing'
    else:
        reason=None
        if r['state']!='completed':reason=r['state']
        elif r.get('resource_violations'):reason='resource_contract_violation'
        elif r.get('exit_code')!=0:reason='nonzero_exit'
        elif error:reason='invalid_answer_descriptor'
        elif result is None:reason='missing_result'
        elif result.get('engine',{}).get('source_hash')!=source:reason='result_source_hash_mismatch'
        elif result.get('status')!='solved':reason='solver_'+str(result.get('status'))
        elif keys!=ref['canonical_set']:reason='answer_set_mismatch'
        ok=reason is None;cost=r.get('total_wall_through_cleanup_seconds',r.get('wall_seconds')) if ok else 180.0
        reason=reason or 'exact_whole_set_match'
    return dict(**job,state=r['state'],ok=ok,C_seed=cost,reason=reason,wall_seconds=r.get('wall_seconds'),
                actual_tree_wall_seconds=r.get('total_wall_through_cleanup_seconds'),answer_set=keys,
                descriptor_error=error,reference_set_sha256=ref['set_sha256'],resource_violations=r.get('resource_violations',[]))


def csv_write(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})


def problem_summary(case,group,config,rs):
    assert len(rs)==3
    complete=all(r['ok'] is not None for r in rs)
    return dict(case_id=case,main_cause=group,configuration=config,gradable_complete=complete,
        correct_seeds=sum(r['ok'] is True for r in rs),solved=sum(r['ok'] is True for r in rs)>=2 if complete else None,
        C=st.mean(r['C_seed'] for r in rs) if complete else None,
        incomplete_seeds=[r['seed'] for r in rs if r['ok'] is None])


def aggregate(out,freeze):
    import fcntl
    lock=(out/'campaign.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    refs=load(HERE/'references.json');runs=[]
    for j in freeze['jobs']:
        p=out/'receipts'/f"{j['queue_index']:04d}.end.json"
        r=load(p) if p.exists() else dict(state='not_started')
        assert all(r.get(k,v)==v for k,v in j.items()),'receipt specification mismatch'
        for f in r.get('files',{}).values():assert sha(f['path'])==f['sha256'],'raw changed'
        runs.append(grade_one(j,r,refs,freeze['source_hash']))
    problems=[]
    for row in load(HERE/'assignment.json')['problems']:
        for c in freeze['configs']:
            rs=[r for r in runs if r['case_id']==row['case_id'] and r['configuration']==c]
            problems.append(problem_summary(row['case_id'],row['main_cause'],c,rs))
    groups={}
    for g in ['a','b','c','e','no_failure']:
        groups[g]={}
        for c in freeze['configs']:
            ps=[r for r in problems if r['main_cause']==g and r['configuration']==c]
            observed=[r for r in ps if r['solved'] is not None]
            groups[g][c]=dict(n=len(ps),observed_n=len(observed),incomplete_n=len(ps)-len(observed),
                solved=sum(r['solved'] for r in observed),mean_C=st.mean(r['C'] for r in ps) if len(observed)==len(ps) else None)
    effects={g:{c:(groups[g][c]['mean_C']-groups[g]['B0']['mean_C']) if groups[g][c]['mean_C'] is not None and groups[g]['B0']['mean_C'] is not None else None
        for c in freeze['configs'] if c!='B0'} for g in groups}
    def greater(c,a,b):
        x,y=effects[a].get(c),effects[b].get(c)
        return x>y if x is not None and y is not None else None
    def both(x,y):return x and y if x is not None and y is not None else None
    predictions=dict(K1_a_gt_e=greater('B046','a','e'),K1_c_gt_e=greater('B046','c','e'),
        K2_b_gt_a=greater('B056','b','a'),K2_b_gt_e=greater('B056','b','e'),
        K3_b046_a_gt_b_and_b056_b_gt_a=both(greater('B046','a','b'),greater('B056','b','a')),
        K4='exploratory BMADS effects only; no directional prediction')
    report=dict(created_utc=utc(),groups=groups,effects_C_minus_B0=effects,predictions=predictions,
        states=dict(Counter(r['state'] for r in runs)),reasons=dict(Counter(r['reason'] for r in runs)),
        references_sha256=freeze['references_sha256'],source_hash=freeze['source_hash'],
        policy='solved >=2/3 exact whole-set matches; C = mean of three seed costs; correct actual wall through cleanup, otherwise 180; interrupted/ungradable null. Negative effects retained.')
    save(out/'summary.json',report);csv_write(out/'per-run.csv',runs);csv_write(out/'per-problem.csv',problems)
    lines=['# S10 部分B','',report['policy'],'','| 群 | 構成 | n | 採点完備 | 解けた | 平均C | B0との差 |','|---|---|---:|---:|---:|---:|---:|']
    for g,cs in groups.items():
        for c,s in cs.items():lines.append(f"| {g} | {c} | {s['n']} | {s['observed_n']} | {s['solved']} | {s['mean_C']} | {effects[g].get(c,0)} |")
    lines+=['','予測判定（nullは判定不能）：',json.dumps(predictions,ensure_ascii=False,indent=2)]
    (out/'answer.md').write_text('\n'.join(lines)+'\n')
    progress(out,f'S10B 採点終了 {len(runs)}枠; summary.json/answer.md')
    print(json.dumps(report,ensure_ascii=False))
