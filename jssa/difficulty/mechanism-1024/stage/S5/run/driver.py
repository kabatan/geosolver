"""S3 sequential stage procedure, eight fixed single-core streams, no retries."""
import concurrent.futures
import hashlib
import json
import os
import resource
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text());ROOT=Path(M['scratch'])
LOCK=threading.Lock();EVENTS=[];STOP=threading.Event()

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def event(**kw):
    with LOCK:
        row=dict(utc=datetime.now(timezone.utc).isoformat(),loadavg=list(os.getloadavg()),**kw);EVENTS.append(row)
        with (ROOT/'events.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        done=sum(e.get('stage')=='problem_done' for e in EVENTS)
        lines=['# S5 段階(2) 進捗','',f'完了 {done}/32問。最大8並列、各1コア、内部1スレッド。',f'生データ: `{ROOT}`','','```']
        lines += [f"{e['utc']} {e.get('case_id','')} {e['stage']} {e.get('arm','')} {e.get('returncode','')}" for e in EVENTS if e['stage']!='load_sample']
        lines += ['```',''];p=OUT/'progress.md.tmp';p.write_text('\n'.join(lines));p.replace(OUT/'progress.md')

def stage(task,cpu,mode,arm=None):
    case=task['case_id'];d=ROOT/'runs'/case
    env={k:v for k,v in os.environ.items() if not k.startswith('GEOSOLVER_ABLATE_') and k!='GEOSOLVER_S3_TANGENCY_MODE'}
    env.update(M['thread_environment']);env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',PYTHONHASHSEED='0')
    env['PYTHONPATH']=M['frozen_origin' if mode in ['verify','references'] else 'source_origin']
    if mode=='refine':env['GEOSOLVER_S3_TANGENCY_MODE']=arm
    cmd=['taskset','-c',str(cpu),M['python'],'-B',str(OUT/'worker.py'),str(ROOT),mode,case]+([arm] if arm else [])
    event(case_id=case,stage=mode+'_start',arm=arm,cpu=cpu);t=time.monotonic()
    with (d/(mode+('.'+arm if arm else '')+'.log')).open('x') as log:
        p=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:code=p.wait(timeout=180 if mode=='search' else 98 if mode in ['refine','verify'] else 90)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGTERM)
            try:p.wait(timeout=2)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
            code=124
    event(case_id=case,stage=mode+'_end',arm=arm,cpu=cpu,returncode=code,seconds=time.monotonic()-t)
    return code==0

def stream(tasks,cpu):
    for task in tasks:
        d=ROOT/'runs'/task['case_id']
        if stage(task,cpu,'search') and (d/'initial.json').exists():
            init=json.loads((d/'initial.json').read_text())
            snap=dict(initial_sha256=sha(d/'initial.pkl'),initial_json_sha256=sha(d/'initial.json'),candidate_uids=init['candidate_uids'],config_repr=init['config_repr'])
            (d/'initial-snapshot.json').write_text(json.dumps(snap,indent=2)+'\n')
            if init['candidates']:
                if stage(task,cpu,'scales'):
                    stage(task,cpu,'references')
                    for arm in task['arm_order']:
                        if stage(task,cpu,'refine',arm):
                            stage(task,cpu,'measure',arm)
                            before=sha(d/(arm+'.refined.pkl'))
                            stage(task,cpu,'verify',arm)
                            assert sha(d/(arm+'.refined.pkl'))==before
                else:event(case_id=task['case_id'],stage='missing',reason='scales stage failed')
            else:event(case_id=task['case_id'],stage='missing',reason='primary search returned zero candidates')
        else:event(case_id=task['case_id'],stage='missing',reason='primary refinement handoff unavailable; see search log and returncode')
        event(case_id=task['case_id'],stage='problem_done')

def sample_load():
    while not STOP.wait(30):event(stage='load_sample')

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_FSIZE,(2_999_999,2_999_999))
    for collection in ['files','source_files']:
        for path,expected in M[collection].items():assert sha(Path(path))==expected,path
    with (ROOT/'started.json').open('x') as f:json.dump(dict(pid=os.getpid(),utc=datetime.now(timezone.utc).isoformat()),f)
    event(stage='campaign_start');threading.Thread(target=sample_load,daemon=True).start()
    with concurrent.futures.ThreadPoolExecutor(max_workers=M['parallel']) as pool:
        jobs=[pool.submit(stream,M['inputs'][i::M['parallel']],cpu) for i,cpu in enumerate(M['cpus'])]
        for job in jobs:job.result()
    STOP.set();event(stage='campaign_done')
    subprocess.run([M['python'],'-B',str(OUT/'analyze.py')],check=True);event(stage='analysis_done')
    subprocess.run([M['python'],'-B',str(OUT/'audit.py')],check=True)
