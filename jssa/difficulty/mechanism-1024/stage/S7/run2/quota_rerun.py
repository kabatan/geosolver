"""One explicitly authorized environmental-quota replacement; original solver unchanged."""
import csv
import fcntl
import hashlib
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
M = json.loads((OUT / 'pre-run-hashes.json').read_text())
ROOT = Path(M['scratch'])
CASE = 'HMMT-2023-FEB-GEO-07'
D = ROOT / 'runs' / CASE
EVIDENCE = OUT / 'interrupted-env-quota'
ARCHIVE = ROOT / 'interrupted-env-quota' / CASE
MIN_FREE = 6 * 1024**3


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text())


def save(p, value, exclusive=True):
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    assert len(data.encode()) < 3_000_000, p
    with p.open('x' if exclusive else 'w') as f:
        f.write(data)


def inventory(d):
    return {str(p.relative_to(d)): sha(p) for p in sorted(d.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def digest(d):
    return hashlib.sha256(json.dumps(inventory(d), sort_keys=True).encode()).hexdigest()


def gate():
    free = shutil.disk_usage('/tmp').free
    assert free >= MIN_FREE, f'/tmp free {free} < {MIN_FREE}: stopped'
    return free


def history(kind, **fields):
    p = OUT / 'hash-update-history.json'
    h = read(p)
    h['updates'].append(dict(created_utc=stamp(), kind=kind, **fields))
    save(p, h, exclusive=False)


def prepare():
    free = gate()
    assert '[Errno 122] Disk quota exceeded' in (D / 'search.log').read_text()
    assert read(D / 'search.ended.json')['returncode'] == 1
    assert (D / 'initial.pkl').stat().st_size == 0
    assert not EVIDENCE.exists() and not ARCHIVE.exists()
    for path, expected in M['files'].items():
        assert sha(Path(path)) == expected, path
    assert read(ROOT / 'measure-correction-audit.json')['passed']
    EVIDENCE.mkdir()
    before = dict(utc=stamp(), case_id=CASE, status='interrupted_env_quota',
        reason='User-authorized replacement of Errno 122 environmental missing data only',
        original_files=inventory(D),
        other_run_digests={p.name: digest(p) for p in sorted((ROOT / 'runs').iterdir()) if p.is_dir() and p.name != CASE},
        immutable_files={str(p): sha(p) for p in [OUT/'pre-run-hashes.json', ROOT/'manifest.json',
            ROOT/'events.jsonl', ROOT/'measure-correction-baseline.json', ROOT/'measure-correction-audit.json',
            OUT/'analyze.py', OUT/'driver.py', OUT/'worker.py', OUT/'raw_switch.py', OUT/'README.md']},
        original_events=[json.loads(s) for s in (ROOT/'events.jsonl').read_text().splitlines() if CASE in s],
        free_bytes=free, cpu=31, parallel=1, thread_environment=M['thread_environment'],
        seed=0, search_budget_seconds=178, refinement_budget_seconds=90,
        stage_order=['search','scales','refine.BASE','refine.RAW','measure-corrected.BASE','measure-corrected.RAW'])
    save(EVIDENCE / 'before.json', before)
    shutil.copytree(D, EVIDENCE / CASE)
    shutil.copy2(OUT/'answer.md', OUT/'answer-before-quota-rerun.md')
    for name in ['judgments.json','per-problem.csv','per-candidate.csv','audit.json','used-hashes.json',
                 'raw-hashes-00.json','raw-hashes-01.json','raw-hashes-02.json']:
        shutil.copy2(OUT/name, EVIDENCE/name)
    shutil.copy2(ROOT/'resume-started.json', EVIDENCE/'resume-started-before.json')
    shutil.copy2(OUT/'hash-update-history.json', EVIDENCE/'hash-update-history-before.json')
    ARCHIVE.parent.mkdir(exist_ok=True)
    D.rename(ARCHIVE)
    D.mkdir()
    # The unchanged analyzer verifies completed originals by path. Relocate only
    # these five references, retaining their exact hashes and original receipt.
    r = read(ROOT/'resume-started.json')
    relocated = {}
    for path in list(r['completed_files']):
        if path.startswith('runs/'+CASE+'/'):
            new = 'interrupted-env-quota/'+CASE+'/'+Path(path).name
            relocated[path] = new
            r['completed_files'][new] = r['completed_files'].pop(path)
    assert len(relocated) == 5
    save(ROOT/'resume-started.json', r, exclusive=False)
    save(EVIDENCE/'original-hashes.json', dict(status='interrupted_env_quota',
        scratch_archive=str(ARCHIVE), workspace_copy=str(EVIDENCE/CASE),
        files=before['original_files'], original_events=before['original_events'],
        resume_inventory_relocations=relocated,
        resume_before_sha256=sha(EVIDENCE/'resume-started-before.json'),
        resume_after_sha256=sha(ROOT/'resume-started.json')))
    history('single-case-env-quota-rerun-authorized', case_id=CASE, status='interrupted_env_quota',
        scope='Only this case; seed 0 search once, save candidates, fixed scales, BASE 90s, RAW 90s, measure saved refined.pkl',
        unchanged_analyze_sha256=sha(OUT/'analyze.py'), unchanged_worker_sha256=sha(OUT/'worker.py'),
        unchanged_manifest_sha256=sha(OUT/'pre-run-hashes.json'),
        runner=dict(path=str(OUT/'quota_rerun.py'), sha256=sha(OUT/'quota_rerun.py')),
        original_evidence=dict(path=str(EVIDENCE/'original-hashes.json'), sha256=sha(EVIDENCE/'original-hashes.json')),
        old_answer=dict(path=str(OUT/'answer-before-quota-rerun.md'), sha256=sha(OUT/'answer-before-quota-rerun.md')),
        resume_inventory_relocations=relocated, cpu=31, parallel=1,
        decision_rules='unchanged', denominators='unchanged', thresholds='unchanged', configurations='unchanged')
    print('Prepared interrupted_env_quota originals and one-case authorization', flush=True)


def stage(mode, arm=None):
    free = gate()
    name = ('measure-corrected' if mode == 'measure' else mode) + ('.'+arm if arm else '')
    env = {k:v for k,v in os.environ.items() if not k.startswith(('GEOSOLVER_ABLATE_', 'GEOSOLVER_S3_', 'GEOSOLVER_S7_'))}
    env.update(M['thread_environment'])
    env.update(PYTHONPATH=str(ROOT/'final/src'), PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1', TMPDIR='/tmp')
    if mode == 'refine':
        env.update(M['switch_settings'][arm])
    cmd = ['taskset','-c','31',M['python'],'-B',str(OUT/'worker.py'),str(ROOT),mode,CASE]
    if arm:
        cmd.append(arm)
    started = dict(utc=stamp(), case_id=CASE, cpu=31, mode=mode, arm=arm,
        command=cmd, free_bytes=free, thread_environment=M['thread_environment'])
    if mode == 'measure':
        started['refined_sha256'] = sha(D/(arm+'.refined.pkl'))
    save(D/(name+'.started.json'), started)
    limit = 180 if mode == 'search' else 98 if mode == 'refine' else 90
    reason = None
    observations = set()
    t0 = time.monotonic()
    print(stamp(), name, 'start; cpu=31, parallel=1', flush=True)
    with (D/(name+'.log')).open('x') as log:
        p = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while p.poll() is None:
                try:
                    status = Path(f'/proc/{p.pid}/status').read_text()
                    threads = int(next(s.split(':')[1] for s in status.splitlines() if s.startswith('Threads:')))
                    affinity = tuple(sorted(os.sched_getaffinity(p.pid)))
                    if (D/(name+'.runtime-start.json')).exists():
                        observations.add((threads, affinity))
                        if affinity != (31,):
                            reason = 'affinity_violation'
                        if mode == 'measure' and threads != 1:
                            reason = 'measure_thread_violation'
                except (FileNotFoundError, ProcessLookupError, StopIteration):
                    pass
                if shutil.disk_usage('/tmp').free < MIN_FREE:
                    reason = 'low_disk'
                if time.monotonic()-t0 >= limit:
                    reason = 'outer_timeout'
                if (D/(name+'.log')).stat().st_size >= 2_900_000:
                    reason = 'log_size_limit'
                if reason:
                    os.killpg(p.pid, signal.SIGTERM)
                    try:
                        p.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(p.pid, signal.SIGKILL)
                    break
                time.sleep(.05)
            code = p.wait()
        except BaseException:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            raise
    ended = dict(utc=stamp(), returncode=code, reason=reason, seconds=time.monotonic()-t0,
        cpu=31, mode=mode, arm=arm, pid=p.pid, all_processes_waited=True,
        environment={k:v for k,v in env.items() if k.startswith(('GEOSOLVER_','OMP_','OPENBLAS_','MKL_','NUMEXPR_','BLIS_','VECLIB_'))},
        observations=[dict(threads=n, affinity=list(a)) for n,a in sorted(observations)], free_bytes=gate())
    save(D/(name+'.ended.json'), ended)
    print(stamp(), name, 'end', code, reason, round(ended['seconds'],3), flush=True)
    assert code == 0 and reason is None, ended
    for which in ('start','end'):
        receipt = read(D/(name+'.runtime-'+which+'.json'))
        assert receipt['affinity'] == [31] and receipt['threads'] == 1, receipt


def run():
    assert (EVIDENCE/'before.json').exists()
    assert not (D/'quota-rerun.started.json').exists(), 'No second replacement attempt'
    save(D/'quota-rerun.started.json', dict(utc=stamp(), free_bytes=gate(), cpu=31, parallel=1))
    stage('search')
    assert (D/'initial.pkl').stat().st_size > 0
    assert read(D/'initial.json')['seed'] == 0
    stage('scales')
    for arm in ('BASE','RAW'):
        stage('refine', arm)
    for arm in ('BASE','RAW'):
        stage('measure', arm)
    save(D/'quota-rerun.ended.json', dict(utc=stamp(), passed=True, cpu=31, parallel=1,
        all_processes_waited=True, files=inventory(D)))
    print('One-case replacement complete; all foreground children waited', flush=True)


def verify():
    before = read(EVIDENCE/'before.json')
    assert inventory(ARCHIVE) == before['original_files'] == inventory(EVIDENCE/CASE)
    assert all(digest(ROOT/'runs'/case) == h for case,h in before['other_run_digests'].items())
    assert all(sha(Path(p)) == h for p,h in before['immutable_files'].items())
    for p,h in M['files'].items():
        assert sha(Path(p)) == h, p
    for p,h in M['source_files'].items():
        assert sha(ROOT/p) == h, p
    resumed = read(ROOT/'resume-started.json')
    original = read(EVIDENCE/'resume-started-before.json')
    for old,new in read(EVIDENCE/'original-hashes.json')['resume_inventory_relocations'].items():
        assert resumed['completed_files'].pop(new) == original['completed_files'][old]
        resumed['completed_files'][old] = original['completed_files'][old]
    assert resumed == original
    completion = read(D/'quota-rerun.ended.json')
    assert completion['passed']
    assert all(sha(D/p) == h for p,h in completion['files'].items())
    initial_sha = sha(D/'initial.pkl')
    stages = []
    for name in before['stage_order']:
        start = read(D/(name+'.started.json'))
        end = read(D/(name+'.ended.json'))
        assert end['returncode'] == 0 and end['reason'] is None and end['all_processes_waited']
        assert start['cpu'] == end['cpu'] == 31 and start['free_bytes'] >= MIN_FREE
        assert all(o['affinity'] == [31] for o in end['observations'])
        for which in ('start','end'):
            r = read(D/(name+'.runtime-'+which+'.json'))
            assert r['threads'] == 1 and r['affinity'] == [31]
        stages.append(dict(name=name, seconds=end['seconds'], observations=end['observations']))
    for arm in ('BASE','RAW'):
        assert read(D/(arm+'.refinement.json'))['initial_sha256'] == initial_sha
        assert read(D/('measure-corrected.'+arm+'.started.json'))['refined_sha256'] == sha(D/(arm+'.refined.pkl'))
        assert read(D/(arm+'.measure.json'))['rows']
    thread_observations = [dict(stage=s['name'], **o) for s in stages for o in s['observations'] if o['threads'] != 1]
    return dict(utc=stamp(), passed=True, case_id=CASE, interrupted_status='interrupted_env_quota',
        original_files_preserved=True, other_265_runs_unchanged=True, immutable_files_unchanged=True,
        analyze_sha256=sha(OUT/'analyze.py'), worker_sha256=sha(OUT/'worker.py'),
        parallel=1, cpu=31, seed=0, all_processes_waited=True, same_initial_candidates=True,
        stages=stages, resume_inventory_only_relocated=True, historical_events_unchanged=True,
        thread_environment=M['thread_environment'], runtime_start_end_threads=1,
        live_thread_violations=thread_observations,
        execution_contract_status='violations' if thread_observations else 'pass')


def report():
    result = verify()
    # Run the existing analyzer as-is. Its event/no-retry fields describe the
    # historical campaign; this replacement has separate exclusive receipts.
    subprocess.run(['taskset','-c','31',M['python'],'-B',str(OUT/'analyze.py')], check=True)
    subprocess.run(['taskset','-c','31',M['python'],'-B',str(OUT/'annotate_failures.py')], check=True)
    old = read(EVIDENCE/'judgments.json')
    new = read(OUT/'judgments.json')
    assert old['population'] == new['population'] == 266
    assert old['denominator_policy'] == new['denominator_policy']
    rows_before = {r['case_id']:r for r in csv.DictReader((EVIDENCE/'per-problem.csv').open())}
    rows_after = {r['case_id']:r for r in csv.DictReader((OUT/'per-problem.csv').open())}
    assert all(rows_before[c] == rows_after[c] for c in rows_before if c != CASE)
    for w in ('W1','W2','W3','W4'):
        assert old['judgments'][w].get('threshold') == new['judgments'][w].get('threshold')
        assert old['judgments'][w].get('total') == new['judgments'][w].get('total')
    assert old['judgments']['W2']['non_singular']['total'] == new['judgments']['W2']['non_singular']['total']
    assert old['judgments']['W2']['singular']['total'] == new['judgments']['W2']['singular']['total']
    candidate_before = [r for r in csv.DictReader((EVIDENCE/'per-candidate.csv').open()) if r['case_id'] != CASE]
    candidate_after = [r for r in csv.DictReader((OUT/'per-candidate.csv').open()) if r['case_id'] != CASE]
    assert candidate_before == candidate_after
    result['D_base'] = rows_after[CASE]['D_base']
    result['D_raw'] = rows_after[CASE]['D_raw']
    assert result['D_base'] and result['D_raw']
    result['judgments'] = {w:dict(old=old['judgments'][w]['judgment'], new=new['judgments'][w]['judgment']) for w in ('W1','W2','W3','W4')}
    result['changed_judgments'] = {w:v for w,v in result['judgments'].items() if v['old'] != v['new']}
    result['non_singular_success'] = dict(old=old['judgments']['W1']['success'], new=new['judgments']['W1']['success'], total=228)
    save(OUT/'quota-rerun-audit.json', result)
    comparison = '、'.join(f"{w}: {v['old']}→{v['new']}" for w,v in result['judgments'].items())
    note = (f"HMMT-2023-FEB-GEO-07 の環境欠測補完を完了。D_base={result['D_base']}、D_raw={result['D_raw']}。\n\n"
        f"W判定の旧→新: {comparison}。変更した判定: "+('、'.join(result['changed_judgments']) or 'なし')+'。\n\n'
        '元のErrno 122は interrupted_env_quota として interrupted-env-quota/ に元ログ・receipt・0バイトinitial.pkl・SHA-256を保存。'
        '旧answer.mdは answer-before-quota-rerun.md に保存。ユーザーの明示指示によりこの1問のみ、seed 0の主探索1回→候補保存→固定scales→BASE精密化90秒→RAW精密化90秒→保存refined.pklから両measureを実行した。'
        '1枠、taskset -c 31、内部OMP/BLAS等1スレッド、全工程foregroundでwait。各runtime開始終了receiptはThreads=1・affinity=[31]。'
        'ただし実行中のsearchとrefine.BASEではOS Threads=2を観測した。新規補完の実行条件監査もviolationsとし、内部1スレッド条件の完全充足は主張しない。追加threadの役割は観測receiptのみでは不明。再探索・再精密化は追加しない。'
        '他265問の生ファイル・集計行、solverソース、driver.py、worker.py、analyze.py、入力・参照値・分類・分母・閾値・構成は不変。'
        '元events.jsonlは変更せず、新工程は対象run内の専用receiptに記録した。'
        '旧resume-started.jsonは保存し、completed_files内の当該5原本の参照先だけをscratchの事故退避先に移し、hash値と他フィールドは不変。'
        'analyze.pyを無変更で実行し、旧報告と同じannotate_failures.pyで既存例外詳細を追記して再集計した。下記の「測定修正」「再実行なし」「no_retries」および元イベント由来の工程数は先行campaign/measure修正時点の履歴を述べる。'
        '今回の1問の例外は本補完記録とquota-rerun-audit.jsonが示す。元の2件のthread逸脱は保持。\n\n')
    (OUT/'quota-rerun-report.md').write_text(note)
    answer = OUT/'answer.md'
    answer.write_text(note+'---\n\n'+answer.read_text())
    audit = read(OUT/'audit.json')
    audit['environment_quota_replacement'] = result
    if result['live_thread_violations']:
        audit['execution_contract_status'] = 'violations'
    audit['event_audit_scope'] = 'Original campaign only; quota replacement recorded in separate exclusive per-stage receipts'
    save(OUT/'audit.json', audit, exclusive=False)
    history('single-case-env-quota-rerun-complete', case_id=CASE,
        original_status='interrupted_env_quota', unchanged_analyze_sha256=sha(OUT/'analyze.py'),
        result=result, artifacts={name:sha(OUT/name) for name in ['quota-rerun-audit.json','quota-rerun-report.md','answer.md','judgments.json','audit.json','per-problem.csv','per-candidate.csv']})
    with (OUT/'progress.md').open('a') as f:
        f.write('\n'+stamp()+' 環境quota補完1問完了。'+comparison+'。\n')
    save(OUT/'used-hashes.json', {str(p.relative_to(OUT)):dict(sha256=sha(p), bytes=p.stat().st_size)
        for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'used-hashes.json' and '__pycache__' not in p.parts}, exclusive=False)
    assert all(p.stat().st_size < 3_000_000 for p in OUT.rglob('*') if p.is_file())
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_FSIZE, (2_999_999, 2_999_999))
    locks = []
    for path in (ROOT/'driver.lock', ROOT/'measure-correction.lock', ROOT/'quota-rerun.lock'):
        lock = path.open('a')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locks.append(lock)
    gate()
    {'prepare':prepare, 'run':run, 'report':report}[sys.argv[1]]()
