"""Aggregate immutable receipts without any numeric re-execution."""
import collections
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics

OUT = Path(__file__).resolve().parent
MAN = json.loads((OUT/'pre-run-hashes.json').read_text())
SCHEDULE = json.loads((OUT/'schedule.json').read_text())
CONDITIONS = ['a_120', 'a_250', 'a_max', 'b_100000000', 'b_100000000000000', 'b_1000000000000000000000']
rows, problems = [], []
for item in SCHEDULE:
    folder = OUT/'raw'/item['key']
    ref = json.loads((folder/'refined.json').read_text()) if (folder/'refined.json').exists() else {}
    for condition in CONDITIONS:
        path = folder/(condition+'.json')
        data = json.loads(path.read_text()) if path.exists() else dict(outcome='欠測', exception='receipt absent')
        arm, arg = condition.split('_')
        truth = ref.get('true_max_coefficient', max(abs(int(v)) for p in item['reference_polynomials'] for v in p))
        bound = 10**8 if arm == 'a' else int(arg)
        rows.append(dict(key=item['key'], id=item['id'], group=item['group'], kind=item['kind'],
                         condition=condition, arm=arm, digits=data.get('digits', int(arg) if arm=='a' and arg!='max' else ref.get('achieved_digits',0)),
                         max_coeff=bound, achieved_digits=ref.get('achieved_digits',0),
                         outcome=data.get('outcome','欠測'), polynomial=json.dumps(data.get('polynomial'), separators=(',',':')),
                         seconds=data.get('seconds',''), wall_seconds=data.get('wall_seconds',''),
                         true_polynomial=json.dumps(ref.get('true_polynomial',item['reference_polynomials'][0]),separators=(',',':')),
                         true_max_coefficient=truth, bound_strictly_exceeds_truth=bound>truth,
                         returned_max_coefficient=data.get('returned_max_coefficient',''),
                         returned_coeff_exceeds_bound=data.get('returned_coeff_exceeds_bound',False),
                         rounded_input_relative_error=data.get('rounded_input_relative_error',''),
                         unavailable=data.get('outcome')=='到達不可',
                         missing_reason=data.get('missing_reason',data.get('exception','')),
                         reason=data.get('reason',''), cpu=data.get('cpu',''),
                         receipt=str(path.relative_to(OUT))))
    mine=rows[-6:]
    counter=collections.Counter(r['outcome'] for r in mine)
    problems.append(dict(key=item['key'],id=item['id'],group=item['group'],kind=item['kind'],
                         achieved_digits=ref.get('achieved_digits',0),refinement_status=ref.get('status','missing'),
                         refinement_seconds=ref.get('refinement_seconds',''),refinement_wall_seconds=ref.get('wall_seconds',''),stage_count=ref.get('stage_count',''),selected_sample=ref.get('selected_sample',''),selected_working_dps=ref.get('working_dps',''),stop_reason=ref.get('stop_reason',''),original_residual_norm=ref.get('original_residual_norm',''),
                         hard_feasible=ref.get('hard_feasible',''),relative_error=ref.get('relative_error',''),
                         true_polynomial=mine[0]['true_polynomial'],true_max_coefficient=mine[0]['true_max_coefficient'],
                         correct=counter['正しい式'],wrong=counter['誤った式'],rejected=counter['棄却'],
                         unavailable=counter['到達不可'],missing=counter['欠測'],
                         pslq_seconds=sum(float(r['seconds']) for r in mine if r['seconds']!='' and r['seconds'] is not None),
                         reference_source=item['reference_source'],figure_source=item['figure_source'],
                         reference_description=ref.get('reference_description','')))

def write_csv(name, data):
    with (OUT/name).open('w', newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)

write_csv('per-condition.csv', rows)
write_csv('per-problem.csv', problems)
targets=[r for r in rows if r['group']=='target']
controls=[r for r in rows if r['group']=='control']
ta=[r for r in targets if r['arm']=='a']
uncertain=lambda r:r['outcome'] in ['到達不可','欠測']
p4='外れ' if any(r['outcome']=='正しい式' for r in ta) else ('判定不能' if not any(r['outcome'] in ['棄却','誤った式'] for r in ta) or any(r['outcome']=='欠測' for r in ta) else '的中')
eligible=[r for r in targets if r['arm']=='b' and r['bound_strictly_exceeds_truth']]
p5counts={str(b):sum(r['outcome']=='正しい式' for r in eligible if r['max_coeff']==b) for b in [10**8,10**14,10**21]}
p5='的中' if max(p5counts.values())>=1 else ('判定不能' if not any(r['outcome'] not in ['到達不可','欠測'] for r in eligible) or any(r['outcome']=='欠測' for r in eligible) else '外れ')
wrong=sum(r['outcome']=='誤った式' for r in rows)
controlwrong=sum(r['outcome']=='誤った式' for r in controls)
p6='外れ' if any(r['outcome'] in ['棄却','誤った式'] for r in controls) else ('判定不能' if any(r['outcome']=='欠測' for r in controls) or any(not any(r['outcome']=='正しい式' for r in controls if r['key']==k) for k in {r['key'] for r in controls}) else '的中')
counter=collections.Counter(r['outcome'] for r in rows)
timings=[r['seconds'] for r in rows if isinstance(r['seconds'],(int,float))]
loads=[]
for p in (OUT/'raw').glob('*/*.started.json'):
    loads.append(json.loads(p.read_text())['loadavg'][0])
summary=dict(predictions=dict(P4=p4,P5=p5,P6=p6),counts=dict(counter),p5_eligible_correct=p5counts,
             control_correct=sum(r['outcome']=='正しい式' for r in controls),control_wrong=controlwrong,
             all_wrong=wrong,conditions=len(rows),problems=len(problems),
             pslq_seconds_total=sum(timings),pslq_seconds_median=statistics.median(timings) if timings else None,
             loadavg_1m_range=[min(loads),max(loads)] if loads else [],
             refinement_failures=[p['key'] for p in problems if p['refinement_status']!='ok'],
             generated_utc=datetime.now(timezone.utc).isoformat())
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
numeric=lambda n:f'{n:.3f}'
answer=[
    '| 予測 | 判定 | 観測 | 到達不可（別欄） |','|---|---|---|---|',
    f"| P4'：対象(a)は全て同定失敗 | {p4} | 正しい式 {sum(r['outcome']=='正しい式' for r in ta)}、棄却 {sum(r['outcome']=='棄却' for r in ta)} | {sum(r['unavailable'] for r in ta)} |",
    f"| P5'：真の係数を上回る上限で1件以上回収 | {p5} | 適格な正解件数（1e8 / 1e14 / 1e21）：{' / '.join(str(p5counts[str(b)]) for b in [10**8,10**14,10**21])} | {sum(r['unavailable'] for r in eligible)} |",
    f"| P6'：到達した対照条件は全て正解、誤式0 | {p6} | 正しい式 {summary['control_correct']}、対照誤式 {controlwrong}、全体誤式 {wrong} | {sum(r['unavailable'] for r in controls)} |",'',
    '**事前登録7の主判定は判定不能のまま、この補遺は事後。** 到達不可は予測判定から除き、別に表示した。欠測は'+str(counter['欠測'])+'条件。','',
    f"4量×6条件＝24条件。正しい式{counter['正しい式']}、誤った式{counter['誤った式']}、棄却{counter['棄却']}、到達不可{counter['到達不可']}。問題交換・再試行0。",'',
    '| 量 | 実測到達桁数D | 採用値の計算設定桁数 | (a)120 / 250 / D | (b)1e8 / 1e14 / 1e21 |',
    '|---|---:|---:|---|---|']
for p in problems:
    mine=[r for r in rows if r['key']==p['key']]
    rr=json.loads((OUT/'raw'/p['key']/'refined.json').read_text())
    answer.append(f"| {p['key']} | {p['achieved_digits'] or '未取得'} | {rr.get('working_dps','—')} | "+' / '.join(r['outcome'] for r in mine[:3])+' | '+' / '.join(r['outcome'] for r in mine[3:])+' |')
answer.extend(['',
    '凍結版60db4b6の通常経路を各量1回だけ実行した。LMは50→100→120桁、closureは120→250→350→500桁（通常分岐により省略あり）。各段の実際の時間・段数・目標値はraw/*/stages.json。参照値との700桁比較でDを測り、設定桁数や残差で代用していない。各段の有効な完了値のうちD最大のものを採用した。参照値からPSLQ入力を作っていない。','',
    '対象の真の最大係数は長さ131886598434451146000、面積308249968294125。P5′の適格上限は両方とも1e21だけ。対照の正解基準はS2と同じ既存最小多項式であり、図の条件からの独立証明ではない。','',
    f"PSLQ呼出し合計{sum(timings):.3f}秒。精密化合計{sum(float(p['refinement_seconds'] or 0) for p in problems):.3f}秒（4量の合算、並列wall時間とは異なる）。起動・参照評価は別計上。並列2、各1 CPU、内部スレッド1、各段180秒、各量の精密化合計600秒以内。共有PC {MAN['host']} の1分負荷平均は"+('〜'.join(f'{v:.2f}' for v in summary['loadavg_1m_range']) if loads else '未測定')+'。他タスクの負荷を含み、専用PCの性能とはみなせない。','',
    '元変数で係数上限を超えた返却は'+str(sum(r['returned_coeff_exceeds_bound'] for r in rows))+'条件。凍結PSLQの返却をそのまま保持し、真の最小多項式と係数列を照合した。一般的な成功率や問題全体の解の完全性は示さない。詳細はper-condition.csv、per-problem.csv、raw/、validation.json。'])
(OUT/'answer.md').write_text('\n'.join(answer)+'\n')
changed=[p for p,h in MAN['files'].items() if not Path(p).exists() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
source=Path(MAN['frozen_source']).parent
changed_src=[p for p,h in MAN['source_files'].items() if hashlib.sha256((source/p).read_bytes()).hexdigest()!=h]
audit=dict(input_hash_changes=changed,source_hash_changes=changed_src,
           frozen_pslq_copy_identical=(OUT/'frozen_polynomial_search.py').read_bytes()==(source/'src/geosolver/exact/polynomial_search.py').read_bytes(),
           condition_count=len(rows),unique_conditions=len({(r['key'],r['condition']) for r in rows}),
           scheduled_count=len(list((OUT/'raw').glob('*/*.scheduled.json'))),
           maximum_artifact_bytes=max(p.stat().st_size for p in OUT.rglob('*') if p.is_file()),
           generated_utc=datetime.now(timezone.utc).isoformat())
(OUT/'validation.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
s2changes=[p for p,h in MAN['s2_files'].items() if not Path(p).exists() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
audit['s2_hash_changes']=s2changes
(OUT/'validation.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
assert not changed and not changed_src and not s2changes and audit['frozen_pslq_copy_identical']
assert len(rows)==24 and audit['unique_conditions']==24 and audit['scheduled_count']==28
assert audit['maximum_artifact_bytes']<3_000_000
print(json.dumps(summary,ensure_ascii=False,indent=2))
