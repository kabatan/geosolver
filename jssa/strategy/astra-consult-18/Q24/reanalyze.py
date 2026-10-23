"""Read existing DEVELOPMENT data and write small Q24-only analysis artifacts."""
import csv
import hashlib
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from static_features import features, predict, RULE_NAMES

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
MANIFEST = {}


def read(relative):
    p = ROOT / relative
    assert 'unseen' not in str(p) and 'sealed' not in str(p)
    b = p.read_bytes()
    MANIFEST[relative] = {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
    return b.decode('utf-8-sig')


def rows(relative):
    return list(csv.DictReader(read(relative).splitlines()))


def save_json(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def save_csv(name, rs):
    if not rs:
        raise ValueError('empty CSV: ' + name)
    keys = list(dict.fromkeys(k for r in rs for k in r))
    with (OUT / name).open('w', newline='') as h:
        w = csv.DictWriter(h, keys)
        w.writeheader()
        w.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in rs)


def num(value):
    if value in (None, '', 'None', 'nan'):
        return None
    v = float(value)
    return v if math.isfinite(v) else None


def observed_exact(e):
    cl = e['msolve_class']
    if cl in ('positive_dimensional', 'free_parameter'):
        return 'enumeration_mismatch', None
    if cl == 'timeout':
        return 'costly', None
    if cl != 'answer_set_matches':
        return cl, None
    ts = [num(e[k]) for k in ('translate_s', 'msolve_s', 'filter_s')]
    if None in ts:
        return 'missing_time', None
    total = sum(ts)
    return ('fast' if total <= 1 else ('costly' if total > 10 else 'intermediate')), total


def brief(rs):
    ps = [r['p'] for r in rs if r['p'] is not None]
    return {'n': len(rs), 'local': dict(Counter(r['observed_local'] for r in rs)),
            'exact': dict(Counter(r['observed_exact'] for r in rs)),
            'p_median': statistics.median(ps) if ps else None,
            'full_any': sum(r['geo_matched'] > 0 for r in rs),
            'full_all': sum(r['geo_matched'] == r['geo_runs'] for r in rs)}


def main():
    started = time.perf_counter()
    cases = {c['id']: c for c in map(json.loads, read('benchmarks/cases.jsonl').splitlines())}
    basin = rows('jssa/difficulty/minima/basins-323.csv')
    exact_path = 'jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv'
    exact = {r['id']: r for r in rows(exact_path)}
    provenance = json.loads(read('jssa/strategy/astra-consult-17/H/sources/provenance.json'))
    source_check = []
    for entry in provenance['files']:
        p = 'jssa/strategy/astra-consult-17/H/sources/' + entry['local']
        b = read(p).encode('utf-8')
        sha = hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest()
        canonical = b.rstrip(b'\n') + b'\n'
        canonical_sha = hashlib.sha1(b'blob ' + str(len(canonical)).encode() + b'\0' + canonical).hexdigest()
        source_check.append({'path': p, 'computed_git_blob_sha1': sha, 'recorded_sha': entry['sha'], 'matches': sha == entry['sha'], 'single_final_lf_blob_sha1': canonical_sha, 'single_final_lf_matches': canonical_sha == entry['sha'], 'url': entry['display_url']})
    qf = rows('jssa/strategy/astra-consult-18/q21f-homotopy/comparison.csv')
    hc = rows('jssa/strategy/astra-consult-18/q21f-homotopy/hc-summary.csv')
    multiplicity = {r['id']: r for r in json.loads(read('jssa/difficulty/multiplicity/dsl-census.json'))}
    false = {r['id']: r for r in rows('jssa/difficulty/false-attractors/per-problem.csv')}
    condition = {r['id']: r for r in rows('jssa/strategy/astra-consult-18/q21d-conditioning/per-problem.csv')}
    cert = [r for r in rows('jssa/difficulty/certify-all/per-case.csv') if r['group'] == 'development323']
    result, raw_mismatches, branch_rows = [], [], []
    class_totals = Counter()
    for row in sorted(basin, key=lambda r: r['id']):
        id = row['id']
        f = features(cases[id]['dsl'])
        raw = json.loads(read('jssa/difficulty/minima/raw-323/' + id + '.json'))
        records = raw.get('records', [])
        n = len(records)
        hits = sum(r['cls'] == 'hit' for r in records)
        p = hits / n if n else None
        class_totals.update(r['cls'] for r in records)
        if row['n_starts'] == '':
            assert f['d'] == 0 and n == 0
        if (n != int(row['n_starts'] or 0) or f['d'] != int(row['n_vars']) or
                (n and abs(p - float(row['p'])) > 1e-12)):
            raw_mismatches.append(id)
        e = exact[id]
        ex_class, ex_time = observed_exact(e)
        local = 'no_search' if not n else ('easy' if p >= .9 else ('hard' if p <= .1 else 'intermediate'))
        sec = sum(r.get('sec', 0.) for r in records)
        evals = sum(r.get('nfev', 0) or 0 for r in records)
        r = {'id': id, **f, 'n_starts': n, 'hits': hits, 'p': p,
             'observed_local': local, 'mean_trial_seconds': sec/n if n else None,
             'empirical_seconds_per_hit': sec/hits if hits else None,
             'mean_trial_nfev': evals/n if n else None,
             'empirical_nfev_per_hit': evals/hits if hits else None,
             'truncated_below200': 0 < n < 200,
             'msolve_class': e['msolve_class'], 'observed_exact': ex_class,
             'exact_total_seconds': ex_time, 'poly_vars': num(e['poly_vars']),
             'max_degree': num(e['max_degree']), 'bezout': e['bezout'],
             'geo_runs': int(e['geo_runs']), 'geo_matched': int(e['geo_matched']),
             'geo_median_s': num(e['geo_median_s']),
             'qactive_existing': multiplicity[id]['q_active'],
             'false_attractor_main': false.get(id, {}).get('main_cause', ''),
             'raw_classes': dict(Counter(x['cls'] for x in records))}
        r['full_easy_secondary'] = r['geo_matched'] == r['geo_runs'] and r['geo_median_s'] <= 10
        if n and len(raw.get('references', [])) > 1:
            counts = [sum(x['cls'] == 'hit' and x.get('ref') == j for x in records) for j in range(len(raw['references']))]
            branch_rows.append({'id': id, 'n': n, 'hits_by_ref': raw.get('hits_by_ref'), 'recounted_hits_by_ref': counts, 'p_any': p, 'p_min_recorded': raw.get('p_min_ref'), 'geo_matched': r['geo_matched'], 'geo_runs': r['geo_runs']})
        result.append(r)
    all_predictions = []
    scores, directional = {}, []
    for rule in RULE_NAMES:
        local_table, exact_table, groups = Counter(), Counter(), defaultdict(list)
        for r in result:
            prediction = predict(r, rule)
            local_table[(prediction['local'], r['observed_local'])] += 1
            exact_table[(prediction['exact'], r['observed_exact'])] += 1
            valid_exact = r['observed_exact'] in ('fast', 'intermediate', 'costly', 'enumeration_mismatch')
            local_judged = prediction['local'] in ('easy', 'hard') and r['observed_local'] != 'no_search'
            exact_judged = prediction['exact'] in ('fast', 'costly', 'enumeration_mismatch') and valid_exact
            record = {'id': r['id'], 'rule': rule, **prediction,
                      'observed_local': r['observed_local'], 'observed_exact': r['observed_exact'],
                      'local_judged': local_judged, 'local_correct': local_judged and prediction['local'] == r['observed_local'],
                      'exact_judged': exact_judged, 'exact_correct': exact_judged and prediction['exact'] == r['observed_exact'],
                      'p': r['p'], 'msolve_class': r['msolve_class'], 'exact_total_seconds': r['exact_total_seconds'],
                      'geo_matched': r['geo_matched'], 'geo_runs': r['geo_runs']}
            all_predictions.append(record)
            if prediction['direction'] != 'none':
                record = dict(record)
                record['both_correct'] = record['local_correct'] and record['exact_correct']
                directional.append(record)
                groups[prediction['direction']].append(record)
        scores[rule] = {
            'local_confusion': [{'pred': a, 'observed': b, 'n': n} for (a,b),n in sorted(local_table.items())],
            'exact_confusion': [{'pred': a, 'observed': b, 'n': n} for (a,b),n in sorted(exact_table.items())],
            'directions': {g:{'n':len(rs), 'both_correct':sum(x['both_correct'] for x in rs), 'ids':[x['id'] for x in rs], 'correct_ids':[x['id'] for x in rs if x['both_correct']]} for g,rs in groups.items()},
        }
    by_id = {r['id']:r for r in result}
    qf_join = []
    for row in qf:
        r = by_id[row['id']]
        qf_join.append({**row, 'nonlinear_gates':r['nonlinear_gates'], 'nonlinear_depth':r['nonlinear_depth'], 'hazard_depth':r['hazard_depth'], 'unmatched_variables':r['unmatched_variables'], **{'prediction_'+rule: predict(r,rule) for rule in RULE_NAMES}})
    nonmatch = [r for r in result if r['msolve_class'] != 'answer_set_matches']
    subsets = {
        'all323': brief(result), 'active292': brief([r for r in result if r['d']]),
        'msolve_not_match122': brief(nonmatch),
        'msolve_not_match_active': brief([r for r in nonmatch if r['d']]),
        'exact_costly_local_easy': brief([r for r in result if r['observed_exact']=='costly' and r['observed_local']=='easy']),
        'exact_fast_local_hard': brief([r for r in result if r['observed_exact']=='fast' and r['observed_local']=='hard']),
        'enumeration_mismatch_local_easy': brief([r for r in result if r['observed_exact']=='enumeration_mismatch' and r['observed_local']=='easy']),
    }
    save_csv('development.csv', result)
    save_csv('development-predictions-all.csv', all_predictions)
    save_csv('development-errors-all.csv', [r for r in all_predictions if (r['local_judged'] and not r['local_correct']) or (r['exact_judged'] and not r['exact_correct'])])
    save_csv('development-directional.csv', directional)
    save_csv('q21f-reanalysis.csv', qf_join)
    save_csv('multiple-targets.csv', branch_rows)
    save_json('development-summary.json', {
        'raw_mismatches': raw_mismatches, 'raw_class_counts': dict(class_totals),
        'raw_starts':sum(r['n_starts'] for r in result), 'raw_hits':sum(r['hits'] for r in result),
        'truncated_below200':sum(r['truncated_below200'] for r in result),
        'zero_hits_active':sum(r['hits']==0 and r['d']>0 for r in result),
        'subsets':subsets, 'msolve_classes':{c:brief([r for r in result if r['msolve_class']==c]) for c in sorted({r['msolve_class'] for r in result})},
        'dimension_strata':{str(d):brief([r for r in result if r['d']==d]) for d in sorted({r['d'] for r in result})},
        'source_checks': source_check, 'source_provenance': provenance,
        'nonmatch_failure_ids':[r['id'] for r in nonmatch if not r['geo_matched']],
        'rules':scores, 'hc_run_rows':len(hc),
        'conditioning_rows_read':len(condition), 'certify_development_rows':len(cert),
        'elapsed_seconds':time.perf_counter()-started,
    })
    save_json('development-input-manifest.json', MANIFEST)
    print(json.dumps({'cases':len(result),'raw_starts':sum(r['n_starts'] for r in result),'raw_mismatches':raw_mismatches,'source_blobs_all_match_after_final_lf_normalization':all(x['single_final_lf_matches'] for x in source_check),'seconds':time.perf_counter()-started},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
