#!/usr/bin/env python3
"""Preregistration 9b, unseen nonmembers only; unchanged certify worker."""
import argparse
import ast
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

E = Path(__file__).resolve().parent
BASE = E.parent
DEST = E / 'unseen'
ROOT = BASE.parents[2]
sys.path.insert(0, str(BASE))
import certify as c
c.environment()
ORIGINAL_HASHES = c.source_hashes()


def sign_rule(target):
    def walk(n):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in {'Distance', 'Length', 'Perimeter', 'Area', 'Radius', 'sqrt'}
                and n.args and not n.keywords):
            return True, True
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return math.isfinite(n.value) and n.value >= 0, False
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Mult)):
            a, b = walk(n.left), walk(n.right)
            return a[0] and b[0], a[1] or b[1]
        return False, False
    try:
        tree = ast.parse(str(target), mode='eval')
        valid, atom = walk(tree.body)
        accepted = valid and atom
        tree_text = ast.dump(tree, include_attributes=False)
    except (SyntaxError, ValueError):
        accepted, tree_text = False, None
    return {'nonnegative_form': accepted, 'target': target, 'ast': tree_text,
            'category_ja': '非負形で正の根' if accepted else 'solver数値で選択',
            'explanation': '非負の量なので正の根' if accepted else '±の選択はsolverの数値で選んだ'}


def freeze():
    import sympy as sp
    if (E/'pre-run-hashes.json').exists() or (DEST/'runs').exists():
        raise RuntimeError('ALREADY_FROZEN_OR_ATTEMPTED')
    old = json.loads((BASE/'eval/pre-run-hashes.json').read_text())
    rows = list(csv.DictReader((BASE/'eval/per-problem.csv').open()))
    selected = [r for r in rows if r['category_ja'] == '非所属']
    ids = sorted([r['id'] for r in selected], key=lambda x: hashlib.sha256(x.encode()).hexdigest())
    assert len(ids) == len(set(ids)) == 16
    assert all(r['group'] == 'unseen29' and r['status'] == 'nonmember' for r in selected)
    assert not set(ids) & set(c.dev5())
    for p, h in ORIGINAL_HASHES.items():
        assert old['hashes'][p] == h, 'PREREG9_DEPENDENCY_CHANGED:' + p
    hashes = dict(ORIGINAL_HASHES)
    for p in [Path(__file__), E/'sign-rule.md', BASE/'preregistration-9b.md',
              BASE/'preregistration-9.md', BASE/'README.md', BASE/'eval/pre-run-hashes.json',
              BASE/'eval/per-problem.csv', BASE/'eval/answer-unseen29.md']:
        hashes[str(p)] = c.sha(p)
    records, cases = {}, {}
    actual_cases = {}
    for group in 'ab':
        path = BASE.parent/f'unseen-2/{group}/cases.jsonl'
        hashes[str(path)] = c.sha(path)
        for line in path.read_text().splitlines():
            item = json.loads(line)
            if item['id'] in ids:
                assert item['id'] not in actual_cases
                actual_cases[item['id']] = {'id': item['id'], 'dsl': item['dsl']}
    assert set(actual_cases) == set(ids)
    T = sp.Symbol('T')
    for cid in ids:
        row = next(r for r in selected if r['id'] == cid)
        source = old['records'][cid]
        pfile = ROOT/source['source']
        assert c.sha(pfile) == source['source_sha256'] == row['polynomial_source_sha256']
        raw = json.loads(pfile.read_text())
        assert raw['case_id'] == cid
        assert len(raw['solver_result']['answers']) == source['answer_count']
        p = sp.prod(sp.Poly.from_list(list(map(sp.Rational, a['value']['minimal_polynomial'])), T).as_expr()
                    for a in raw['solver_result']['answers'])
        assert sp.expand(p-sp.sympify(source['polynomial'])) == 0
        assert sp.expand(p-sp.sympify(row['polynomial'])) == 0
        case = old['cases'][cid]
        assert case == actual_cases[cid], 'DSL_CHANGED:' + cid
        dslhash = hashlib.sha256(json.dumps(case['dsl'], sort_keys=True).encode()).hexdigest()
        assert dslhash == source['dsl_sha256']
        q = sp.Poly(sp.expand(p*p.subs(T, -T)), T)
        candidate = dict(source, polynomial=str(q.as_expr()), degree=q.degree(),
                         original_polynomial=str(p), original_category_ja='非所属',
                         transformation='q(T)=p(T)*p(-T), no normalization or factor selection',
                         sign=sign_rule(case['dsl']['target']))
        records[cid], cases[cid] = candidate, case
        hashes[str(pfile)] = c.sha(pfile)
    version = subprocess.check_output(['Singular', '--version'], text=True, stderr=subprocess.STDOUT)
    m = dict(scope='preregistration9b unseen nonmembers only; development not run', order=ids,
             records=records, cases=cases, hashes=hashes, original_implementation_hashes=ORIGINAL_HASHES,
             singular_version=version, singular_version_sha256=hashlib.sha256(version.encode()).hexdigest(),
             python=sys.executable, parallelism=2, cpus_per_problem=1, wall_seconds_per_problem=600,
             memory_bytes_per_problem=c.MEM, max_file_bytes=c.MAX_FILE, attempts_per_problem=1,
             order_rule='ascending SHA256(problem ID)', created_unix=time.time(),
             timing_note='負荷付きの参考値。各問開始時の1分load averageを記録。')
    c.write_json(E/'pre-run-hashes.json', m)
    progress(m, [], [], '実行前固定済み')
    print('frozen', len(ids), flush=True)


def check_frozen(m):
    for p, h in m['hashes'].items():
        if c.sha(p) != h:
            raise RuntimeError('FROZEN_HASH_MISMATCH:' + p)


def limits(cpu):
    resource.setrlimit(resource.RLIMIT_AS, (c.MEM, c.MEM))
    resource.setrlimit(resource.RLIMIT_FSIZE, (c.MAX_FILE, c.MAX_FILE))
    os.sched_setaffinity(0, {cpu})


def launch(cid, cpu, m):
    check_frozen(m)
    work = DEST/'runs'/(cid+'.work')
    work.mkdir(exist_ok=False)  # permanent single-attempt ledger
    start = time.monotonic()
    c.write_json(work/'input.json', m['cases'][cid])
    c.write_json(work/'candidate.json', m['records'][cid])
    receipt = dict(id=cid, start_unix=time.time(), load_average_1m=os.getloadavg()[0],
                   cpu=cpu, parallelism=2, wall_seconds=600, memory_bytes=c.MEM, attempt=1)
    c.write_json(work/'start.json', receipt)
    log = (work/'worker.log').open('w')
    proc = subprocess.Popen([sys.executable, str(__file__), '--worker', cid], stdout=log,
                            stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=lambda: limits(cpu))
    return dict(cid=cid, work=work, start=start, peak=0, proc=proc, log=log, receipt=receipt)


def poll(job, run):
    proc, work = job['proc'], job['work']
    job['peak'] = max(job['peak'], run.own_tree_rss(proc.pid))
    elapsed = time.monotonic()-job['start']
    reason = 'TIME_LIMIT' if elapsed >= 600 else 'MEMORY_LIMIT' if job['peak'] >= c.MEM else None
    if any(p.stat().st_size > c.MAX_FILE for p in work.iterdir() if p.is_file()):
        reason = 'ARTIFACT_SIZE_LIMIT'
    if not reason and proc.poll() is None:
        return False
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()
    job['log'].close()
    output = DEST/'runs'/(job['cid']+'.json')
    if reason or not output.exists():
        p = work/'progress.json'
        result = json.loads(p.read_text()) if p.exists() else {'id':job['cid']}
        slog = work/'singular.log'
        if slog.exists():
            parsed, blocks = c.parse_log(slog.read_text())
            for method in ('power', 'rabinowitsch'):
                parsed[method].update({k:v for k,v in result.get(method,{}).items()
                                      if k in ('independent_verification','verification_seconds','certificate')})
            result.update(parsed)
            c.write_json(work/'algebra-output.json', blocks)
        result.update(status='timeout' if reason=='TIME_LIMIT' else 'resource_limit' if reason else 'worker_error',
                      reason_code=reason or f'WORKER_EXIT_{proc.returncode}', proof_verified=False)
    else:
        result = json.loads(output.read_text())
    if result.get('reason_code') == 'MemoryError' or result.get('singular_returncode') in (-9,-11,-6,-25):
        result.update(status='resource_limit', proof_verified=False)
    result.update(wall_seconds=elapsed, peak_tree_rss_bytes=job['peak'], attempts=1,
                  supervisor_returncode=proc.returncode, start_receipt=job['receipt'])
    result.setdefault('limits', {}).update(wall_seconds=600, memory_bytes=c.MEM, threads=1, parallelism=2)
    c.write_json(output, result)
    print(json.dumps({k:result.get(k) for k in ('id','status','proof_verified','wall_seconds')}, ensure_ascii=False), flush=True)
    return True


def progress(m, active, completed, state):
    lines = ['# 事前登録9b：開発外のみの進捗', '',
             f'状態：{state}。完了 {len(completed)}/{len(m["order"])}、実行中 {len(active)}。', '',
             '600秒・8 GiB・1 CPU/問、並列2、各1回。IDのSHA-256昇順。再試行・対象交換なし。',
             '開発群は未実施。eval/dev/ は読み書きしない。時間は負荷付きの参考値。', '']
    for cid in m['order']:
        if cid in completed:
            r = json.loads((DEST/'runs'/(cid+'.json')).read_text())
            lines.append(f'- {cid}: {r["status"]}, {r.get("wall_seconds",0):.3f}秒')
        elif any(j['cid']==cid for j in active):
            lines.append(f'- {cid}: 実行中')
    (E/'progress.md').write_text('\n'.join(lines)+'\n')


def campaign():
    m = json.loads((E/'pre-run-hashes.json').read_text())
    check_frozen(m)
    (DEST/'runs').mkdir(exist_ok=False)
    cpus = sorted(os.sched_getaffinity(0))[:2]
    assert len(cpus) == 2
    run, _ = c.dependencies()
    queue, active, completed, last = list(m['order']), [], [], 0
    try:
        while queue or active:
            while queue and len(active)<2:
                cpu = next(cpu for cpu in cpus if cpu not in {j['receipt']['cpu'] for j in active})
                active.append(launch(queue.pop(0), cpu, m))
            for job in active[:]:
                if poll(job, run):
                    active.remove(job)
                    completed.append(job['cid'])
            if time.monotonic()-last > 5:
                progress(m, active, completed, '実行中')
                last = time.monotonic()
            time.sleep(.1)
        check_frozen(m)
        progress(m, active, completed, '全16問終了')
        c.write_json(DEST/'completion.json', dict(completed=completed, attempts=len(completed), retries=0,
                                                finished_unix=time.time(), all_frozen_hashes_match=True))
    finally:
        for job in active:
            try:
                os.killpg(job['proc'].pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=['freeze','run'])
    parser.add_argument('--worker')
    args = parser.parse_args()
    if args.worker:
        m = json.loads((E/'pre-run-hashes.json').read_text())
        check_frozen(m)
        assert args.worker in m['order']
        c.HERE = DEST
        c.source_hashes = lambda: m['original_implementation_hashes']
        c.worker(args.worker)
    elif args.action == 'freeze':
        freeze()
    elif args.action == 'run':
        campaign()
