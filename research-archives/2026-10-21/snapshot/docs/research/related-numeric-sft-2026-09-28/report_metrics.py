"""Summarize final, matched-budget evaluations without treating censoring as failure."""
from pathlib import Path
import hashlib, json, statistics, sys

P = Path(__file__).resolve().parent
R = P.parents[2]
O = R / 'qwen/.runtime/related_numeric_sft_20260928'
SH = R / 'qwen/.runtime/program_self_training_20260926'
sys.path.insert(0, str(P))
import analyze as an

ARMS = ['base', 'sft-a', 'sft-b']

def read(p):
    return json.loads(p.read_text())

def summarize(rows):
    correct = sum(r['finish_reason'] == 'stop' and r['numeric_correct'] is True for r in rows)
    unfinished = sum(r['finish_reason'] == 'length' for r in rows)
    return {
        'n': len(rows), 'completed_correct': correct, 'unfinished': unfinished,
        'completed_unparsed': sum(r['finish_reason'] == 'stop' and r['numeric_correct'] is None for r in rows),
        'censoring_bounds_counts': [correct, correct + unfinished],
        'tokens_total': sum(r['tokens'] for r in rows),
        'tokens_median': statistics.median(r['tokens'] for r in rows) if rows else None,
    }

def main():
    done = read(O / 'generation-complete.json')
    assert done['status'] == 'complete'
    scores = read(O / 'numeric-scores.json')
    assert scores['status'] == 'complete'
    rows = scores['numeric']
    assert len(rows) == 120 and len(scores['proof']) == 12
    report = {'by_split': {}, 'by_source': {}, 'paired': {}, 'initial_32768': {}, 'computation': {}}
    for arm in ARMS:
        report['by_split'][arm] = {
            split: summarize([r for r in rows if r['arm'] == arm and r['split'] == split])
            for split in ['untrained_configuration', 'trained_example', 'new_shape', 'retention']
        }
    for source in sorted({r['source_id'] for r in rows}):
        report['by_source'][source] = {
            arm: [dict(job_id=r['job_id'], split=r['split'], correct=r['numeric_correct'], finish=r['finish_reason'], cap=r['cap'])
                  for r in rows if r['source_id'] == source and r['arm'] == arm]
            for arm in ARMS
        }
    for split in ['untrained_configuration', 'trained_example', 'new_shape', 'retention']:
        base = {r['job_id']: r for r in rows if r['arm'] == 'base' and r['split'] == split}
        report['paired'][split] = {}
        for arm in ARMS[1:]:
            gains, losses, censored = [], [], []
            for r in rows:
                if r['arm'] != arm or r['split'] != split:
                    continue
                b = base[r['job_id']]
                if b['finish_reason'] != 'stop' or r['finish_reason'] != 'stop':
                    censored.append(r['job_id'])
                elif r['numeric_correct'] is True and b['numeric_correct'] is not True:
                    gains.append(r['job_id'])
                elif b['numeric_correct'] is True and r['numeric_correct'] is not True:
                    losses.append(r['job_id'])
            report['paired'][split][arm] = {'gained_jobs': gains, 'lost_jobs': losses, 'censored_jobs': censored}
    # Score the preserved initial answers separately with the exact same parser/tolerance.
    for arm in ARMS:
        initial = []
        for r in rows:
            if r['arm'] != arm:
                continue
            kind = 'main' if r['split'] in ['untrained_configuration', 'retention'] else 'diagnostic'
            original = read(O / f'{arm}-{kind}' / (r['job_id'] + '-0.json'))
            got, _, _ = an.parse(original['raw_text'])
            correct = None
            if got is not None:
                try:
                    value, expected = float(an.parse_numeric(got)), float(an.parse_numeric(r['expected']))
                    correct = abs(value-expected) <= 1e-4 or abs(value-expected) <= 1e-5*abs(expected)
                except (ValueError, TypeError, OverflowError):
                    pass
            initial.append(dict(r, numeric_correct=correct, finish_reason=original['finish_reason'], tokens=len(original['completion_ids'])))
        report['initial_32768'][arm] = {s: summarize([r for r in initial if r['split'] == s]) for s in report['by_split'][arm]}
    jobs = []
    for p in sorted(SH.glob('related-numeric-*-20260928/receipt.json')):
        r = read(p)
        jobs.append({'stage': p.parent.name, 'status': r['status'], 'elapsed_seconds': r.get('elapsed_seconds'), 'receipt': str(p)})
    report['computation'] = {'guarded_jobs': jobs, 'guarded_wall_seconds': sum(r['elapsed_seconds'] or 0 for r in jobs), 'note': 'Sequential guarded process wall time, including model load/teardown; not GPU utilization integral.'}
    report['chosen_caps'] = done['chosen_caps']
    report['numeric_scores_sha256'] = hashlib.sha256((O/'numeric-scores.json').read_bytes()).hexdigest()
    (O/'report-metrics.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report['by_split'], ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
