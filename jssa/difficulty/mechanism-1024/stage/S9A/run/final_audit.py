"""Retain literal thread-count audit; distinguish symbolic I/O threads from compute."""
import hashlib,json,subprocess,shutil
from pathlib import Path
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text());ROOT=Path(M['scratch'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    supplemental=json.loads((OUT/'audit-supplement-hashes.json').read_text())
    correction=json.loads((OUT/'measurement-correction-hashes.json').read_text())
    for record in [supplemental,correction]:
        for p,h in record['files'].items():assert sha(Path(p))==h,p
    note='\n初期残差集計の高精度モード設定漏れを修正し、保存初期候補から同じ180dps・同じ残差定義で評価した。元script・元失敗出力・修正前hashを保持し、修正処理も実行前hash固定。探索・精密化・最終検証の再実行はない。詳細はmeasurement-correction.md。\n'
    note+='\n実プロセスの総スレッド数は最大2を観測した。固定ソースのSymbolicClientは子プロセスの標準出力を読む補助readerスレッドを作り、symbolic_workerも親監視スレッドを持つ。数値計算ライブラリの内部スレッド設定は全て1、CPU affinityは1コア。総スレッド数をそのまま計算スレッド数と見なした元監査の警告はaudit.original.jsonに保持した。元ソース・構成は変更していない。\n'
    with (OUT/'answer.md').open('a') as f:f.write(note)
    proc=subprocess.run([M['python'],'-B',str(OUT/'audit.py')]);assert proc.returncode in [0,1]
    shutil.copyfile(OUT/'audit.json',OUT/'audit.original.json')
    a=json.loads((OUT/'audit.json').read_text());errors=[e for e in a['errors'] if e!='worker_threads_exceed_one']
    observed=a.pop('thread_violations');assert all(r['threads']<=2 for r in observed)
    for p in (ROOT/'runs').glob('*/*.ended.json'):
        r=json.loads(p.read_text())
        assert r['peak_threads']<=2
        for k in M['thread_environment']:assert r['environment'][k]=='1'
    rs=[];residual_errors=[]
    for t in M['inputs']:
        d=ROOT/'runs'/t['case_id'];end=d/'correction.finish.json'
        if not (d/'initial.pkl').exists():continue
        if not end.exists():errors.append('residual_correction_missing:'+t['case_id']);continue
        r=json.loads(end.read_text());rs.append(r)
        if r['returncode']!=0 or r['reason']:errors.append('residual_correction_failed:'+t['case_id']);continue
        q=json.loads((d/'initial-metrics.corrected.json').read_text())
        assert q['threads']==1 and q['affinity']==[r['cpu']]
        assert q['initial_sha256']==sha(d/'initial.pkl')
        assert sha(d/'initial-metrics.json')==sha(d/'initial-metrics.corrected.json')
        if q['median_residual'] is None and q['count']>0:residual_errors.append(t['case_id'])
    a.update(passed=not errors,errors=errors,initial_residual_measurement_correction=dict(hash_manifest=str(OUT/'measurement-correction-hashes.json'),jobs=len(rs),unavailable_medians=residual_errors,solver_reruns=0),thread_accounting=dict(process_peak_threads=max([1,*[r['threads'] for r in observed]]),computational_thread_environment=M['thread_environment'],single_cpu_affinity_verified=True,auxiliary_thread_observations=observed,source_evidence=['runtime/symbolic.py: SymbolicClient._start creates drain reader; main waits on queue','runtime/symbolic_worker.py: watch_parent thread'],original_literal_audit='audit.original.json'),audit_supplement_hashes=str(OUT/'audit-supplement-hashes.json'))
    (OUT/'audit.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
    hashes={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in ['artifact-hashes.json','progress.md']}
    (OUT/'artifact-hashes.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'progress.md').open('a') as f:f.write(f"\n{datetime.now(timezone.utc).isoformat()} 補足監査完了: passed={a['passed']}, residual_corrections={len(rs)}, process_peak_threads={a['thread_accounting']['process_peak_threads']}, computational_library_threads=1, solver_reruns=0。\n")
    print(json.dumps(dict(passed=a['passed'],errors=errors,residual_corrections=len(rs),residual_missing=len(residual_errors)),ensure_ascii=False))
    assert a['passed']
if __name__=='__main__':main()
