"""Q41 continuation controller; frozen measurement programs are not edited."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(OUT))
from stage2_common import RAW, CLEAN, PYTHON, environment, assert_identity, utc, save, digest
sys.path.insert(0, str(CLEAN / 'src'))

PROGRESS = OUT / 'execution/progress-resume.md'
LEASE = Path('/tmp/q41-stage2-resume-b.controller.lock')
EVENTS = Path('/tmp/q41-stage2-resume-b.events.jsonl')
STATE = OUT / 'execution/resume-controller.json'
phase = 'initializing'


def event(**row):
    with EVENTS.open('a') as f:
        f.write(json.dumps(dict(utc=utc(), **row), ensure_ascii=False) + '\n')


def counts(kind):
    path = RAW / f'{"full" if kind == "verify" else kind}-jobs.json'
    if not path.exists():
        return None
    jobs = json.loads(path.read_text())
    folder = RAW / ('full' if kind == 'verify' else kind)
    marker = 'verification.json' if kind == 'verify' else 'done.json'
    done = sum((folder / f'{i:04d}' / marker).exists() for i in range(len(jobs)))
    start_marker = 'candidate-check-starts.jsonl' if kind == 'verify' else 'launched.json'
    started = sum(not (folder / f'{i:04d}' / marker).exists() and
                  (folder / f'{i:04d}' / start_marker).exists() for i in range(len(jobs)))
    return dict(completed=done, total=len(jobs), started_without_marker=started)


def progress(status='running', error=None):
    rows = {k: counts(k) for k in ('local', 'full', 'verify', 'scaling', 'jacobian')}
    save(STATE, dict(utc=utc(), status=status, phase=phase, pid=os.getpid(),
                    pgid=os.getpgrp(), sid=os.getsid(0), counts=rows, error=error,
                    maximum_parallel=2, log='/tmp/q41-stage2-resume-b.log',
                    events=str(EVENTS), controller_sha256=digest(__file__)))
    table = '\n'.join(f'| {k} | {r["completed"]}/{r["total"]} | {r["started_without_marker"]} |'
                      for k, r in rows.items() if r is not None)
    PROGRESS.write_text(f'''更新 UTC {utc()} / 状態: {status} / 工程: {phase}

| 工程 | 結果あり | 開始済み・工程結果なし |
|---|---:|---:|
{table}

2026-10-24の再監査では局所752/752ブロック（35,600試行）、完成solver500/534件が完了。
完成0500・0501の2試行は開始済み・結果なしで、中断失敗（T=180秒）として保持し再実行しない。
未着手32件だけを追加実行。完了済み試行の再実行、seed追加、予算延長はしない。
同時実験は最大2、BLAS/OMP各1スレッド。元の採点器・実装・段階1の封印を維持。

`ps`で確認できたPID名前空間内に旧実験プロセスなし。`batch.lock`は排他取得できたため、
保持プロセスなしと確認し、同じファイルを残して使用する。他タスクのプロセスには触れない。
`setsid nohup`で端末・標準入出力を切り離した。通常のバックグラウンド起動だけでは
コマンド終了時にsandboxのPID名前空間が消えるため、実行セッションの親を待機させて保持。
アプリ全体停止後の生存はこの環境では保証できない。

順序: local → full → verify（未処理候補のみ反復）→ J prepare → scaling → jacobian → analyze → audit。
再監査: [resume-20261024b.json](resume-20261024b.json)。
制御ログ: `/tmp/q41-stage2-resume-b.log`。状態: [resume-controller.json](resume-controller.json)。
{('停止理由: ' + error) if error else ''}
''')


def run(script, arg=None):
    command = [PYTHON, '-B', str(OUT / script)] + ([arg] if arg is not None else [])
    event(action='command_start', phase=phase, command=command)
    print(json.dumps(dict(utc=utc(), command=command)), flush=True)
    p = subprocess.Popen(command, cwd=CLEAN, env=environment())
    while True:
        try:
            rc = p.wait(timeout=30)
            break
        except subprocess.TimeoutExpired:
            progress()
    event(action='command_end', phase=phase, returncode=rc)
    if rc:
        raise RuntimeError(f'{script} {arg}: returncode={rc}; inspect before continuing')
    progress()


def batches(kind):
    global phase
    phase = kind
    progress()
    while True:
        before = counts(kind)
        # Also invoke the registered runner once for already completed phases.
        log = OUT / 'execution/batches.jsonl'
        size = log.stat().st_size if log.exists() else 0
        run('run_stage2.py', kind)
        if log.exists() and kind in ('local', 'verify', 'scaling'):
            with log.open() as f:
                f.seek(size)
                failures = [json.loads(line) for line in f if line.strip()]
            if any(r['kind'] == kind and r['returncode'] for r in failures):
                raise RuntimeError(f'{kind} worker failed; no automatic retry')
        after = counts(kind)
        if after['completed'] == after['total']:
            break


def finalize_answer():
    p = OUT / 'answer.md'
    text = p.read_text()
    pred_start = text.index('| 予言 |')
    pred_end = text.index('\npは', pred_start)
    table = text[pred_start:pred_end]
    predictions = json.loads((OUT / 'predictions.json').read_text())
    table = table.replace('不支持（主検定未通過）', '外れ（主検定も未通過）').replace('不支持', '外れ')
    for key in ('P2', 'P3', 'P4'):
        if predictions[key]['conditions_met'] and not predictions[key]['supported']:
            lines = table.splitlines()
            lines = [line.replace('外れ（主検定も未通過）', '数値条件達成・主検定未通過のため支持せず')
                     if line.startswith(f'| {key}：') else line for line in lines]
            table = '\n'.join(lines)
    text = table + '\n\n' + text[:pred_start] + text[pred_end:]
    begin = text.index('前回はcommit ')
    end = text.index('\n\n全40問の主表', begin)
    checks = json.loads((OUT / 'analysis-checks.json').read_text())
    resume = json.loads((OUT / 'execution/resume-20261024b.json').read_text())
    interrupted = []
    for kind in ('full', 'jacobian'):
        jobs = json.loads((RAW / f'{kind}-jobs.json').read_text())
        for i in range(len(jobs)):
            r = json.loads((RAW / kind / f'{i:04d}' / 'done.json').read_text())
            if r.get('interrupted') or r.get('reason') == 'interrupted_no_retry':
                interrupted.append(dict(kind=kind, index=i, id=r['id'], arm=r['arm']))
    save(OUT / 'execution/interrupted-failures.json', dict(count=len(interrupted), trials=interrupted,
         local_started_without_result=resume['local']['started_slots_without_result'], retries=0))
    history = f'''commit `795565c2` のpush確認（UTC 2026-10-23T17:43:24Z）と実行許可後、最初のツール実行前に一度中断。段階2開始後もアプリ全体の停止で中断し、10月24日の前回再開記録では局所752/752ブロック、完成312/534件が完了していた。その後12:30 JSTごろに再中断し、今回の監査では完成500件が完了、2件が開始済み・結果なし、32件が未着手だった。

**中断失敗として残した試行は{len(interrupted)}件**（完成solverの0500・0501、JMO-2025-PRE-12のseed410252、+1%版とS版）。T=180秒として保持し、再実行していない。局所の開始済み・結果なしは0件。完了済み試行の再実行・追加seed・予算延長はない。最終的に局所35,600試行、完成534枠の結果・失敗記録と候補検証が揃い、完成の観測欠測は{checks['full_observation_missing']}枠。最初から変換不能の20,400局所枠・306完成枠は別に失敗扱いで分母に残した。

`ps`で確認できる範囲は隔離されたPID名前空間内で、旧実験プロセスは見えなかった。`batch.lock`は排他取得でき、保持プロセスがないことを確認してファイルを保持した。他タスクのプロセスには触れていない。`setsid nohup`と待機用の親で端末から切り離して実行したが、この環境ではアプリ全体停止後の生存を保証できない。詳細は [execution/resume-20261024b.json](execution/resume-20261024b.json)。

`/tmp/q41-clean` の凍結src・段階1・採点器・実装のhashを再照合し、最大2並列、1実験1コアで続行した。共有機の負荷はp・Tへ影響し得る。候補保存費用はTに含み、完成solverの通常の探索箱・残差尺度の違いもTに含む。'''
    p.write_text(text[:begin] + history + text[end:])


lease = LEASE.open('a')
fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
try:
    assert_identity()
    for lockname in ('implementation.lock.json', 'full-implementation.lock.json', 'jacobian-implementation.lock.json'):
        for name, sha in json.loads((OUT / 'execution' / lockname).read_text())['files'].items():
            assert digest(OUT / name) == sha, name
    event(action='controller_started', pid=os.getpid(), sid=os.getsid(0), maximum_parallel=2)
    progress()
    for kind in ('local', 'full', 'verify'):
        batches(kind)
    phase = 'jacobian_prepare'
    if not (RAW / 'jacobian-jobs.json').exists():
        run('jacobian_stage2.py', 'prepare')
    for kind in ('scaling', 'jacobian'):
        batches(kind)
    phase = 'analysis'
    run('analyze_stage2.py')
    finalize_answer()
    phase = 'audit'
    run('audit_stage2.py')
    phase = 'complete'
    progress('complete')
    event(action='complete')
except BaseException as error:
    progress('stopped', f'{type(error).__name__}: {error}')
    event(action='stopped', error=f'{type(error).__name__}: {error}')
    raise
