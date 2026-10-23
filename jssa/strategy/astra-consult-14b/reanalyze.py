"""Read-only audit of existing solver results; writes only beside this script."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from scipy.special import expit
from scipy.stats import binomtest, spearmanr

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
STARTED = datetime.now(timezone.utc).isoformat()
T0 = time.monotonic()
HASHES = {}
RNG = np.random.default_rng(14023)
B = 10000


def read(path):
    p = ROOT / path
    content = p.read_bytes()
    HASHES[path] = hashlib.sha256(content).hexdigest()
    return content.decode()


def csv_rows(path):
    return list(csv.DictReader(read(path).splitlines()))


def json_data(path):
    return json.loads(read(path))


def write_csv(name, rows):
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def ci_mean(x):
    x = np.asarray(x, dtype=float)
    ix = RNG.integers(0, len(x), size=(B, len(x)))
    return np.quantile(x[ix].mean(axis=1), [.025, .975]).tolist()


def corr(x, y):
    return float(spearmanr(x, y).statistic)


def ci_corr(x, y):
    x, y = np.asarray(x), np.asarray(y)
    values = []
    for _ in range(B):
        ix = RNG.integers(0, len(x), len(x))
        if len(np.unique(x[ix])) > 1 and len(np.unique(y[ix])) > 1:
            values.append(corr(x[ix], y[ix]))
    return {'interval': np.quantile(values, [.025, .975]).tolist(),
            'valid_draws': len(values)}


def stats(rows):
    d = np.array([r['delta'] for r in rows])
    pos, neg = int((d > 1e-12).sum()), int((d < -1e-12).sum())
    return {'n': len(rows), 'plain_mean': np.mean([r['p_plain'] for r in rows]),
            'feasible_mean': np.mean([r['p_feasible'] for r in rows]),
            'mean_delta': float(d.mean()), 'mean_delta_ci': ci_mean(d),
            'median_delta': float(np.median(d)),
            'improved': pos, 'worsened': neg, 'unchanged': len(rows)-pos-neg,
            'delta_ge_0.1': int((d >= .1-1e-12).sum()),
            'delta_ge_0.3': int((d >= .3-1e-12).sum()),
            'sign_test_one_sided': float(binomtest(pos, pos+neg, .5, alternative='greater').pvalue) if pos+neg else None,
            'planned200_mean_delta_bounds': [np.mean([r['delta_lower'] for r in rows]),
                                               np.mean([r['delta_upper'] for r in rows])],
            'planned200_median_delta_bounds': [np.median([r['delta_lower'] for r in rows]),
                                                 np.median([r['delta_upper'] for r in rows])]}


prefix = 'jssa/difficulty/start-feasibility-1023/'
source = {r['id']: r for r in csv_rows(prefix+'per-problem.csv')}
predictions = {r['id']: r for r in csv_rows(prefix+'predictions.csv')}
summaries = csv_rows(prefix+'seed2-summary.csv')
rows = []
for summary in summaries:
    cid = summary['id']
    r = {'id': cid, 'p0': float(summary['p0']), 'n_vars': int(predictions[cid]['n_vars']),
         'phi0': float(predictions[cid]['phi0']), 'n_feasible0': int(source[cid]['n_feas'])}
    for arm in ('plain', 'feasible'):
        raw = json_data(prefix+f'seed2-{arm}/{cid}.json')
        records = raw['records']
        n, h = len(records), sum(x['cls'] == 'hit' for x in records)
        nf = sum(x['start_feasible'] is True for x in records)
        assert n == int(summary['starts_'+arm]) == raw['starts_done']
        assert math.isclose(h/n, float(summary['p_'+arm]), abs_tol=1e-12)
        assert raw['starts_requested'] == 200
        r.update({f'n_{arm}': n, f'hits_{arm}': h, f'p_{arm}': h/n,
                  f'n_H1_{arm}': nf, f'elapsed_{arm}': raw['elapsed'],
                  f'local_seconds_{arm}': sum(x['sec'] for x in records)})
        if arm == 'feasible':
            # This CSV column is rounded to three decimals; all analysis uses raw counts.
            assert abs(nf/n-float(summary['share_feasible_starts'])) <= .0005+1e-12
            r['redraws'] = sum(x['redraws'] for x in records)
            r['n_capped_H0'] = sum(x['redraws'] == 2000 and not x['start_feasible'] for x in records)
    r['delta'] = r['p_feasible']-r['p_plain']
    r['pred_delta'] = float(summary['pred_delta']) if summary['pred_delta'] else None
    r['pred_p_feasible'] = float(summary['pred_p_feasible']) if summary['pred_p_feasible'] else None
    r['all_H1'] = r['n_H1_feasible'] == r['n_feasible']
    r['complete'] = r['n_plain'] == r['n_feasible'] == 200
    r['delta_lower'] = (r['hits_feasible']-r['hits_plain']-(200-r['n_plain']))/200
    r['delta_upper'] = (r['hits_feasible']+(200-r['n_feasible'])-r['hits_plain'])/200
    rows.append(r)
assert len(rows) == 150
write_csv('seed2-audit.csv', rows)
groups = {'all': rows, 'both_complete': [r for r in rows if r['complete']],
          'all_actual_H1': [r for r in rows if r['all_H1']],
          'complete_and_H1': [r for r in rows if r['all_H1'] and r['complete']]}
intervention = {name: stats(rs) for name, rs in groups.items()}
intervention['low_p0'] = {name: stats([r for r in rs if r['p0'] < .3]) for name, rs in groups.items()}
intervention['execution'] = {arm: {'starts': sum(r['n_'+arm] for r in rows),
       'hits': sum(r['hits_'+arm] for r in rows),
       'under200_problems': sum(r['n_'+arm] < 200 for r in rows),
       'elapsed_sum': sum(r['elapsed_'+arm] for r in rows),
       'local_seconds_sum': sum(r['local_seconds_'+arm] for r in rows)} for arm in ('plain','feasible')}
intervention['execution'].update({'actual_H0_starts_in_feasible_arm': sum(r['n_feasible']-r['n_H1_feasible'] for r in rows),
    'problems_with_actual_H0': sum(not r['all_H1'] for r in rows),
    'problems_with_no_H1': sum(r['n_H1_feasible'] == 0 for r in rows),
    'capped_H0_starts': sum(r['n_capped_H0'] for r in rows),
    'redraws': sum(r['redraws'] for r in rows)})
pr = [r for r in rows if r['pred_delta'] is not None]
x = np.array([r['pred_delta'] for r in pr]); y = np.array([r['delta'] for r in pr])
slope, intercept = np.polyfit(x, y, 1)
intervention['prediction'] = {'n': len(pr), 'spearman': corr(x,y), 'spearman_ci': ci_corr(x,y),
    'mae': float(np.mean(abs(x-y))), 'rmse': float(np.sqrt(np.mean((x-y)**2))),
    'observed_minus_predicted_mean': float((y-x).mean()), 'calibration_slope': float(slope),
    'calibration_intercept': float(intercept),
    'within_0.1_pF': sum(abs(r['p_feasible']-r['pred_p_feasible']) <= .1+1e-12 for r in pr),
    'feasible0_under10': sum(r['n_feasible0'] < 10 for r in pr),
    'largest_errors': sorted(pr, key=lambda r: abs(r['delta']-r['pred_delta']), reverse=True)[:8]}
intervention['large_low_p_gains'] = sorted([r for r in rows if r['p0'] < .3 and r['delta'] >= .3],key=lambda r: -r['delta'])
intervention['largest_losses'] = sorted(rows, key=lambda r: r['delta'])[:5]

prefix = 'jssa/difficulty/new2026-predict/'
pred = {r['id']: r for r in csv_rows(prefix+'predictions.csv')}
outcomes = csv_rows(prefix+'outcomes.csv')
model = json_data(prefix+'inputs/model-1023.json')
test_rows = []
for s in outcomes:
    cid = s['id']; p = pred[cid]
    raw = json_data(prefix+f'raw/{cid}.json')
    records = raw['records']; h = sum(r['cls']=='hit' for r in records)
    assert len(records) == 200 and h == int(s['hits'])
    phi = sum(r['start_feasible'] for r in records)/200
    assert phi == float(p['phi'])
    y = math.log((h+.5)/(200-h+.5))
    assert math.isclose(y, float(s['observed_logit']))
    full = float(s['pred_logit_full']); base = float(s['pred_logit_nvars_only'])
    f = model['full']; lev = str(min(7, int(p['n_vars'])))
    assert math.isclose(full, f['intercept']+f['n_vars'].get(lev,0)+f['G']*int(p['G'])+f['phi']*phi)
    noG = full-f['G']*int(p['G'])
    r = {'id':cid, 'n_vars':int(p['n_vars']), 'phi':phi, 'G':int(p['G']),
         'pairs_excluded':int(p['n_pairs_excluded']), 'hits':h,'p':h/200,'observed_logit':y}
    for name, z in [('full',full),('nvars_only',base),('fixed_G_term_removed',noG)]:
        r[name+'_logit'] = z
        r[name+'_p'] = float(expit(z))
        r[name+'_squared_logit_error'] = (z-y)**2
        r[name+'_cross_entropy'] = float(np.logaddexp(0,z)-r['p']*z)
        r[name+'_squared_p_error'] = (float(expit(z))-r['p'])**2
    r['full_minus_base_squared_logit_error'] = r['full_squared_logit_error']-r['nvars_only_squared_logit_error']
    test_rows.append(r)
write_csv('heldout-audit.csv', test_rows)
test = {'n':len(test_rows), 'G1_ids':[r['id'] for r in test_rows if r['G']],
        'pairs_excluded_problems':[{'id':r['id'],'n':r['pairs_excluded']} for r in test_rows if r['pairs_excluded']],
        'models':{}}
for name in ('full','nvars_only','fixed_G_term_removed'):
    z = np.array([r[name+'_logit'] for r in test_rows]); p = np.array([r['p'] for r in test_rows])
    test['models'][name] = {'spearman':corr(z,p),
      'squared_logit_error_sum':sum(r[name+'_squared_logit_error'] for r in test_rows),
      'cross_entropy_mean':np.mean([r[name+'_cross_entropy'] for r in test_rows]),
      'p_rmse':float(np.sqrt(np.mean([r[name+'_squared_p_error'] for r in test_rows])))}
d = np.array([r['full_minus_base_squared_logit_error'] for r in test_rows])
test.update({'full_minus_base_mse':float(d.mean()),'full_minus_base_mse_ci':ci_mean(d),
 'LOO_sum_difference_range':[float((d.sum()-d).min()),float((d.sum()-d).max())],
 'improved_problems':int((d<0).sum()),'worsened_problems':int((d>0).sum()),
 'full_spearman_ci':ci_corr([r['full_logit'] for r in test_rows],[r['p'] for r in test_rows])})
for metric in ('cross_entropy', 'squared_p_error'):
    difference = [r['full_'+metric]-r['nvars_only_'+metric] for r in test_rows]
    test[metric+'_difference'] = {'mean':float(np.mean(difference)), 'ci':ci_mean(difference)}

gi = csv_rows('jssa/difficulty/ghost-intervention/per-start.csv')
gp = csv_rows('jssa/difficulty/ghost-intervention/per-problem.csv')
transitions = Counter((r['original_cls'], r['treatment_cls']) for r in gi)
write_csv('ghost-treatment-transitions.csv',[{'original':a,'treatment':b,'count':n} for (a,b),n in sorted(transitions.items())])
ghost = {'n_starts':len(gi), 'n_problems':len(gp),
    'treatment_rescues':sum(r['original_hit']=='0' and r['treatment_hit']=='1' for r in gi),
    'treatment_losses_observed':sum(r['original_hit']=='1' and r['treatment_hit']=='0' for r in gi),
    'original_hits_treatment_missing':sum(r['original_hit']=='1' and r['treatment_hit']=='' for r in gi),
    'complete_problem_delta_signs':dict(Counter('up' if float(r['delta_treatment']) > 1e-12 else 'down' if float(r['delta_treatment']) < -1e-12 else 'equal' for r in gp if r['delta_treatment'])),
    'wrong_answer_transitions':{b:n for (a,b),n in transitions.items() if a=='wrong_answer'},
    'mean_delta_bounds':[float(np.mean([float(r['delta_treatment_lower']) for r in gp])),float(np.mean([float(r['delta_treatment_upper']) for r in gp]))]}

human = json_data('jssa/strategy/astra-consult-13/audit.json')['human']
result = {'scope':'Exploratory reanalysis of stored data only; no local search or new starts.',
 'bootstrap':{'unit':'problem','draws':B,'seed':14023,'method':'percentile; descriptive'},
 'intervention':intervention,'heldout':test,'ghost_intervention':ghost,
 'human_from_consult13':human}
for path, h in HASHES.items():
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == h, path
result['manifest'] = {'started_utc':STARTED,'seconds':time.monotonic()-T0,
    'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,
    'input_files':len(HASHES),'input_hashes_unchanged':True,
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'plan_sha256':hashlib.sha256((OUT/'analysis-plan.md').read_bytes()).hexdigest()}
(OUT/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
(OUT/'input-sha256.json').write_text(json.dumps(HASHES, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'intervention':{k:v for k,v in intervention.items() if k not in ('prediction','large_low_p_gains','largest_losses')},
 'prediction':{k:v for k,v in intervention['prediction'].items() if k!='largest_errors'},
 'heldout':test,'ghost':ghost,'manifest':result['manifest']},ensure_ascii=False,indent=2,allow_nan=False))
