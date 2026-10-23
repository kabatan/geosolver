"""Descriptive, paired counts from the unchanged Q43a trial records.

This does not run the solver, select conditions, or change correctness labels.
The problem (not an individual run) is the unit of seed-stability reporting.
"""
from __future__ import annotations

import collections
import hashlib
import json
import statistics
from pathlib import Path

BASE = Path(__file__).resolve().parent
BASELINE = "scale_+0"
STAGES = ("short", "long", "fixedbox")


def load(path):
    return json.loads(path.read_text())


def jobkey(j):
    return f"{j['id']}__{j['variant']}__{j['seed']}__{j['budget']}"


def paired(rows, ids, variants, seeds, control):
    lookup = {(r['id'], r['variant'], r['seed']): r for r in rows}
    results = {}
    for variant in variants:
        stable_loss, stable_gain, any_change, unstable_direction = [], [], [], []
        wins = losses = 0
        seed_counts = {}
        for seed in seeds:
            pairs = [(lookup[i, control, seed], lookup[i, variant, seed]) for i in ids]
            seed_counts[str(seed)] = {
                'control_correct': sum(a['exact_correct'] for a, b in pairs),
                'variant_correct': sum(b['exact_correct'] for a, b in pairs),
                'wins': sum(not a['exact_correct'] and b['exact_correct'] for a, b in pairs),
                'losses': sum(a['exact_correct'] and not b['exact_correct'] for a, b in pairs),
            }
        for problem in ids:
            delta = [int(lookup[problem, variant, s]['exact_correct']) -
                     int(lookup[problem, control, s]['exact_correct']) for s in seeds]
            wins += delta.count(1)
            losses += delta.count(-1)
            if all(d == -1 for d in delta):
                stable_loss.append(problem)
            if all(d == 1 for d in delta):
                stable_gain.append(problem)
            if any(delta):
                any_change.append(problem)
            if -1 in delta and 1 in delta:
                unstable_direction.append(problem)
        results[variant] = dict(
            control=control, problems=len(ids), runs=len(ids)*len(seeds),
            wins=wins, losses=losses,
            percentage_point_change=100*(wins-losses)/(len(ids)*len(seeds)),
            stable_loss_ids=stable_loss, stable_gain_ids=stable_gain,
            any_change_ids=any_change, opposite_directions_ids=unstable_direction,
            by_seed=seed_counts,
        )
    return results


def main():
    inputs = load(BASE/'inputs.json')
    ids = [i['id'] for i in inputs]
    cohorts = {'all': ids, **{
        g: [i['id'] for i in inputs if i['group'] == g]
        for g in ('development', 'unseen2026')
    }}
    result = {'unit': 'problem; repeated seeds are paired within each problem', 'stages': {}}
    stages = {}
    for stage in STAGES:
        assert (BASE/f'{stage}-complete.json').exists(), stage
        jobs = load(BASE/f'{stage}-jobs.json')
        rows = [load(BASE/stage/'records'/f'{jobkey(j)}.json') for j in jobs]
        assert len({jobkey(j) for j in jobs}) == len(jobs)
        assert all(all(r[k] == j[k] for k in j) for j, r in zip(jobs, rows))
        assert all(r['exact_correct'] == (r['actual_keys'] == i['reference_keys'])
                   for r in rows for i in inputs if i['id'] == r['id'])
        stages[stage] = rows
        seeds = sorted({j['seed'] for j in jobs})
        variants = sorted({j['variant'] for j in jobs})
        full_scale_sweep = all(f'scale_{k:+d}' in variants for k in range(-6, 7))
        summary = load(BASE/f'{stage}-summary.json')
        figures = load(BASE/f'{stage}-figures-summary.json')
        nonempty_sets = {i: {tuple(r['actual_keys']) for r in rows
                            if r['id'] == i and r['actual_keys']} for i in ids}
        shares = [r['cpu_seconds']/r['wall_seconds'] for r in rows
                  if r.get('cpu_seconds') is not None and r['wall_seconds'] > 0]
        result['stages'][stage] = dict(
            jobs=len(jobs), seeds=seeds, variants=variants,
            statuses=dict(collections.Counter(r['status'] for r in rows)),
            correct=sum(r['exact_correct'] for r in rows),
            source_hashes=dict(collections.Counter(r.get('source_hash') for r in rows)),
            cpu_wall_share_quartiles=statistics.quantiles(shares, n=4),
            baseline_pairs={g: paired(rows, subset, variants, seeds, BASELINE)
                            for g, subset in cohorts.items()},
            sham_pairs=paired(rows, ids, variants, seeds, 'identity_rewrite'),
            all_conditions_correct_ids=[p['id'] for p in summary['problems'] if p['all_variants_correct']],
            all_conditions_failed_ids=[p['id'] for p in summary['problems'] if p['all_variants_failed']],
            full_scale_sweep_measured=full_scale_sweep,
            nonmonotone_both_ids=([p['id'] for p in summary['problems'] if p['nonmonotone_all_seeds']]
                                 if full_scale_sweep else None),
            multiple_nonempty_answer_sets_ids=[i for i, sets in nonempty_sets.items() if len(sets) > 1],
            extra_answer_runs=sum(bool(r.get('extra')) for r in rows),
            figures=dict(
                materialized=figures['figures'],
                distinct_coordinate_records=sum(r['distinct_coordinates'] for r in figures['rows']),
                original_valid_witnesses=sum(r['original_valid_witnesses'] for r in figures['rows']),
                evaluation_errors=sum(len(r['errors']) for r in figures['rows']),
                runs_with_witnesses=sum(r['original_valid_witnesses'] > 0 for r in figures['rows']),
            ),
        )
    short = result['stages']['short']['baseline_pairs']['all']
    long = result['stages']['long']['baseline_pairs']['all']
    result['short_to_long'] = {
        v: dict(
            short_stable_losses=short[v]['stable_loss_ids'],
            long_stable_losses=long[v]['stable_loss_ids'],
            stable_loss_in_both=sorted(set(short[v]['stable_loss_ids']) & set(long[v]['stable_loss_ids'])),
            short_stable_gains=short[v]['stable_gain_ids'],
            long_stable_gains=long[v]['stable_gain_ids'],
        ) for v in long
    }
    # Same short seeds, budget and transformations; only the planned box hook differs.
    lookups = {stage: {(r['id'], r['variant'], r['seed']): r for r in rows}
               for stage, rows in stages.items()}
    result['native_to_fixedbox'] = {}
    for v in result['stages']['fixedbox']['variants']:
        stable_gain, stable_loss, wins, losses = [], [], 0, 0
        for i in ids:
            delta = [int(lookups['fixedbox'][i, v, s]['exact_correct']) -
                     int(lookups['short'][i, v, s]['exact_correct'])
                     for s in result['stages']['short']['seeds']]
            wins += delta.count(1)
            losses += delta.count(-1)
            if all(d == 1 for d in delta):
                stable_gain.append(i)
            if all(d == -1 for d in delta):
                stable_loss.append(i)
        result['native_to_fixedbox'][v] = dict(
            runs=48, wins=wins, losses=losses,
            stable_gain_ids=stable_gain, stable_loss_ids=stable_loss,
        )
    result['input_files_sha256'] = {
        f.name: hashlib.sha256(f.read_bytes()).hexdigest()
        for f in [BASE/'inputs.json', BASE/'long-selection.json',
                  *[BASE/f'{stage}-summary.json' for stage in STAGES]]
    }
    data = json.dumps(result, ensure_ascii=False, indent=2)+'\n'
    assert len(data.encode()) < 5_000_000
    (BASE/'report-metrics.json').write_text(data)
    print(json.dumps({s: {k: r[k] for k in ['jobs', 'correct', 'figures']}
                      for s, r in result['stages'].items()}, indent=2))


if __name__ == '__main__':
    main()
