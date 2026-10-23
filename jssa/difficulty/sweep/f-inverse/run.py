"""Run the fixed Q43f inputs through the unmodified production CLI, at most 3 streams."""
from __future__ import annotations
import os
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[k] = '1'
import argparse
import hashlib
import json
import queue
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import psutil
from geosolver.runtime.integrity import source_tree_hash, verify_engine_lock
from geosolver.platform.processes import spawn_process, terminate_process_tree

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, default=str)+'\n')
    tmp.replace(path)

def choose_cpus():
    eligible = psutil.Process().cpu_affinity()
    usage = psutil.cpu_percent(interval=1, percpu=True)
    groups = {}
    for cpu in eligible:
        topology = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        key = tuple((topology/n).read_text().strip() for n in ('physical_package_id','core_id'))
        groups.setdefault(key, []).append(cpu)
    ranked = sorted(groups.values(), key=lambda cpus: sum(usage[c] for c in cpus))
    return [min(cpus, key=lambda c: usage[c]) for cpus in ranked[:3]], usage

def run_one(task, cpu, manifest, raw):
    inp, seed, ordinal = task
    folder = raw/'runs'/inp['id']/inp['arm']
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder/f'{seed}.receipt.json'
    if receipt.exists():
        return json.loads(receipt.read_text())
    output = folder/f'{seed}.solver.json'
    if output.exists():
        raise RuntimeError(f'output without receipt: preserve and audit {output}')
    environment = os.environ.copy()
    environment.update(PYTHONPATH=os.pathsep.join([str(ROOT/'src'), str(ROOT)]), PYTHONHASHSEED='0')
    command = [sys.executable,'-m','geosolver.application.cli','solve',str(HERE/inp['path']),
               '--time-limit-seconds',str(manifest['seconds_per_run']),'--cores','1',
               '--seed',str(seed),'--output',str(output)]
    start = time.monotonic()
    utc = datetime.now(timezone.utc).isoformat()
    load = os.getloadavg()
    timed_out, resource_stop, peak_rss, cpu_sec = False, False, 0, 0.
    with (folder/f'{seed}.stdout.txt').open('w') as stdout, (folder/f'{seed}.stderr.txt').open('w') as stderr:
        process = spawn_process(command,cwd=ROOT,env=environment,stdout=stdout,stderr=stderr)
        psutil.Process(process.pid).cpu_affinity([cpu])
        cpu_max = {}
        while process.poll() is None:
            try:
                proc = psutil.Process(process.pid)
                allp = [proc,*proc.children(recursive=True)]
            except psutil.Error:
                allp = []
            rss = 0
            for proc in allp:
                try:
                    rss += proc.memory_info().rss
                    t = proc.cpu_times()
                    cpu_max[proc.pid] = max(cpu_max.get(proc.pid,0),t.user+t.system)
                except psutil.Error:
                    pass
            peak_rss = max(peak_rss,rss)
            if rss > 3*1024**3:
                resource_stop = True
                terminate_process_tree(process,grace_seconds=.2)
                break
            if time.monotonic()-start > manifest['seconds_per_run']+8:
                timed_out = True
                terminate_process_tree(process,grace_seconds=.2)
                break
            time.sleep(.25)
        cpu_sec = sum(cpu_max.values())
        terminate_process_tree(process,grace_seconds=.1)
    elapsed = time.monotonic()-start
    result = json.loads(output.read_text()) if output.exists() else {}
    identity = result.get('engine',{})
    info = result.get('diagnostics',{}).get('process_info',{})
    issues = []
    if identity and identity.get('source_hash') != manifest['source_hash']:
        issues.append('source_hash_mismatch')
    if info and info.get('import_root') != str(ROOT/'src/geosolver'):
        issues.append('import_root_mismatch')
    if info and info.get('cpu_affinity') != [cpu]:
        issues.append('affinity_mismatch')
    status = ('external_timeout' if timed_out else 'memory_limit' if resource_stop
              else result.get('status','artifact_missing'))
    record = dict(id=inp['id'],group=inp['group'],arm=inp['arm'],seed=seed,ordinal=ordinal,
                  started_utc=utc,assigned_cpu=cpu,status=status,returncode=process.returncode,
                  elapsed_seconds=elapsed,solver_elapsed_seconds=result.get('elapsed_seconds'),
                  external_timeout=timed_out,memory_limit=resource_stop,peak_rss_bytes=peak_rss,
                  sampled_cpu_seconds=cpu_sec,load_start=load,load_end=os.getloadavg(),
                  input_sha256=sha(HERE/inp['path']),source_hash=manifest['source_hash'],
                  executed_source_hash=identity.get('source_hash'),executed_import_root=info.get('import_root'),
                  contract_issues=issues,raw_path=str(output),raw_sha256=sha(output) if output.exists() else None,
                  answer_count=len(result.get('answers',[])),termination=result.get('termination_reason'))
    save(receipt,record)
    return record

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    manifest=json.loads((HERE/'manifest.json').read_text())
    amendment=json.loads((HERE/'execution-amendment.json').read_text())
    manifest['seconds_per_run']=amendment['seconds_per_run']
    manifest['raw_directory']=amendment['raw_directory']
    assert source_tree_hash()==manifest['source_hash'] and verify_engine_lock()[0]
    assert not subprocess.check_output(['git','diff',manifest['frozen_commit'],'--','src'],cwd=ROOT)
    for inp in manifest['inputs']: assert sha(HERE/inp['path'])==inp['sha256']
    raw=Path(manifest['raw_directory']); raw.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(raw/'campaign.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    tasks=[]
    # Interleave problem groups and rotate arm order across seeds, before reading any outcomes.
    cases=list(dict.fromkeys(i['id'] for i in manifest['inputs']))
    for seed in manifest['solver_seeds']:
        ordered=sorted(cases,key=lambda s:hashlib.sha256(f'order:{seed}:{s}'.encode()).hexdigest())
        for cid in ordered:
            arms=[i for i in manifest['inputs'] if i['id']==cid]
            offset=seed%len(arms); arms=arms[offset:]+arms[:offset]
            for inp in arms:
                tasks.append((inp,seed,len(tasks)))
    if args.limit: tasks=tasks[:args.limit]
    cpus,usage=choose_cpus()
    cpupool=queue.Queue()
    for cpu in cpus:cpupool.put(cpu)
    start_record=dict(utc=datetime.now(timezone.utc).isoformat(),cpus=cpus,cpu_usage=usage,
                      max_parallel=3,pid=os.getpid(),manifest_sha256=sha(HERE/'manifest.json'),
                      code_sha256={p.name:sha(p) for p in HERE.glob('*.py')},tasks=len(tasks),
                      source_hash=source_tree_hash(),python=sys.executable,load=os.getloadavg())
    save(raw/f'start-{time.time_ns()}.json',start_record)
    if not (HERE/'execution-start-180.json').exists():save(HERE/'execution-start-180.json',start_record)
    print(json.dumps(dict(event='start',tasks=len(tasks),cpus=cpus,raw=str(raw))),flush=True)
    def worker(task):
        cpu=cpupool.get()
        try:return run_one(task,cpu,manifest,raw)
        finally:cpupool.put(cpu)
    done=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(worker,t) for t in tasks]
        for future in as_completed(futures):
            row=future.result();done.append(row)
            print(json.dumps({k:row[k] for k in ('id','arm','seed','status','elapsed_seconds','answer_count')}|dict(done=len(done),total=len(tasks))),flush=True)
    save(raw/'completion.json',dict(utc=datetime.now(timezone.utc).isoformat(),completed=len(done),source_hash=source_tree_hash()))

if __name__=='__main__':main()
