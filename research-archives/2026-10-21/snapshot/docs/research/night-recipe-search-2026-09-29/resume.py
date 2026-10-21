"""Operational continuation: guarded admission and recorded live GPU policy.

No training data, optimizer, decoding, or experiment selection is changed.
The original frozen campaign implementation still verifies its input hashes and
runs the original exclusive GPU guard. The live monitor follows the explicit
runtime policy, including observe-only mode when the user handles contention.
"""
import json,os,signal,subprocess,time
from pathlib import Path
import campaign as c
import timing
import gpu_priority
original_run_gpu=c.run_gpu
GPU_QUIET_SECONDS=60
def install_shutdown_handlers():
    """Let the owned-job cleanup run on launcher termination as on Ctrl-C."""
    def shutdown(signum, frame):
        raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,shutdown)
    signal.signal(signal.SIGHUP,shutdown)
def run_without_deadline(label,cmd,inputs):
    """Same guard/commands/receipts as frozen runner, without wall-clock timeout."""
    c.verify_manifest()
    inv=c.inventory();log=c.RUN/'logs'/f'{label}.log';log.parent.mkdir(exist_ok=True)
    guard=[str(c.PY),str(c.GPU),'--runtime',str(c.SHARED),'--label','night20260929-'+label,'--recovery-libs','/usr/lib/x86_64-linux-gnu','--desktop-inventory',str(inv)]
    for p in inputs:guard+=['--input',str(p)]
    guard+=['--']+list(map(str,cmd));start=time.time()
    c.status(state='running',job=label,command=cmd,start_unix=start,timing_policy='complete_original_plan')
    with log.open('x') as out:
        proc=subprocess.Popen(guard,stdout=out,stderr=subprocess.STDOUT,start_new_session=True,cwd=c.ROOT)
        try:
            c.write(c.RUN/'active-process.json',dict(pid=proc.pid,pgid=proc.pid,job=label,deadline_unix=None,owned_by='night_recipe_search_20260929'))
            rc=proc.wait()
        except BaseException as exc:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait()
            c.status(state='interrupted',job=label,error=repr(exc),elapsed_seconds=time.time()-start)
            c.write(c.RUN/'active-process.json',dict(active=False,last_job=label,interrupted=True))
            raise
    c.status(state='job_complete' if rc==0 else 'job_failed',job=label,returncode=rc,elapsed_seconds=time.time()-start)
    c.write(c.RUN/'active-process.json',dict(active=False,last_job=label))
    if rc:raise RuntimeError(f'GPU job {label} failed: {rc}; inspect and preserve before retry')
def desktop_inventory(observed=None):
    p=c.RUN/'desktop-inventory.json'
    c.write(p,gpu_priority.snapshot() if observed is None else observed)
    return p
def wait_and_run(label,cmd,inputs):
    prior=None;last_report=0;free_since=None
    while True:
        limit=c.deadline()
        assert limit is None or time.time()<limit-60,'Hard deadline reached while waiting for GPU'
        assert not (c.RUN/'campaign-complete.json').exists(),'Campaign already complete'
        observed=gpu_priority.snapshot();desktop_inventory(observed)
        competing=sorted({r['pid'] for r in observed['competing_processes']})
        if not competing:
            timing.end_wait()
            if free_since is None:
                free_since=time.monotonic()
                c.status(state='waiting_for_gpu_quiet_period',job=label,
                         quiet_seconds=GPU_QUIET_SECONDS,
                         note='Require continuous absence of competing compute; this quiet period is not credited as GPU contention')
            if time.monotonic()-free_since>=GPU_QUIET_SECONDS:
                break
        else:
            free_since=None
            timing.begin_wait()
            if competing!=prior or time.time()-last_report>=60:
                effective=timing.snapshot()
                c.status(state='waiting_for_gpu',job=label,competing_pids=competing,
                         competing_processes=observed['competing_processes'],
                         deadline_utc=effective['deadline_utc'],credited_wait_seconds=effective['credited_wait_seconds'],
                         note=effective['policy'])
                prior=competing;last_report=time.time()
        time.sleep(15 if limit is None else min(15,max(0,limit-time.time()-60)))
    with gpu_priority.watch(label):
        runner=run_without_deadline if c.deadline() is None else original_run_gpu
        runner(label,cmd,inputs)
c.inventory=desktop_inventory
c.run_gpu=wait_and_run
c.deadline=timing.deadline
if __name__=='__main__':
    install_shutdown_handlers()
    c.main()
