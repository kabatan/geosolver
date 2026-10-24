#!/usr/bin/env python3
"""Preregistration 9 development adapter; original algebra/checker are unchanged.

Only redirects certify.worker's HERE and source_hashes (absolute original paths).
The original worker, translation, script, parsing, proof extraction and verifier
are used without editing. Each problem has an exclusive ledger and one process
group, one CPU, 600 wall seconds including startup/verification, and 8 GiB.
"""
from __future__ import annotations
import collections
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import signal
import statistics
import subprocess
import sys
import time

DEV = Path(__file__).resolve().parent
BASE = DEV.parent.parent
ROOT = BASE.parents[2]
MEM = 8 << 30
WALL = 600
PARALLELISM = 2
MAX_FILE = 2_900_000
sys.dont_write_bytecode = True
sys.path.insert(0, str(BASE))
import certify as cert
cert.environment()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, value):
    cert.write_json(p, value)


def shared_checks():
    """Read-only references; reject mismatching hashes before any attempt."""
    actual = cert.source_hashes()
    names = ('certify.py', 'verify_certificate.py', 'strong_translate.py', 'run_strong.py')
    references = []
    for name in ('pre-run-hashes.json', 'pre-eval-check.md'):
        p = DEV.parent / name
        if not p.exists():
            references.append({'path': str(p.relative_to(ROOT)), 'exists': False})
            continue
        content = p.read_text()
        checked = {}
        if p.suffix == '.json':
            obj = json.loads(content)
            def walk(v, keys=()):
                if isinstance(v, dict):
                    for k, x in v.items():
                        yield from walk(x, keys + (str(k),))
                elif isinstance(v, list):
                    for x in v:
                        yield from walk(x, keys)
                elif isinstance(v, str):
                    yield keys, v
            for keys, value in walk(obj):
                if re.fullmatch(r'[0-9a-f]{64}', value):
                    for code in names:
                        if any(Path(k).name == code for k in keys):
                            expected = next(h for f, h in actual.items() if Path(f).name == code)
                            if value != expected:
                                raise RuntimeError('SHARED_CODE_HASH_MISMATCH:' + code)
                            checked[code] = value
        else:
            for line in content.splitlines():
                for code in names:
                    if code in line:
                        values = re.findall(r'\b[0-9a-f]{64}\b', line)
                        expected = next(h for f, h in actual.items() if Path(f).name == code)
                        if values and expected not in values:
                            raise RuntimeError('SHARED_CHECK_HASH_MISMATCH:' + code)
                        if values:
                            checked[code] = expected
        references.append({'path': str(p.relative_to(ROOT)), 'exists': True,
                           'sha256': sha(p), 'verified_code_hashes': checked})
    return references


def prepare():
    if (DEV / 'pre-run-hashes.json').exists() or (DEV / 'runs').exists():
        raise RuntimeError('FREEZE_ALREADY_EXISTS_NO_OVERWRITE')
    refs = shared_checks()
    import sympy as sp
    T = sp.Symbol('T')
    source = BASE / 'dev-answers-seed0.json'
    answers = json.loads(source.read_text())
    cases_path = ROOT / 'benchmarks/cases.jsonl'
    cases = [json.loads(l) for l in cases_path.read_text().splitlines()]
    by_id = {c['id']: c for c in cases}
    assert len(answers) == len(cases) == len(by_id) == 323 and set(answers) == set(by_id)
    excluded = set((cert.STRONG / 'dev5-ids.txt').read_text().splitlines())
    records = []
    for cid in sorted(answers, key=lambda x: hashlib.sha256(x.encode()).hexdigest()):
        raw = answers[cid]
        case = by_id[cid]
        dsl_path = ROOT / 'benchmarks' / case['dsl_path']
        assert json.loads(dsl_path.read_text()) == case['dsl'], cid
        polys = [x.get('minimal_polynomial') for x in raw.get('answers', [])]
        eligible = bool(polys) and all(polys)
        polynomial = sp.Poly(1, T, domain=sp.QQ)
        if eligible:
            for coefficients in polys:
                assert isinstance(coefficients, list) and all(isinstance(c, str) for c in coefficients)
                p = sp.Poly.from_list([sp.Rational(c) for c in coefficients], T, domain=sp.QQ)
                assert p.degree() >= 1
                polynomial *= p
        record = {'id': cid, 'group': 'dev323',
                  'id_sha256': hashlib.sha256(cid.encode()).hexdigest(),
                  'status': raw['status'], 'answer_count': len(raw.get('answers', [])),
                  'source': str(source.relative_to(ROOT)), 'source_sha256': raw['sha256'],
                  'answer_file_sha256': sha(source), 'coefficient_order': 'descending',
                  'minimal_polynomials': polys, 'eligible': eligible and cid not in excluded,
                  'excluded_dev5': cid in excluded,
                  'dsl_source': str(dsl_path.relative_to(ROOT)), 'dsl_sha256': sha(dsl_path),
                  'dsl_canonical_sha256': hashlib.sha256(json.dumps(case['dsl'], sort_keys=True).encode()).hexdigest()}
        if eligible:
            record.update(polynomial=str(polynomial.as_expr()), degree=polynomial.degree(),
                          coefficients=list(map(str, polynomial.all_coeffs())), source_kind='solver_record_product')
        else:
            record['exclusion_reason'] = 'no_answer_found' if not polys else 'missing_minimal_polynomial'
        records.append(record)
    write(DEV / 'candidates.json', records)
    inputs = [{'id': r['id'], 'dsl': by_id[r['id']]['dsl']} for r in records if r['eligible']]
    with (DEV / 'inputs.jsonl').open('x') as f:
        for c in inputs:
            f.write(json.dumps(c, ensure_ascii=False) + '\n')
    with (DEV / 'target-order.csv').open('x') as f:
        w = csv.writer(f); w.writerow(['order', 'id', 'id_sha256'])
        w.writerows((i, r['id'], r['id_sha256']) for i, r in enumerate((r for r in records if r['eligible']), 1))
    version = subprocess.check_output(['Singular', '--version'], text=True, stderr=subprocess.STDOUT)
    sources = cert.source_hashes()
    for p in [source, cases_path, BASE / 'preregistration-9.md', BASE / 'README.md',
              BASE / 'development-changes.json', Path(__file__)]:
        sources[str(p)] = sha(p)
    write(DEV / 'pre-run-hashes.json', {
        'created_unix': time.time(), 'scope': 'development only; preregistration-9 appendix',
        'parallelism': PARALLELISM, 'wall_seconds': WALL, 'memory_bytes': MEM,
        'threads_per_problem': 1, 'attempts_per_problem': 1, 'retry': False,
        'max_file_bytes': MAX_FILE, 'python': sys.executable,
        'sources': sources, 'singular_version': version,
        'singular_version_sha256': hashlib.sha256(version.encode()).hexdigest(),
        'inputs_sha256': sha(DEV / 'inputs.jsonl'), 'candidates_sha256': sha(DEV / 'candidates.json'),
        'target_order_sha256': sha(DEV / 'target-order.csv'),
        'target_ids': [c['id'] for c in inputs], 'input_provenance': records,
        'dev5_overlap': sorted(set(answers) & excluded), 'shared_read_only_references': refs,
        'success_definition': 'translation complete; J nonunit; Rab member; at least one independent identity verified; no power contradiction; full attempt within limits',
        'translated_denominator': 'translation.json saved (translation, prepare, Singular script/model construction completed)',
        'timing_note': '負荷付き参考値。全体時間は起動・変換・飽和・基底・正規形・証明書・独立検算を含む。',
        'adapter': 'Import original certify.worker; redirect HERE to eval/dev; source_hashes continues hashing original absolute paths; do not call dev5-only campaign/supervise.'})
    (DEV / 'runs').mkdir()
    progress([], {}, len(inputs), '準備完了')
    print(json.dumps({'targets':len(inputs), 'excluded_no_polynomial':sum(not r['eligible'] and not r['excluded_dev5'] for r in records), 'dev5_overlap':sorted(set(answers)&excluded)}, ensure_ascii=False))


def frozen_check(manifest):
    for p, h in manifest['sources'].items():
        if sha(p) != h:
            raise RuntimeError('FROZEN_SOURCE_CHANGED:' + p)
    for file, key in [('inputs.jsonl','inputs_sha256'), ('candidates.json','candidates_sha256'), ('target-order.csv','target_order_sha256')]:
        if sha(DEV / file) != manifest[key]:
            raise RuntimeError('FROZEN_INPUT_CHANGED:' + file)
    for r in manifest['input_provenance']:
        if sha(ROOT / r['dsl_source']) != r['dsl_sha256']:
            raise RuntimeError('DSL_CHANGED:' + r['id'])


def worker(cid):
    manifest = json.loads((DEV / 'pre-run-hashes.json').read_text())
    original_paths = list(cert.source_hashes())
    cert.source_hashes = lambda: {p: sha(p) for p in original_paths}
    cert.HERE = DEV
    cert.worker(cid)


def category(r):
    status = r.get('status')
    if status == 'timeout': return '時間上限'
    if status == 'resource_limit': return '資源上限'
    if status == 'unsupported': return '変換不能'
    if status in ('error', 'worker_error', 'inconsistent_methods'): return '実装エラー'
    if status == 'nonmember': return '非所属'
    if (status == 'member' and r.get('unit_ideal') is False
        and r.get('rabinowitsch', {}).get('status') == 'member'
        and r.get('proof_verified') and r.get('power', {}).get('status') != 'invalid_singular_output'):
        return '認証'
    return '検算不能'


def progress(done, active, total, state):
    counts = collections.Counter(category(r) for r in done)
    text = f'事前登録9・開発群の進捗\n\n状態：{state}。終了 {len(done)}/{total} 問、実行中 {len(active)} 問。並列2固定、各問600秒・8 GiB・1 CPU、再試行0。\n\n'
    text += '区分：' + '、'.join(f'{k} {v}' for k,v in counts.items()) + '。\n\n'
    for cid, a in active.items():
        text += f'- {cid}：経過 {time.monotonic()-a["start"]:.1f} 秒、開始時1分load average {a["load"]:.2f}\n'
    text += '\n時間は共有機の負荷付き参考値。開発外29問の出力には書き込まない。\n'
    p=DEV/'progress.md'; tmp=p.with_suffix('.tmp'); tmp.write_text(text); tmp.replace(p)


def launch(cid, case, candidate, slot, manifest):
    frozen_check(manifest)
    shared_checks()
    work=DEV/'runs'/(cid+'.work'); work.mkdir(exist_ok=False)
    start=time.monotonic(); load=os.getloadavg()[0]
    write(work/'input.json', case); write(work/'candidate.json', candidate)
    cpus=sorted(os.sched_getaffinity(0)); cpu=cpus[slot % len(cpus)]
    write(work/'attempt.json', {'id':cid, 'start_unix':time.time(), 'load_average_1m':load,
        'cpu':cpu, 'parallelism':2, 'attempt':1, 'wall_seconds':600,'memory_bytes':MEM,
        'timing_note':'負荷付き参考値', 'pre_run_hashes_sha256':sha(DEV/'pre-run-hashes.json')})
    def limits():
        resource.setrlimit(resource.RLIMIT_AS,(MEM,MEM))
        resource.setrlimit(resource.RLIMIT_FSIZE,(MAX_FILE,MAX_FILE))
        os.sched_setaffinity(0,{cpu})
    log=(work/'worker.log').open('w')
    proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker',cid],
        env=dict(os.environ),stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
    return {'proc':proc,'log':log,'start':start,'load':load,'peak':0,'slot':slot,'candidate':candidate}


def finish(cid, a, reason):
    p=a['proc']; work=DEV/'runs'/(cid+'.work'); output=DEV/'runs'/(cid+'.json')
    try: os.killpg(p.pid,signal.SIGKILL)
    except ProcessLookupError: pass
    p.wait(); a['log'].close()
    if output.exists() and not reason:
        r=json.loads(output.read_text())
    else:
        checkpoint=work/'progress.json'
        r=json.loads(checkpoint.read_text()) if checkpoint.exists() else {'id':cid,'candidate':a['candidate']}
        if (work/'singular.log').exists():
            parsed,blocks=cert.parse_log((work/'singular.log').read_text())
            for m in ('power','rabinowitsch'):
                parsed[m].update({k:v for k,v in r.get(m,{}).items() if k in ('independent_verification','verification_seconds','certificate')})
            r.update(parsed); write(work/'algebra-output.json',blocks)
        r.update(status='timeout' if reason=='TIME_LIMIT' else 'resource_limit' if reason else 'worker_error',
                 reason_code=reason or f'WORKER_EXIT_{p.returncode}',proof_verified=False)
    if r.get('reason_code')=='MemoryError' or r.get('singular_returncode') in (-signal.SIGXFSZ,) or p.returncode == -signal.SIGXFSZ:
        r.update(status='resource_limit',reason_code='MEMORY_OR_FILE_LIMIT',proof_verified=False)
    r.update(wall_seconds=time.monotonic()-a['start'],peak_tree_rss_bytes=a['peak'],
             supervisor_returncode=p.returncode,attempts=1,campaign_parallelism=2,
             load_average_1m_start=a['load'],translation_completed=(work/'translation.json').exists())
    r['category_ja']=category(r)
    write(output,r)
    print(json.dumps({k:r.get(k) for k in ('id','category_ja','wall_seconds','reason_code')},ensure_ascii=False),flush=True)
    return r


def run():
    manifest=json.loads((DEV/'pre-run-hashes.json').read_text())
    frozen_check(manifest); shared_checks()
    # A second launch is never allowed, even if the previous controller died.
    with (DEV/'campaign-start.json').open('x') as f:
        json.dump({'pid':os.getpid(),'start_unix':time.time(),'parallelism':2},f)
    cases={c['id']:c for c in map(json.loads,(DEV/'inputs.jsonl').read_text().splitlines())}
    candidates={r['id']:r for r in json.loads((DEV/'candidates.json').read_text())}
    pending=list(manifest['target_ids']); active={}; done=[]; last_progress=0
    run_strong,_=cert.dependencies()
    try:
        while pending or active:
            while pending and len(active)<2:
                cid=pending.pop(0); slots={a['slot'] for a in active.values()}; slot=next(x for x in range(2) if x not in slots)
                active[cid]=launch(cid,cases[cid],candidates[cid],slot,manifest)
            for cid,a in list(active.items()):
                p=a['proc']; a['peak']=max(a['peak'],run_strong.own_tree_rss(p.pid))
                reason='TIME_LIMIT' if time.monotonic()-a['start']>=WALL else 'MEMORY_LIMIT' if a['peak']>=MEM else None
                if reason or p.poll() is not None:
                    done.append(finish(cid,a,reason)); del active[cid]
            if time.monotonic()-last_progress>=5:
                progress(done,active,len(cases),'実行中'); last_progress=time.monotonic()
            time.sleep(.1)
    finally:
        for cid,a in list(active.items()):
            done.append(finish(cid,a,'CONTROLLER_STOP')); del active[cid]
    frozen_check(manifest)
    write(DEV/'campaign-end.json',{'end_unix':time.time(),'completed':len(done),'retries':0})
    report()
    progress(done,{},len(cases),'完了')


def report():
    candidates=json.loads((DEV/'candidates.json').read_text()); rows=[]; results=[]
    fields=['id','group','p_source','source_sha256','answer_file_sha256','answer_count','category_ja','degree','polynomial','wall_seconds',
        'worker_wall_seconds','translation_seconds','saturation_seconds','singular_wall_seconds',
        'power_basis_seconds','power_nf_seconds','power_basis_size','power_certificate_seconds','power_verification_seconds','power_independent_verification',
        'rabinowitsch_basis_seconds','rabinowitsch_nf_seconds','rabinowitsch_basis_size','rabinowitsch_certificate_seconds','rabinowitsch_verification_seconds','rabinowitsch_independent_verification',
        'translation_completed','unit_ideal','independent_verification','power_status','rabinowitsch_status','last_algebra_event','reason_code','reason',
        'load_average_1m_start','peak_tree_rss_bytes','attempts','dsl_source','dsl_sha256','id_sha256']
    for c in candidates:
        row={k:c.get(k) for k in fields if k in c}; row['p_source']=c['source']+'; original_sha256='+c['source_sha256']
        if not c['eligible']:
            row.update(category_ja='対象外：dev5' if c['excluded_dev5'] else '対象外：答えなし',reason_code=c.get('exclusion_reason'),attempts=0)
        else:
            r=json.loads((DEV/'runs'/(c['id']+'.json')).read_text()); results.append(r)
            row.update({k:r[k] for k in fields if k in r}); row['category_ja']=category(r)
            row['independent_verification']=any(r.get(m,{}).get('independent_verification')=='verified' for m in ('power','rabinowitsch'))
            for method in ('power','rabinowitsch'):
                obj=r.get(method,{})
                for key in ('basis_seconds','basis_size','certificate_seconds','verification_seconds','independent_verification','status'):
                    row[method+'_'+key]=obj.get(key)
                row[method+'_nf_seconds']=obj.get('normal_form_seconds')
        rows.append(row)
    with (DEV/'per-problem.csv').open('w') as f:
        w=csv.DictWriter(f,fields); w.writeheader(); w.writerows(rows)
    counts=collections.Counter(category(r) for r in results)
    n=len(results); translated=sum(r['translation_completed'] for r in results); passed=[r for r in results if category(r)=='認証']
    median=statistics.median(r['wall_seconds'] for r in passed) if passed else None
    summary={'counts':dict(counts),'all_targets':n,'translated':translated,'certified':len(passed),
        'rate_all':len(passed)/n,'rate_translated':len(passed)/translated if translated else None,
        'certified_wall_median_seconds':median,'C1':bool(translated and len(passed)/translated>=.5),
        'C2':bool(median is not None and median<=2),'attempts':sum(r['attempts'] for r in results),'retries':0,
        'excluded_no_answer':sum(not c['eligible'] and not c['excluded_dev5'] for c in candidates),'dev5_overlap':[c['id'] for c in candidates if c['excluded_dev5']]}
    write(DEV/'summary.json',summary)
    order=['認証','非所属','変換不能','時間上限','資源上限','実装エラー','検算不能']
    text='区分別件数：'+'、'.join(f'{k} {counts[k]}問' for k in order)+f'。対象外：答えなし {summary["excluded_no_answer"]}問。\n\n'
    text+=f'認証率は全対象 {len(passed)}/{n}（{len(passed)/n:.2%}）、変換できた問題 {len(passed)}/{translated}（{len(passed)/translated:.2%}）。開発群だけの値で、C1（50%以上）は'+('的中' if summary['C1'] else '外れ')+'。'
    text+=f'認証問題の全体時間中央値は {median:.3f}秒。C2（2秒以下）は'+('的中' if summary['C2'] else '外れ')+'。\n\n' if median is not None else '認証がないためC2は判定不能。\n\n'
    text+=f'母集団323問のうち、最小多項式が全答えにある{n}問を各1回評価した。対象外10問は答え自体がない3問と、答え記録はあるが最小多項式がない7問。dev5との重複は0問で、除外追加はない。複数答えは重複も省かず全最小多項式を掛けた。処理順は問題IDのSHA-256昇順（target-order.csv）。\n\n'
    text+='並列2固定、各問600秒・8 GiB・1 CPU。再試行・問題の入れ替え・代用は0。時間は共有機の負荷付き参考値で、起動から変換・飽和・基底・正規形・証明書抽出・独立検算までを含む。各問開始時の1分load averageをCSVとattempt.jsonに保存した。変換できた問題の母数はtranslation.json保存まで完了した問（その後の失敗も含む）。\n\n'
    text+='非所属・変換不能・時間上限の内訳と代表例：\n\n'
    for cat in ['非所属','変換不能','時間上限']:
        group=[r for r in results if category(r)==cat]
        buckets=collections.defaultdict(list)
        for r in group:
            key=(r.get('reason_code','不明')+': '+r.get('reason','')) if cat=='変換不能' else r.get('last_algebra_event') or r.get('stage') or '不明'
            buckets[key].append(r['id'])
        if not buckets: text+=f'- {cat}：0問。\n'
        for key,ids in sorted(buckets.items(),key=lambda kv:(-len(kv[1]),kv[0])):
            text+=f'- {cat}：{key}、{len(ids)}問（例：{", ".join(ids[:3])}）。\n'
    for cat in ['資源上限','実装エラー','検算不能']:
        group=[r for r in results if category(r)==cat]
        if group:
            text+=f'\n{cat}：'+ '、'.join(f'{reason} {count}問' for reason,count in collections.Counter(r.get('reason_code') or r.get('status') for r in group).items())+'。\n'
    text+='\n非所属は、この複素数の等式・非零条件によるJではpが従わないという計算結果であり、solverの誤答とは扱わない。符号・範囲・根号の枝などを失うことで余分な解が残り得るが、個別原因はこの集計だけでは断定できない。非所属の基底計算には独立検算がない。認証も多項式関係の認証に限られ、実図の存在・一意性・答え集合の完全性は保証しない。Jが単位の場合は成功にせず検算不能に含めた。\n\n'
    text+='dev5（評価外・別掲）：AIME-2005-I-01、AIME-2012-I-14、HMMT-2011-FEB-GUTS-01、HMMT-2019-FEB-GUTS-17、HMMT-2023-FEB-GUTS-03。今回の323問に含まれず、再実行していない。既存の段階A結果は../../README.mdを参照。\n\n'
    text+='入力・コード・Singularの固定情報はpre-run-hashes.json、各問の詳細はper-problem.csvとruns/。certify.pyとverify_certificate.pyは変更せず、run_dev.pyは既存workerの出力先だけを切り替え、元の絶対パスをハッシュ検査した。eval直下の既存記録は参照のみ。\n'
    (DEV/'answer-dev.md').write_text(text)
    inventory=[{'path':str(p.relative_to(DEV)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(DEV.rglob('*')) if p.is_file() and p.name not in ('artifact-hashes.json','artifact-hashes.jsonl','progress.md')]
    assert all(x['bytes']<=MAX_FILE for x in inventory), 'ARTIFACT_SIZE_LIMIT'
    # JSONL keeps the audit index comfortably below the file size limit.
    with (DEV/'artifact-hashes.jsonl').open('w') as f:
        for r in inventory: f.write(json.dumps(r)+'\n')


if __name__=='__main__':
    action=sys.argv[1]
    if action=='prepare': prepare()
    elif action=='worker': worker(sys.argv[2])
    elif action=='run': run()
    elif action=='report': report()
    else: raise SystemExit('unknown action')
