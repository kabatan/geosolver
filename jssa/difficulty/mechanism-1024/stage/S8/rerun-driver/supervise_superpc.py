"""Foreground owner of the 320-slot rerun; resume only unstarted slots."""
import argparse
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import psutil
from measurement_common import HERE, load, save, utc


def cleanup_owned(raw_root):
    """Only solver roots whose explicit --output belongs to this raw directory."""
    killed=[]
    for p in psutil.process_iter(['cmdline']):
        try:
            cmd=p.info['cmdline'] or []
            if 'geosolver.application.cli' not in cmd or '--output' not in cmd:continue
            output=Path(cmd[cmd.index('--output')+1]).resolve()
            if not output.is_relative_to(raw_root.resolve()):continue
            for child in reversed(p.children(recursive=True)):
                try:child.kill()
                except psutil.NoSuchProcess:pass
            p.kill();killed.append(p.pid)
        except (psutil.Error,OSError,ValueError,IndexError):continue
    return killed


def supervise(args,command_factory=None,grade_factory=None):
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    lock=(out/'supervisor.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    status=out/'supervisor-status.json'
    if status.exists() and load(status)['state']=='complete':return 0
    shared=['--machine','superpc','--configs','N','C1','C2','C3','C4','C5','BASE',
            '--slots-file',str(args.slots_file.resolve()),'--output',str(out),
            '--raw-root',str(args.raw_root.resolve()),'--base-src',str(args.base_src.resolve()),
            '--repo-root',str(args.repo_root.resolve()),'--python',args.python,
            '--max-parallel',str(args.max_parallel)]
    command_factory=command_factory or (lambda mode:[args.python,'-B',str(HERE/'driver.py'),mode,*shared])
    grade_factory=grade_factory or (lambda:command_factory('grade'))
    history=[];save(status,dict(pid=os.getpid(),state='starting',utc=utc()))
    while True:
        if shutil.disk_usage('/tmp').free<6*1024**3:
            save(status,dict(pid=os.getpid(),state='storage_stop',history=history,utc=utc()));return 2
        killed=cleanup_owned(args.raw_root)
        mode='resume' if (out/'measurement-freeze.json').exists() else 'run'
        with (out/'driver.log').open('ab',buffering=0) as log:
            # Supervisor stays in the foreground and waits for this child.
            p=subprocess.Popen(command_factory(mode),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            save(status,dict(pid=os.getpid(),driver_pid=p.pid,state='running',command=mode,prior_orphans_killed=killed,history=history,utc=utc()))
            try:code=p.wait()
            except KeyboardInterrupt:
                p.terminate()
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait()
                cleanup_owned(args.raw_root)
                save(status,dict(pid=os.getpid(),state='interrupted',history=history,utc=utc()));return 130
        history.append(dict(command=mode,driver_pid=p.pid,exit_code=code,end_utc=utc()))
        frozen=out/'measurement-freeze.json'
        if not frozen.exists():
            save(status,dict(pid=os.getpid(),state='preflight_failed',history=history,utc=utc()));return 1
        f=load(frozen);ends=[load(x) for x in (out/'receipts').glob('*.end.json')]
        if len(ends)==len(f['jobs']):break
        if code==0 or any(x['state']=='interrupted_environment_storage' for x in ends):
            save(status,dict(pid=os.getpid(),state='stopped_incomplete',ends=len(ends),history=history,utc=utc()));return 2
        # Repeated resume/preflight failures need operator attention.
        if len(history)>=2 and all(x['exit_code']!=0 for x in history[-2:]) and mode=='resume':
            save(status,dict(pid=os.getpid(),state='repeated_driver_failure',ends=len(ends),history=history,utc=utc()));return 1
        time.sleep(1)
    with (out/'grade.log').open('ab',buffering=0) as log:
        code=subprocess.call(grade_factory(),stdout=log,stderr=subprocess.STDOUT)
    save(status,dict(pid=os.getpid(),state='complete' if code==0 else 'grading_failed',ends=len(ends),history=history,utc=utc()))
    return code


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=HERE.parent/'run-superpc-rerun')
    p.add_argument('--raw-root',type=Path,default=Path('/tmp/mechanism-S8-rerun-raw'))
    p.add_argument('--slots-file',type=Path,default=HERE.parent/'run-plan-rerun.json')
    p.add_argument('--base-src',type=Path,default=Path('/tmp/mechanism-7b-lkdjle5l/final'))
    p.add_argument('--repo-root',type=Path,default=HERE.parents[5])
    p.add_argument('--python',default='/home/kabatan/work/solver/.venv/bin/python')
    p.add_argument('--max-parallel',type=int,default=8)
    args=p.parse_args();assert 1<=args.max_parallel<=8
    return supervise(args)

if __name__=='__main__':sys.exit(main())
