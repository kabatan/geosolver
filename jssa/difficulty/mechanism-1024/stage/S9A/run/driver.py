"""Single-core streams adapted from S1/S7; exclusive receipts prohibit retries."""
import concurrent.futures, hashlib, json, os, resource, shutil, signal, subprocess, sys, threading, time
from pathlib import Path
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text());ROOT=Path(M['scratch'])
LOCK=threading.Lock();ACTIVE=0;PEAK=0;STOP=threading.Event()
def event(**kw):
    global ACTIVE,PEAK
    with LOCK:
        if kw['stage'].endswith('_start') and kw['stage']!='campaign_start':ACTIVE+=1
        elif kw['stage'].endswith('_end'):ACTIVE-=1
        PEAK=max(PEAK,ACTIVE);assert 0<=ACTIVE<=6
        row=dict(utc=datetime.now(timezone.utc).isoformat(),active=ACTIVE,peak=PEAK,loadavg=list(os.getloadavg()),free_bytes=shutil.disk_usage('/tmp').free,**kw)
        with (ROOT/'events.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        if kw['stage'] in ['campaign_start','campaign_done','problem_done','disk_stop']:
            with (OUT/'progress.md').open('a') as f:f.write(f"\n{row['utc']} {kw['stage']} {kw.get('case_id','')} {kw.get('reason','')}; active={ACTIVE}, peak={PEAK}, free={row['free_bytes']} bytes。\n")
def kill(p):
    try:os.killpg(p.pid,signal.SIGTERM)
    except ProcessLookupError:return
    try:p.wait(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGKILL);p.wait()
def stage(task,cpu,mode,arm=None):
    case=task['case_id'];d=ROOT/'runs'/case;name=mode+('.'+arm if arm else '')
    # Started means never run again, even if the parent died.
    if (d/(name+'.started.json')).exists():
        end=d/(name+'.ended.json')
        return end.exists() and json.loads(end.read_text())['returncode']==0 and json.loads(end.read_text())['reason'] is None
    if STOP.is_set():return False
    if shutil.disk_usage('/tmp').free<M['minimum_free_bytes']:
        STOP.set();event(stage='disk_stop',case_id=case,reason='less_than_6_GiB');return False
    with (d/(name+'.started.json')).open('x') as f:json.dump(dict(utc=datetime.now(timezone.utc).isoformat(),cpu=cpu),f)
    env={k:v for k,v in os.environ.items() if not k.startswith(('GEOSOLVER_ABLATE_','GEOSOLVER_S3_','GEOSOLVER_S7_'))}
    env.update(M['thread_environment']);env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',PYTHONPATH=M['source_paths'][mode])
    if mode=='refine':env.update(M['switch_settings'][arm])
    cmd=['taskset','-c',str(cpu),M['python'],'-B',str(OUT/'worker.py'),str(ROOT),mode,case]
    if arm:cmd.append(arm)
    limit=M['seconds'][mode+'_outer'];logpath=d/(name+'.log')
    event(stage=mode+'_start',case_id=case,arm=arm,cpu=cpu)
    started=time.monotonic();reason=None;peak_threads=0
    with logpath.open('w') as log:
        p=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        while p.poll() is None:
            try:peak_threads=max(peak_threads,len(list(Path(f'/proc/{p.pid}/task').iterdir())))
            except FileNotFoundError:pass
            if time.monotonic()-started>=limit or logpath.stat().st_size>=2_900_000:
                reason='outer_timeout' if time.monotonic()-started>=limit else 'log_size_limit';kill(p);break
            time.sleep(.2)
        code=p.wait()
    receipt=dict(returncode=code,reason=reason,seconds=time.monotonic()-started,cpu=cpu,mode=mode,arm=arm,peak_threads=peak_threads,environment={k:env[k] for k in env if k.startswith(('GEOSOLVER_','OMP_','OPENBLAS_','MKL_','NUMEXPR_','BLIS_','VECLIB_'))})
    (d/(name+'.ended.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    event(stage=mode+'_end',case_id=case,arm=arm,cpu=cpu,returncode=code,reason=reason,seconds=receipt['seconds'])
    return code==0 and reason is None

def stream(tasks,cpu):
    for task in tasks:
        if STOP.is_set():return
        d=ROOT/'runs'/task['case_id']
        if not task['n_variables']:
            (d/'missing.json').write_text(json.dumps(dict(reason='no_search_variables',structural=True))+'\n')
        else:
            ready=task['reuse'] is not None or stage(task,cpu,'search')
            if ready and (d/'initial.pkl').exists():
                stage(task,cpu,'initial')
                info=d/'initial-metrics.json'
                count=json.loads(info.read_text())['count'] if info.exists() else len(json.loads((d/'initial.json').read_text()).get('candidates',[]))
                if count:
                    for arm in task['arm_order']:
                        if stage(task,cpu,'refine',arm):
                            stage(task,cpu,'measure',arm);stage(task,cpu,'verify',arm)
                else:(d/'missing.json').write_text(json.dumps(dict(reason='empty_primary_candidate_tuple'))+'\n')
            else:
                reason='primary_search_handoff_unavailable'
                if (d/'search.ended.json').exists():reason+=': '+str(json.loads((d/'search.ended.json').read_text()))
                (d/'missing.json').write_text(json.dumps(dict(reason=reason))+'\n')
        event(stage='problem_done',case_id=task['case_id'])

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_FSIZE,(2_999_999,2_999_999))
    for p,h in M['files'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
    # Source/input integrity has been fixed before launch, check all again.
    sm=json.loads(Path(M['source_manifest']).read_text())
    for key,fk in [('base_source','base_files_sha256'),('patched_source','patched_files_sha256'),('frozen_source','frozen_files_sha256')]:
        for p,h in sm[fk].items():assert hashlib.sha256((Path(sm[key])/p).read_bytes()).hexdigest()==h,p
    for t in M['inputs']:
        assert hashlib.sha256(Path(t['input_copy']).read_bytes()).hexdigest()==t['sha256']
        if t['reuse']:
            for n,h in t['reuse']['sha256'].items():assert hashlib.sha256((ROOT/'runs'/t['case_id']/n).read_bytes()).hexdigest()==h
    with (ROOT/'driver-invocations.jsonl').open('a') as f:f.write(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid()))+'\n')
    event(stage='campaign_start')
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        jobs=[pool.submit(stream,M['inputs'][i::6],cpu) for i,cpu in enumerate(M['cpus'])]
        for job in jobs:job.result()
    event(stage='campaign_done' if not STOP.is_set() else 'disk_stop')
    print(json.dumps(dict(completed=not STOP.is_set(),peak=PEAK)),flush=True)
    if STOP.is_set():sys.exit(75)
