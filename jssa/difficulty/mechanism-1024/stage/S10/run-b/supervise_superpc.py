"""S10B detached parent. Explicit invocation only; resumes unstarted jobs after driver death."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import psutil
from measurement_common import HERE,load,save,utc
from measurement_runtime import storage_available


def cleanup_owned(output):
    """Identify only this campaign's descendants by an unforgeable-in-session path token."""
    prefix=str(output.resolve())+':'
    owned=[]
    for p in psutil.process_iter(['pid']):
        try:
            if p.environ().get('S10B_JOB_TOKEN','').startswith(prefix):owned.append(p)
        except psutil.NoSuchProcess:pass
        except psutil.AccessDenied:
            continue # other users/projects are not ours
    for p in reversed(owned):
        try:p.kill()
        except psutil.NoSuchProcess:pass
    gone,alive=psutil.wait_procs(owned,timeout=2)
    assert all(p.status()==psutil.STATUS_ZOMBIE for p in alive),'owned subprocess survived cleanup'
    return [p.pid for p in owned]


def supervise(a,command_factory=None,grade_factory=None):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    lock=(out/'supervisor.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (out/'supervisor-status.json').exists() and load(out/'supervisor-status.json')['state']=='complete':return 0
    history=load(out/'supervisor-status.json').get('history',[]) if (out/'supervisor-status.json').exists() else []
    def status(state,**extra):save(out/'supervisor-status.json',dict(pid=os.getpid(),state=state,history=history,utc=utc(),**extra))
    common=['--max-parallel',str(a.max_parallel),'--raw-root',str(a.raw_root.resolve()),'--output',str(out),
        '--repo-root',str(a.repo_root.resolve()),'--base-src',str(a.base_src.resolve()),'--python',a.python]
    status('starting')
    while True:
        a.raw_root.mkdir(parents=True,exist_ok=True)
        if not storage_available(a.raw_root):status('storage_stop');return 2
        cleanup=cleanup_owned(out)
        cmd='resume' if (out/'measurement-freeze.json').exists() else 'run'
        command=command_factory(cmd) if command_factory else [a.python,'-B',str(HERE/'driver.py'),cmd,*common]
        with (out/'driver.log').open('ab',buffering=0) as log:
            p=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            status('running',driver_pid=p.pid,command=cmd,prior_orphans_killed=cleanup)
            def stop(sig,frame):
                p.send_signal(signal.SIGTERM)
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait()
                cleanup_owned(out);status('supervisor_stopped');raise SystemExit(128+sig)
            old={s:signal.signal(s,stop) for s in [signal.SIGTERM,signal.SIGINT]}
            try:code=p.wait()
            finally:
                for s,h in old.items():signal.signal(s,h)
        history.append(dict(command=cmd,driver_pid=p.pid,exit_code=code,end_utc=utc()))
        cleanup_owned(out)
        fp=out/'measurement-freeze.json'
        if not fp.exists():status('preflight_failed');return 1
        f=load(fp);ends=[load(x) for x in (out/'receipts').glob('*.end.json')]
        if len(ends)==len(f['jobs']):break
        if code==0 or not storage_available(a.raw_root) or any(r['state']=='interrupted_environment_storage' for r in ends):
            status('stopped_incomplete',ends=len(ends));return 2
        # No retries of started slots: driver.pending_jobs closes them as interrupted.
        time.sleep(1)
    command=grade_factory() if grade_factory else [a.python,'-B',str(HERE/'driver.py'),'grade',*common]
    with (out/'grade.log').open('ab') as log:code=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT)
    status('complete' if code==0 else 'grading_failed',ends=len(ends));return code


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--max-parallel',type=int,default=16);p.add_argument('--raw-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repo-root',type=Path,default=HERE.parents[5]);p.add_argument('--base-src',type=Path,default=Path(load(HERE/'source-hashes.json')['source_root']))
    p.add_argument('--python',default=sys.executable);a=p.parse_args()
    assert 1<=a.max_parallel<=len(os.sched_getaffinity(0));a.python=os.path.abspath(a.python)
    assert not a.raw_root.resolve().is_relative_to(a.repo_root.resolve()),'raw must be outside repo'
    return supervise(a)

if __name__=='__main__':raise SystemExit(main())
