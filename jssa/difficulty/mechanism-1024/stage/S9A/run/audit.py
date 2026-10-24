"""Read-only validation of fixed scripts/sources and all campaign receipts."""
import hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text());ROOT=Path(M['scratch'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    errors=[]
    for p,h in M['files'].items():
        if sha(p)!=h:errors.append('fixed_file_changed:'+p)
    s=json.loads(Path(M['source_manifest']).read_text())
    for k,fk in [('base_source','base_files_sha256'),('patched_source','patched_files_sha256'),('frozen_source','frozen_files_sha256')]:
        actual={str(p.relative_to(Path(s[k]))):sha(p) for p in sorted(Path(s[k]).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
        if actual!=s[fk]:errors.append('source_changed:'+k)
    events=[json.loads(l) for l in (ROOT/'events.jsonl').read_text().splitlines()]
    peaks=max(e['peak'] for e in events)
    if peaks>6:errors.append('parallel_limit')
    jobs=[];failures=[];thread_violations=[];missing_runtime=[]
    for t in M['inputs']:
        d=ROOT/'runs'/t['case_id']
        if sha(Path(t['input_copy']))!=t['sha256']:errors.append('input_changed:'+t['case_id'])
        if t['reuse']:
            for n,h in t['reuse']['sha256'].items():
                if sha(d/n)!=h:errors.append('reused_candidate_changed:'+t['case_id'])
        for p in sorted(d.glob('*.started.json')):
            name=p.name[:-len('.started.json')];end=d/(name+'.ended.json')
            if not end.exists():errors.append('started_without_end:'+str(p));continue
            r=json.loads(end.read_text());jobs.append(r)
            if r['returncode']!=0 or r['reason'] is not None:failures.append(dict(case_id=t['case_id'],stage=name,**r))
            if r['peak_threads']>1:thread_violations.append(dict(case_id=t['case_id'],stage=name,threads=r['peak_threads']))
            mode=r['mode'];arm=r['arm'];expected=M['switch_settings'][arm] if mode=='refine' else {}
            runtime=d/(name+'.runtime-start.json')
            if runtime.exists():
                rr=json.loads(runtime.read_text())
                if rr['environment']!=expected:errors.append('switch_mismatch:'+str(runtime))
                if rr['affinity']!=[r['cpu']]:errors.append('affinity_mismatch:'+str(runtime))
                sh=M['base_source_hash'] if mode=='search' else M['source_hash'] if mode=='refine' else M['frozen_source_hash']
                if rr['source_hash']!=sh:errors.append('source_route:'+str(runtime))
                if rr['threads']!=1:errors.append('runtime_threads:'+str(runtime))
            else:missing_runtime.append(str(runtime))
        for arm in ['R0','R1','R2','R3']:
            ref=d/(arm+'.refinement.json')
            if ref.exists():
                r=json.loads(ref.read_text())
                if r['initial_sha256']!=sha(d/'initial.pkl'):errors.append('different_initial:'+str(ref))
                meas=d/(arm+'.measure.json')
                if meas.exists():
                    q=json.loads(meas.read_text())
                    if q['complete'] and len(q['rows'])!=r['returned']:errors.append('candidate_row_count:'+str(meas))
    oversize=[str(p) for base in [OUT,ROOT] for p in base.rglob('*') if p.is_file() and p.stat().st_size>=3_000_000]
    if oversize:errors.append('oversize_files')
    if thread_violations:errors.append('worker_threads_exceed_one')
    # Campaign failures are disclosed missingness, not hidden or retried.
    j=json.loads((OUT/'judgments.json').read_text())
    report=dict(created_utc=datetime.now(timezone.utc).isoformat(),passed=not errors,errors=errors,population=j['population'],peak_parallel=peaks,jobs=len(jobs),failed_jobs=failures,thread_violations=thread_violations,missing_runtime_receipts=missing_runtime,oversize=oversize,fixed_sources_unchanged=True if not any('source_changed' in e for e in errors) else False,retries=0,seeds=[0],free_bytes=shutil.disk_usage('/tmp').free,raw=str(ROOT),provenance='S1 and completed S7/run2 seed0 primary handoffs; no S7/run2 digit table opened')
    (OUT/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    hashes={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in ['artifact-hashes.json','progress.md']}
    (OUT/'artifact-hashes.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'progress.md').open('a') as f:f.write(f"\n{report['created_utc']} 最終監査: passed={report['passed']}, jobs={len(jobs)}, failed_jobs={len(failures)}, peak_parallel={peaks}, errors={errors}。\n")
    print(json.dumps({k:report[k] for k in ['passed','errors','jobs','peak_parallel']},ensure_ascii=False))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
