"""S1 best-error measurement aggregation, fixed S7 W1-W4 and complete audit."""
import collections
import csv
import hashlib
import json
import math
from datetime import datetime,timezone
from pathlib import Path
from mpmath import mp

mp.dps=750
OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text())
ROOT=Path(M['scratch'])


def read(path):
    return json.loads(path.read_text()) if path.exists() else None


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,obj):
    data=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    assert len(data.encode())<3_000_000,path
    path.write_text(data)


def short(value):
    return mp.nstr(mp.mpf(value),25,min_fixed=0,max_fixed=0) if value is not None else None


def write_csv(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys)
        w.writeheader();w.writerows(rows)
    assert path.stat().st_size<3_000_000


def failure(d,name):
    receipt=read(d/(name+'.ended.json'))
    if receipt:
        return f"{name}: returncode={receipt['returncode']}, reason={receipt['reason']}"
    return name+': not started/completed'


def fmt(x):
    return '欠測' if x is None else f'{x:.2f}'


def rate(rows):
    n=len(rows)
    missing=sum(p['D_base'] is None for p in rows)
    success=sum(p['base_ge300'] for p in rows)
    return dict(total=n,measured=n-missing,missing=missing,success=success,
        fixed_rate=success/n if n else None,
        measured_rate=success/(n-missing) if n-missing else None,
        lower=success/n if n else None,upper=(success+missing)/n if n else None)


def pct(x):
    return '—' if x is None else f'{100*x:.2f}%'


problems=[];candidates=[];missing=[]
for task in M['inputs']:
    case=task['case_id'];d=ROOT/'runs'/case
    initial=read(d/'initial.json')
    classification=task['classification']
    p={k:classification[k] for k in ('case_id','has_tangency','sigma_base','sigma_base_check','base_judgment','sigma_raw','sigma_raw_check','raw_judgment','type','W3_target')}
    p.update(seed=0,order='>'.join(task['arm_order']),initial_candidates=len(initial['candidates']) if initial else None,
        search_seconds=initial['search_seconds'] if initial else None,
        reference_path=task['reference_path'],reference_answer_source='stage1 saved reference answer')
    for arm in ('BASE','RAW'):
        prefix=arm.lower();ref=read(d/(arm+'.refinement.json'));mes=read(d/(arm+'.measure.json'))
        rows=mes['rows'] if mes else []
        usable=[r for r in rows if r.get('absolute_error') is not None and mp.isfinite(mp.mpf(r['absolute_error']))]
        best=min(usable,key=lambda r:mp.mpf(r['absolute_error'])) if usable else None
        reason=None
        if not best:
            if not initial: reason=failure(d,'search')
            elif not initial['candidates']: reason='主探索の返却候補0件'
            elif not ref: reason=failure(d,'refine.'+arm)
            elif not mes: reason=failure(d,'measure.'+arm)
            elif not rows: reason='精密化返却候補0件'
            else:
                # Full original exceptions remain in the immutable measure JSON.
                kinds=collections.Counter(r.get('answer_error','unknown').split('(',1)[0] for r in rows)
                reason='全候補の目標評価不能: '+', '.join(f'{k} {v}件' for k,v in sorted(kinds.items()))
                reason+='; details='+str(d/(arm+'.measure.json'))+'; sha256='+sha(d/(arm+'.measure.json'))
            missing.append(dict(case_id=case,arm=arm,reason=reason))
        p['D_base' if arm=='BASE' else 'D_raw']=best['error_digits'] if best else None
        p.update({prefix+'_missing_reason':reason,prefix+'_best_candidate_uid':best['candidate_uid'] if best else None,
            prefix+'_best_absolute_error':short(best['absolute_error']) if best else None,
            prefix+'_best_normalized_l2':short(best.get('normalized_l2')) if best else None,
            prefix+'_refinement_seconds':ref['seconds'] if ref else None,
            prefix+'_measurement_seconds':mes['seconds'] if mes else None,
            prefix+'_attempted':ref['attempted'] if ref else None,
            prefix+'_returned':ref['returned'] if ref else None,
            prefix+'_unattempted':ref['unattempted'] if ref else None,
            prefix+'_deadline_hit':ref['deadline_hit'] if ref else None,
            prefix+'_answer_missing_candidates':len(rows)-len(usable) if mes else None})
        seen=set()
        for row_index,row in enumerate(rows):
            r=dict(row)
            for key in ('answer_error','residual_error'):
                if key in r:
                    original=r[key]
                    r[key]=original.split('(',1)[0]
                    r['error_details']=arm+f'.measure.json#rows/{row_index}'
            r['refinement_seconds']=(ref or {}).get('candidate_seconds',{}).get(r['source_uid'])
            r['missing_reason']=r.get('answer_error')
            r['selected_best']=bool(best is row)
            for k in ('answer','absolute_error','solver_residual','original_residual_norm','normalized_l2','normalized_max','error_digits_exact'):
                if k in r:r[k]=short(r[k])
            candidates.append(r);seen.add(row['source_uid'])
        if initial:
            for c in initial['candidates']:
                if c['candidate_uid'] not in seen:
                    candidates.append(dict(case_id=case,seed=0,arm=arm,candidate_id=c['candidate_id'],
                        candidate_uid=c['candidate_uid'],source_uid=c['candidate_uid'],status='not_returned' if ref else 'refinement_missing',
                        missing_reason='候補未精密化/未返却' if ref else reason,selected_best=False))
    p['base_ge300']=p['base_best_absolute_error'] is not None and mp.mpf(p['base_best_absolute_error'])<=mp.mpf('1e-300')
    p['D_base_minus_D_raw']=p['D_base']-p['D_raw'] if p['D_base'] is not None and p['D_raw'] is not None else None
    problems.append(p)

non=rate([p for p in problems if p['base_judgment']=='非特異'])
sing=rate([p for p in problems if p['base_judgment']=='特異'])
uncertain=rate([p for p in problems if p['base_judgment']=='不定'])
w3=[p for p in problems if p['W3_target']=='True']
assert len(w3)==5
w4_success=sum(p['D_base_minus_D_raw'] is not None and p['D_base_minus_D_raw']>=40 for p in w3)
w4_missing=sum(p['D_base_minus_D_raw'] is None for p in w3)
gap=non['fixed_rate']-sing['fixed_rate'] if non['total'] and sing['total'] else None
judgments={
    'W1':dict(judgment='当たり' if non['fixed_rate'] is not None and non['fixed_rate']>=.8 else '外れ',**non,threshold=.8),
    'W2':dict(judgment='判定不能' if gap is None else ('当たり' if gap>=.2 else '外れ'),
        non_singular=non,singular=sing,rate_difference=gap,threshold=.2,
        difference_lower=non['lower']-sing['upper'] if gap is not None else None,
        difference_upper=non['upper']-sing['lower'] if gap is not None else None),
    'W3':dict(judgment='当たり' if len(w3)>=1 else '外れ',total=len(problems),success=len(w3),missing=0,
        candidates=[p['case_id'] for p in w3],threshold=1,source='fixed stage1 classification'),
    'W4':dict(judgment='当たり' if 2*w4_success>=len(w3) else '外れ',total=len(w3),success=w4_success,
        measured=len(w3)-w4_missing,missing=w4_missing,threshold=.5,
        fixed_rate=w4_success/len(w3),lower=w4_success/len(w3),upper=(w4_success+w4_missing)/len(w3))}
write_csv(OUT/'per-problem.csv',problems)
write_csv(OUT/'per-candidate.csv',candidates)
events=[json.loads(line) for line in (ROOT/'events.jsonl').read_text().splitlines()]
resume=read(ROOT/'resume-started.json')
effective_events=events
resume_audit=None
if resume:
    prefix=(ROOT/'events.jsonl').read_bytes()[:resume['original_events_bytes']]
    assert hashlib.sha256(prefix).hexdigest()==resume['original_events_sha256']
    old=[json.loads(line) for line in prefix.splitlines()]
    effective_events=[e for e in old if e.get('case_id') not in resume['interrupted']]+events[len(old):]
    completed_changes=[p for p,h in resume['completed_files'].items() if sha(ROOT/p)!=h]
    archive_changes=[p for p,h in resume['interrupted_files'].items()
                     if sha(ROOT/'interrupted/attempt-0'/Path(p).relative_to('runs'))!=h]
    assert not completed_changes and not archive_changes
    resume_audit=dict(completed_preserved=len(resume['completed']),interrupted_excluded=resume['interrupted'],
        not_started_at_resume=resume['not_started'],completed_files_changed=completed_changes,
        interrupted_archive_changed=archive_changes,original_events_preserved=True,
        policy=resume['reason'],archive=str(ROOT/'interrupted/attempt-0'))
runtime=[(p,read(p)) for p in (ROOT/'runs').rglob('*.runtime-*.json')]
bad=[e for e in events if e.get('returncode',0)!=0 or e.get('reason')]
changed=[p for p,h in M['files'].items() if sha(Path(p))!=h]
source_changed=[p for p,h in M['source_files'].items() if sha(ROOT/p)!=h]
files=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
oversized=[str(p) for p in files if p.stat().st_size>=3_000_000]
raw_hashes={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in files if 'src' not in p.parts}
# Split inventories to keep each artifact strictly below the file-size ceiling.
chunks=[];chunk={}
for k,v in sorted(raw_hashes.items()):
    chunk[k]=v
    if len(json.dumps(chunk).encode())>1_000_000:
        chunks.append(chunk);chunk={}
if chunk:chunks.append(chunk)
for i,chunk in enumerate(chunks):save(OUT/f'raw-hashes-{i:02d}.json',chunk)
audit=dict(created_utc=datetime.now(timezone.utc).isoformat(),population=len(problems),
    fixed_classification_sha256=sha(OUT.parent/'classification.csv'),
    fixed_readonly_inputs_changed=changed,source_changed=source_changed,
    campaign_complete=any(e['stage']=='campaign_done' for e in events),
    completed_problems=sum(e['stage']=='problem_done' for e in events),
    search_starts=sum(e['stage']=='search_start' for e in effective_events),
    refine_starts={a:sum(e['stage']=='refine_start' and e.get('arm')==a for e in effective_events) for a in ('BASE','RAW')},
    search_starts_including_interrupted=sum(e['stage']=='search_start' for e in events),
    interruption_resume=resume_audit,
    peak_parallel=max(e['active'] for e in events),
    affinity_violations=[str(p) for p,r in runtime if len(r['affinity'])!=1],
    thread_violations=[dict(path=str(p),threads=r['threads']) for p,r in runtime if r['threads']!=1],
    execution_contract_status='violations' if any(r['threads']!=1 or len(r['affinity'])!=1 for p,r in runtime) else 'pass',
    all_D_missing=all(p['D_base'] is None and p['D_raw'] is None for p in problems),
    runtime_receipts=len(runtime),no_final_verification=not any(e['stage'].startswith('verify') for e in events),
    no_retries=all(sum(e.get('case_id')==t['case_id'] and e['stage']==mode+'_start' and e.get('arm')==arm
                      for e in effective_events)<=1
                   for t in M['inputs'] for mode,arm in [('search',None),('scales',None),
                       ('refine','BASE'),('refine','RAW'),('measure','BASE'),('measure','RAW')]),
    same_initial_candidates=True,raw_switch_checks=[],nonzero_stages=bad,missing=missing,
    unattempted_candidates=sum((p[a+'_unattempted'] or 0) for p in problems for a in ('base','raw')),
    candidate_answer_missing=sum((p[a+'_answer_missing_candidates'] or 0) for p in problems for a in ('base','raw')),
    raw_file_count=len(files),max_raw_file_bytes=max(p.stat().st_size for p in files),oversized=oversized,
    raw_directory=str(ROOT),load1_range=[min(e['loadavg'][0] for e in events),max(e['loadavg'][0] for e in events)],
    preflight=read(OUT/'preflight.json')['status'])
for task in M['inputs']:
    d=ROOT/'runs'/task['case_id']
    for arm in ('BASE','RAW'):
        r=read(d/(arm+'.refinement.json'))
        if r:
            audit['same_initial_candidates'] &= r['initial_sha256']==sha(d/'initial.pkl')
            receipt=read(d/('refine.'+arm+'.runtime-start.json'))
            env=receipt['environment']
            if arm=='RAW':
                assert env==M['switch_settings']['RAW'],env
                audit['raw_switch_checks'].append(dict(case_id=task['case_id'],receipt=r['raw_receipt']))
            else:assert not env,env
assert not changed and not source_changed and not oversized
assert audit['peak_parallel']<=10 and not audit['affinity_violations']
assert audit['same_initial_candidates'] and audit['campaign_complete'] and audit['completed_problems']==266
assert audit['no_retries'] and audit['search_starts']==266
save(OUT/'judgments.json',dict(judgments=judgments,missing=missing,population=266,
    denominator_policy='fixed stage1 groups; missing not counted as success',indeterminate_base=uncertain))
save(OUT/'audit.json',audit)
lines=['| 予測 | 判定 | 固定分母での結果 | 欠測 |','|---|---|---|---|',
    f"| W1 | {judgments['W1']['judgment']} | 非特異 {non['success']}/{non['total']} = {pct(non['fixed_rate'])}（必要80%以上） | {non['missing']} |",
    f"| W2 | {judgments['W2']['judgment']} | 非特異 {non['success']}/{non['total']} − 特異 {sing['success']}/{sing['total']} = {100*gap:.2f}ポイント（必要20以上） | 非特異{non['missing']} / 特異{sing['missing']} |" if gap is not None else '| W2 | 判定不能 | 分母なし | — |',
    f"| W3 | {judgments['W3']['judgment']} | 固定266問のうち接する条件なし・raw特異/base非特異 {len(w3)}問（必要1問以上） | 分類欠測0 |",
    f"| W4 | {judgments['W4']['judgment']} | W3対象のうち D_base−D_raw≥40: {w4_success}/{len(w3)} = {pct(w4_success/len(w3))}（必要3問以上） | {w4_missing} |",'',
    'seed 0の主探索直後の同じ候補集合から各90秒で一度ずつ精密化した。Dは最良候補の目標値の絶対誤差の−log10（上限600）。最良候補は通過状態で選別しない。参照値は段階(1)の保存参照解のanswer。最終検証は行っていない。','',
    '分母は固定分類の全該当問題。欠測を成功に数えない。追加除外・再分類・失敗/外枠タイムアウトの再試行・別seedはない。W3/W4は接する条件なしの固定5問を使う。','',
    '| base区分 | raw区分 | 接する条件 | 全問 | 測定 | 欠測 | D_base≥300 | 固定分母割合 | 測定分母割合 |','|---|---|---|---:|---:|---:|---:|---:|---:|']
groups=collections.defaultdict(list)
for p in problems:groups[(p['base_judgment'],p['raw_judgment'],p['has_tangency'])].append(p)
for (a,b,t),rows in sorted(groups.items()):
    r=rate(rows)
    lines.append(f"| {a} | {b} | {'あり' if t=='True' else 'なし'} | {r['total']} | {r['measured']} | {r['missing']} | {r['success']} | {pct(r['fixed_rate'])} | {pct(r['measured_rate'])} |")
lines+=['','| 接する条件 | 全問 | 測定 | 欠測 | D_base≥300 | 固定分母割合 | 測定分母割合 |','|---|---:|---:|---:|---:|---:|---:|']
for t in ('False','True'):
    r=rate([p for p in problems if p['has_tangency']==t])
    lines.append(f"| {'あり' if t=='True' else 'なし'} | {r['total']} | {r['measured']} | {r['missing']} | {r['success']} | {pct(r['fixed_rate'])} | {pct(r['measured_rate'])} |")
lines+=['','| W3問題（接する条件なし） | σ_base | σ_raw | D_base | D_raw | 符号付き差 | ≥40 |','|---|---:|---:|---:|---:|---:|---|']
for p in w3:
    delta=p['D_base_minus_D_raw']
    lines.append(f"| {p['case_id']} | {p['sigma_base']} | {p['sigma_raw']} | {fmt(p['D_base'])} | {fmt(p['D_raw'])} | {fmt(delta)} | {'欠測' if delta is None else ('○' if delta>=40 else '×')} |")
lines+=['',f"base不定は{uncertain['total']}問（D_base欠測{uncertain['missing']}問）。型別表には含め、W1/W2の特異/非特異分母には入れない。",'',
    f"欠測を除いた参考成功率: 非特異 {pct(non['measured_rate'])}、特異 {pct(sing['measured_rate'])}。欠測を全て不成功/成功とした率の範囲: 非特異 {pct(non['lower'])}〜{pct(non['upper'])}、特異 {pct(sing['lower'])}〜{pct(sing['upper'])}。",
    f"W2の率差の欠測感度範囲: {100*judgments['W2']['difference_lower']:.2f}〜{100*judgments['W2']['difference_upper']:.2f}ポイント。W4成功率範囲: {pct(judgments['W4']['lower'])}〜{pct(judgments['W4']['upper'])}。" if gap is not None else '',
    '', '外れた予測: '+('、'.join(k for k,v in judgments.items() if v['judgment']=='外れ') or 'なし')+'。閾値や対象を変えず、そのまま報告する。',
    'W1/W2がともに当たらない場合、正しい図での特異さが精密化の難しさを決めるという一般化は主張しない。W3/W4がともに当たらない場合、書き換え一般への原理の拡張は主張しない。','',
    f"Dの欠測は計{len(missing)}問題×構成。返却候補の目標評価欠測{audit['candidate_answer_missing']}件、精密化で未処理{audit['unattempted_candidates']}候補。非ゼロ/外枠打切り工程{len(bad)}件。理由は次表とCSV/JSONに保存。",'',
    '| 問題 | 構成 | 欠測理由 |','|---|---|---|']
for r in missing:lines.append(f"| {r['case_id']} | {r['arm']} | {r['reason'].replace('|','/')} |")
if not missing:lines.append('| — | — | なし |')
lines+=['',f"実行は{M['host']}、最大{audit['peak_parallel']}並列、CPU {M['cpus']}、各1コア・内部1スレッド設定。runtime receiptのOS Threadsが1を超えたものは{len(audit['thread_violations'])}件であり、実行条件監査は{audit['execution_contract_status']}。共有機の1分load averageは{audit['load1_range'][0]:.2f}〜{audit['load1_range'][1]:.2f}。壁時計予算下の結果であり速度を一般化しない。",'',
    f"BASEソース: `{M['source_hash']}`。rawはREADME/raw_switch.py記載のNO_RESIDUAL_REWRITE+T1。段階(1)と同じT1式・固定円円分枝を使う。接点、距離0の座標差、半径補助式は使わない。実行前の参照残差チェック266問は全件一致。",'',
    'per-problem.csvは全266問の固定σ・型・D・時間・欠測、per-candidate.csvは全返却候補と未返却初期候補を記録する。小さい値は指数表記、CSVは25有効桁、生データは700桁で評価。判断は丸め前の値で行う。',
    f"生ログ・全座標・入力・ソースコピーは `{ROOT}`。全ファイル3,000,000bytes未満、hashはraw-hashes-*.json。実行前hashはpre-run-hashes.json、固定入力不変・最大並列・CPU/スレッド・同一初期候補の監査はaudit.json。",'']
if resume:
    lines+=['',f"環境事故（/tmp容量超過・sandbox障害）で中断後、完了済み{len(resume['completed'])}問は全生ファイルのSHA-256一致を確認し再実行しなかった。problem_doneなしの{len(resume['interrupted'])}問は中断=結果に数えず、旧ファイルを退避し問題の最初から各1回のみ実行した。これは失敗の再試行ではなく中断の再開。未着手{resume['not_started']}問も元の条件で実行した。失敗(returncode≠0)・外枠タイムアウト工程の再試行はない。旧events.jsonlの全prefixと退避ファイルも不変。CPU割当は元のstreamのまま、全新規工程で/tmp空き6 GiB以上を開始条件とした。",'',
        '中断して結果から除いた問題: '+', '.join(resume['interrupted'])+'。ハッシュ更新履歴はhash-update-history.jsonとresume-history/pre-run-hashes.json。探索・精密化のworker、ソース、予算、分類、参照値、閾値、判定式は変更していない。','']
lines+=['','報告上の制約: 目標評価例外の全文は元の各BASE/RAW.measure.jsonに保持し、CSV/欠測表は例外型・件数・参照先・hashに要約した。per-candidate.csvのerror_detailsはscratch/runs/<case_id>/に対する相対参照であり、親measure.jsonのhashはper-problem.csvとraw-hashesに保存した。これは3 MB未満の出力制約のための集計表示だけの修正であり、候補評価を再実行していない。', '']
if all(p['D_base'] is None and p['D_raw'] is None for p in problems):
    lines+=['全266問でD_base・D_rawとも欠測。W1/W2/W4の「外れ」は欠測を成功に数えない事前登録の固定分母ルールによる形式判定であり、精密化の数値的成否を実測で判定できたことを意味しない。全候補で発生した目標評価例外を修正した再評価は行っていない。','']
if audit['thread_violations']:
    lines+=['実行条件逸脱: 次の終了receiptでOS Threads=2を観測した。CPU affinityは各1コア、OMP/BLAS等の設定値は1。追加スレッドの役割はこのreceiptからは確定できないため、内部1スレッド条件を全工程で満たしたとは主張しない。再実行は行っていない。','']
    lines += ['- '+r['path'] for r in audit['thread_violations']]
    lines+=['']
if audit['all_D_missing']:
    lines=['全266問のD_base・D_rawが欠測（532問題×構成）。主因は保存済みの目標評価例外HighPrecisionContaminationError。以下のW1/W2/W4は欠測を成功に数えない固定分母ルールによる形式判定であり、実測による精密化性能の判定はできない。','']+lines
if audit['thread_violations']:
    lines=['実行条件監査: violations。OS Threads=2の終了receiptが2件あるため、内部1スレッド条件の完全充足は確認できない。CPU affinity各1コアと最大10並列は維持。','']+lines
(OUT/'answer.md').write_text('\n'.join(lines))
with (OUT/'progress.md').open('a') as f:
    f.write('\n'+datetime.now(timezone.utc).isoformat()+' 集計・監査完了。'+json.dumps({k:v['judgment'] for k,v in judgments.items()},ensure_ascii=False)+f'。D欠測{len(missing)}件。\n')
save(OUT/'used-hashes.json',{str(p.relative_to(OUT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='used-hashes.json' and '__pycache__' not in p.parts})
assert all(p.stat().st_size<3_000_000 for p in OUT.rglob('*') if p.is_file())
print(json.dumps({k:v['judgment'] for k,v in judgments.items()},ensure_ascii=False),flush=True)
