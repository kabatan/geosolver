"""Frozen FIFO full-process S6 measurement, at most 12 distinct pinned CPU slots.

Usage: <fixed-python> -B driver.py prepare | run
No solver calls during prepare; no references are passed to a solver process.
"""
import fcntl
import importlib.metadata
import json
import os
import platform
import signal
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import psutil
from common import (HERE, IMPL, PYTHON, REPO, S6, SOURCE, THREADS, load, progress,
                    save, sha, source_manifest, utc)

MEASUREMENT_FILES = ['common.py', 'driver.py', 'grade.py', 'test_contract.py',
                     'grading-policy.md', 'references.json', 'preflight.json']
WATCH_ENV = set(THREADS) | {'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE'}
STOP = False

def check_preparation():
    p = load(S6 / 'preparation-hashes.json')
    for category in ['files_sha256', 'input_occurrences_sha256', 'protected_source_files_sha256',
                     'reference_provenance_sha256']:
        for relative, expected in p[category].items():
            path = Path(relative) if relative.startswith('/') else REPO / relative
            assert sha(path) == expected, ('preparation mismatch', str(path))
    source, files = source_manifest()
    saved = load(S6 / 'source-hashes.json')
    assert source == SOURCE == p['source_hash'] == saved['source_hash']
    assert files == saved['files_sha256'], 'source file inventory changed'
    assert sha(IMPL / 'dependency-lock.json') == p['dependency_lock_sha256']
    assert str(Path(PYTHON).resolve()) == p['planned_solver_python']['resolved']
    assert sha(Path(PYTHON).resolve()) == p['planned_solver_python']['sha256']
    assert Path(sys.executable).resolve() == Path(PYTHON).resolve(), 'use fixed Python'
    assert sha(REPO / 'uv.lock') == load(IMPL / 'dependency-lock.json')['uv_lock_sha256']
    locked = load(IMPL / 'dependency-lock.json')['packages']
    actual, missing = {}, []
    for name, expected in locked.items():
        try:
            actual[name] = importlib.metadata.version(name)
            assert actual[name] == expected, ('dependency mismatch', name, actual[name], expected)
        except importlib.metadata.PackageNotFoundError:
            # colorama is the sole absent Windows-only dependency on this Linux host.
            assert name == 'colorama' and sys.platform == 'linux', ('missing dependency', name)
            missing.append(name)
    jobs = load(S6 / 'run-plan.json')['jobs']
    targets = load(S6 / 'targets.json')['targets']
    assert len(jobs) == 264 and len(targets) == 44
    assert [t['identity'] for t in targets] == sorted(t['identity'] for t in targets)
    for i, t in enumerate(targets):
        assert sha(REPO / t['dsl_path']) == t['sha256']
        for j, seed in enumerate([501, 502, 503]):
            modes = ['T2','T1'] if (i+j)%2 == 0 else ['T1','T2']
            for k, mode in enumerate(modes):
                q = jobs[6*i+2*j+k]
                assert q['queue_index'] == 6*i+2*j+k
                assert (q['identity'], q['case_id'], q['seed'], q['configuration']) == (t['identity'],t['case_id'],seed,mode)
                assert q['input_sha256'] == t['sha256'] and q['dsl_path'] == t['dsl_path']
                assert (q['time_limit_seconds'],q['cores'],q['internal_threads']) == (180,1,1)
    split = load(S6 / 'same-group-split.json')
    assert split['groups_sha256'] == sha(S6 / 'groups.json')
    assert len(split['same_formula_18']) == 18 and len(split['distance_only_differs_15']) == 15
    assert set(split['same_formula_18']).isdisjoint(split['distance_only_differs_15'])
    assert set(split['same_formula_18'] + split['distance_only_differs_15']) == set(load(S6 / 'groups.json')['groups']['同式群'])
    return dict(checked_utc=utc(), all_preparation_hashes_match=True, source_hash=source,
        python=dict(path=PYTHON, resolved=str(Path(PYTHON).resolve()), sha256=sha(Path(PYTHON).resolve()), version=sys.version),
        dependency_lock_sha256=sha(IMPL / 'dependency-lock.json'), uv_lock_sha256=sha(REPO / 'uv.lock'),
        installed_dependencies=actual, absent_platform_only_dependencies=missing,
        platform=platform.platform(), host=platform.node(), eligible_cpus=sorted(os.sched_getaffinity(0)))

def prepare():
    assert not (HERE / 'freeze.json').exists(), 'freeze exists; never overwrite'
    result = check_preparation()
    from grade import freeze_references
    references = freeze_references()
    assert len(references['cases']) == 44
    assert {k for k,v in references['cases'].items() if not v['available']} == {'HMMT-2013-FEB-TEAM-03','HMMT-2022-FEB-TEAM-03'}
    save(HERE / 'references.json', references, exclusive=True)
    save(HERE / 'preflight.json', result, exclusive=True)
    raw = Path('/tmp') / ('mechanism-S6-prereg13-raw-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    raw.mkdir()
    freeze = dict(created_utc=utc(), source_hash=SOURCE, raw_root=str(raw),
        measurement_files_sha256={f:sha(HERE / f) for f in MEASUREMENT_FILES},
        preparation_sha256=sha(S6 / 'preparation-hashes.json'),
        same_group_split_sha256=sha(S6 / 'same-group-split.json'),
        run_plan_sha256=sha(S6 / 'run-plan.json'),
        intent='User-authorized preregistration 13 execution; README future-driver specification; no commit/push',
        no_retries=True, no_extra_seeds=True, reference_solver_separation=True)
    save(HERE / 'freeze.json', freeze, exclusive=True)
    progress('実行前固定完了。準備・ソース・入力・Python・依存lock照合、採点コード/独立参照集合hashをfreeze.jsonに固定。新規参照計算なし。')
    print(json.dumps(freeze, ensure_ascii=False))

def environment(mode):
    env = {k:v for k,v in os.environ.items() if not k.startswith('GEOSOLVER_')}
    env.update(THREADS, PYTHONPATH='/tmp/s3-impl/src', PYTHONDONTWRITEBYTECODE='1')
    if mode == 'T1':
        env['GEOSOLVER_S3_TANGENCY_MODE'] = 'T1'
    return env

def selected_environment(env):
    return {k:v for k,v in env.items() if k in WATCH_ENV or k.startswith('GEOSOLVER_')}

def signal_stop(signum, frame):
    global STOP
    STOP = True

class Job:
    def __init__(self, spec, cpu, raw_root, freeze):
        self.spec, self.cpu = spec, cpu
        self.q = spec['queue_index']
        self.base = HERE / 'receipts' / f'{self.q:03d}'
        self.raw = raw_root / f'{self.q:03d}'
        self.raw.mkdir()
        self.nodes, self.violations = {}, set()
        self.peak_tree_rss = 0
        self.start_utc = utc()
        env = environment(spec['configuration'])
        self.command = ['/usr/bin/taskset', '-c', str(cpu), PYTHON, '-B', '-m',
            'geosolver.application.cli', 'solve', str(REPO / spec['dsl_path']),
            '--time-limit-seconds', '180', '--cores', '1', '--seed', str(spec['seed']),
            '--output', str(self.raw / 'result.json')]
        self.start_receipt = dict(**spec, start_utc=self.start_utc, cpu=cpu, command=self.command,
            actual_environment=selected_environment(env), source_hash=SOURCE,
            python_sha256=freeze['python_sha256'], reference_set_sha256=freeze['reference_hashes'][spec['case_id']],
            result_path=str(self.raw / 'result.json'), raw_directory=str(self.raw))
        save(Path(str(self.base) + '.start.json'), self.start_receipt, exclusive=True)
        self.stdout = (self.raw / 'stdout.log').open('xb')
        self.stderr = (self.raw / 'stderr.log').open('xb')
        self.telemetry = (self.raw / 'process-samples.jsonl').open('x')
        self.t0 = time.monotonic()
        self.deadline = self.t0 + 180
        self.proc = None
        self.spawn_error = None
        try:
            self.proc = subprocess.Popen(self.command, cwd=REPO, env=env,
                stdout=self.stdout, stderr=self.stderr, start_new_session=True)
        except Exception as e:
            self.spawn_error = f'{type(e).__name__}: {e}'
        self.next_sample = self.t0
        print(f"START {self.q:03d} {spec['identity']} seed={spec['seed']} {spec['configuration']} cpu={cpu}", flush=True)

    def sample(self):
        if self.proc is None:
            return
        try:
            root = psutil.Process(self.proc.pid)
            processes = [root, *root.children(recursive=True)]
        except psutil.Error:
            processes = []
        # Retain known descendants even if reparented or in a separate process group.
        for node in list(self.nodes.values()):
            try:
                p = psutil.Process(node['pid'])
                if p.create_time() == node['create_time'] and all(p.pid != x.pid for x in processes):
                    processes.append(p)
            except psutil.Error:
                pass
        rss, samples = 0, []
        for p in processes:
            try:
                with p.oneshot():
                    key = f'{p.pid}:{p.create_time()}'
                    affinity = p.cpu_affinity()
                    mem = p.memory_info().rss
                    rss += mem
                    threads = p.threads()
                    usage = p.cpu_times()
                    node = self.nodes.get(key)
                    if node is None:
                        actual = selected_environment(p.environ())
                        node = dict(pid=p.pid, ppid=p.ppid(), create_time=p.create_time(),
                            name=p.name(), cmdline=p.cmdline(), actual_environment=actual,
                            first_seen_utc=utc(), affinity_sets=[], peak_rss_bytes=0, max_os_threads=0,
                            thread_affinity_sets=[])
                        self.nodes[key] = node
                        for k,v in THREADS.items():
                            if actual.get(k) != v:
                                self.violations.add(f'{key}:thread_env:{k}')
                        expected = 'T1' if self.spec['configuration'] == 'T1' else None
                        if actual.get('GEOSOLVER_S3_TANGENCY_MODE') != expected:
                            self.violations.add(f'{key}:mode')
                        if any(k.startswith('GEOSOLVER_ABLATE_') for k in actual):
                            self.violations.add(f'{key}:ablation')
                        if actual.get('PYTHONPATH') != '/tmp/s3-impl/src':
                            self.violations.add(f'{key}:pythonpath')
                    if affinity not in node['affinity_sets']:
                        node['affinity_sets'].append(affinity)
                    if affinity != [self.cpu]:
                        self.violations.add(f'{key}:affinity:{affinity}')
                    for thread in threads:
                        try:
                            ta = sorted(os.sched_getaffinity(thread.id))
                            if ta not in node['thread_affinity_sets']:
                                node['thread_affinity_sets'].append(ta)
                            if ta != [self.cpu]:
                                self.violations.add(f'{key}:thread_affinity:{ta}')
                        except ProcessLookupError:
                            pass
                    node['peak_rss_bytes'] = max(node['peak_rss_bytes'], mem)
                    node['max_os_threads'] = max(node['max_os_threads'], len(threads))
                    node['last_seen_utc'] = utc()
                    node['cpu_seconds'] = usage.user + usage.system
                    samples.append(dict(pid=p.pid, ppid=node['ppid'], affinity=affinity,
                        rss_bytes=mem, os_threads=len(threads), cpu_seconds=node['cpu_seconds']))
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                pass
            except (psutil.AccessDenied, PermissionError) as e:
                self.violations.add(f'{p.pid}:monitor_unavailable:{type(e).__name__}')
        self.peak_tree_rss = max(self.peak_tree_rss, rss)
        self.telemetry.write(json.dumps(dict(monotonic=time.monotonic(), processes=samples)) + '\n')
        self.next_sample = time.monotonic() + .5

    def cleanup(self):
        begin = time.monotonic()
        self.sample()
        owned = []
        if self.proc is not None:
            try:
                root = psutil.Process(self.proc.pid)
                owned += root.children(recursive=True) + [root]
            except psutil.Error:
                pass
            for n in self.nodes.values():
                try:
                    p = psutil.Process(n['pid'])
                    if p.create_time() == n['create_time'] and all(p.pid != x.pid for x in owned):
                        owned.append(p)
                except psutil.Error:
                    pass
            # Terminate at the deadline without a grace period that allows more computation.
            for p in reversed(owned):
                try:
                    p.kill()
                except psutil.Error:
                    pass
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                self.proc.wait(timeout=max(0, 2 - (time.monotonic() - begin)))
            except subprocess.TimeoutExpired:
                self.violations.add('cleanup_exceeded_2_seconds')
        return time.monotonic() - begin

    def finish(self, state, wall):
        cleanup = self.cleanup()
        for stream in [self.stdout, self.stderr, self.telemetry]:
            stream.close()
        files = {p.name:dict(path=str(p), size_bytes=p.stat().st_size, sha256=sha(p))
                 for p in sorted(self.raw.iterdir()) if p.is_file()}
        r = dict(**self.spec, state=state, cpu=self.cpu, pid=self.proc.pid if self.proc else None,
            start_utc=self.start_utc, end_utc=utc(), start_monotonic=self.t0,
            deadline_monotonic=self.deadline, wall_seconds=wall, cleanup_seconds=cleanup,
            exit_code=self.proc.returncode if self.proc else None, spawn_error=self.spawn_error,
            result_eligible=state == 'completed' and wall < 180 and not self.violations,
            result_path=str(self.raw / 'result.json'), files=files,
            source_hash=SOURCE, input_sha256_verified=self.spec['input_sha256'],
            actual_environment=self.start_receipt['actual_environment'],
            reference_set_sha256=self.start_receipt['reference_set_sha256'],
            python_sha256=self.start_receipt['python_sha256'],
            peak_tree_rss_bytes=self.peak_tree_rss, observed_processes=list(self.nodes.values()),
            resource_violations=sorted(self.violations))
        save(Path(str(self.base) + '.end.json'), r, exclusive=True)
        progress(f"完了 {self.q+1:03d}/264 queue={self.q}: {self.spec['case_id']} seed={self.spec['seed']} {self.spec['configuration']} state={state}, wall={wall:.6e}s, resource_violations={len(self.violations)}。未採点。")
        print(f"END {self.q:03d} state={state} wall={wall:.3f} violations={len(self.violations)}", flush=True)
        return r

def run():
    lock = (HERE / 'campaign.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    freeze = load(HERE / 'freeze.json')
    for f,h in freeze['measurement_files_sha256'].items():
        assert sha(HERE / f) == h, ('frozen file changed', f)
    assert freeze['preparation_sha256'] == sha(S6 / 'preparation-hashes.json')
    assert freeze['same_group_split_sha256'] == sha(S6 / 'same-group-split.json')
    assert freeze['run_plan_sha256'] == sha(S6 / 'run-plan.json')
    check = check_preparation()
    freeze['python_sha256'] = check['python']['sha256']
    freeze['reference_hashes'] = {k:v['set_sha256'] for k,v in load(HERE / 'references.json')['cases'].items()}
    cpus = sorted(os.sched_getaffinity(0))[:12]
    assert cpus
    raw = Path(freeze['raw_root'])
    (HERE / 'receipts').mkdir(exist_ok=True)
    jobs = load(S6 / 'run-plan.json')['jobs']
    pending = []
    for j in jobs:
        base = HERE / 'receipts' / f"{j['queue_index']:03d}"
        if Path(str(base) + '.end.json').exists():
            continue
        if Path(str(base) + '.start.json').exists():
            s = load(Path(str(base) + '.start.json'))
            save(Path(str(base) + '.end.json'), dict(**j, state='interrupted_prior_start_no_retry',
                cpu=s['cpu'], pid=None, start_utc=s['start_utc'], end_utc=utc(),
                wall_seconds=180, exit_code=None, result_path=s['result_path'],
                resource_violations=[], files={}), exclusive=True)
            progress(f"既開始未完了queue={j['queue_index']}は中断として記録。再実行なし。")
        else:
            pending.append(j)
    if (HERE / 'execution-audit.json').exists():
        assert not pending, 'completed audit exists with pending queue'
        print('All jobs already receipted; no solver restarted.')
        return
    signal.signal(signal.SIGTERM, signal_stop)
    signal.signal(signal.SIGINT, signal_stop)
    started_utc, t0 = utc(), time.monotonic()
    progress(f"本計測開始: FIFO残り{len(pending)}件、固定CPU slot={cpus}、最大{len(cpus)}並列、180秒。参照集合はsolverへ渡さない。")
    active, done, index, max_active = {}, [], 0, 0
    loads, next_load, last_heartbeat = [], 0, t0
    load_stream = (raw / f'load-{time.time_ns()}.jsonl').open('x')
    try:
        while active or index < len(pending):
            now = time.monotonic()
            if STOP:
                for cpu, job in list(active.items()):
                    done.append(job.finish('interrupted', min(180, now-job.t0)))
                    del active[cpu]
                progress('driver停止signal受信。開始済みを中断記録し、未開始は残す。自動再試行なし。')
                return
            for cpu, job in list(active.items()):
                now = time.monotonic()
                if job.spawn_error:
                    done.append(job.finish('spawn_failure', min(180, now-job.t0)))
                    del active[cpu]
                elif now >= job.deadline:
                    done.append(job.finish('timeout', 180.0))
                    del active[cpu]
                elif job.proc.poll() is not None:
                    wall = time.monotonic() - job.t0
                    done.append(job.finish('completed' if wall < 180 else 'timeout', min(wall,180)))
                    del active[cpu]
                elif now >= job.next_sample:
                    job.sample()
            for cpu in cpus:
                if cpu not in active and index < len(pending):
                    job = Job(pending[index], cpu, raw, freeze)
                    active[cpu] = job
                    index += 1
                    max_active = max(max_active, len(active))
            now = time.monotonic()
            if now >= next_load:
                vm = psutil.virtual_memory()
                sample = dict(utc=utc(), monotonic=now, load=os.getloadavg(),
                    available_memory_bytes=vm.available, active=len(active),
                    active_queues=[j.q for j in active.values()], per_cpu_percent=psutil.cpu_percent(percpu=True))
                loads.append(sample)
                load_stream.write(json.dumps(sample) + '\n')
                load_stream.flush()
                next_load = now + 5
            if now - last_heartbeat >= 30:
                progress(f"稼働中: 完了receipt={sum(1 for _ in (HERE/'receipts').glob('*.end.json'))}/264、実行中={len(active)}、load1={os.getloadavg()[0]:.6e}。")
                last_heartbeat = now
            # Tight parent deadline polling. No grading or reference math in this loop.
            remaining = min((j.deadline-time.monotonic() for j in active.values()), default=.025)
            time.sleep(max(0, min(.025, remaining)))
    finally:
        load_stream.close()
        for job in active.values():
            job.cleanup()
    elapsed = time.monotonic() - t0
    ended_utc = utc()
    source, files = source_manifest()
    assert source == SOURCE and files == load(S6 / 'source-hashes.json')['files_sha256']
    all_receipts = [load(HERE / 'receipts' / f"{j['queue_index']:03d}.end.json") for j in jobs]
    starts = [load(HERE / 'receipts' / f"{j['queue_index']:03d}.start.json") for j in jobs]
    assert [s['queue_index'] for s in sorted(starts, key=lambda s:s['start_utc'])] == list(range(264)), 'FIFO start order'
    load_file = Path(load_stream.name)
    audit = dict(started_utc=started_utc, ended_utc=ended_utc, campaign_wall_seconds=elapsed,
        raw_root=str(raw), source_hash=source, source_rechecked_after=True,
        measurement_freeze_sha256=sha(HERE / 'freeze.json'),
        slot_cpus=cpus, eligible_cpus_at_launch=sorted(os.sched_getaffinity(0)), max_active=max_active,
        resource_policy='taskset before exec; distinct slot CPUs; thread environment all 1; descendant/thread affinity sampled every 0.5s',
        states=dict(Counter(r['state'] for r in all_receipts)),
        started_count=len(starts), completed_count=len(all_receipts), fifo_start_order_verified=True,
        load_summary=dict(load1=[min(s['load'][0] for s in loads),statistics.mean(s['load'][0] for s in loads),max(s['load'][0] for s in loads)],
            min_available_memory_bytes=min(s['available_memory_bytes'] for s in loads), samples=len(loads)),
        load_file=dict(path=str(load_file), size_bytes=load_file.stat().st_size, sha256=sha(load_file)),
        parent_environment_removed_geosolver_keys=sorted(k for k in os.environ if k.startswith('GEOSOLVER_')),
        startup_preflight=check, no_retries=True, no_early_seed_skips=True, no_commit_or_push=True)
    save(HERE / 'execution-audit.json', audit, exclusive=True)
    progress('264ジョブの本計測終了。source_hash再照合一致。これ以降に独立採点・集計を行う。')
    print('MEASUREMENT COMPLETE: 264 receipts. Grading remains separate.', flush=True)

if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in {'prepare', 'run'}:
        raise SystemExit('usage: driver.py prepare|run')
    prepare() if sys.argv[1] == 'prepare' else run()
