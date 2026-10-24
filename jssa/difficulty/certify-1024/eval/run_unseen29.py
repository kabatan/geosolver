#!/usr/bin/env python3
"""Preregistration 9 external runner; unchanged certify.worker, no retry."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

E = Path(__file__).resolve().parent
BASE = E.parent
sys.path.insert(0, str(BASE))
import certify as c
c.environment()
ORIGINAL_HASHES = c.source_hashes()
ROOT = BASE.parents[2]
TARGET = c.STRONG / 'stageB/targets-unseen29.txt'
PYTHON = sys.executable

def dump(p, obj):
    c.write_json(p, obj)

def configure(destination):
    c.HERE = destination
    c.source_hashes = lambda: ORIGINAL_HASHES

def limits(cpu):
    resource.setrlimit(resource.RLIMIT_AS, (c.MEM, c.MEM))
    resource.setrlimit(resource.RLIMIT_FSIZE, (c.MAX_FILE, c.MAX_FILE))
    os.sched_setaffinity(0, {cpu})

def launch(cid, case, candidate, destination, cpu, frozen):
    for path, expected in frozen.items():
        if c.sha(path) != expected:
            raise RuntimeError('FROZEN_HASH_MISMATCH:' + path)
    work = destination / 'runs' / (cid + '.work')
    work.mkdir(exist_ok=False)
    start = time.monotonic()
    dump(work/'input.json', case)
    dump(work/'candidate.json', candidate)
    receipt = {'id': cid, 'start_unix': time.time(), 'load_average_1m': os.getloadavg()[0],
               'cpu': cpu, 'parallelism': 4 if destination == E else 1,
               'wall_seconds': 600, 'memory_bytes': c.MEM, 'attempt': 1}
    dump(work/'start.json', receipt)
    log = (work/'worker.log').open('w')
    proc = subprocess.Popen([PYTHON, str(__file__), '--worker', cid, '--destination', str(destination)],
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                            preexec_fn=lambda: limits(cpu))
    return dict(cid=cid, destination=destination, work=work, start=start, peak=0, proc=proc, log=log, receipt=receipt)

def poll(job):
    run, _ = c.dependencies()
    proc = job['proc']
    job['peak'] = max(job['peak'], run.own_tree_rss(proc.pid))
    elapsed = time.monotonic()-job['start']
    reason = 'TIME_LIMIT' if elapsed >= 600 else 'MEMORY_LIMIT' if job['peak'] >= c.MEM else None
    # Enforce artifact ceiling also on temporary writes.
    if any(p.stat().st_size > c.MAX_FILE for p in job['work'].iterdir() if p.is_file()):
        reason = 'ARTIFACT_SIZE_LIMIT'
    if not reason and proc.poll() is None:
        return False
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()
    job['log'].close()
    output = job['destination']/'runs'/(job['cid']+'.json')
    if reason or not output.exists():
        progress = job['work']/'progress.json'
        result = json.loads(progress.read_text()) if progress.exists() else {'id': job['cid']}
        slog = job['work']/'singular.log'
        if slog.exists():
            parsed, blocks = c.parse_log(slog.read_text())
            for m in ('power','rabinowitsch'):
                parsed[m].update({k:v for k,v in result.get(m,{}).items()
                                 if k in ('independent_verification','verification_seconds','certificate')})
            result.update(parsed)
            dump(job['work']/'algebra-output.json', blocks)
        result.update(status='timeout' if reason=='TIME_LIMIT' else 'resource_limit' if reason else 'worker_error',
                      reason_code=reason or f'WORKER_EXIT_{proc.returncode}', proof_verified=False)
    else:
        result = json.loads(output.read_text())
    # A failed worker caused by address-space exhaustion remains a resource failure.
    if result.get('reason_code') == 'MemoryError' or result.get('singular_returncode') in (-9,-11,-6,-25):
        result.update(status='resource_limit', proof_verified=False)
    result.update(wall_seconds=elapsed, peak_tree_rss_bytes=job['peak'], attempts=1,
                  supervisor_returncode=proc.returncode, start_receipt=job['receipt'])
    result.setdefault('limits', {}).update(wall_seconds=600, memory_bytes=c.MEM, threads=1,
                                         parallelism=job['receipt']['parallelism'])
    dump(output, result)
    print(json.dumps({k:result.get(k) for k in ('id','status','proof_verified','wall_seconds')},ensure_ascii=False), flush=True)
    return True

def precheck():
    dest = E/'precheck'
    dest.mkdir(exist_ok=True)
    (dest/'runs').mkdir(exist_ok=True)
    dump(dest/'code-hashes.json', ORIGINAL_HASHES)
    import importlib.util
    spec = importlib.util.spec_from_file_location('certify_smoke_checks', BASE/'smoke_checks.py')
    smoke_checks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke_checks)
    configure(dest)
    smoke_checks.main()
    cid = 'HMMT-2011-FEB-GUTS-01'
    case = next(json.loads(l) for l in (c.STRONG/'dev5-inputs.jsonl').read_text().splitlines() if json.loads(l)['id']==cid)
    candidate = json.loads((BASE/'candidates.json').read_text())['records'][cid]
    if not (dest/'runs'/(cid+'.json')).exists():
        job = launch(cid,case,candidate,dest,min(os.sched_getaffinity(0)),ORIGINAL_HASHES)
        while not poll(job):
            time.sleep(.1)
    result = json.loads((dest/'runs'/(cid+'.json')).read_text())
    passed = (result['status']=='nonmember' and result.get('stage')=='finished' and
              result.get('rabinowitsch',{}).get('status')=='nonmember' and result.get('unit_ideal') is False
              and not result.get('singular_errors') and result.get('last_algebra_event')=='finished end'
              and result.get('singular_returncode')==0)
    text = '# 評価前の確認（評価結果に含めない）\n\n'
    text += '合成7例・改変棄却・旧証明書互換の確認は全て通過。rational_scalingは有理係数の括弧修正を実行して検証。\n\n'
    text += f'HMMT-2011-FEB-GUTS-01（dev5）：{result["status"]}、独立検算={result.get("proof_verified")}、全体{result["wall_seconds"]:.3f}秒。修正版による動作確認は{"通過" if passed else "失敗（評価停止）"}。既存dev5結果は変更しない。\n\n'
    text += 'HMMT-2011は正常終了した非所属。p=3T−1に対し、出力基底には9T²+36v−13と9v²−1があり、Tの符号等を元の実条件より広く許す。非所属は構文不備や実装失敗を意味しない。非所属証明の独立検算は未実装。\n\n'
    text += '事前確認の実行器に2点を修正：同名のexact-strong側合成チェックを読み込んだため絶対パス指定に変更（こちらも11項目通過、既存ファイルの内容差分なし）。また最初は認証を誤って必須としたが、事前確認は正常な非所属判定も許す動作確認であり、終了マーカー・エラーなし・非単位・両法無矛盾を確認して通過とした。HMMTは再実行せず同じ1回の記録を使用。\n\n'
    text += 'certify.py・verify_certificate.py・翻訳器は変更なし。Singularへの出力は整数多項式全体を括弧に入れてから分母で割り、エラー出力を棄却する。外部実行器だけを追加し、同じworkerを別出力先で呼ぶ。\n\n'
    for p,h in ORIGINAL_HASHES.items():
        if Path(p).name in ('certify.py','verify_certificate.py'):
            text += f'- `{p}`: `{h}`\n'
    text += '\n詳細：`precheck/smoke-checks.json`、`precheck/runs/`、`precheck/code-hashes.json`。事前確認の実行回数は評価の試行数に含めない。\n'
    (E/'pre-eval-check.md').write_text(text)
    dump(dest/'gate.json', {'passed':passed, 'evaluation_attempts':0, 'code_changes':[]})
    if not passed:
        raise SystemExit('HMMT_PRECHECK_FAILED; no code changes, no evaluation')

def prepare():
    assert json.loads((E/'precheck/gate.json').read_text())['passed']
    import sympy as sp
    T = sp.Symbol('T')
    ids = TARGET.read_text().splitlines()
    assert len(ids)==len(set(ids))==29 and not set(ids)&set(c.dev5())
    ids.sort(key=lambda s: hashlib.sha256(s.encode()).hexdigest())
    cases = {}
    hashes = dict(ORIGINAL_HASHES)
    for p in [TARGET, BASE/'preregistration-9.md',Path(__file__)]:
        hashes[str(p)] = c.sha(p)
    for group in 'ab':
        p=BASE.parent/f'unseen-2/{group}/cases.jsonl'
        hashes[str(p)] = c.sha(p)
        for line in p.read_text().splitlines():
            case=json.loads(line)
            if case['id'] in ids:
                assert case['id'] not in cases
                cases[case['id']]={'id':case['id'],'dsl':case['dsl']}
    assert set(cases)==set(ids)
    records={}
    for cid in ids:
        group='a' if cid.startswith('AIME') else 'b'
        directory=BASE.parent/f'unseen-2/{group}/execution/runs'/cid
        searched=[]; candidate=None
        for p in sorted(directory.glob('*.json'),key=lambda p:int(p.stem)):
            if int(p.stem)<301:
                continue
            raw=json.loads(p.read_text()); hashes[str(p)]=c.sha(p)
            searched.append({'path':str(p.relative_to(ROOT)),'sha256':c.sha(p)})
            assert raw.get('case_id')==cid
            answers=(raw.get('solver_result') or {}).get('answers',[])
            if not answers:
                continue
            polynomials=[]; descriptors=[]
            for a in answers:
                value=a.get('value',{})
                coeff=value.get('minimal_polynomial') if isinstance(value,dict) else None
                if not coeff:
                    if a.get('kind') != 'affine_pi':
                        raise ValueError('ANSWER_WITHOUT_MINPOLY:'+cid)
                    descriptors.append(a)
                    continue
                poly=sp.Poly.from_list(list(map(sp.Rational,coeff)),T)
                assert poly.degree()>=1 and poly.is_irreducible
                polynomials.append(poly.as_expr()); descriptors.append(value)
            product=sp.Poly(sp.prod(polynomials),T) if len(polynomials)==len(answers) else None
            candidate={'source_kind':'solver_record','source':str(p.relative_to(ROOT)),
                       'source_sha256':c.sha(p),'seed':int(p.stem),'answer_count':len(answers),
                       'polynomial':str(product.as_expr()) if product is not None else None,
                       'degree':product.degree() if product is not None else None,
                       'polynomial_missing_reason':None if product is not None else 'affine_pi answer; no value.minimal_polynomial; no substitution',
                       'json_paths':[['solver_result','answers',i,'value','minimal_polynomial'] for i in range(len(answers))],
                       'descriptors':descriptors,'branch':{'status':'not_used_in_proof','proof':False}}
            break
        records[cid]=candidate or {'source_kind':'no_answer','answer_count':0,'reason':'対象外：答えなし'}
        records[cid]['searched_solver_records']=searched
        records[cid]['dsl_sha256']=hashlib.sha256(json.dumps(cases[cid]['dsl'],sort_keys=True).encode()).hexdigest()
    manifest={'scope':'unseen29 only; development excluded','order':ids,'parallelism':4,
              'wall_seconds_per_problem':600,'memory_bytes_per_problem':c.MEM,'cpus_per_problem':1,
              'hashes':hashes,'singular_version':subprocess.check_output(['Singular','--version'],text=True,stderr=subprocess.STDOUT),
              'python':PYTHON,'records':records,'cases':cases,'code_changes':[],
              'runner_adaptation':'Unchanged certify.worker; HERE redirected to eval, source hashes retained from original location. External four-slot supervisor.',
              'timing_note':'負荷付きの参考値。各問開始直前の1分load averageを記録。',
              'created_unix':time.time()}
    if (E/'pre-run-hashes.json').exists():
        raise RuntimeError('ALREADY_FROZEN')
    dump(E/'pre-run-hashes.json',manifest)
    print('frozen',len(ids),'eligible',sum(r['answer_count']>0 for r in records.values()),flush=True)

def progress(manifest, active, completed, state):
    lines=['# 事前登録9：開発外29問の進捗','',f'状態：{state}。完了 {len(completed)}/29、実行中 {len(active)}。',
           '', '開発群は今回の対象外。600秒・8 GiB・1 CPU/問、4並列固定。IDのSHA-256昇順に開始。再試行・代用なし。',
           '時間は他作業の負荷付きの参考値。各問開始時の1分load averageは各 `.work/start.json` に記録。','']
    for cid in manifest['order']:
        if cid in completed:
            p=E/'runs'/(cid+'.json'); r=json.loads(p.read_text())
            lines.append(f'- {cid}: {r["status"]}, {r.get("wall_seconds",0):.3f}秒')
        elif any(j['cid']==cid for j in active):
            lines.append(f'- {cid}: 実行中')
    (E/'progress.md').write_text('\n'.join(lines)+'\n')

def campaign():
    m=json.loads((E/'pre-run-hashes.json').read_text())
    (E/'runs').mkdir(exist_ok=False)
    cpus=sorted(os.sched_getaffinity(0))
    assert len(cpus)>=4
    queue=list(m['order']); active=[]; completed=[]; last=0
    try:
        while queue or active:
            while queue and len(active)<4:
                cid=queue.pop(0); candidate=m['records'][cid]
                if not candidate['answer_count']:
                    dump(E/'runs'/(cid+'.json'),{'id':cid,'status':'no_answer','candidate':candidate,'attempts':0})
                    completed.append(cid); continue
                occupied={j['receipt']['cpu'] for j in active}
                cpu=next(cpu for cpu in cpus[:4] if cpu not in occupied)
                active.append(launch(cid,m['cases'][cid],candidate,E,cpu,m['hashes']))
            for j in active[:]:
                if poll(j):
                    active.remove(j); completed.append(j['cid'])
            if time.monotonic()-last>10:
                progress(m,active,completed,'実行中');last=time.monotonic()
            time.sleep(.1)
        progress(m,active,completed,'全29問終了')
        dump(E/'completion.json',{'completed':completed,'finished_unix':time.time(),'attempts':sum(m['records'][cid]['answer_count']>0 for cid in completed),'retries':0})
    finally:
        for j in active:
            try: os.killpg(j['proc'].pid,signal.SIGKILL)
            except ProcessLookupError: pass

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',nargs='?',choices=['precheck','prepare','run']);p.add_argument('--worker');p.add_argument('--destination',type=Path)
    a=p.parse_args()
    if a.worker:
        configure(a.destination);c.worker(a.worker)
    elif a.action=='precheck': precheck()
    elif a.action=='prepare': prepare()
    elif a.action=='run': campaign()
