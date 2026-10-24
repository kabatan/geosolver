"""Pre-frozen load annotation and concurrency-restricted time reporting; never runs solver."""
import csv
import hashlib
import json
import statistics as st
from datetime import datetime, timedelta
from pathlib import Path
from measurement_common import HERE, load, save, sha, utc
from measurement_grade import csv_write

OUT=HERE/'run-superpc'
LOG=Path('/home/kabatan/work/tmp-evac/loadlog/load-log.jsonl')
POLICY={
 'scope':'superPC 53 problems only, before WinPC combination',
 'solved':'at least 2 of fixed seeds 601,602,603 exact whole-set matches; incomplete stays null',
 'C':'correct: actual tree wall through cleanup; failure/timeout:180; interrupted:null; average seeds then problems; all time values reference only',
 'environment':'quota/no-space proven interruptions are not results; no retries; no exclusions or extra seeds',
 'load_intervals':'external samples cover [utc,utc+60s); high_load_overlap=true if any high interval overlaps; false only with complete coverage; otherwise null (unknown)',
 'time_pairs':'same case and seed, same host/contract, actual intervals overlap >=1s, absolute difference of start 1-minute load <=5, both high_load_overlap known and equal, difference of interval-weighted external cpu_pct_other <=200 percentage points; interrupted excluded',
 'time_predictions':'B4 and cumulative B5 time comparisons only for eligible concurrent pairs; compute ratio of paired mean C; also report paired-correct actual-time median ratios. Full unmatched means are descriptive only; no final timing support verdict under external load.',
 'B1':'N<=60% and BASE>=90%, superPC interim only',
 'B2':'report all adjacent solved increments including losses, and difference from N',
 'B5':'single G4 (N+4) not run, full B5 pending; no single-arm inference',
 'analysis':'freeze policy and reporting source hashes before fresh campaign; retain missed predictions; no commit/push'
}

def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))

def annotate(start,end,samples):
 a,b=dt(start),dt(end);duration=max((b-a).total_seconds(),1e-9)
 overlaps=[]
 for x in samples:
  t=dt(x['utc']);lo=max(a,t);hi=min(b,t+timedelta(seconds=60))
  if hi>lo:overlaps.append((lo,hi,x))
 covered=0.;right=a
 for lo,hi,x in sorted(overlaps,key=lambda x:x[0]):
  covered+=max(0.,(hi-max(right,lo)).total_seconds());right=max(right,hi)
 high=any(x.get('high_load') is True for _,_,x in overlaps)
 full=covered>=duration-.001
 weights=[((hi-lo).total_seconds(),x) for lo,hi,x in overlaps];total=sum(w for w,x in weights)
 return dict(high_load_overlap=True if high else False if full else None,external_load_coverage=min(covered/duration,1.),
  external_cpu_pct_other_mean=sum(w*x['cpu_pct_other'] for w,x in weights)/total if total else None,
  external_load_sample_utcs=[x['utc'] for _,_,x in overlaps])

def eligible(a,b):
 if a['ok'] is None or b['ok'] is None:return False
 if min(dt(a['end_utc']),dt(b['end_utc']))-max(dt(a['start_utc']),dt(b['start_utc']))<timedelta(seconds=1):return False
 if abs(a['load'][0]-b['load'][0])>5:return False
 if a['high_load_overlap'] is None or b['high_load_overlap'] is None or a['high_load_overlap']!=b['high_load_overlap']:return False
 x,y=a['external_cpu_pct_other_mean'],b['external_cpu_pct_other_mean']
 return x is not None and y is not None and abs(x-y)<=200

def main():
 freeze=load(OUT/'analysis-freeze.json')
 assert freeze['policy']==POLICY
 assert freeze['reporting_sha256']==sha(Path(__file__))
 assert freeze['grade_sha256']==sha(HERE/'measurement_grade.py')
 snap=OUT/'load-log-snapshot.jsonl';snap.write_bytes(LOG.read_bytes())
 samples=[json.loads(l) for l in snap.read_text().splitlines() if l.strip()]
 assert all(dt(a['utc'])<dt(b['utc']) for a,b in zip(samples,samples[1:])), 'load sample order'
 with (OUT/'per-run.csv').open() as f:runs=list(csv.DictReader(f))
 for r in runs:
  q=int(r['queue_index']);start=load(OUT/'receipts'/f'{q:04d}.start.json');end=load(OUT/'receipts'/f'{q:04d}.end.json')
  r.update(queue_index=q,seed=int(r['seed']),ok={'True':True,'False':False,'':None}[r['ok']],C_seed=float(r['C_seed']) if r['C_seed'] else None,
   start_utc=start['start_utc'],end_utc=end['end_utc'],cpu=start['cpu'],load=start['load'])
  r.update(annotate(r['start_utc'],r['end_utc'],samples))
 csv_write(OUT/'per-run.csv',runs)
 summary=load(OUT/'summary.json');chain=['N','C1','C2','C3','C4','C5','BASE']
 lookup={(r['case_id'],r['seed'],r['configuration']):r for r in runs}
 time_comparisons=[];pair_rows=[]
 for a,b in [('N','BASE'),*zip(chain,chain[1:])]:
  pairs=[]
  for r in runs:
   if r['configuration']!=a:continue
   s=lookup[(r['case_id'],r['seed'],b)]
   if eligible(r,s):
    pairs.append((r,s));pair_rows.append(dict(case_id=r['case_id'],seed=r['seed'],before=a,after=b,before_queue=r['queue_index'],after_queue=s['queue_index'],before_C=r['C_seed'],after_C=s['C_seed'],high_load_overlap=r['high_load_overlap'],both_correct=r['ok'] is True and s['ok'] is True))
  before=st.mean(r['C_seed'] for r,s in pairs) if pairs else None
  after=st.mean(s['C_seed'] for r,s in pairs) if pairs else None
  ratios=[r['C_seed']/s['C_seed'] for r,s in pairs if r['ok'] is True and s['ok'] is True]
  time_comparisons.append(dict(before=a,after=b,eligible_pairs=len(pairs),before_mean_C=before,after_mean_C=after,before_over_after=before/after if after else None,after_over_before=after/before if before else None,both_correct_pairs=len(ratios),median_correct_before_over_after=st.median(ratios) if ratios else None))
 csv_write(OUT/'concurrent-time-pairs.csv',pair_rows)
 counts={c:dict(high=sum(r['high_load_overlap'] is True for r in runs if r['configuration']==c),low=sum(r['high_load_overlap'] is False for r in runs if r['configuration']==c),unknown=sum(r['high_load_overlap'] is None for r in runs if r['configuration']==c)) for c in chain}
 original=summary.pop('predictions');summary['unadjusted_preregistration_arithmetic_reference_only']=original
 summary.update(load_policy=POLICY,load_snapshot_sha256=sha(snap),load_overlap_by_config=counts,concurrent_time_comparisons=time_comparisons,analysis_freeze_sha256=sha(OUT/'analysis-freeze.json'))
 summary['predictions']={'prereg15_B1':original['prereg15_B1'],'prereg15_B4':dict(status='reference_only; final support withheld under load',concurrent_comparison=time_comparisons[0]),'prereg15_B5':dict(status='single G4 not measured; final B5 pending; time reference only',concurrent_comparison=next(t for t in time_comparisons if t['before']=='C3' and t['after']=='C4'))}
 save(OUT/'summary.json',summary)
 fmt=lambda v:'—' if v is None else f'{v:.6f}'
 lines=['# 事前登録15 S8：superPC分の中間集計','', 'superPC固定53問のみ。WinPC分と合算前。106問の最終判定ではない。','',
 'seed 601〜603、180秒、1コア・内部1スレッド・CPU固定、最大8並列。N/C1/C2/C3/C4/C5/BASEのみ。解けた=3seed中2回以上で独立参照集合と完全一致。失敗/timeoutはC=180、正解は所有木回収までの実時間、中断はok/C=nullで結果に数えない。再試行・別seed・問題追加除外なし。', '',
 '**時間・費用Cはすべて参考値（†）**。他プロジェクトの負荷が重なり、全体平均の構成差から速度効果を判定しない。時間の比較は事前固定した同条件の同時実行ペアだけ。正解数はそのまま有効。','',
 '| 構成 | 問題数 | 解けた数 | 未完 | C平均† 秒 | Nからの累積増分 | high_load_overlap 真/偽/不明（枠数） |','|---|---:|---:|---:|---:|---:|---|']
 for c in chain:
  s=summary['summary'][c];n=summary['summary']['N'];d=s['solved']-n['solved'];co=counts[c]
  lines.append(f"| {c} | {s['n']} | {s['solved']} | {s['incomplete_n']} | {fmt(s['mean_C'])} | {d:+d} | {co['high']}/{co['low']}/{co['unknown']} |")
 lines+=['','C平均はseed費用の問題内平均を53問で平均。環境中断があれば全体平均は未確定。high_load_overlapは外部1分ログのhigh_loadを時刻照合し、欠測は偽にしない。各枠のdriver load/start/end/CPUと外部負荷の重なりはper-run.csvに保存。','',
 '| 累積段階 | 解けた数の純増 | 新規成功 | 失った成功 |','|---|---:|---:|---:|']
 for d in summary['cumulative_increments']:lines.append(f"| {d['before']} → {d['after']} | {d['solved_increment']} | {len(d['gained'])} | {len(d['lost'])} |")
 b1=original['prereg15_B1'];b4=original['prereg15_B4'];b5=original['prereg15_B5']
 lines+=['',f"B1（中間値）: N={b1['N_solved']}/53 ({b1['N_fraction']:.2%})、BASE={b1['BASE_solved']}/53 ({b1['BASE_fraction']:.2%})。N≤60%かつBASE≥90%の部分集合条件: {b1['subset_condition']}。",'',
 f"B4（参考の事前登録式）: 全体C平均のN/BASE={fmt(b4['N_C_over_BASE_C'])}†（予測3以上）。この算術値は負荷を揃えた時間比較ではなく、支持判定には使わない。",'',
 f"B5（参考の事前登録式）: 全体C平均のC4/C3={fmt(b5['cumulative_C4_over_C3'])}†、算術上の減少率={fmt(b5['cumulative_cost_reduction'])}†（予測10%以上）。支持判定には使わない。単独G4=N+4は未実行のためB5全体は保留。",'',
 '外れた方向・負の増分もそのまま保存。B2は上表の全増分を掲載。B3および単独群は今回の対象外。', '',
 '| 同条件の同時実行† | 適格seedペア数 | C前/後† | 両方正解ペア数 | 正解実時間 前/後の中央値† |','|---|---:|---:|---:|---:|']
 for t in time_comparisons:lines.append(f"| {t['before']} → {t['after']} | {t['eligible_pairs']} | {fmt(t['before_over_after'])} | {t['both_correct_pairs']} | {fmt(t['median_correct_before_over_after'])} |")
 lines+=['', '時間ペアの固定条件: 同一問題・同seed、同一契約、実行区間の重なり1秒以上、driver開始1分load差≤5、外部high_load_overlapが両方既知で同じ、区間加重平均cpu_pct_other差≤200（2コア相当）。適格ペアのC平均比と、両方完全一致した実時間比の中央値を掲載。ペアが0なら比較不能。適格な並行ペアも専有環境の再測定ではない。', '',
 f"判定規則は計測開始前のanalysis-freeze.jsonでhash固定（sha256 {sha(OUT/'analysis-freeze.json')}）。外部ログのスナップショット: load-log-snapshot.jsonl（sha256 {sha(snap)}）。原本: {LOG}。",'',
 f"状態: {summary['states']}。採点理由: {summary['reasons']}。旧試行は ../run-superpc-aborted-attempt1/ に保存、全件結果に含めない。",'',
 f"固定参照: {summary.get('reference_sha256')}; source/入力/参照hashはmeasurement-freeze.json。raw: {summary['raw_root']}。全個別ファイルhashはreceipts、成果物hashはartifact-hashes.json。commit/pushなし。"]
 (OUT/'answer.md').write_text('\n'.join(lines)+'\n')
 save(OUT/'artifact-hashes.json',dict(created_utc=utc(),files_sha256={str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ['artifact-hashes.json','campaign.lock','driver.log','supervisor.log']}))
 print(json.dumps(dict(load_overlap=counts,time_comparisons=time_comparisons),ensure_ascii=False))

if __name__=='__main__':main()
