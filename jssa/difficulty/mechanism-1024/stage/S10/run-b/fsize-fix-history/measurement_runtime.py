"""S6 FIFO/process-tree monitor adapted to parameterized S8 jobs and bounded raw files."""
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import threading
import time
import psutil
from measurement_common import HERE, load, save, sha, utc, progress


def environment(config, base_src, configs, inherited=None):
    env={k:v for k,v in (os.environ if inherited is None else inherited).items() if not k.startswith('GEOSOLVER_') and not k.startswith('PYTHON') and k not in ('SEARCH_MODE','S10B_JOB_TOKEN')}
    env.update(configs['thread_environment'])
    env.update(next(c['environment'] for c in configs['configurations'] if c['name']==config))
    env.update(PYTHONPATH=os.pathsep.join([str(HERE),str(base_src/'src')]), PYTHONDONTWRITEBYTECODE='1')
    # Prevent externally injected startup/profile code and hash randomization from leaking in.
    for k in ('PYTHONSTARTUP','PYTHONHOME','PYTHONINSPECT','PYTHONPROFILEIMPORTTIME'):
        env.pop(k,None)
    return env


def selected_environment(env):
    return {k:v for k,v in env.items() if k.startswith('GEOSOLVER_') or k in load(HERE/'configs.json')['thread_environment'] or k in ('PYTHONPATH','PYTHONDONTWRITEBYTECODE','SEARCH_MODE','S10B_JOB_TOKEN')}


def environment_matches(actual, expected):
    # Frozen solver injects these two runtime bookkeeping values in descendants.
    # Keep their raw values in receipts, but do not mistake them for ablations.
    internal = {'GEOSOLVER_MEMORY_LIMIT_BYTES', 'GEOSOLVER_SYMBOLIC_PARENT'}
    return {k:v for k,v in actual.items() if k not in internal} == expected


def storage_available(raw_root):
    return min(shutil.disk_usage('/tmp').free, shutil.disk_usage(raw_root).free) >= 6*1024**3


class ChunkLog:
    def __init__(self, root, name):
        self.root,self.name=root,name
        self.index=0;self.size=0;self.f=None
    def write(self,data):
        while data:
            if self.f is None:
                self.f=(self.root/f'{self.name}.{self.index:04d}').open('xb')
            b=data[:2_000_000-self.size];self.f.write(b);self.size+=len(b);data=data[len(b):]
            if self.size==2_000_000:
                self.f.close();self.f=None;self.size=0;self.index+=1
    def close(self):
        if self.f:self.f.close()
    def pump(self, pipe):
        try:
            while b:=pipe.read(65536):self.write(b)
        finally:
            pipe.close();self.close()


class Job:
    def __init__(self, spec, cpu, out, raw_root, freeze, command_override=None):
        self.spec,self.cpu,self.out,self.freeze=spec,cpu,out,freeze
        self.q=spec['queue_index'];self.base=out/'receipts'/f'{self.q:04d}'
        self.raw=raw_root/f'{self.q:04d}';self.raw.mkdir()
        self.nodes={};self.violations=set();self.peak_tree_rss=0
        self.start_utc=utc();self.proc=None;self.spawn_error=None
        self.env=environment(spec['configuration'],Path(freeze['base_src']),load(HERE/'configs.json'))
        self.env['S10B_JOB_TOKEN']=f'{out.resolve()}:{self.q}'
        solver=[freeze['python'],'-B',str(HERE/'solver_entry.py'),'solve',str(Path(freeze['repo_root'])/spec['dsl_path']),
                '--time-limit-seconds',str(spec['time_limit_seconds']),'--cores','1','--seed',str(spec['seed']),
                '--output',str(self.raw/'result.json')]
        self.command=[freeze['python'],'-B',str(HERE/'measurement_launch.py'),str(cpu),str(freeze['address_space_mib']),*(command_override or solver)]
        self.start_receipt=dict(**spec,start_utc=self.start_utc,cpu=cpu,command=self.command,
            actual_environment=selected_environment(self.env), source_hash=freeze['source_hash'],
            python_sha256=freeze['python_sha256'],result_path=str(self.raw/'result.json'),
            load=list(os.getloadavg()), available_memory_bytes=psutil.virtual_memory().available,
            raw_directory=str(self.raw))
        save(Path(str(self.base)+'.start.json'),self.start_receipt,True)
        progress(out,f"START queue={self.q} {spec['case_id']} seed={spec['seed']} {spec['configuration']} cpu={cpu} load={self.start_receipt['load']}")
        self.telemetry=ChunkLog(self.raw,'process-samples.jsonl')
        self.pumps=[];self.t0=time.monotonic();self.deadline=self.t0+spec['time_limit_seconds'];self.next_sample=self.t0
        try:
            previous_affinity=os.sched_getaffinity(0)
            try:
                os.sched_setaffinity(0,{cpu})
                self.proc=subprocess.Popen(self.command,cwd=freeze['repo_root'],env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            finally:
                os.sched_setaffinity(0,previous_affinity)
            for name,pipe in [('stdout.log',self.proc.stdout),('stderr.log',self.proc.stderr)]:
                t=threading.Thread(target=ChunkLog(self.raw,name).pump,args=(pipe,),daemon=True);t.start();self.pumps.append(t)
        except Exception as e:self.spawn_error=f'{type(e).__name__}: {e}'

    def processes(self):
        processes=[]
        if self.proc:
            try:
                root=psutil.Process(self.proc.pid);processes=[root,*root.children(recursive=True)]
            except psutil.Error:pass
        for n in list(self.nodes.values()):
            try:
                p=psutil.Process(n['pid'])
                if p.create_time()==n['create_time'] and all(p.pid!=x.pid for x in processes):processes.append(p)
            except psutil.Error:pass
        return processes

    def sample(self):
        rss=0;samples=[];expected=selected_environment(self.env)
        for p in self.processes():
            try:
                with p.oneshot():
                    key=f'{p.pid}:{p.create_time()}';mem=p.memory_info().rss;rss+=mem
                    affinity=p.cpu_affinity();threads=p.threads();usage=p.cpu_times()
                    if key not in self.nodes:
                        actual=selected_environment(p.environ())
                        self.nodes[key]=dict(pid=p.pid,create_time=p.create_time(),ppid=p.ppid(),name=p.name(),actual_environment=actual,first_seen_utc=utc(),affinity_sets=[],thread_affinity_sets=[],peak_rss_bytes=0,max_os_threads=0)
                        if not environment_matches(actual,expected):self.violations.add(f'{key}:environment')
                    n=self.nodes[key]
                    for field,value in [('affinity_sets',affinity)]:
                        if value not in n[field]:n[field].append(value)
                    if affinity!=[self.cpu]:self.violations.add(f'{key}:affinity')
                    for t in threads:
                        try:
                            ta=sorted(os.sched_getaffinity(t.id))
                            if ta not in n['thread_affinity_sets']:n['thread_affinity_sets'].append(ta)
                            if ta!=[self.cpu]:self.violations.add(f'{key}:thread_affinity')
                        except ProcessLookupError:pass
                    n['peak_rss_bytes']=max(mem,n['peak_rss_bytes']);n['max_os_threads']=max(len(threads),n['max_os_threads'])
                    n['cpu_seconds']=usage.user+usage.system;n['last_seen_utc']=utc()
                    samples.append(dict(pid=p.pid,rss_bytes=mem,os_threads=len(threads),cpu_seconds=n['cpu_seconds']))
            except (psutil.NoSuchProcess,psutil.ZombieProcess):pass
            except (psutil.AccessDenied,PermissionError):self.violations.add(f'{p.pid}:monitor_unavailable')
        self.peak_tree_rss=max(rss,self.peak_tree_rss)
        if rss>self.freeze['memory_mib']*1024**2:self.violations.add('tree_memory_limit')
        self.telemetry.write((json.dumps(dict(utc=utc(),processes=samples))+'\n').encode())
        self.next_sample=time.monotonic()+.5

    def cleanup(self):
        begin=time.monotonic();self.sample()
        for p in reversed(self.processes()):
            try:p.kill()
            except psutil.Error:pass
        if self.proc:
            try:os.killpg(self.proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            try:self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:self.violations.add('cleanup_exceeded_2_seconds')
        for t in self.pumps:t.join(timeout=2)
        if any(t.is_alive() for t in self.pumps):self.violations.add('log_pipe_not_closed')
        return time.monotonic()-begin

    def finish(self,state,wall):
        cleanup=self.cleanup();self.telemetry.close()
        files={p.name:dict(path=str(p),size_bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(self.raw.iterdir()) if p.is_file()}
        # Only explicit infrastructure errors justify excluding a finished slot.
        for p in self.raw.iterdir():
            if p.is_file() and (p.name.startswith('stderr.log') or p.name=='result.json'):
                body=p.read_text(errors='replace')
                if 'Disk quota exceeded' in body or 'No space left on device' in body:
                    state='interrupted_environment_storage'
                    self.violations.add('explicit_storage_exhaustion')
        if any(v['size_bytes']>=3_000_000 for v in files.values()):raise RuntimeError('oversize raw file')
        r=dict(**self.spec,state=state,cpu=self.cpu,pid=self.proc.pid if self.proc else None,start_utc=self.start_utc,end_utc=utc(),
            wall_seconds=wall,total_wall_through_cleanup_seconds=time.monotonic()-self.t0,cleanup_seconds=cleanup,
            exit_code=self.proc.returncode if self.proc else None,spawn_error=self.spawn_error,result_path=str(self.raw/'result.json'),
            files=files,source_hash=self.freeze['source_hash'],python_sha256=self.freeze['python_sha256'],
            actual_environment=self.start_receipt['actual_environment'],peak_tree_rss_bytes=self.peak_tree_rss,
            tree_cpu_seconds_observed=sum(n.get('cpu_seconds',0) for n in self.nodes.values()),
            observed_processes=list(self.nodes.values()),resource_violations=sorted(self.violations))
        save(Path(str(self.base)+'.end.json'),r,True)
        progress(self.out,f"END queue={self.q} {self.spec['case_id']} {self.spec['configuration']} seed={self.spec['seed']} state={state} wall={wall:.6f} resource_violations={len(self.violations)}; 未採点")
        return r


def pending_jobs(jobs,out):
    pending=[]
    for j in jobs:
        base=out/'receipts'/f"{j['queue_index']:04d}"
        end=Path(str(base)+'.end.json');start=Path(str(base)+'.start.json')
        if end.exists():
            r=load(end)
            assert all(r[k]==v for k,v in j.items()), 'receipt job mismatch'
            assert start.exists(), 'end without start'
            for f in r.get('files',{}).values():assert sha(f['path'])==f['sha256'], 'raw changed'
        elif start.exists():
            r=load(start)
            assert all(r[k]==v for k,v in j.items()), 'start job mismatch'
            save(end,dict(**j,state='interrupted_prior_start_no_retry',start_utc=r['start_utc'],end_utc=utc(),wall_seconds=None,
                          exit_code=None,files={},resource_violations=[],result_path=r['result_path']),True)
            progress(out,f"中断 queue={j['queue_index']}: startのみ。再試行せず、結果/費用に数えない。")
        else:pending.append(j)
    return pending


def execute(jobs,out,freeze,max_parallel,stop=lambda:False,command_factory=None):
    cpus=freeze['slot_cpus'][:max_parallel];pending=pending_jobs(jobs,out)
    active={};i=0;max_active=0;last_heartbeat=time.monotonic();storage_stop=False
    progress(out,f'FIFO開始 pending={len(pending)} cpus={cpus} max_parallel={max_parallel}')
    try:
        while active or i<len(pending):
            if stop():
                for job in active.values():job.finish('interrupted',time.monotonic()-job.t0)
                active.clear();progress(out,'停止要求: 中断枠を記録。未開始はresume可能。');return False
            for cpu,job in list(active.items()):
                now=time.monotonic();state=None
                if job.spawn_error:state='spawn_failure'
                elif now>=job.deadline:state='timeout'
                elif job.proc.poll() is not None:state='completed'
                elif now>=job.next_sample:
                    job.sample()
                    if 'tree_memory_limit' in job.violations:state='memory_limit'
                if state:
                    receipt=job.finish(state,180.0 if state=='timeout' and job.spec['time_limit_seconds']==180 else time.monotonic()-job.t0)
                    if receipt['state']=='interrupted_environment_storage':
                        storage_stop=True
                        progress(out,'環境停止: 明示的quota/no-spaceエラー。新規開始なし・中断枠の再試行なし。')
                    del active[cpu]
            for cpu in cpus:
                if cpu not in active and i<len(pending) and not storage_stop:
                    if not storage_available(freeze['raw_root']):
                        storage_stop=True
                        progress(out,'環境停止: /tmpまたはrawの空きが6GiB未満。新規枠を開始しない。稼働枠終了後停止。')
                        break
                    j=pending[i]
                    active[cpu]=Job(j,cpu,out,Path(freeze['raw_root']),freeze,command_factory(j) if command_factory else None)
                    i+=1;max_active=max(max_active,len(active))
            if storage_stop and not active:return False
            now=time.monotonic()
            if now-last_heartbeat>=30:
                n=len(list((out/'receipts').glob('*.end.json')))
                progress(out,f'稼働中 receipts={n}/{len(jobs)} active={len(active)} load={list(os.getloadavg())}')
                print(f'RECEIPTS {n}/{len(jobs)} active={len(active)}',flush=True);last_heartbeat=now
            time.sleep(.015)
    finally:
        for job in active.values():
            if not Path(str(job.base)+'.end.json').exists():job.finish('interrupted_driver_exception',time.monotonic()-job.t0)
    starts=[load(p) for p in (out/'receipts').glob('*.start.json')]
    order=[s['queue_index'] for s in sorted(starts,key=lambda s:s['start_utc'])]
    assert order==[j['queue_index'] for j in jobs if j['queue_index'] in set(order)],'FIFO violation'
    save(out/f'execution-session-{time.time_ns()}.json',dict(ended_utc=utc(),jobs=len(jobs),max_active=max_active,slot_cpus=cpus,fifo_start_order_verified=True),True)
    return True
