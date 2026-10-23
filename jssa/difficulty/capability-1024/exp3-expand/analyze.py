"""No solver execution. Audit the fixed plan, rescore saved evidence, report."""
import csv, datetime, io, json, statistics
from collections import Counter
from pathlib import Path
import experiment as e

OUT=e.OUT
def csv_write(path,rows):
    stream=io.StringIO(); writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader()
    for row in rows: writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    assert len(stream.getvalue().encode())<5_000_000
    path.write_text(stream.getvalue())
def median(values): return statistics.median(values) if values else None
def fmt(v,d=2): return '—' if v is None else f'{v:.{d}f}'

def main():
    plan=e.read(OUT/'plan.json'); manifest=e.read(OUT/'expanded-dsl/manifest.json'); e.gate()
    assert e.sha(OUT/'experiment.py')==plan['orchestrator_sha256']
    assert all(e.sha(OUT/p)==h for p,h in plan['snapshots_sha256'].items())
    assert (e.INPUT/'expand_k.py').read_bytes()==e.git('show','70443d65:jssa/difficulty/expand_k.py',cwd=e.WORK)
    for group in 'ab':
        lock=e.read(e.INPUT/f'{group}/prediction.lock.json')
        mapping=lock['artifact_sha256'] if group=='a' else lock['artifacts_sha256']
        for name in (['cases.jsonl','references.json','score.py'] if group=='a' else ['cases.jsonl','audit/static.json']):
            assert e.sha(e.INPUT/f'{group}/{name}')==mapping[name]
        if group=='b': assert e.sha(e.CLEAN/'benchmarks/research_runner.py')==lock['control_file_sha256']['benchmarks/research_runner.py']
    q30a=list(csv.DictReader((e.INPUT/'a/per-run.csv').open()))
    q30b=[json.loads(line) for line in (e.INPUT/'b/results.jsonl').read_text().splitlines()]
    q30={}
    for case in plan['cases']:
        cid=case['case_id']; source=q30a if case['group']=='a' else q30b
        rows=[r for r in source if r['case_id']==cid]; assert len(rows)==5
        q30[cid]={'correct':sum(str(r['matched']).lower()=='true' for r in rows),'missing':sum(str(r.get('record_missing',r.get('missing_record',False))).lower()=='true' for r in rows)}
    rows=[]; events=[]; loads=[]; rawfiles=[]; contract_failures=[]; batch_elapsed=[]
    for n,tasks in enumerate(plan['batches'],1):
        start=e.read(OUT/f'batches/{n:02d}-start.json'); end=e.read(OUT/f'batches/{n:02d}-complete.json')
        assert end['all_workers_joined']; loads.extend([start['load'],end['load']])
        assert start['tasks']==tasks
        batch_elapsed.append((datetime.datetime.fromisoformat(end['finished_at_utc'])-datetime.datetime.fromisoformat(start['started_at_utc'])).total_seconds())
        for task in tasks:
            cid,seed,arm=[task[k] for k in ['case_id','seed','arm']]
            root=OUT/'execution'/arm
            path=root/f'runs/{cid}/{seed}.json'; life=root/f'lifecycle/{cid}/{seed}.json'
            raw=e.read(path) if path.exists() else {}; receipt=e.read(life) if life.exists() else {}
            if receipt.get('started_at_utc'): events.append((receipt['started_at_utc'],1))
            if receipt.get('finished_at_utc'): events.append((receipt['finished_at_utc'],-1))
            if receipt.get('load_start'): loads.extend([receipt['load_start'],receipt['load_end']])
            if raw:
                assert e.sha(path)==receipt['record_sha256']
                a=e.scorer(raw,task['group']); assert a==raw['assessment']
                external=raw['external_raw']; assert e.sha(external['path'])==external['sha256']; rawfiles.append(external)
                assert external['score_preserved'] and external['all_answers_retained']
                dsl_path=e.INPUT/f'{task["group"]}/dsl/{cid}.json' if arm=='BASE' else OUT/f'expanded-dsl/{cid}.json'
                checks={'source_hash':raw['source_hash']==e.EXPECTED,'identity':raw['case_id']==cid and raw['seed']==seed,'problem_hash':raw['problem_hash']==e.rr._sha256_bytes(e.rr._canonical_json(e.read(dsl_path)).encode()),
                        'cpu':raw['process']['actual_affinity']==[task['cpu']], 'limit':raw['config']['time_limit_seconds']==180 and raw['config']['cores']==1,
                        'execution_contract':not raw['execution_contract_issues']}
                if not all(checks.values()): contract_failures.append({**task,'checks':checks})
            else: a={}
            missing=not raw or not raw.get('solver_result') or not raw.get('assessment')
            diag=(raw.get('solver_result') or {}).get('diagnostics') or {}
            rows.append({**task,'batch':n,'parallel_slots':len(tasks),'matched':bool(a.get('matched')) and not missing,'record_missing':missing,
                'status':a.get('status'),'failure_stage':a.get('failure_stage'),'normal_completion':a.get('normal_completion'),
                'wall_seconds':a.get('wall_seconds'),'process_wall_seconds':a.get('process_wall_seconds'),'cpu_seconds':a.get('cpu_seconds'),'peak_rss_bytes':a.get('peak_rss_bytes'),
                'n_answers':a.get('n_answers'),'actual_exact_keys':a.get('actual_exact_keys'),'numeric_feasible':diag.get('numeric_feasible'),'exact_identified':diag.get('exact_identified'),
                'termination_reason':a.get('termination_reason'),'started_at_utc':receipt.get('started_at_utc'),'finished_at_utc':receipt.get('finished_at_utc'),
                'load_start':receipt.get('load_start'),'load_end':receipt.get('load_end'),'execution_contract_issues':raw.get('execution_contract_issues'),
                'record_path':str(path.relative_to(OUT)),'record_sha256':e.sha(path) if path.exists() else None,'external_raw':raw.get('external_raw'),
                'runner_exception':receipt.get('runner_exception')})
    assert len(rows)==204 and len({(r['case_id'],r['seed'],r['arm']) for r in rows})==204
    concurrency=peak=0
    for _,delta in sorted(events,key=lambda t:(t[0],t[1])):
        concurrency+=delta; peak=max(peak,concurrency)
    assert concurrency==0 and peak<=4
    pairs=[]; problems=[]
    for item in manifest:
        cid=item['case_id']; selected=[r for r in rows if r['case_id']==cid]; local=[]
        for seed in (311,312,313):
            b=next(r for r in selected if r['seed']==seed and r['arm']=='BASE'); x=next(r for r in selected if r['seed']==seed and r['arm']=='EXPAND')
            assert b['cpu']==x['cpu'] and b['parallel_slots']==x['parallel_slots']
            both=b['matched'] and x['matched']
            p={'case_id':cid,'seed':seed,'changed':bool(item['expanded_points']),'both_correct':both,'base_correct':b['matched'],'expand_correct':x['matched'],
               'time_ratio_expand_over_base':x['wall_seconds']/b['wall_seconds'] if both else None,
               'process_time_ratio':x['process_wall_seconds']/b['process_wall_seconds'] if both else None,'parallel_slots':b['parallel_slots'],'cpu':b['cpu']}
            local.append(p); pairs.append(p)
        bc=sum(r['matched'] for r in selected if r['arm']=='BASE'); xc=sum(r['matched'] for r in selected if r['arm']=='EXPAND')
        problems.append({'case_id':cid,'group':item['group'],'original_variables':item['original_variables'],'expanded_variables':item['expanded_variables'],
            'expanded_points':item['expanded_points'],'unexpandable_points':item['unexpandable_point_count'],
            'base_correct_of_3':bc,'expand_correct_of_3':xc,'expand_minus_base':xc-bc,
            'base_missing':sum(r['record_missing'] for r in selected if r['arm']=='BASE'),'expand_missing':sum(r['record_missing'] for r in selected if r['arm']=='EXPAND'),
            **{f'{arm.lower()}_{seed}':('missing' if r['record_missing'] else 'correct' if r['matched'] else 'incorrect') for arm in ['BASE','EXPAND'] for seed in (311,312,313) for r in selected if r['arm']==arm and r['seed']==seed},
            'both_correct_pairs':sum(p['both_correct'] for p in local),'paired_time_ratio_median':median([p['time_ratio_expand_over_base'] for p in local if p['both_correct']]),
            'q30_correct_of_5':q30[cid]['correct'],'q30_missing':q30[cid]['missing'],'base_minus_q30_percentage_points':100*(bc/3-q30[cid]['correct']/5)})
    def aggregate(ids):
        selected=[r for r in rows if r['case_id'] in ids]
        ps=[p for p in pairs if p['case_id'] in ids]; good=[p for p in ps if p['both_correct']]
        return {'problems':len(ids),'runs_per_arm':len(selected)//2,
            **{arm:{'correct':sum(r['matched'] for r in selected if r['arm']==arm),'missing':sum(r['record_missing'] for r in selected if r['arm']==arm),
                'status_counts':dict(Counter(str(r['status']) for r in selected if r['arm']==arm))} for arm in ['BASE','EXPAND']},
            'both_correct_pairs':len(good),'time_ratio_median':median([p['time_ratio_expand_over_base'] for p in good]),'process_time_ratio_median':median([p['process_time_ratio'] for p in good])}
    all_ids=[c['case_id'] for c in manifest]; overall=aggregate(all_ids); changed=aggregate([c['case_id'] for c in manifest if c['expanded_points']]); unchanged=aggregate([c['case_id'] for c in manifest if not c['expanded_points']])
    b=overall['BASE']['correct']; x=overall['EXPAND']['correct']; ratio=overall['time_ratio_median']; reduction=b-x
    x1=reduction>=15; x2=ratio is not None and ratio>=2
    qcorrect=sum(q['correct'] for q in q30.values()); qmissing=sum(q['missing'] for q in q30.values())
    inventory=[]
    expansion=e.module('fixed_expansion_inventory',e.INPUT/'expand_k.py')
    for item in manifest:
        original=e.read(e.INPUT/f'{item["group"]}/dsl/{item["case_id"]}.json')
        picked={r['index'] for r in item['replacements']}
        retained={r['name']:r for r in item['retained_nonprimitive_constructions']}
        for i,c in enumerate(original['constructions']):
            head,_=expansion.head_args(c['expression'])
            category='expanded' if i in picked else 'retained_Point_definition' if head=='Point' else 'retained_nonpoint_primitive' if head in {'Line','Circle'} else 'unexpandable_known_point_call' if retained[c['name']]['point_returning'] else 'retained_other_expression'
            inventory.append({'case_id':item['case_id'],'index':i,**c,'kind':head,'classification':category})
    time_by_parallel={str(slots):{'both_correct_pairs':sum(p['both_correct'] and p['parallel_slots']==slots for p in pairs),'time_ratio_median':median([p['time_ratio_expand_over_base'] for p in pairs if p['both_correct'] and p['parallel_slots']==slots])} for slots in (2,4)}
    lost_changed=[p for p in pairs if p['changed'] and p['base_correct'] and not p['expand_correct']]
    summary={'completed_at_utc':e.now(),'overall':overall,'changed_4_problems_auxiliary':changed,'unchanged_30_problems_auxiliary':unchanged,
        'predictions':{'X1':{'fixed_threshold':15,'observed_base_minus_expand':reduction,'met':x1},'X2':{'fixed_threshold':2,'observed_ratio_median':ratio,'met':x2}},
        'Q30':{'correct':qcorrect,'denominator':170,'missing':qmissing,'base_difference_percentage_points':100*(b/102-qcorrect/170),'time_comparison_performed':False},
        'maximum_parallel':peak,'per_arm_runs':102,'scored_saved_records':sum(not r['record_missing'] for r in rows),'contract_failures':contract_failures,
        'load_samples':len(loads),'load_1m_min':min(v[0] for v in loads),'load_1m_max':max(v[0] for v in loads),'load_1m_median':median([v[0] for v in loads]),
        'per_seed':{str(s):{arm:sum(r['matched'] for r in rows if r['seed']==s and r['arm']==arm) for arm in ['BASE','EXPAND']} for s in (311,312,313)},
        'time_by_parallel':time_by_parallel,'maximum_batch_elapsed_seconds':max(batch_elapsed),'shell_watchdog_seconds':205,'shell_kill_grace_seconds':2,
        'pair_counts':{'both_correct':sum(p['both_correct'] for p in pairs),'base_only':sum(p['base_correct'] and not p['expand_correct'] for p in pairs),'expand_only':sum(p['expand_correct'] and not p['base_correct'] for p in pairs),'neither_correct':sum(not p['base_correct'] and not p['expand_correct'] for p in pairs)},
        'changed_pairs_losing_correctness':lost_changed,'construction_inventory_counts':dict(Counter(i['classification'] for i in inventory)),
        'all_static_equivalent':True,'expanded_points':8,'unexpandable_points':sum(c['unexpandable_point_count'] for c in manifest),
        'external_raw_files':len(rawfiles),'external_raw_gzip_bytes':sum(r['gzip_bytes'] for r in rawfiles),'external_raw_directory':str(e.RAW)}
    assert not contract_failures
    csv_write(OUT/'per-run.csv',rows); csv_write(OUT/'per-problem.csv',problems); csv_write(OUT/'paired-times.csv',pairs); e.save(OUT/'summary.json',summary)
    csv_write(OUT/'expanded-dsl/unexpandable.csv',[{'case_id':c['case_id'],**u} for c in manifest for u in c['retained_nonprimitive_constructions']])
    csv_write(OUT/'expanded-dsl/construction-inventory.csv',inventory)
    decision=lambda v:'的中' if v else '外れ'
    text=f'''| 固定した予測 | 観測 | 判定 |
|---|---|---|
| X1：展開版はBASEより15実行以上少ない | BASE {b}/102、展開 {x}/102（BASE−展開={reduction}） | {decision(x1)} |
| X2：両方正解の時間比の中央値が2倍以上 | 展開/BASE {fmt(ratio)}倍、{overall['both_correct_pairs']}組 | {decision(x2)} |

4基準：①大幅悪化の予測は外れたが、変わった問題は中点を含む4問だけで、強い意外性の根拠にはしにくい。②深い理論を要する現象は示せていない。③中点以外へ広く再現する証拠はない。④変数を減らす利点は数値探索一般にも関わる。Aの中心を担う証拠としては弱い。

展開した4問の補助集計はBASE {changed['BASE']['correct']}/12、展開 {changed['EXPAND']['correct']}/12、両方正解{changed['both_correct_pairs']}組の時間比中央値{fmt(changed['time_ratio_median'])}倍。主判定は全34問のままである。

| 実際に展開した問題 | 変数数 | BASE正解/3 | 展開正解/3 | 両方正解の時間比中央値 |
|---|---:|---:|---:|---:|
'''
    for p in problems:
        if p['expanded_points']: text+=f"| {p['case_id']} | {p['original_variables']}→{p['expanded_variables']} | {p['base_correct_of_3']} | {p['expand_correct_of_3']} | {fmt(p['paired_time_ratio_median'])}倍 |\n"
    text+=f'''
展開した問題でBASEの正解を失った組は{len(lost_changed)}件。今回は「展開で壊れる問題」の特徴を見つけられなかった。HMMT-2018は1→11変数でも全seedで正解した。AIME-2005-II-12では探索箱も変わった（e: [0,3600]→[0,1600]、f: [−2700,900]→[−800,900]）が、これを失敗原因とは呼べない。実行前に計算した探索箱は `expanded-dsl/manifest.json` にある。

`expand_k.py` の `eligible()` と `expand()` を無変更で使い、中点8点を展開した。未対応の点作図呼び出し{summary['unexpandable_points']}件は保持した（`unexpandable.csv`）。`IntersectLines`、線分上の点、反射、回転、規則が認識できない引数の垂足などを含む。`Point(...)` の座標式も固定規則に従って保持した。全構成は `construction-inventory.csv` に列挙した。残る30問はid末尾以外同じで、BASE {unchanged['BASE']['correct']}/90、展開 {unchanged['EXPAND']['correct']}/90。差の1件は変更のないHMMT-2017のseed313（BASE不正解、展開側正解）であり、展開の効果とは解釈しない。

中点の追加等式を記号的に解くと、座標は両端の平均に一意に戻る。非退化の仮定は不要。全34問で元の条件・不等式・目標・未展開作図の保存、名前の衝突なし、静的な構文・コンパイルを確認した。数学的な実解・答えは同値だが、有限の探索箱は同じとは限らない（`equivalence.json`）。

BASEとQ30の正解率は{b}/102（{100*b/102:.1f}%）対{qcorrect}/170（{100*qcorrect/170:.1f}%）、差{100*(b/102-qcorrect/170):+.1f}ポイント。Q30はseed301〜305、今回311〜313で、欠測は今回BASE {overall['BASE']['missing']}件・展開 {overall['EXPAND']['missing']}件、Q30 {qmissing}件。欠測は答えなしとして分母に残した。seed以外に実行時の負荷も違い、この差をseedだけの効果とは呼ばない。Q30との時間比較は行っていない。

事前登録は `70443d65`（2026-10-23T18:06:13Z）。実行前にpush済みのユーザー申告とremote-tracking refへの包含を確認。予測・閾値・対象は変更なし。DSLはQ30の固定lockと全件hash一致。凍結commit `60db4b6` のクリーンcheckout `/tmp/q6e3-clean` からsolver・benchmarksを読み込み、実行前・各batch・集計時に依存lockと source_hash `{e.EXPECTED}` を確認した。共有worktreeのsrc/benchmarksは実行に使っていない。

180秒・各1コア、CPU {plan['cpus']}固定、最大4並列。問題ごとに先に走る腕を入れ替え、対応する2腕は同じCPU・同じ並列枠数で測定した。末尾2batchのみ2枠。各コマンドは205秒＋強制終了猶予2秒の制限、内部watchdog188秒、再試行なし。時間比は同じ問題・seedの両方正解だけで計算した。4枠だけでも中央値{fmt(time_by_parallel['4']['time_ratio_median'])}倍、プロセス全体の時間比中央値は{fmt(overall['process_time_ratio_median'])}倍（`paired-times.csv`）。

共有機の1分loadは{summary['load_1m_min']:.1f}〜{summary['load_1m_max']:.1f}、中央値{summary['load_1m_median']:.1f}（{len(loads)}標本）。CPU固定でも負荷の偏りは消えず、180秒は実時間なので成否も揺れうる。

採点はQ30aの無変更の `score.py`、Q30bの固定した答え集合と同じnormal_completion判定を使用。全204記録を再採点し、保存前後の一致を確認。最大同時実行{peak}、実行条件違反0件。`per-run.csv` は204行、`per-problem.csv` は34行。

生記録はリポジトリ外 `{e.RAW}` にgzip保存し、各receiptにパスとSHA-256を記録。リポジトリ内は全ファイル5MB未満で、答えの記述子・採点・経過時間・実行条件を保持した。詳細は `plan.json`、`summary.json`、`batches/`、`completion-audit.json`。
'''
    (OUT/'answer.md').write_text(text)
    files=[p for p in OUT.rglob('*') if p.is_file() and p.name!='completion-audit.json']
    assert all(p.stat().st_size<5_000_000 for p in files)
    e.save(OUT/'completion-audit.json',{'finished_at_utc':e.now(),'files':{str(p.relative_to(OUT)):{'bytes':p.stat().st_size,'sha256':e.sha(p)} for p in files},'clean_checkout_status':e.git('status','--porcelain').decode(),'runtime':e.gate(),'full_plan_complete':True,'all_artifacts_under_5MB':True})
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
