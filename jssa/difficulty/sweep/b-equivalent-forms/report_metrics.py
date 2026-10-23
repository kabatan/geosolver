"""Descriptive paired effects only; never launches or rescales solver trials."""
from __future__ import annotations

import collections
import statistics

from common import BASE, SEEDS, read, save
from analyze import same_diagrams
from transforms import ARMS


def median(values):
    values = list(values)
    return statistics.median(values) if values else None


def main():
    rows = read(BASE / 'per-run.json')
    ids = [c['id'] for c in read(BASE / 'selection.json')['cases']]
    lookup = {(r['id'], r['arm'], r['seed']): r for r in rows}
    assert len(rows) == len(ids) * len(ARMS) * len(SEEDS) == len(lookup)
    arms = {}
    for arm in ARMS:
        pairs = [(lookup[(i, 'base', s)], lookup[(i, arm, s)])
                 for i in ids for s in SEEDS]
        loss = lambda b, r: b['matched'] and not r['matched']
        gain = lambda b, r: r['matched'] and not b['matched']
        both = lambda predicate, i: all(predicate(lookup[(i, 'base', s)],
                                                  lookup[(i, arm, s)]) for s in SEEDS)
        correct_pairs = [(b, r) for b, r in pairs if b['matched'] and r['matched']]
        independent_pairs = [(b, r) for b, r in pairs if not r['alias']]
        arms[arm] = {
            'correct': sum(r['matched'] for _, r in pairs), 'n': len(pairs),
            'independent_runs': sum(not r['alias'] for _, r in pairs),
            'independent_baseline_correct': sum(b['matched'] for b, _ in independent_pairs),
            'independent_correct': sum(r['matched'] for _, r in independent_pairs),
            'correct_by_seed': {str(s): sum(lookup[(i, arm, s)]['matched'] for i in ids)
                                for s in SEEDS},
            'loss_pairs': [[r['id'], r['seed']] for b, r in pairs if loss(b, r)],
            'gain_pairs': [[r['id'], r['seed']] for b, r in pairs if gain(b, r)],
            'loss_both_seeds': [i for i in ids if both(loss, i)],
            'gain_both_seeds': [i for i in ids if both(gain, i)],
            'same_answers': sum(b['actual'] == r['actual'] for b, r in pairs),
            'same_saved_diagrams': sum(same_diagrams(b['diagrams'], r['diagrams']) for b, r in pairs),
            'changed_diagram_problems': sorted({r['id'] for b, r in pairs
                                               if not same_diagrams(b['diagrams'], r['diagrams'])}),
            'median_wall_seconds': median(r['wall_seconds'] for _, r in pairs),
            'median_cpu_seconds': median(r['cpu_seconds'] for _, r in pairs
                                         if r['cpu_seconds'] is not None),
            'both_correct_pairs': len(correct_pairs),
            'median_paired_wall_ratio_both_correct': median(r['wall_seconds'] / b['wall_seconds']
                                                           for b, r in correct_pairs),
            'median_paired_cpu_ratio_both_correct': median(r['cpu_seconds'] / b['cpu_seconds']
                                                          for b, r in correct_pairs
                                                          if r['cpu_seconds'] is not None and b['cpu_seconds']),
        }
    trajectories = []
    for i in ids:
        for s in SEEDS:
            order = ('base', 'dummy_1', 'dummy_8', 'dummy_32')
            pattern = [lookup[(i, a, s)]['matched'] for a in order]
            if any(not pattern[j] and pattern[j + 1] for j in range(3)):
                trajectories.append({'id': i, 'seed': s, 'order': order, 'matched': pattern})
    result = {'scope': 'exploratory; 20 fixed problems, two paired seeds; no significance test',
              'arms': arms, 'nonmonotone_dummy_trajectories': trajectories}
    save(BASE / 'effects.json', result)
    if (BASE / 'followup-per-run.json').exists():
        followup = read(BASE / 'followup-per-run.json')
        groups = collections.defaultdict(list)
        for row in followup:
            groups[(row['id'], row['arm'])].append(row)
        compact = []
        for (i, a), rs in sorted(groups.items()):
            compact.append({'id': i, 'arm': a, 'correct': sum(r['matched'] for r in rs),
                            'n': len(rs), 'seeds': {str(r['seed']): {
                                k: r[k] for k in ('matched', 'status', 'wall_seconds',
                                                 'cpu_seconds', 'diagram_count', 'actual')}
                                for r in sorted(rs, key=lambda r: r['seed'])}})
        save(BASE / 'followup-summary.json', {'groups': compact, 'runs': len(followup),
             'correct': sum(r['matched'] for r in followup),
             'statuses': dict(collections.Counter(r['status'] for r in followup)),
             'note': 'same selected problems and same two seeds at 180 seconds; not heldout confirmation'})
    print('Saved effects for', len(ids), 'problems and', len(rows), 'expanded rows')


if __name__ == '__main__':
    main()
