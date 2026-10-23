"""Exploratory checks of the selected depth hypothesis, without solver runs."""
from __future__ import annotations

import json
import math
import re

import numpy as np
from scipy.stats import rankdata

from explore import OUT, csv, read, write_csv, INPUTS

CONTROLS = ["n_vars", "n_cons", "dsl_len"]
BASESEED = 20261023
BOOT = 2000


def finite(r, keys):
    return all(np.isfinite(r.get(k, np.nan)) for k in keys)


def ranked_residuals(data, keys):
    a = np.array([[r[k] for k in keys] for r in data])
    # Human ratings and solver percentiles are compared within contests.
    contests = np.array([r["contest"] for r in data])
    for contest in sorted(set(contests)):
        mask = contests == contest
        n = sum(mask)
        a[mask] = (rankdata(a[mask], axis=0) - 0.5) / n
    ctr = np.column_stack([np.ones(len(data)), (contests == "HMMT").astype(float), a[:, 3:]])
    return a[:, :3] - ctr @ np.linalg.lstsq(ctr, a[:, :3], rcond=None)[0]


def statistic(data, target, controls):
    r = ranked_residuals(data, ["construction_depth", "human", target] + controls)
    corr = np.corrcoef(r.T)
    return np.array([corr[0, 1], corr[0, 2], corr[0, 1] - corr[0, 2]])


def resample(data, rng):
    out = []
    for contest in sorted({r['contest'] for r in data}):
        groups = sorted({r['group'] for r in data if r['contest'] == contest})
        by = {g: [r for r in data if r['group'] == g] for g in groups}
        for g in rng.choice(groups, len(groups), replace=True):
            out.extend(by[g])
    return out


def evaluate(data, target="log_cost", controls=CONTROLS):
    data = [r for r in data if finite(r, ['construction_depth', 'human', target] + controls)]
    point = statistic(data, target, controls)
    rng = np.random.default_rng(BASESEED)
    samples = np.array([statistic(resample(data, rng), target, controls) for _ in range(BOOT)])
    ci = np.nanquantile(samples, [0.025, 0.975], axis=0).T
    return {"n": len(data), "n_year_groups": len({r['group'] for r in data}),
            "controls": controls, "target": target,
            "rho_depth_human": float(point[0]), "rho_depth_solver": float(point[1]),
            "difference": float(point[2]), "ci_human": ci[0].tolist(),
            "ci_solver": ci[1].tolist(), "ci_difference": ci[2].tolist()}


def percentile(train, test):
    a = np.sort(train)
    return (np.searchsorted(a, test, side='left') + np.searchsorted(a, test, side='right')) / (2 * len(a))


def rank_encode(train, test, features, target):
    keys = features + [target]
    a = np.zeros((len(train), len(keys)))
    b = np.zeros((len(test), len(keys)))
    for contest in ['AIME', 'HMMT']:
        im = [i for i, r in enumerate(train) if r['contest'] == contest]
        jm = [i for i, r in enumerate(test) if r['contest'] == contest]
        for j, key in enumerate(keys):
            tr = np.array([train[i][key] for i in im])
            te = np.array([test[i][key] for i in jm])
            a[im, j] = percentile(tr, tr)
            b[jm, j] = percentile(tr, te)
    xa, xb, ya, yb = a[:, :-1], b[:, :-1], a[:, -1], b[:, -1]
    mean, scale = xa.mean(axis=0), xa.std(axis=0)
    scale = np.where(scale > 0, scale, 1)
    xa, xb = (xa - mean) / scale, (xb - mean) / scale
    xa = np.column_stack([np.ones(len(train)), [r['contest'] == 'HMMT' for r in train], xa])
    xb = np.column_stack([np.ones(len(test)), [r['contest'] == 'HMMT' for r in test], xb])
    return xa, xb, ya, yb


def cv(data, target):
    data = [r for r in data if finite(r, CONTROLS + ['construction_depth', target])]
    output = []
    for group in sorted({r['group'] for r in data}):
        train = [r for r in data if r['group'] != group]
        test = [r for r in data if r['group'] == group]
        rows = [{"case_id": r['case_id'], "contest": r['contest'], "group": group, "target": target} for r in test]
        for name, features in [('base', CONTROLS), ('depth', CONTROLS + ['construction_depth'])]:
            a, b, y, t = rank_encode(train, test, features, target)
            reg = np.eye(a.shape[1])
            reg[0, 0] = 0
            coef = np.linalg.solve(a.T @ a + reg, a.T @ y)
            pred = np.clip(b @ coef, 0, 1)
            for row, value, actual in zip(rows, pred, t):
                row[name] = float(value)
                row['actual'] = float(actual)
                row[f'error_{name}'] = float((value - actual) ** 2)
        output.extend(rows)
    base = np.mean([r['error_base'] for r in output])
    deep = np.mean([r['error_depth'] for r in output])
    return output, {'n': len(output), 'folds': len({r['group'] for r in output}),
                    'mse_base': float(base), 'mse_depth': float(deep),
                    'relative_reduction': float(1 - deep / base)}


def main():
    rows = csv('jssa/strategy/astra-consult-17/J/exploration-per-problem.csv')
    rows = [r for r in rows if np.isfinite(r['human'])]
    original = [json.loads(l) for l in read('jssa/strategy/astra-consult-14/E/e2h-rows.jsonl').splitlines()]
    joins = []
    for r in rows:
        parts = r['case_id'].split('-')
        year, index = int(parts[1]), int(parts[-1])
        matches = [s for s in original if s['contest'] == r['contest'] and s['year'] == year and s['index'] == index
                   and ((r['contest'] == 'AIME' and s['subtest'] == parts[2])
                        or (r['contest'] == 'HMMT' and s['subtest'] == 'geo' and s['month'] == 'Feb'))]
        assert len(matches) == 1, (r['case_id'], len(matches))
        s = matches[0]
        assert abs(s['rating'] - r['human']) < 1e-12
        assert not s['truncated_cells']
        r['text_words'] = len(re.findall(r'\b[A-Za-z]+\b', s['problem']))
        r['year'] = year
        r['group'] = f"{r['contest']}-{year}"
        joins.append({'case_id': r['case_id'], 'rating_difference': s['rating'] - r['human'],
                      'source_split': s['split'], 'source_row': s['row_idx'], 'text_words': r['text_words']})
    write_csv('human-source-join.csv', joins)
    write_csv('depth-analysis-per-problem.csv', rows)
    comparisons = {}
    for label, data in [('all_human', rows), ('AIME', [r for r in rows if r['contest'] == 'AIME']),
                        ('HMMT', [r for r in rows if r['contest'] == 'HMMT']),
                        ('positive_variables', [r for r in rows if r['n_vars'] > 0]),
                        ('exclude_deepest', [r for r in rows if r['case_id'] != 'HMMT-2022-FEB-GEO-02'])]:
        comparisons[label] = evaluate(data)
        print(label, json.dumps(comparisons[label]), flush=True)
    comparisons['text_control'] = evaluate(rows, controls=CONTROLS + ['text_words'])
    comparisons['local_seed0'] = evaluate(rows, target='difficulty0')
    comparisons['local_seed1'] = evaluate(rows, target='difficulty1')
    outputs, cvs = [], {}
    for target in ['human', 'log_cost', 'difficulty0', 'difficulty1']:
        p, metrics = cv(rows, target)
        cvs[target] = metrics
        outputs.extend(p)
    write_csv('depth-cross-validation.csv', outputs)
    results = {'bootstrap_repeats': BOOT, 'bootstrap_seed': BASESEED, 'comparisons': comparisons,
               'cross_validation': cvs,
               'notes': ['Exploratory selection, not preregistered confirmation.',
                         'Bootstrap unit is contest-year, stratified by contest.',
                         'Repeated seeds are not independent problems.',
                         'No new local searches; full-solver cost penalizes every wrong run by 180 seconds.']}
    (OUT / 'depth-summary.json').write_text(json.dumps(results, indent=2, ensure_ascii=False) + '\n')
    old = json.loads((OUT / 'input-sha256.json').read_text())
    old.update(INPUTS)
    (OUT / 'input-sha256.json').write_text(json.dumps(old, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
