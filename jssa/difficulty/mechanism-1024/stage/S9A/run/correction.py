"""Correct only the HP evaluation context on saved initial candidates."""
import concurrent.futures,hashlib,json,os,pickle,resource,shutil,signal,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent;M=json.loads((OUT/'pre-run-hashes.json').read_text());ROOT=Path(M['scratch'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp():return datetime.now(timezone.utc).isoformat()
def check():
    c=json.loads((OUT/'measurement-correction-hashes.json').read_text())
    for p,h in c['files'].items():assert sha(Path(p))==h,p

def worker(case):
    resource.setrlimit(resource.RLIMIT_FSIZE,(2_999_999,2_999_999))
    from mpmath import mp
    from geosolver.runtime.integrity import source_tree_hash
    from geosolver.problem.models import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import boundary_float_to_mpf,BoundaryOrigin
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    assert source_tree_hash()==M['frozen_source_hash']
    t=next(t for t in M['inputs'] if t['case_id']==case);d=ROOT/'runs'/case
    assert sha(Path(t['input_copy']))==t['sha256']
    with (d/'initial.pkl').open('rb') as f:candidates,config=pickle.load(f)
    bundle=load_problem_bundle(GeometryProblem.model_validate_json(Path(t['input_copy']).read_text()).engine_document());evaluator=build_ir_evaluator(bundle)
    num=lambda v:None if v is None else mp.nstr(v,710,min_fixed=0,max_fixed=0)
    rows=[]
    with mp.workdps(180):
        for i,c in enumerate(candidates):
            row=dict(rank=i,candidate_uid=c.candidate_uid,candidate_id=c.candidate_id)
            try:
                point=tuple(boundary_float_to_mpf(v,origin=BoundaryOrigin.INITIAL_POINT) for v in c.x_float)
                with high_precision_mode():ev=evaluator.evaluate_hp_residual(point,precision=180)
                row['residual_norm']=num(ev.residual_norm_hp)
            except Exception as e:row['error']=repr(e)
            rows.append(row)
        values=[mp.mpf(r['residual_norm']) for r in rows if 'residual_norm' in r];values=[v if mp.isfinite(v) else mp.inf for v in values];values.sort()
        median=(values[len(values)//2] if len(values)%2 else (values[len(values)//2-1]+values[len(values)//2])/2) if values and len(values)==len(rows) else None
        report=dict(source_hash=source_tree_hash(),count=len(rows),config_repr=repr(config),median_residual=num(median),rows=rows,correction='high_precision_mode around residual evaluation only',affinity=sorted(os.sched_getaffinity(0)),threads=int(next(l.split(':')[1] for l in Path('/proc/self/status').read_text().splitlines() if l.startswith('Threads:'))),initial_sha256=sha(d/'initial.pkl'))
        (d/'initial-metrics.corrected.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

def run_one(t,cpu):
    d=ROOT/'runs'/t['case_id']
    if not (d/'initial.pkl').exists():return
    if (d/'correction.begin.json').exists():return
    assert shutil.disk_usage('/tmp').free>=6*1024**3,'less than 6 GiB; do not start'
    with (d/'correction.begin.json').open('x') as f:json.dump(dict(utc=stamp(),cpu=cpu),f)
    old=d/'initial-metrics.json'
    if old.exists():old.rename(d/'initial-metrics.original.json')
    env={k:v for k,v in os.environ.items() if not k.startswith(('GEOSOLVER_ABLATE_','GEOSOLVER_S3_','GEOSOLVER_S7_'))};env.update(M['thread_environment']);env.update(PYTHONPATH=M['source_paths']['initial'],PYTHONDONTWRITEBYTECODE='1')
    cmd=['taskset','-c',str(cpu),M['python'],'-B',str(OUT/'correction.py'),'worker',t['case_id']]
    started=time.monotonic();reason=None
    with (d/'correction.log').open('w') as log:
        p=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:code=p.wait(timeout=90)
        except subprocess.TimeoutExpired:
            reason='outer_timeout';os.killpg(p.pid,signal.SIGKILL);code=p.wait()
    fixed=d/'initial-metrics.corrected.json'
    if fixed.exists():shutil.copyfile(fixed,d/'initial-metrics.json')
    end=dict(case_id=t['case_id'],returncode=code,reason=reason,seconds=time.monotonic()-started,cpu=cpu,utc=stamp())
    (d/'correction.finish.json').write_text(json.dumps(end,indent=2)+'\n')
    return end

def audit():
    check()
    note='\n初期残差集計の高精度モード設定漏れを修正し、保存初期候補から同じ180dps・同じ残差定義で評価した。元script・元失敗出力・修正前hashを保持し、修正処理も実行前hash固定。探索・精密化・最終検証の再実行はない。詳細はmeasurement-correction.md。\n'
    answer=OUT/'answer.md'
    if note not in answer.read_text():
        with answer.open('a') as f:f.write(note)
    p=subprocess.run([M['python'],'-B',str(OUT/'audit.py')]);assert p.returncode==0
    a=json.loads((OUT/'audit.json').read_text());rs=[];errors=[]
    for t in M['inputs']:
        d=ROOT/'runs'/t['case_id'];end=d/'correction.finish.json'
        if end.exists():
            r=json.loads(end.read_text());rs.append(r)
            if r['returncode']!=0 or r['reason']:errors.append(r)
            fixed=d/'initial-metrics.corrected.json'
            if fixed.exists():
                q=json.loads(fixed.read_text())
                assert q['threads']==1 and q['affinity']==[r['cpu']]
                assert q['initial_sha256']==sha(d/'initial.pkl')
    a['initial_residual_measurement_correction']=dict(hash_manifest=str(OUT/'measurement-correction-hashes.json'),jobs=len(rs),failed=errors,solver_reruns=0,reason='HP evaluation context missing from original measurement harness')
    a['passed']=a['passed'] and not errors
    (OUT/'audit.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
    hashes={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in ['artifact-hashes.json','progress.md']}
    (OUT/'artifact-hashes.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'progress.md').open('a') as f:f.write(f"\n{stamp()} 初期残差モード修正の監査完了: jobs={len(rs)}, failed={len(errors)}, solver_reruns=0。\n")
    assert a['passed']

if __name__=='__main__':
    check()
    if sys.argv[1]=='worker':worker(sys.argv[2])
    elif sys.argv[1]=='audit':audit()
    else:
        events=[json.loads(l) for l in (ROOT/'events.jsonl').read_text().splitlines()];assert events[-1]['stage']=='campaign_done'
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            def stream(ts,cpu):
                for t in ts:run_one(t,cpu)
            jobs=[pool.submit(stream,M['inputs'][i::6],cpu) for i,cpu in enumerate(M['cpus'])]
            for j in jobs:j.result()
        with (OUT/'progress.md').open('a') as f:f.write(f"\n{stamp()} 保存候補から初期残差の評価モード修正完了。探索・精密化・検証の再実行なし。\n")
        print('Initial residual correction complete')
