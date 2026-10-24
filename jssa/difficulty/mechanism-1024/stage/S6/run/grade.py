"""Independent exact-set grading. Never imports geosolver; runs outside measurement."""
import csv
import json
import statistics
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

import sympy as sp
from common import HERE, S6, SOURCE, load, progress, save, sha, utc

X = sp.Symbol('x')

def primitive(poly):
    p = sp.Poly(poly, X, domain=sp.QQ).clear_denoms()[1].primitive()[1]
    return p if p.LC() > 0 else -p

@lru_cache(maxsize=None)
def algebraic_expression(text):
    # rational=True is essential: (2/9)**(1/3) denotes an exact rational power.
    e = sp.sympify(text, rational=True)
    if e.has(sp.Float) or e.free_symbols or e.is_real is False:
        raise ValueError(f'not an exact real constant: {text}')
    p = primitive(sp.minimal_polynomial(e, X))
    roots = sp.real_roots(p.as_expr(), X)
    intervals = sp.polys.polytools.intervals(p, eps=sp.Rational(1, 10**60))
    matches = []
    for i, (((a, b), _), root) in enumerate(zip(intervals, roots, strict=True)):
        if sp.simplify(e - root) == 0 or ((e >= a) is sp.true and (e <= b) is sp.true):
            matches.append(i)
    if len(matches) != 1:
        raise ValueError(f'cannot isolate exact reference: {text}')
    return (tuple(str(c) for c in p.all_coeffs()), matches[0])

@lru_cache(maxsize=None)
def expression_key(text):
    e = sp.expand(sp.sympify(text, rational=True))
    if e.has(sp.pi):
        a = sp.simplify(e.coeff(sp.pi))
        b = sp.simplify(e.subs(sp.pi, 0))
        if sp.simplify(e - a * sp.pi - b) != 0:
            raise ValueError('non affine pi reference')
        if a != 0:
            return ('affine_pi', algebraic_expression(str(a)), algebraic_expression(str(b)))
        e = b
    return ('algebraic', algebraic_expression(str(e)))

@lru_cache(maxsize=None)
def descriptor_key(coefficients, index):
    if not coefficients or isinstance(index, bool) or not isinstance(index, int):
        raise ValueError('invalid algebraic descriptor')
    coeff = [sp.Rational(c) for c in coefficients]
    p = primitive(sum(c * X**i for i, c in enumerate(reversed(coeff))))
    if p.degree() < 1 or not p.is_sqf:
        raise ValueError('invalid minimal polynomial')
    roots = sp.real_roots(p.as_expr(), X)
    if index < 0 or index >= len(roots):
        raise ValueError('invalid real root index')
    if p.is_irreducible:
        return (tuple(str(c) for c in p.all_coeffs()), index)
    # Normalize an equivalent reducible representation using its selected exact root.
    return algebraic_expression(str(roots[index]))

def descriptor(d):
    return descriptor_key(tuple(d['minimal_polynomial']), d['real_root_index'])

def answer_key(a):
    if a['kind'] == 'algebraic':
        return ('algebraic', descriptor(a['value']))
    if a['kind'] == 'affine_pi':
        coefficient, constant = descriptor(a['pi_coefficient']), descriptor(a['constant'])
        if coefficient == algebraic_expression('0'):
            return ('algebraic', constant)
        return ('affine_pi', coefficient, constant)
    raise ValueError('unknown exact answer kind')

def serial(keys):
    # Stable ordering and de-duplication; no tolerance or numerical nearest-root rule.
    return [json.loads(k) for k in sorted({json.dumps(k, separators=(',', ':')) for k in keys})]

def freeze_references():
    doc = load(S6 / 'reference-sources.json')
    cases = {}
    for r in doc['cases']:
        keys = serial(expression_key(s) for s in r['reference_expressions']) if r['available'] else None
        cases[r['case_id']] = dict(expressions=r['reference_expressions'], canonical_set=keys,
            available=r['available'], origin=r['origin'],
            set_sha256=__import__('hashlib').sha256(json.dumps(keys, sort_keys=True).encode()).hexdigest())
    return dict(created_utc=utc(), source_manifest_sha256=sha(S6 / 'reference-sources.json'),
        provenance='Existing manifest expressions only; mathematical normalization, no new geometry/reference derivation.',
        method='SymPy exact rational parsing, primitive positive minimal polynomial, zero-based ascending real root index proven by exact identity or rational isolating interval; affine-pi coefficients independently normalized. Whole sets equal after de-duplication.',
        missing_policy='Execute all jobs; ok, solved, C are null for absent references, never false/180 replacement.',
        cases=cases)

def grade_one(job, receipt, references):
    ref = references['cases'][job['case_id']]
    path = Path(receipt.get('result_path', '/nonexistent'))
    result, keys, parse_error = None, None, None
    if path.is_file():
        try:
            result = load(path)
            keys = serial(answer_key(a) for a in result['answers'])
        except Exception as e:
            parse_error = f'{type(e).__name__}: {e}'
    if not ref['available']:
        ok, cost, reason = None, None, 'reference_missing'
    else:
        reason = None
        if receipt['state'] != 'completed':
            reason = receipt['state']
        elif receipt.get('resource_violations'):
            reason = 'resource_contract_violation'
        elif receipt.get('exit_code') != 0:
            reason = 'nonzero_exit'
        elif result is None:
            reason = 'missing_result'
        elif parse_error:
            reason = 'invalid_answer_descriptor'
        elif result.get('engine', {}).get('source_hash') != SOURCE:
            reason = 'result_source_hash_mismatch'
        elif result.get('status') != 'solved':
            reason = 'solver_' + str(result.get('status'))
        elif keys != ref['canonical_set']:
            reason = 'answer_set_mismatch'
        ok = reason is None
        cost = receipt['wall_seconds'] if ok else 180.0
        reason = reason or 'exact_whole_set_match'
    return dict(**job, state=receipt['state'], exit_code=receipt.get('exit_code'),
        cpu=receipt.get('cpu'), pid=receipt.get('pid'), start_utc=receipt.get('start_utc'),
        end_utc=receipt.get('end_utc'), wall_seconds=receipt.get('wall_seconds'),
        solver_elapsed_seconds=result.get('elapsed_seconds') if result else None,
        solver_status=result.get('status') if result else None, answer_set=keys,
        reference_set_sha256=ref['set_sha256'], ok=ok, C_seed=cost, reason=reason,
        descriptor_error=parse_error, resource_violations=receipt.get('resource_violations', []),
        peak_tree_rss_bytes=receipt.get('peak_tree_rss_bytes'),
        result_sha256=receipt.get('files', {}).get('result.json', {}).get('sha256'))

def csv_write(name, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (HERE / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in r.items()})

def summarize(problems):
    result = dict(n=len(problems), missing=[p['case_id'] for p in problems if p['solved_T2'] is None],
        observed_n=sum(p['solved_T2'] is not None for p in problems))
    observed = [p for p in problems if p['solved_T2'] is not None]
    for mode in ['T2', 'T1']:
        costs = [p['C_' + mode] for p in observed]
        result['observed_solved_' + mode] = sum(p['solved_' + mode] for p in observed)
        result['mean_C_' + mode] = None if result['missing'] else statistics.mean(costs)
        result['observed_mean_C_' + mode] = statistics.mean(costs) if costs else None
        result['observed_sigma_C_' + mode] = statistics.pstdev(costs) if costs else None
    t2 = sum(p['solved_T2'] and not p['solved_T1'] for p in observed)
    t1 = sum(p['solved_T1'] and not p['solved_T2'] for p in observed)
    missing = len(result['missing'])
    result.update(T2_only_observed=t2, T1_only_observed=t1,
        T2_only_bounds=[t2, t2 + missing], T1_only_bounds=[t1, t1 + missing],
        solved_difference_T2_minus_T1_bounds=[result['observed_solved_T2'] - result['observed_solved_T1'] - missing,
            result['observed_solved_T2'] - result['observed_solved_T1'] + missing],
        ratio_C_T1_over_T2=None if result['missing'] else result['mean_C_T1'] / result['mean_C_T2'])
    return result

def aggregate():
    freeze = load(HERE / 'freeze.json')
    for rel, h in freeze['measurement_files_sha256'].items():
        assert sha(HERE / rel) == h, rel
    references = load(HERE / 'references.json')
    jobs = load(S6 / 'run-plan.json')['jobs']
    runs, receipts = [], []
    for j in jobs:
        end = load(HERE / 'receipts' / f"{j['queue_index']:03d}.end.json")
        receipts.append(end)
        runs.append(grade_one(j, end, references))
    assert len(runs) == 264
    groups = load(S6 / 'groups.json')['groups']
    split = load(S6 / 'same-group-split.json')
    problems = []
    for t in load(S6 / 'targets.json')['targets']:
        p = dict(case_id=t['case_id'], identity=t['identity'], group=next(g for g, ids in groups.items() if t['case_id'] in ids),
            split='same_formula_18' if t['case_id'] in split['same_formula_18'] else 'distance_only_differs_15' if t['case_id'] in split['distance_only_differs_15'] else '',
            reference_available=references['cases'][t['case_id']]['available'])
        for mode in ['T2', 'T1']:
            rs = [r for r in runs if r['case_id'] == t['case_id'] and r['configuration'] == mode]
            assert len(rs) == 3
            p['correct_seeds_' + mode] = None if not p['reference_available'] else sum(r['ok'] for r in rs)
            p['solved_' + mode] = None if not p['reference_available'] else p['correct_seeds_' + mode] >= 2
            p['C_' + mode] = None if not p['reference_available'] else statistics.mean(r['C_seed'] for r in rs)
        problems.append(p)
    summaries = {g: summarize([p for p in problems if p['case_id'] in ids]) for g, ids in groups.items()}
    for g in ['same_formula_18', 'distance_only_differs_15']:
        summaries[g] = summarize([p for p in problems if p['case_id'] in split[g]])
    summaries['全体44問'] = summarize(problems)
    v1, v2, v3 = summaries['接点効果群'], summaries['same_formula_18'], summaries['全体44問']
    judgments = dict(created_utc=utc(), groups=summaries,
        V1=dict(status='supported' if v1['ratio_C_T1_over_T2'] >= 1.5 or v1['T2_only_observed'] >= 1 else 'not_supported',
            ratio=v1['ratio_C_T1_over_T2'], T2_only=v1['T2_only_observed']),
        V2=dict(status='indeterminate_missing_reference' if v2['missing'] else 'supported' if abs(v2['observed_solved_T2'] - v2['observed_solved_T1']) <= 1 and .8 <= v2['ratio_C_T1_over_T2'] <= 1.25 else 'not_supported',
            ratio=v2['ratio_C_T1_over_T2'], missing=v2['missing'],
            solved_difference_bounds=v2['solved_difference_T2_minus_T1_bounds']),
        V3=dict(status=('supported_despite_missing' if v3['T2_only_observed'] - v3['T1_only_observed'] >= len(v3['missing']) else
            'not_supported_despite_missing' if v3['T2_only_observed'] - v3['T1_only_observed'] + len(v3['missing']) < 0 else 'indeterminate_missing_reference') if v3['missing'] else
            ('supported' if v3['T2_only_observed'] >= v3['T1_only_observed'] else 'not_supported'),
            T2_only_bounds=v3['T2_only_bounds'], T1_only_bounds=v3['T1_only_bounds'], missing=v3['missing']))
    csv_write('per-run.csv', runs)
    csv_write('per-problem.csv', problems)
    save(HERE / 'judgments.json', judgments)
    save(HERE / 'graded-answers.json', [dict(queue_index=r['queue_index'], answer_set=r['answer_set'], reference_set_sha256=r['reference_set_sha256'], ok=r['ok'], reason=r['reason'], descriptor_error=r['descriptor_error']) for r in runs])
    audit = load(HERE / 'execution-audit.json')
    audit.update(grading_completed_utc=utc(), counts=dict(runs=len(runs), problems=len(problems),
        ok_true=sum(r['ok'] is True for r in runs), ok_false=sum(r['ok'] is False for r in runs),
        ungradable=sum(r['ok'] is None for r in runs), reasons=dict(Counter(r['reason'] for r in runs))),
        grading='outside all 264 calculation windows; whole exact independent sets; missing is null',
        cost_policy='correct wall; incorrect/timeout/crash/resource violation 180; reference missing null',
        resource_contract_violations=[r['queue_index'] for r in runs if r['resource_violations']],
        raw_file_manifests={f"{j['queue_index']:03d}":r.get('files', {}) for j,r in zip(jobs,receipts)},
        no_retry_unique_keys=len({(r['identity'],r['seed'],r['configuration']) for r in runs}) == 264,
        predictions=judgments)
    save(HERE / 'audit.json', audit)
    def f(v):
        return '欠測' if v is None else f'{v:.6e}'
    def verdict(k):
        return {'supported':'支持','not_supported':'予測不成立','indeterminate_missing_reference':'参照欠測のため確定不能',
            'supported_despite_missing':'欠測を考慮しても支持','not_supported_despite_missing':'欠測を考慮しても予測不成立'}[judgments[k]['status']]
    lines = ['| 判定 | 事前固定の条件 | 結果 |', '|---|---|---|',
        f"| V1 | 接点効果6問: C平均比≥1.5 またはT2のみ成功≥1 | {verdict('V1')}: 比={f(v1['ratio_C_T1_over_T2'])}, T2のみ={v1['T2_only_observed']} |",
        f"| V2 | 式一致18問: 成功数差±1以内、C平均比0.8–1.25 | {verdict('V2')}: 差の範囲={v2['solved_difference_T2_minus_T1_bounds']}, 固定18問の比は欠測 |",
        f"| V3 | 全44問: T2のみ成功数≥T1のみ成功数 | {verdict('V3')}: T2のみ範囲={v3['T2_only_bounds']}, T1のみ範囲={v3['T1_only_bounds']} |", '',
        '事前登録13の本計測。264ジョブを固定FIFOで実行。対象・seed・ソースは変更せず、再試行なし。V2の対象はユーザー指定のsame_formula_18。外れた予測も上表のまま報告する。', '',
        '独立参照はreference-sources.jsonの既存式を本計測前に正規化して固定した。新しい正解の幾何計算は行っていない。solverへの入力は代表DSL・通常CLI引数のみで、参照集合は渡していない。採点は全計測終了後、最小多項式・実根index、affine-pi係数の正規化による集合全体の完全一致で行った。', '',
        'HMMT-2013-FEB-TEAM-03、HMMT-2022-FEB-TEAM-03は参照式がなく、12ジョブのok/Cと2問のsolved/Cは欠測。実行対象から除外せず、不正解・費用180への置換もしない。固定分母の群平均は欠測のまま、観測部分の平均は別列に示す。V3は欠測各問が片側成功を最大1増やす範囲で判定する。', '',
        '| 群 | 固定n | 欠測n | 観測solved T2/T1 | C_T2平均(秒) | C_T1平均(秒) | 比T1/T2 | 観測部分C平均T2/T1 | 観測σT2/T1 |', '|---|---:|---:|---:|---:|---:|---:|---|---|']
    for g, s in summaries.items():
        lines.append(f"| {g} | {s['n']} | {len(s['missing'])} | {s['observed_solved_T2']}/{s['observed_solved_T1']} | {f(s['mean_C_T2'])} | {f(s['mean_C_T1'])} | {f(s['ratio_C_T1_over_T2'])} | {f(s['observed_mean_C_T2'])}/{f(s['observed_mean_C_T1'])} | {f(s['observed_sigma_C_T2'])}/{f(s['observed_sigma_C_T1'])} |")
    lines += ['', 'σは観測問題のCの母標準偏差であり、有意差や因果効果の検定ではない。時間は共有機負荷に依存する参考値。', '',
        '| 問題 | 群/内訳 | C_T2(秒) | C_T1(秒) | solved T2 | solved T1 | 正解seed数 T2/T1 |', '|---|---|---:|---:|---|---|---|']
    for p in problems:
        solved = lambda v: '欠測' if v is None else 'yes' if v else 'no'
        lines.append(f"| {p['case_id']} | {p['group']}/{p['split']} | {f(p['C_T2'])} | {f(p['C_T1'])} | {solved(p['solved_T2'])} | {solved(p['solved_T1'])} | {p['correct_seeds_T2']}/{p['correct_seeds_T1']} |")
    lines += ['', 'Distanceのみ相違15問は上表のdistance_only_differs_15に全件記載した。元の同式群33問はそのまま保持し、式一致18問との区別を維持する。', '',
        f"資源契約: 固定source_hash={SOURCE}、PYTHONPATH=/tmp/s3-impl/src、T2はモード未設定、T1は=T1。CPU slot={audit['slot_cpus']}、最大同時solver={audit['max_active']}。内部数値スレッド環境7変数は全て1。子孫・各OSスレッドのaffinityと環境を標本監視し、PID別観測・peak RSS・実環境は終了receiptに記録。OS管理スレッド数は内部数値スレッド数と区別する。資源違反検出={len(audit['resource_contract_violations'])}ジョブ。標本監視の間に生滅した短命プロセスは直接観測できないが、起動前tasksetと継承規則で固定する。", '',
        f"時間契約: 親monotonic時計で起動直前から通常終了まで。180秒到達で計算結果を拒否し木を停止、cleanupは最大2秒で費用に含めない。失敗は180秒、採点欠測はnull。状態内訳={json.dumps(audit['states'],ensure_ascii=False)}。", '',
        f"共有機負荷: 実測期間={audit['started_utc']}–{audit['ended_utc']}、wall={f(audit['campaign_wall_seconds'])}秒。load1 min/mean/max={audit['load_summary']['load1']}、利用可能メモリ最小={audit['load_summary']['min_available_memory_bytes']} bytes。生の負荷時系列は外部rawのload.jsonl。", '',
        '同一solved判定となった問題では、今回の条件下で精密化の差は最終性能では補われた。これを接点残差の一般的な効用の否定へ広げない。最終検証はモード非依存だが、精密化を通じた候補・追加探索・残り予算の間接効果を含む完成solverの比較である。Distance15問では非接点式の変更も含み、接点だけの介入とは解釈しない。', '',
        f"生ログ・solver出力原本: `{audit['raw_root']}`（リポジトリ外/tmp）。個別SHA-256は終了receiptとaudit.json、全成果物hashはartifact-hashes.json。各ファイル3,000,000 bytes未満を検査。git commit/pushは実施していない。"]
    (HERE / 'answer.md').write_text('\n'.join(lines) + '\n')
    progress(f"採点・集計完了: {audit['counts']}; V1={judgments['V1']['status']}, V2={judgments['V2']['status']}, V3={judgments['V3']['status']}")
    hashes = {str(p.relative_to(HERE)): sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and p.name != 'artifact-hashes.json' and '__pycache__' not in p.parts and p.name != 'campaign.lock'}
    assert all(p.stat().st_size < 3_000_000 for p in HERE.rglob('*') if p.is_file())
    save(HERE / 'artifact-hashes.json', dict(created_utc=utc(), files_sha256=hashes))
    print(json.dumps({k:judgments[k] for k in ['V1','V2','V3']}, ensure_ascii=False))

if __name__ == '__main__':
    aggregate()
