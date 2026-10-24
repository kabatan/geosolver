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


def aggregate(out,freeze):
    # Exclusive flock prevents concurrent grading and measurement in this output.
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
    for case in dict.fromkeys(j['case_id'] for j in freeze['jobs']):
        for c in freeze['configs']:
            rs=[r for r in runs if r['case_id']==case and r['configuration']==c];assert len(rs)==3
            complete=all(r['ok'] is not None for r in rs)
            times=[r['C_seed'] for r in rs if r['ok'] is True]
            problems.append(dict(case_id=case,configuration=c,gradable_complete=complete,
                correct_seeds=sum(r['ok'] is True for r in rs),solved=sum(r['ok'] is True for r in rs)>=2 if complete else None,
                C=st.mean(r['C_seed'] for r in rs) if complete else None,
                median_correct_wall=st.median(times) if times else None,
                incomplete_seeds=[r['seed'] for r in rs if r['ok'] is None]))
    summary={}
    for c in freeze['configs']:
        ps=[p for p in problems if p['configuration']==c];observed=[p for p in ps if p['solved'] is not None]
        n=len(ps);solved=sum(p['solved'] for p in observed);missing=n-len(observed)
        summary[c]=dict(n=n,observed_n=len(observed),incomplete_n=missing,solved=solved,solved_bounds=[solved,solved+missing],
            mean_C=st.mean(p['C'] for p in ps) if not missing else None,
            observed_mean_C=st.mean(p['C'] for p in observed) if observed else None)
    get=lambda case,c:next(p for p in problems if p['case_id']==case and p['configuration']==c)
    chain=['N','C1','C2','C3','C4','C5','BASE'];deltas=[]
    for a,b in zip(chain,chain[1:]):
        if a in summary and b in summary:
            a0,b0=summary[a],summary[b];delta=None if a0['incomplete_n'] or b0['incomplete_n'] else b0['solved']-a0['solved']
            gained=[];lost=[]
            for case in dict.fromkeys(p['case_id'] for p in problems):
                pa,pb=get(case,a),get(case,b)
                if pa['solved'] is False and pb['solved'] is True:gained.append(case)
                if pa['solved'] is True and pb['solved'] is False:lost.append(case)
            ratio=b0['mean_C']/a0['mean_C'] if a0['mean_C'] and b0['mean_C'] is not None else None
            deltas.append(dict(before=a,after=b,solved_increment=delta,gained=gained,lost=lost,C_after_over_before=ratio))
    predictions={};times=[];nomad_gains=[];fast=[];paired=[]
    if all(c in summary for c in ['N','C1','BASE']):
        for case in dict.fromkeys(p['case_id'] for p in problems):
            n,c=get(case,'N'),get(case,'C1')
            if n['solved'] is False and c['solved'] is True:nomad_gains.append(case)
            if n['solved'] is True and c['solved'] is True:
                ratio=n['median_correct_wall']/c['median_correct_wall'];times.append(dict(case_id=case,N_over_C1=ratio))
                if ratio>=2:fast.append(case)
                for seed in (601,602,603):
                    nr=next(r for r in runs if r['case_id']==case and r['configuration']=='N' and r['seed']==seed)
                    cr=next(r for r in runs if r['case_id']==case and r['configuration']=='C1' and r['seed']==seed)
                    if nr['ok'] is True and cr['ok'] is True:paired.append(nr['C_seed']/cr['C_seed'])
        n,b=summary['N'],summary['BASE'];complete=not(n['incomplete_n'] or b['incomplete_n'])
        predictions['prereg15_B1']=dict(N_solved=n['solved'],BASE_solved=b['solved'],denominator=n['n'],
            N_fraction=n['solved']/n['n'] if complete else None,BASE_fraction=b['solved']/b['n'] if complete else None,
            subset_condition=(n['solved']/n['n']<=.6 and b['solved']/b['n']>=.9) if complete else None)
        ratio=n['mean_C']/b['mean_C'] if complete else None
        predictions['prereg15_B4']=dict(N_C_over_BASE_C=ratio,subset_condition=ratio>=3 if ratio is not None else None)
        all_complete=all(not summary[c]['incomplete_n'] for c in ['N','C1'])
        med=st.median(t['N_over_C1'] for t in times) if times else None
        predictions['prereg16_supplement_B4']=dict(both_solved_n=len(times),median_N_over_C1=med,
            subset_condition=med>=1.5 if med is not None and all_complete else None,per_problem_ratios=times,
            paired_correct_seed_ratios_n=len(paired),paired_correct_seed_median=st.median(paired) if paired else None)
        predictions['prereg16_supplement_B5']=dict(nomad_newly_solved=len(nomad_gains),both_solved_C1_at_least_2x_faster=len(fast),
            subset_condition=len(fast)>len(nomad_gains) if all_complete else None,nomad_gained_cases=nomad_gains,fast_cases=fast)
    if all(c in summary for c in ['C3','C4']):
        a,b=summary['C3'],summary['C4'];ratio=b['mean_C']/a['mean_C'] if a['mean_C'] and b['mean_C'] is not None else None
        predictions['prereg15_B5']=dict(cumulative_C4_over_C3=ratio,cumulative_cost_reduction=1-ratio if ratio is not None else None,
            cumulative_subset_condition=ratio<=.9 if ratio is not None else None,single_G4_status='not_measured; N+4 reserved for later instruction; full B5 pending')
    report=dict(created_utc=utc(),scope=f"{freeze['machine']} 53問のみ。WinPC分と合算前。106問の最終判定ではない。",summary=summary,
        cumulative_increments=deltas,predictions=predictions,states=dict(Counter(r['state'] for r in runs)),reasons=dict(Counter(r['reason'] for r in runs)),
        raw_root=freeze['raw_root'],reference_sha256=freeze['references_sha256'],
        interrupted_policy='not results; null ok/C and incomplete problem; no retry',
        time_ratio_policy='Per jointly solved problem, ratio of medians of actual tree wall of exact-correct seeds N/C1; median over problems. Paired-correct-seed median additionally reported, not substituted.')
    save(out/'summary.json',report);csv_write(out/'per-run.csv',runs);csv_write(out/'per-problem.csv',problems)
    f=lambda v:'未確定' if v is None else f'{v:.6f}'
    lines=['# 事前登録15・16補遺：スーパーPC分の中間集計','',report['scope'],'',
        '固定FIFOから指定構成のみ実行。seed 601–603、内外180秒、1コア、内部thread=1、最大8並列。失敗・タイムアウトC=180秒。中断は結果に数えず、再試行なし。採点不能はnull。',
        '', '| 構成 | 固定問題数 | 3seed完備の採点数 | 解けた問題数 | 未確定問題数 | C平均(秒) |','|---|---:|---:|---:|---:|---:|']
    for c in chain+[c for c in freeze['configs'] if c not in chain]:
        if c in summary:
            s=summary[c];lines.append(f"| {c} | {s['n']} | {s['observed_n']} | {s['solved']} | {s['incomplete_n']} | {f(s['mean_C'])} |")
    lines+=['','解けた=3seed中2回以上、事前固定の独立参照集合との完全一致。Cはseed費用の問題内平均、その問題平均。正解費用は起動直前から所有木回収までの実時間。終了検出時刻・cleanupを含む生値も個別receiptに保持。','',
        '| 累積段階 | 解けた数の純増 | 新規成功 / 失った成功 | C後/前 |','|---|---:|---:|---:|']
    for d in deltas:lines.append(f"| {d['before']} → {d['after']} | {d['solved_increment']} | {len(d['gained'])} / {len(d['lost'])} | {f(d['C_after_over_before'])} |")
    lines+=['','全106問の予測の最終支持判定はWinPCとの合算後。以下の条件成立/不成立はスーパーPC部分集合の中間値であり、外れた方向もそのまま記す。','']
    for k,v in predictions.items():lines.append(f'- **{k}**: `{json.dumps(v,ensure_ascii=False)}`')
    lines+=['','事前登録15 B5の単独G4（N+4）は未計測であり、B5全体は保留。B3も単独構成の後続指示待ち。B2の各累積増分は上表。',
        '', '事前登録16補遺の時間比は、両構成で解けた問題ごとに完全一致seedの実時間中央値を求め、N/C1の比の中央値を取る。seed対応が両方完全一致した比の中央値もsummary.jsonに併記する。',
        '',f"状態内訳: `{json.dumps(report['states'])}`。採点理由: `{json.dumps(report['reasons'])}`。",
        '',f"固定source: `{freeze['source_hash']}`。参照: `{freeze['references_sha256']}`。生ログはリポジトリ外 `{freeze['raw_root']}`、個別hashは終了receipt。3MB以上のファイルなしを検査。commit/pushなし。"]
    (out/'answer.md').write_text('\n'.join(lines)+'\n')
    progress(out,f"採点集計完了: {len(runs)}枠、states={report['states']}; 結果はanswer.md。")
    for p in out.rglob('*'):
        if p.is_file():assert p.stat().st_size<3_000_000,p
    save(out/'artifact-hashes.json',dict(created_utc=utc(),files_sha256={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name not in ['artifact-hashes.json','campaign.lock']}))
    print(json.dumps(dict(summary=summary,predictions=predictions),ensure_ascii=False))
