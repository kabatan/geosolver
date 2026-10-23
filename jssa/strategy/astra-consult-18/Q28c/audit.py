"""Q28c: descriptive audit of existing records; no solver or Galois computation."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

import sympy as sp

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
INPUTS = {}


def read_text(path):
    path = Path(path)
    data = path.read_bytes()
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
    return data.decode()


def csv_rows(path):
    return list(csv.DictReader(read_text(path).splitlines()))


def save_csv(name, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def save_json(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def power_two(n):
    return n > 0 and (n & (n - 1)) == 0


def real_quadratic_tower(e):
    """Sufficient syntactic certificate, not a test based only on degree."""
    if e.is_Rational:
        return True
    if e.is_Add or e.is_Mul:
        return all(real_quadratic_tower(a) for a in e.args)
    if e.is_Pow and e.exp.is_Rational:
        if not real_quadratic_tower(e.base):
            return False
        if e.exp < 0 and e.base.is_zero is not False:
            return False
        if e.exp.q == 1:
            return True
        return power_two(int(e.exp.q)) and e.base.is_nonnegative is True
    return False


def main():
    started = time.perf_counter()
    read_text(OUT / 'preregistration.md')
    read_text(OUT / 'audit.py')
    basins_list = csv_rows(ROOT / 'jssa/difficulty/minima/basins-323.csv')
    basins = {r['id']: r for r in basins_list}
    assert len(basins_list) == len(basins) == 323
    prev = ROOT / 'jssa/strategy/astra-consult-18/q21b-number-theory'
    census = {r['id']: r for r in csv_rows(prev / 'answer-census.csv')}
    values = csv_rows(prev / 'answer-values.csv')
    human = {r['case_id']: r for r in csv_rows(ROOT / 'jssa/difficulty/ghost-1023/human_feat.csv')}
    stages = csv_rows(ROOT / 'jssa/results/stage-profile-20261023/per-case.csv')
    assert set(basins) == set(census) == {r['id'] for r in values}
    by_problem = defaultdict(list)
    value_rows = []
    for r in values:
        assert r['status'] == 'ok', r
        d = int(r['degree']) if r['degree'] else None
        if r['has_pi'] == 'True':
            category = 'pi_excluded'
            syntactic = None
        else:
            e = sp.sympify(r['expression'], locals={'CRootOf': sp.CRootOf}, rational=True)
            syntactic = real_quadratic_tower(e)
            if d is not None and not power_two(d):
                category = 'nonconstructible_number_over_Q_degree'
                assert not syntactic
            elif syntactic:
                category = 'constructible_number_over_Q_tower'
            elif d in (1, 2):
                category = 'constructible_number_over_Q_degree_1_2'
            else:
                category = 'unknown'
        row = {k: r[k] for k in ('id', 'answer_index', 'expression', 'degree', 'coefficients')}
        row.update(category=category, real_quadratic_tower=syntactic)
        value_rows.append(row)
        by_problem[r['id']].append(row)
    problem_rows = []
    for cid in sorted(basins):
        rr = by_problem[cid]
        degrees = [int(v['degree']) for v in rr if v['degree']]
        max_degree = max(degrees) if degrees else None
        assert str(max_degree or '') == census[cid]['degree'], cid
        assert len(rr) == int(census[cid]['n_answers']), cid
        cats = {v['category'] for v in rr}
        if 'nonconstructible_number_over_Q_degree' in cats:
            category = 'has_nonconstructible_algebraic_answer'
        elif 'pi_excluded' in cats:
            category = 'pi_excluded'
        elif cats <= {'constructible_number_over_Q_tower', 'constructible_number_over_Q_degree_1_2'}:
            category = 'all_answers_constructible_numbers_over_Q'
        else:
            category = 'unknown'
        problem_rows.append({'id': cid, 'n_answers': len(rr), 'max_degree': max_degree,
                             'category': category,
                             'n_vars': basins[cid]['n_vars'],
                             'has_human': bool(human.get(cid, {}).get('human', ''))})
    non2_ids = [r['id'] for r in problem_rows if r['category'] == 'has_nonconstructible_algebraic_answer']
    audit_rows = []
    selected_stages = []
    for cid in non2_ids:
        sr = [r for r in stages if r['case_id'] == cid]
        selected_stages.extend(sr)
        for seed, subdir in [(0, 'raw-323'), (1, 'raw-323-seed1')]:
            path = ROOT / 'jssa/difficulty/minima' / subdir / (cid + '.json')
            common = {'id': cid, 'seed': seed, 'n_vars': basins[cid]['n_vars'],
                      'human': human.get(cid, {}).get('human', ''),
                      'contest': human.get(cid, {}).get('contest', ''),
                      'max_degree': census[cid]['degree'],
                      'full_solver_correct_runs': sum(r['correct'] == 'True' for r in sr),
                      'full_solver_runs': len(sr)}
            if not path.exists():
                audit_rows.append({**common, 'status': 'missing'})
                continue
            raw = json.loads(read_text(path))
            rec = raw['records']
            cls = Counter(r['cls'] for r in rec)
            n, hit = len(rec), cls['hit']
            p = hit / n if n else None
            if seed == 0:
                assert n == int(basins[cid]['n_starts']), cid
                assert abs(p - float(basins[cid]['p'])) < 1e-12, cid
            audit_rows.append({**common, 'status': 'ok', 'n_starts': n, 'hits': hit, 'p': p,
                               'classes': json.dumps(dict(cls), sort_keys=True)})
    tools = {name: shutil.which(name) for name in ('bertini', 'bertini2', 'M2', 'phc')}
    modules = {name: importlib.util.find_spec(name) is not None for name in ('phcpy', 'bertini')}
    summary = {
        'population': len(basins), 'answer_values': len(value_rows),
        'problem_max_degree_counts': dict(Counter(str(r['max_degree']) if r['max_degree'] else 'pi' for r in problem_rows)),
        'value_degree_counts': dict(Counter(r['degree'] or 'pi' for r in value_rows)),
        'problem_category_counts': dict(Counter(r['category'] for r in problem_rows)),
        'value_category_counts': dict(Counter(r['category'] for r in value_rows)),
        'non_power_two_problem_ids': non2_ids,
        'non_power_two_problem_fraction_of_323': len(non2_ids) / len(basins),
        'non_power_two_with_human': sum(bool(human.get(cid, {}).get('human', '')) for cid in non2_ids),
        'descriptive_non_power_two_records': audit_rows,
        'numerical_monodromy_executables_on_PATH': tools,
        'numerical_monodromy_modules_in_specified_python': modules,
        'new_solver_runs': 0, 'new_galois_computations': 0,
        'new_predictions': 0, 'hypothesis_test': 'not_performed_early_rejection',
        'limitations': ['Answer-number classification is over Q; not classification of complete geometric configurations.',
                       'Degree counts and early rejection were already known before this audit.',
                       'No prediction of success rates was made; no correlations or group differences estimated.',
                       'No executable/module found is only a PATH/import probe, not an exhaustive filesystem audit.'],
    }
    save_csv('per-value.csv', value_rows)
    save_csv('per-problem.csv', problem_rows)
    save_csv('non2-local.csv', audit_rows)
    save_csv('non2-full-solver.csv', selected_stages)
    save_json('summary.json', summary)
    manifest = {'time_utc': datetime.now(timezone.utc).isoformat(), 'python': sys.executable,
                'sympy': sp.__version__, 'elapsed_seconds_excluding_import': time.perf_counter() - started,
                'environment': {k: os.environ.get(k) for k in ('PYTHONPATH', 'PYTHONDONTWRITEBYTECODE', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')},
                'input_sha256': INPUTS}
    manifest['input_unchanged_after_audit'] = all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == v for p, v in INPUTS.items())
    assert manifest['input_unchanged_after_audit']
    save_json('manifest.json', manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('elapsed_seconds_excluding_import:', manifest['elapsed_seconds_excluding_import'])


if __name__ == '__main__':
    main()
