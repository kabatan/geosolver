"""Mechanical preregistration-12 judgments from pre-verification saved errors."""
import csv
import json
from pathlib import Path
from mpmath import mp
mp.dps=750
OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text());ROOT=Path(M['scratch']);ARMS=['T0','T1','T2']
def read(p):return json.loads(p.read_text()) if p.exists() else None
def short(v):return mp.nstr(mp.mpf(v),25) if v is not None else None
def digits(row):
    if row is None:return None
    e=mp.mpf(row['absolute_error']);return min(mp.mpf(600),-mp.log10(e)) if e else mp.mpf(600)
def best(rows):
    rows=[r for r in rows if r.get('absolute_error') is not None and mp.isfinite(mp.mpf(r['absolute_error']))]
    return min(rows,key=lambda r:mp.mpf(r['absolute_error'])) if rows else None
def write_csv(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r)) or ['case_id']
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def fmt(v):return '欠測' if v is None else f'{float(str(v)):.2f}'
problems=[];candidates=[];missing=[];numerics={};individual=[]
for task in M['inputs']:
    case=task['case_id'];d=ROOT/'runs'/case;initial=read(d/'initial.json');refval=read(d/'references.json')
    p=dict(case_id=case,seed=0,type=task['type'],prediction=task['prediction'],order='>'.join(task['arm_order']),
        initial_candidates=len(initial['candidates']) if initial else 0,search_seconds=initial.get('search_seconds') if initial else None,
        reference_diagram_available=task['classification_reference_status']=='ok',reference_value_available=bool(refval and refval['available']),
        reference_error=(refval or {}).get('error'),classification_reason=task['classification_reason'],**task['sigma'])
    if not initial:p['missing_reason']='主探索の最初の精密化引渡しに到達せず。search.logおよび工程終了コード参照'
    elif not initial['candidates']:p['missing_reason']='主探索の返却候補0件'
    values={}
    for arm in ARMS:
        r,me,v=[read(d/(arm+s)) for s in ['.refinement.json','.measure.json','.verification.json']]
        rows=me['rows'] if me else [];b=best(rows);values[arm]=digits(b);prefix=arm+'_'
        absent=[s for s,ok in [('精密化',r),('測定',me),('最終検証',v and v['complete'])] if not ok]
        if absent:missing.append(dict(case_id=case,arm=arm,stages=absent))
        p.update({prefix+'best_error_digits':short(values[arm]),prefix+'best_absolute_error':short(b['absolute_error']) if b else None,
            prefix+'best_candidate_uid':b['candidate_uid'] if b else None,prefix+'best_normalized_l2':short(b.get('normalized_l2')) if b else None,
            prefix+'refinement_seconds':r['seconds'] if r else None,prefix+'measurement_seconds':me['seconds'] if me else None,
            prefix+'verification_seconds':v['seconds'] if v else None,prefix+'attempted':r['attempted'] if r else None,
            prefix+'returned':r['returned'] if r else None,prefix+'unattempted':r['unattempted'] if r else None,
            prefix+'deadline_hit':r['deadline_hit'] if r else None,prefix+'immediate_pass_count':sum(x['immediate_pass'] for x in rows) if me else None,
            prefix+'final_pass_count':sum(x['final_pass'] for x in v['rows']) if v else None,
            prefix+'verification_unattempted':sum(x['status']=='unattempted_deadline' for x in v['rows']) if v else None,
            prefix+'verification_timedout':sum(x['status']=='deadline_reached' for x in v['rows']) if v else None,
            prefix+'missing_answer':sum(x.get('absolute_error') is None for x in rows) if me else None,
            prefix+'missing_residual':sum('normalized_l2' not in x for x in rows) if me else None,
            prefix+'missing_stages':'/'.join(absent)})
        verification={x['rank']:x for x in v['rows']} if v else {};seen=set()
        for x in rows:
            row=dict(x,type=task['type']);uid=x.get('source_uid') or x['candidate_uid'];seen.add(uid);vr=verification.get(x['rank'])
            row.update(refinement_seconds=(r or {}).get('candidate_seconds',{}).get(uid),final_pass=vr['final_pass'] if vr else None,
                final_status=vr['status'] if vr else 'missing',final_seconds=vr['seconds'] if vr else None,
                final_normalized_residual=vr.get('normalized_residual') if vr else None)
            row['error_digits']=short(digits(row)) if row.get('absolute_error') is not None else None
            for key in ['answer','absolute_error','solver_residual','original_residual_norm','normalized_l2','normalized_max','final_normalized_residual']:
                if key in row:row[key]=short(row[key])
            candidates.append(row)
        for c in (initial or {}).get('candidates',[]):
            if c['candidate_uid'] not in seen:
                candidates.append(dict(case_id=case,seed=0,type=task['type'],arm=arm,candidate_id=c['candidate_id'],candidate_uid=c['candidate_uid'],
                    source_uid=c['candidate_uid'],status='not_returned' if r else 'refinement_missing',immediate_pass=False if r else None,
                    final_pass=False if r else None,final_status='not_returned' if r else 'missing'))
    t1,t2=values['T1'],values['T2'];p['T2_minus_T1']=short(t2-t1) if t1 is not None and t2 is not None else None
    typ=task['type'];hit=None
    if typ=='P' and t1 is not None and t2 is not None:hit=bool(t2-t1>=40)
    if typ=='N' and t1 is not None and t2 is not None:hit=bool(abs(t2-t1)<=20)
    if typ=='B' and t2 is not None:hit=bool(t2<300)
    p['prediction_hit']=hit;p['individual_judgment']=('当たり' if hit else '外れ') if hit is not None else ('欠測' if typ in ['P','N','B'] else '予測なし')
    individual.append(dict(case_id=case,type=typ,prediction=task['prediction'],judgment=p['individual_judgment'],hit=hit,
        T0=short(values['T0']),T1=short(t1),T2=short(t2),T2_minus_T1=p['T2_minus_T1']))
    numerics[case]=values;problems.append(p)
judgments={}
for u,typ,condition in [('U1','P','T2−T1>=40'),('U2','N','|T2−T1|<=20'),('U3','B','T2<300')]:
    group=[p for p in problems if p['type']==typ];n=len(group);hit=sum(p['prediction_hit'] is True for p in group);miss=sum(p['prediction_hit'] is None for p in group)
    needed=(4*n+4)//5
    verdict='判定不能' if n<2 else '当たり' if hit>=needed else '外れ' if hit+miss<needed else '判定不能'
    judgments[u]=dict(type=typ,condition=condition,total=n,measured=n-miss,success=hit,failed=n-miss-hit,missing=miss,required=needed,
        judgment=verdict,reason='型の固定総数が2問未満、個別結果のみ' if n<2 else '固定総数を分母に80%以上。欠測は成功に数えず上下限で判定',
        measured_success_rate=hit/(n-miss) if n>miss else None)
no_reference=[p['case_id'] for p in problems if p['type']=='参照解なし'];undefined=[p['case_id'] for p in problems if p['type']=='不定']
J=dict(predictions=judgments,individual=individual,missing_stages=missing,
    fixed_classification_counts={t:sum(p['type']==t for p in problems) for t in ['P','N','B','不定','参照解なし']},
    no_reference=dict(cases=no_reference,total=len(no_reference),prediction_count=0,missing_for_registered_prediction=True,
        objective_measured_all_arms=sum(all(numerics[c][a] is not None for a in ARMS) for c in no_reference)),
    undefined=dict(cases=undefined,total=len(undefined),prediction_count=0),
    candidate_missing=sum(p['initial_candidates']==0 for p in problems),
    objective_missing_problems=[p['case_id'] for p in problems if any(numerics[p['case_id']][a] is None for a in ARMS)])
write_csv(OUT/'per-problem.csv',problems);write_csv(OUT/'per-candidate.csv',candidates)
(OUT/'judgments.json').write_text(json.dumps(J,ensure_ascii=False,indent=2)+'\n')
lines=['| 予測 | 判定 | 固定条件の結果 |','|---|---|---|']
for u,j in judgments.items():lines.append(f"| {u}（型{j['type']}） | {j['judgment']} | {j['success']}/{j['total']}問（必要{j['required']}問、欠測{j['missing']}。{j['reason']}） |")
lines += ['', '事前登録12・段階(2)の結果。段階(0)(1)の分類・予測を変更せず、外れもそのまま報告する。',
    '', '桁数は最終検証前の精密化直後の最良候補の目標値絶対誤差の−log10、上限600。候補は通過状態で選別しない。判定は700桁保存誤差から再計算し、表示のみ丸める。',
    '', '| 問題 | 固定型 | T0 | T1 | T2 | T2−T1 | 個別予測 |','|---|---|---:|---:|---:|---:|---|']
for p in problems:
    vals=numerics[p['case_id']];delta=vals['T2']-vals['T1'] if vals['T2'] is not None and vals['T1'] is not None else None
    lines.append(f"| {p['case_id']} | {p['type']} | "+' | '.join(fmt(vals[a]) for a in ARMS)+f" | {fmt(delta)} | {p['individual_judgment']} |")
lines += ['', '通過数と精密化時間（T0 / T1 / T2）：','','| 問題 | 直後通過 | 最終通過 | 精密化秒 |','|---|---:|---:|---:|']
for p in problems:
    def counts(key):return ' / '.join('欠測' if p[a+'_'+key] is None else str(p[a+'_'+key]) for a in ARMS)
    lines.append(f"| {p['case_id']} | {counts('immediate_pass_count')} | {counts('final_pass_count')} | "+' / '.join(fmt(p[a+'_refinement_seconds']) for a in ARMS)+' |')
lines += ['',f"欠測：候補なし{J['candidate_missing']}問、目標誤差が1条件以上欠測{len(J['objective_missing_problems'])}問、工程欠測{len(missing)}条件。",'',
    '| 欠測問題・条件 | 理由 |','|---|---|']
for p in problems:
    reasons=[p[a+'_missing_stages'] for a in ARMS if p[a+'_missing_stages']]
    if reasons or not p['reference_value_available'] or any(numerics[p['case_id']][a] is None for a in ARMS):
        reason=p.get('missing_reason') or p['reference_error'] or '; '.join(a+':'+p[a+'_missing_stages'] for a in ARMS if p[a+'_missing_stages']) or '目標値評価不能、候補行参照'
        lines.append(f"| {p['case_id']} | {str(reason).replace('|','/')} |")
lines += ['',f"参照解なし5問は予測を付けず登録予測では欠測として別集計。補助的に全条件の誤差を測定できたのは{J['no_reference']['objective_measured_all_arms']}/5問。不定2問も予測なし。参照図の有無と独立参照式の評価可否を区別する。",'',
    '固定σ（段階(1)CSVの値を指数表記で再掲、再計算・再分類なし）：','','| 問題 | 固定型 | σ1 | σ2 |','|---|---|---:|---:|']
for p in problems:lines.append(f"| {p['case_id']} | {p['type']} | {p['T1_sigma'] or '欠測'} | {p['T2_sigma'] or '欠測'} |")
events=[json.loads(x) for x in (ROOT/'events.jsonl').read_text().splitlines()];loads=[e['loadavg'][0] for e in events]
nonzero=[e for e in events if e.get('returncode',0)!=0]
lines += ['',f"実行機は{M['host']}。最大{M['parallel']}並列、CPU affinity {M['cpus']}、各1コア、内部スレッド1。工程前後・30秒間隔の1分load averageは{min(loads):.2f}〜{max(loads):.2f}。各90秒は壁時計上限で、共有負荷と打切りに影響される。",'',
    f"全32問・seed 0の主探索を各1回。T0/T1/T2は各問で同じ保存候補・順序・Config・尺度を使用。探索・精密化の再試行なし。非ゼロ終了{len(nonzero)}工程。最終検証は凍結版、スイッチ解除、各候補集合別枠90秒。精密化後座標を検証で上書きしない。",'',
    '元DSLの全条件を700桁で評価し、尺度は主探索の全候補から固定した。未処理候補はper-candidate.csvに別行で記録。精密化・参照値評価・測定・最終検証時間は分離して保存した。', '',
    f"精密化src：`{M['source_hash']}`。検証src：`{M['frozen_source_hash']}`。生データ：`{ROOT}`。実行前固定はpre-run-hashes.jsonとrules.md、全生データhashはraw-hashes.json、監査はaudit.json。32問・1 seedの結果であり一般化しない。commit/pushはしていない。",'']
(OUT/'answer.md').write_text('\n'.join(lines))
print(json.dumps(judgments,ensure_ascii=False))
