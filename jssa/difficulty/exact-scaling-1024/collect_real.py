"""Read historic records; incrementally compute only ideal degrees/dimensions."""
import ast
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PYTHON = '/tmp/q38-58e3993-venv/bin/python'
DEV_MS = 'jssa/strategy/astra-consult-18/Q24/source-msolve-cases.csv'
SOURCES = [('unseen34', f'jssa/difficulty/unseen-2/{g}/cases.jsonl') for g in 'ab'] + [
    ('dev323', 'benchmarks/cases.jsonl')]


def now():
    return datetime.now(timezone.utc).isoformat()


def read_csv(p):
    return list(csv.DictReader((ROOT / p).open(encoding='utf-8-sig')))


def med(values):
    return statistics.median(values) if values else ''


def features(dsl):
    """Named-construction DAG. Anonymous calls belong to the enclosing node."""
    names = {c['name'] for c in dsl['constructions']}
    depths, point_depths, rows = {}, {}, []
    point_ops = {'Point', 'Midpoint', 'Intersect', 'IntersectLines', 'FootOfPerpendicular',
                 'Circumcenter', 'Incenter', 'Centroid', 'Orthocenter', 'Reflect', 'Rotate',
                 'PointOnSegment', 'PointOnLine', 'PointOnCircle', 'ContactPoint',
                 'IncircleContactPoint', 'Center', 'Excenter', 'ClosestPoint'}
    for c in dsl['constructions']:
        node = ast.parse(c['expression'], mode='eval').body
        deps = sorted({n.id for n in ast.walk(node) if isinstance(n, ast.Name) and n.id in names})
        if any(n not in depths for n in deps):
            raise ValueError('Forward or cyclic construction reference')
        head = node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else ''
        free_point = head == 'Point' and not deps
        direct_parameter = isinstance(node, ast.Name) and node.id in dsl['variables']
        depth = 0 if free_point or direct_parameter else max((depths[n] for n in deps), default=0) + 1
        point_depth = max((point_depths[n] for n in deps), default=0)
        if head in point_ops and not free_point:
            point_depth += 1
        depths[c['name']] = depth
        point_depths[c['name']] = point_depth
        rows.append(dict(name=c['name'], expression=c['expression'], dependencies=deps,
                         depth=depth, point_depth=point_depth))
    target_ast = ast.parse(dsl['target'], mode='eval')
    target_refs = {n.id for n in ast.walk(target_ast) if isinstance(n, ast.Name) and n.id in depths}
    return dict(depth=max(depths.values(), default=0),
                point_depth=max(point_depths.values(), default=0),
                target_dependency_depth=max((depths[n] for n in target_refs), default=0),
                n_constructions=len(rows), dsl_variables=len(dsl['variables'])), rows


def solver_rows():
    result = defaultdict(list)
    for group, path, col in [
        ('dev323', 'jssa/results/mechanism-attribution/attribution.csv', 'wall_s'),
        ('unseen34', 'jssa/difficulty/unseen-2/a/per-run.csv', 'wall_seconds'),
        ('unseen34', 'jssa/difficulty/unseen-2/b/results.csv', 'wall_seconds')]:
        for r in read_csv(path):
            result[group, r['case_id']].append((r, path, col))
    return result


def initial_rows():
    sr = solver_rows()
    ms_dev = {r['id']: r for r in read_csv(DEV_MS)}
    ms_unseen = {r['case_id']: r for r in read_csv('jssa/difficulty/capability-1024/exp1-msolve/per-problem.csv')}
    rows, inputs = [], {}
    for group, source in SOURCES:
        for line in (ROOT / source).read_text().splitlines():
            case = json.loads(line)
            cid, dsl = case['id'], case['dsl']
            path = str(Path(source).parent / case['dsl_path'])
            disk = json.loads((ROOT / path).read_text())
            if disk != dsl:
                raise ValueError('Embedded DSL differs from DSL file: ' + cid)
            f, trace = features(dsl)
            r = dict(problem_id=cid, group=group, **f, dsl_source=path,
                     dsl_sha256=hashlib.sha256((ROOT / path).read_bytes()).hexdigest())
            samples = sr[group, cid]
            correct = [float(x[col]) for x, _, col in samples if x['matched'] == 'True' and x[col]]
            r.update(solver_runs=len(samples), solver_correct=len(correct),
                     solver_seeds=';'.join(x['seed'] for x, _, _ in samples),
                     solver_correct_seconds_median=med(correct),
                     solver_all_seconds_median=med([float(x[col]) for x, _, col in samples if x[col]]),
                     solver_result='all_correct' if len(correct) == len(samples) and samples else
                     'some_correct' if correct else 'no_correct' if samples else 'missing',
                     solver_status_counts=json.dumps(dict(Counter(x['status'] for x, _, _ in samples))),
                     solver_source=samples[0][1] if samples else '',
                     solver_time_column=samples[0][2] if samples else '',
                     solver_match_column='matched')
            if group == 'dev323':
                ms = ms_dev.get(cid, {})
                r.update(msolve_category=ms.get('msolve_class', '未確認'),
                         msolve_seconds=ms.get('msolve_s', ''), msolve_translate_seconds=ms.get('translate_s', ''),
                         msolve_filter_seconds=ms.get('filter_s', ''), msolve_reason=ms.get('unsupported_reason', ''),
                         msolve_source=DEV_MS, msolve_time_column='msolve_s',
                         msolve_historic_nvars=ms.get('poly_vars', ''), msolve_historic_neqs=ms.get('poly_eqs', ''),
                         msolve_source_confirmation='archived_copy_blob_verified')
            else:
                ms = ms_unseen.get(cid, {})
                r.update(msolve_category=ms.get('msolve_category', '未確認'),
                         msolve_seconds=ms.get('msolve_solve_seconds', ''),
                         msolve_translate_seconds=ms.get('translate_seconds', ''),
                         msolve_filter_seconds=ms.get('filter_seconds', ''), msolve_reason=ms.get('reason', ''),
                         msolve_source='jssa/difficulty/capability-1024/exp1-msolve/per-problem.csv',
                         msolve_time_column='msolve_solve_seconds',
                         msolve_historic_nvars=ms.get('polynomial_vars', ''),
                         msolve_historic_neqs=ms.get('polynomial_equations', ''), msolve_source_confirmation='local_record')
            for mode in ['base', 'strong']:
                for name in ['status', 'degree', 'dimension', 'nvars', 'neqs', 'max_equation_degree',
                             'nonzero_factors', 'omitted_dsl_variables', 'translation_wall_s', 'cas_wall_s', 'reason', 'detail']:
                    r[mode+'_'+name] = 'PENDING' if name == 'status' else ''
                r[mode+'_degree_label'] = '次数不明'
            r['degree_record'] = f'records/{group}/{cid}.*.json'
            rows.append(r)
            directory = HERE / 'inputs' / group
            directory.mkdir(parents=True, exist_ok=True)
            inp = directory / (cid + '.json')
            inp.write_text(json.dumps(dict(id=cid, dsl=dsl), ensure_ascii=False) + '\n')
            trace_dir = HERE / 'depths' / group
            trace_dir.mkdir(parents=True, exist_ok=True)
            (trace_dir / (cid + '.json')).write_text(json.dumps(trace, ensure_ascii=False, indent=1) + '\n')
            inputs[group, cid] = inp
    assert Counter(r['group'] for r in rows) == {'unseen34': 34, 'dev323': 323}
    return rows, inputs


def write_table(rows):
    path = HERE / 'real-problems.csv'
    with path.with_suffix('.csv.tmp').open('w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    path.with_suffix('.csv.tmp').replace(path)


def event(obj):
    obj = dict(utc=now(), **obj)
    with (HERE / 'progress.jsonl').open('a') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def one(row, inp, deadline):
    updates = {}
    for mode in ['base', 'strong']:
        if time.monotonic() > deadline:
            rec = {'status': 'TOTAL_BUDGET_LIMIT', 'reason': '50 minute collection deadline'}
        else:
            out = HERE / 'records' / row['group'] / f'{row["problem_id"]}.{mode}.json'
            if out.exists():
                raise RuntimeError('No implicit rerun: ' + str(out))
            out.parent.mkdir(parents=True, exist_ok=True)
            cmd = [PYTHON, '-B', str(HERE / 'degree_worker.py'), str(inp), mode, str(out)]
            p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                 start_new_session=True)
            try:
                _, err = p.communicate(timeout=55)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                _, err = p.communicate()
            rec = json.loads(out.read_text()) if out.exists() else {}
            if rec.get('status') in (None, 'PENDING', 'CAS_RUNNING'):
                rec.update(status='WORKER_LIMIT', reason='worker timeout or unexpected exit',
                           detail=err.decode(errors='replace')[-600:])
                out.write_text(json.dumps(rec, ensure_ascii=False, indent=2)+'\n')
        for key, value in rec.items():
            if mode+'_'+key in row:
                updates[mode+'_'+key] = ';'.join(value) if isinstance(value, list) else value
    return updates


def skeleton(rows):
    lines = ['# 実問題の次数と作図の深さ', '',
             '実問題表を先行保存した。開発外34問、開発群323問の全行を収録。集計図と人工族は続けて作成する。', '',
             '|群|件数|既存系の次数判明|強化系の次数判明|', '|---|---:|---:|---:|']
    for g in ['unseen34', 'dev323']:
        rr = [r for r in rows if r['group'] == g]
        lines.append(f'|{g}|{len(rr)}|{sum(r["base_degree"] != "" for r in rr)}|{sum(r["strong_degree"] != "" for r in rr)}|')
    lines += ['', '次数は重複度込み。正次元は有限個の複素解数ではなく、次元とイデアル次数を別列に記録する。',
              '既存系は変更しないalgebraize.translate(fresh, with_target=False)とrun_exact.build(rabinowitsch=True)。',
              '強化系は変更しないstrong_translate.translateとrun_strong.prepareによるT付き系を非零因子ごとに飽和する。',
              'Singularのstd, dim, multを使用。各系30秒、1問2系で最大60秒、4並列。solverの新規実行なし。',
              '深さは名前付き作図命令の依存DAG。定数・自由変数だけによるPointは0、他命令は入力の最大深さ+1。',
              '条件とtargetは深さに加えない。匿名入れ子はその命令の一部。詳細はdepths/に保存。',
              '', '## 続く集計', '', '深さ別分布、回帰、既存msolve失敗、solver時間、反例、欠測、人工族、段階2設計。', '']
    (HERE / 'answer.md').write_text('\n'.join(lines))


def main():
    if (HERE / 'progress.jsonl').exists():
        raise RuntimeError('This collection has already been started')
    started = time.monotonic()
    rows, inputs = initial_rows()
    write_table(rows)
    event({'event': 'collection_started', 'rows': len(rows), 'max_parallel': 4})
    for group in ['unseen34', 'dev323']:
        rr = [r for r in rows if r['group'] == group]
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(one, r, inputs[group, r['problem_id']], started+3000): r for r in rr}
            for future in as_completed(futures):
                r = futures[future]
                r.update(future.result())
                write_table(rows)
                event({'event': 'problem_complete', 'group': group, 'id': r['problem_id'],
                       'base': r['base_status'], 'strong': r['strong_status']})
        skeleton(rows)
        event({'event': 'group_complete', 'group': group})
    skeleton(rows)
    event({'event': '実問題表完了', 'rows': len(rows), 'elapsed_s': time.monotonic()-started})


if __name__ == '__main__':
    main()
