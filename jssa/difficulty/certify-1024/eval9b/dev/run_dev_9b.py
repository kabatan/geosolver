#!/usr/bin/env python3
"""Preregistration 9b, development nonmembers only; unchanged certify worker."""
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

import fcntl
import re
import io

sys.dont_write_bytecode = True
E = Path(__file__).resolve().parent
DEST = E
BASE = E.parent.parent
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


def check_frozen(m):
    for p, h in m['hashes'].items():
        if c.sha(p) != h:
            raise RuntimeError('FROZEN_HASH_MISMATCH:' + p)


def limits(cpu):
    resource.setrlimit(resource.RLIMIT_AS, (c.MEM, c.MEM))
    resource.setrlimit(resource.RLIMIT_FSIZE, (c.MAX_FILE, c.MAX_FILE))
    os.sched_setaffinity(0, {cpu})


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
    result.setdefault('limits', {}).update(wall_seconds=600, memory_bytes=c.MEM, threads=1, parallelism=4)
    c.write_json(output, result)
    print(json.dumps({k:result.get(k) for k in ('id','status','proof_verified','wall_seconds')}, ensure_ascii=False), flush=True)
    return True



def stable_version(text):
    # --version contains a per-process random seed and invocation PATH.
    return re.sub(r'random=\d+', 'random=<runtime>', '\n'.join(line for line in text.splitlines() if not line.startswith('Path      :')))


def freeze():
    import sympy as sp
    assert not (E/'pre-run-hashes.json').exists() and not (E/'runs').exists(), 'ALREADY_FROZEN'
    old = json.loads((BASE/'eval/dev/pre-run-hashes.json').read_text())
    unseen = json.loads((E.parent/'pre-run-hashes.json').read_text())
    for path, h in ORIGINAL_HASHES.items():
        assert h == old['sources'][path] == unseen['original_implementation_hashes'][path], path
    rows = list(csv.DictReader((BASE/'eval/dev/per-problem.csv').open()))
    selected = {r['id']:r for r in rows if r['category_ja']=='非所属'}
    ids = sorted(selected, key=lambda x:hashlib.sha256(x.encode()).hexdigest())
    assert len(ids) == 163 and not set(ids)&set(c.dev5())
    candidates = {r['id']:r for r in json.loads((BASE/'eval/dev/candidates.json').read_text())}
    answers = json.loads((BASE/'dev-answers-seed0.json').read_text())
    inputs = {r['id']:r for r in map(json.loads,(BASE/'eval/dev/inputs.jsonl').read_text().splitlines())}
    hashes = dict(ORIGINAL_HASHES)
    for path in [Path(__file__), E/'report_dev_9b.py', E.parent/'run_9b.py', E.parent/'report_9b.py',
                 E.parent/'analyze_nonmembers.py', E.parent/'sign-rule.md', BASE/'preregistration-9.md',
                 BASE/'preregistration-9b.md', BASE/'eval/dev/candidates.json', BASE/'dev-answers-seed0.json',
                 BASE/'eval/dev/inputs.jsonl', BASE/'eval/dev/per-problem.csv', BASE/'eval/dev/pre-run-hashes.json',
                 BASE/'eval/dev/summary.json', BASE/'eval/dev/answer-dev.md', BASE/'eval/dev/run_dev_resume.py',
                 E.parent/'pre-run-hashes.json', E.parent/'progress.md', E.parent/'unseen/answer.md',
                 E.parent/'unseen/per-problem.csv', E.parent/'unseen/summary.json']:
        hashes[str(path)] = c.sha(path)
    records, cases = {}, {}
    T = sp.Symbol('T')
    for cid in ids:
        row, source, raw = selected[cid], candidates[cid], answers[cid]
        assert source['eligible'] and source['source_sha256']==raw['sha256']==row['source_sha256']
        assert source['answer_file_sha256']==c.sha(BASE/'dev-answers-seed0.json')==row['answer_file_sha256']
        assert source['minimal_polynomials']==[a['minimal_polynomial'] for a in raw['answers']]
        p = sp.prod(sp.Poly.from_list(list(map(sp.Rational,a['minimal_polynomial'])),T).as_expr() for a in raw['answers'])
        assert sp.expand(p-sp.sympify(source['polynomial']))==0
        assert sp.expand(p-sp.sympify(row['polynomial']))==0
        path = ROOT/source['dsl_source']
        assert c.sha(path)==source['dsl_sha256']==row['dsl_sha256']
        dsl = json.loads(path.read_text())
        assert inputs[cid]['dsl']==dsl
        assert hashlib.sha256(json.dumps(dsl,sort_keys=True).encode()).hexdigest()==source['dsl_canonical_sha256']
        q=sp.Poly(sp.expand(p*p.subs(T,-T)),T)
        records[cid]=dict(source, polynomial=str(q.as_expr()),degree=q.degree(),original_polynomial=str(p),
            original_category_ja='非所属', transformation='q(T)=p(T)*p(-T), no normalization or factor selection',
            sign=sign_rule(dsl['target']))
        cases[cid]={'id':cid,'dsl':dsl}
        hashes[str(path)]=c.sha(path)
    f=io.StringIO(newline='');w=csv.writer(f);w.writerow(['order','id','id_sha256'])
    w.writerows((i,cid,hashlib.sha256(cid.encode()).hexdigest()) for i,cid in enumerate(ids,1))
    path=E/'target-order.csv'
    if path.exists():
        assert list(csv.reader(path.open()))==list(csv.reader(io.StringIO(f.getvalue())))
    else:
        path.write_text(f.getvalue())
    hashes[str(E/'target-order.csv')]=c.sha(E/'target-order.csv')
    version=subprocess.check_output(['Singular','--version'],text=True,stderr=subprocess.STDOUT)
    assert stable_version(version)==stable_version(old['singular_version'])==stable_version(unseen['singular_version'])
    m=dict(scope='preregistration9b development nonmembers only',order=ids,records=records,cases=cases,
        hashes=hashes,original_implementation_hashes=ORIGINAL_HASHES,singular_version=version,
        singular_version_sha256=hashlib.sha256(version.encode()).hexdigest(),
        singular_stable_version_sha256=hashlib.sha256(stable_version(version).encode()).hexdigest(),
        singular_version_note='Full raw output retained and hashed. Comparison ignores only runtime random= seed and Path line; binary hashes must match.',python=sys.executable,
        parallelism=4,cpus_per_problem=1,wall_seconds_per_problem=600,memory_bytes_per_problem=c.MEM,
        max_file_bytes=c.MAX_FILE,attempts_per_problem=1,order_rule='ascending SHA256(problem ID)',created_unix=time.time(),
        interruption_policy='Interrupted attempts are archived, not results; restart from scratch once only per ID. No retry of completed outcomes.',
        predictions={'C6':'>=60%','C7':'>=70%','C8':'>=50%'},development_original_certified=65,development_translated=254,
        timing_note='負荷付き参考値。各問開始時の1分load averageを記録。')
    c.write_json(E/'pre-run-hashes.json',m)
    progress(m,[],[],'実行前固定済み')
    print('frozen',len(ids),flush=True)


def token(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]
    except FileNotFoundError:
        return None


def stop_owned(receipt):
    pid=receipt.get('worker_pid')
    if pid and token(pid)==receipt.get('worker_start_ticks'):
        assert os.getpgid(pid)==pid
        os.killpg(pid,signal.SIGKILL)


def archive_interruption(cid, reason):
    work=E/'runs'/(cid+'.work')
    archive=E/'interrupted'/(cid+'.work')
    assert not archive.exists(), 'SECOND_INTERRUPTION_NO_MORE_RESTART:'+cid
    receipt=json.loads((work/'start.json').read_text()) if (work/'start.json').exists() else {'id':cid}
    stop_owned(receipt)
    c.write_json(work/'interruption.json',dict(id=cid,status='中断',reason=reason,result_counted=False,
        recorded_unix=time.time(),restart_from_scratch_allowed_once=True))
    output=E/'runs'/(cid+'.json')
    if output.exists():
        output.rename(work/'unfinalized-result.json')
    (E/'interrupted').mkdir(exist_ok=True)
    inventory=[{'path':str(p.relative_to(work)),'sha256':c.sha(p),'bytes':p.stat().st_size} for p in sorted(work.rglob('*')) if p.is_file()]
    c.write_json(work/'archive-hashes.json',inventory)
    work.rename(archive)


def launch(cid,cpu,m):
    check_frozen(m)
    work=E/'runs'/(cid+'.work');work.mkdir(exist_ok=False)
    start=time.monotonic()
    c.write_json(work/'input.json',m['cases'][cid]);c.write_json(work/'candidate.json',m['records'][cid])
    receipt=dict(id=cid,start_unix=time.time(),load_average_1m=os.getloadavg()[0],cpu=cpu,parallelism=4,
        wall_seconds=600,memory_bytes=c.MEM,attempt=1,physical_start_number=2 if (E/'interrupted'/(cid+'.work')).exists() else 1,
        controller_pid=os.getpid(),pre_run_hashes_sha256=c.sha(E/'pre-run-hashes.json'))
    c.write_json(work/'start.json',receipt)
    log=(work/'worker.log').open('w')
    proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker',cid],stdout=log,
        stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True,preexec_fn=lambda:limits(cpu))
    receipt.update(worker_pid=proc.pid,worker_start_ticks=token(proc.pid))
    c.write_json(work/'start.json',receipt)
    return dict(cid=cid,work=work,start=start,peak=0,proc=proc,log=log,receipt=receipt)


def progress(m,active,completed,state):
    from collections import Counter
    done=[json.loads((E/'runs'/(cid+'.json')).read_text()) for cid in completed]
    counts=Counter(r['status'] for r in done)
    lines=['# 事前登録9b：開発群の非所属163問','',
        f'状態：{state}。完了 {len(completed)}/163、実行中 {len(active)}。', '',
        '600秒・8 GiB・1 CPU/問・並列4固定。IDのSHA-256昇順、各1回、対象交換なし。',
        '中断は結果に数えず保存し、該当問だけ最初から1回再実行可能。完了した結果の再試行なし。',
        'eval/ と eval9b/unseen/ は読み取りのみ。時間は負荷付き参考値。','',str(dict(counts)),'']
    for j in active:
        lines.append(f'- {j["cid"]}：経過 {time.monotonic()-j["start"]:.1f}秒、開始時load {j["receipt"]["load_average_1m"]:.2f}')
    tmp=E/'progress.tmp';tmp.write_text('\n'.join(lines)+'\n');tmp.replace(E/'progress.md')


def campaign():
    lock=(E/'controller.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    m=json.loads((E/'pre-run-hashes.json').read_text());check_frozen(m)
    version=subprocess.check_output(['Singular','--version'],text=True,stderr=subprocess.STDOUT)
    assert stable_version(version)==stable_version(m['singular_version'])
    (E/'runs').mkdir(exist_ok=True)
    completed=[]
    for cid in m['order']:
        path=E/'runs'/(cid+'.json');work=E/'runs'/(cid+'.work')
        if path.exists() and json.loads(path.read_text()).get('supervisor_finalized') is True:
            completed.append(cid)
        elif work.exists():
            archive_interruption(cid,'controller ended before supervisor finalization')
        else:
            assert not path.exists(), 'ORPHAN_RESULT:'+cid
    queue=[cid for cid in m['order'] if cid not in completed]
    cpus=sorted(os.sched_getaffinity(0))[:4];assert len(cpus)==4
    c.write_json(E/'controller.json',dict(pid=os.getpid(),sid=os.getsid(0),pgid=os.getpgrp(),
        start_ticks=token(os.getpid()),start_unix=time.time(),parallelism=4,pending=queue,completed=len(completed)))
    def terminated(sig,frame):
        raise RuntimeError('CONTROLLER_SIGNAL_'+str(sig))
    signal.signal(signal.SIGTERM,terminated);signal.signal(signal.SIGINT,terminated)
    run,_=c.dependencies();active=[];last=0
    try:
        while queue or active:
            while queue and len(active)<4:
                cpu=next(x for x in cpus if x not in {j['receipt']['cpu'] for j in active})
                active.append(launch(queue.pop(0),cpu,m))
            for job in active[:]:
                if poll(job,run):
                    output=E/'runs'/(job['cid']+'.json');r=json.loads(output.read_text())
                    if r.get('supervisor_returncode')==-signal.SIGXFSZ:
                        r.update(status='resource_limit',reason_code='ARTIFACT_SIZE_LIMIT',proof_verified=False)
                    r.update(supervisor_finalized=True,physical_start_number=job['receipt']['physical_start_number'])
                    c.write_json(output,r)
                    active.remove(job);completed.append(job['cid'])
            if time.monotonic()-last>=5:
                progress(m,active,completed,'実行中');last=time.monotonic()
            time.sleep(.1)
        check_frozen(m)
        interrupted=[p.name.removesuffix('.work') for p in (E/'interrupted').glob('*.work')] if (E/'interrupted').exists() else []
        c.write_json(E/'completion.json',dict(completed=completed,attempts=len(completed),retries=0,
            interruptions_not_results=interrupted,restarted_once=len(interrupted),finished_unix=time.time(),all_frozen_hashes_match=True))
        progress(m,active,completed,'全163問終了・集計中')
        subprocess.run([sys.executable,str(E/'report_dev_9b.py')],check=True)
        progress(m,active,completed,'完了')
    except BaseException:
        for job in active:
            stop_owned(job['receipt']);job['proc'].wait();job['log'].close()
            archive_interruption(job['cid'],'controller interrupted; not a result')
        progress(m,[],completed,'中断・runで再開可能（中断問は1回だけ再実行）')
        raise


if __name__=='__main__':
    action=sys.argv[1]
    if action=='freeze':freeze()
    elif action=='run':campaign()
    elif action=='worker':
        m=json.loads((E/'pre-run-hashes.json').read_text());check_frozen(m)
        assert sys.argv[2] in m['order']
        c.write_json(E/'runs'/(sys.argv[2]+'.work')/'runtime-limits.json',dict(affinity=sorted(os.sched_getaffinity(0)),rlimit_as=resource.getrlimit(resource.RLIMIT_AS),rlimit_fsize=resource.getrlimit(resource.RLIMIT_FSIZE),threads={k:os.environ[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}))
        c.HERE=E;c.source_hashes=lambda:m['original_implementation_hashes']
        c.worker(sys.argv[2])
    else:raise SystemExit('unknown action')
