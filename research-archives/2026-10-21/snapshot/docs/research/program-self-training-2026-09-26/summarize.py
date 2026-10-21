"""Summarize recorded outcomes without changing selection or grading."""
import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNTIME = ROOT / 'qwen/.runtime/program_self_training_20260926'


def read(path):
    return json.loads(path.read_text())


def program_summary(path, sample_zero=False):
    result = read(path)
    assert result['status'] == 'complete'
    rows = [r for r in result['records'] if not sample_zero or r['id'].endswith('-0')]
    sources = sorted({r['source_id'] for r in rows})
    return {'programs': len(rows), 'passed': sum(r['all_passed'] for r in rows),
            'per_configuration': {s: {'passed': sum(r['all_passed'] for r in rows if r['source_id'] == s),
                                      'total': sum(r['source_id'] == s for r in rows)} for s in sources}}


def proof_summary(rows, base):
    primary = [r for r in rows if r['role'] == 'same_configuration_general_proof']
    secondary = [r for r in rows if r['role'] != 'same_configuration_general_proof']
    base_by_id = {r['job_id']: r for r in base}
    assert len({r['job_id'] for r in rows}) == len(rows)
    sources = sorted({r['source_id'] for r in primary})
    by_source = {s: sum(r['complete_proof'] for r in primary if r['source_id'] == s) for s in sources}
    net = {s: by_source[s] - sum(r['complete_proof'] for r in base if r['source_id'] == s
                               and r['role'] == 'same_configuration_general_proof') for s in sources}
    return {'primary_total': len(primary), 'primary_pass': sum(r['complete_proof'] for r in primary),
            'primary_conservative': sum(r['complete_proof'] and not r['ancillary_math_error'] for r in primary),
            'secondary_total': len(secondary), 'secondary_pass': sum(r['complete_proof'] for r in secondary),
            'secondary_conservative': sum(r['complete_proof'] and not r['ancillary_math_error'] for r in secondary),
            'primary_per_configuration': by_source, 'primary_net_per_configuration': net,
            'primary_wins': sum(r['complete_proof'] and not base_by_id[r['job_id']]['complete_proof'] for r in primary),
            'primary_losses': sum(not r['complete_proof'] and base_by_id[r['job_id']]['complete_proof'] for r in primary)}


def permissive(rows):
    return [{**r, 'complete_proof': r.get('root_review', {}).get('sensitivity_complete_proof',
                                                               r['complete_proof'])} for r in rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=HERE / 'summary.json')
    args = ap.parse_args()
    out = {}
    selection = RUNTIME / 'selection/receipt.json'
    if selection.exists():
        out['selection'] = read(selection)
        public = read(RUNTIME / 'initial-public/public-checks.json')
        out['initial_public'] = dict(Counter(r['status'] for r in public))
    out['program_checks'] = {}
    for name in ['accepted', 'initial', 'base', 'code', 'numeric']:
        path = RUNTIME / f'final-check-{name}.json'
        if path.exists() and read(path)['status'] == 'complete':
            out['program_checks'][name] = program_summary(path)
            if name == 'base':
                out['program_checks']['base_sample0'] = program_summary(path, sample_zero=True)
    base = read(HERE / 'base-proof-grades.json')
    out['proof'] = {'base': proof_summary(base, base)}
    out['proof_sensitivity'] = {'base': proof_summary(permissive(base), permissive(base))}
    grades_path = HERE / 'proof-grades-unblinded.json'
    if grades_path.exists():
        grades = read(grades_path)
        for condition in sorted({r['condition'] for r in grades}):
            rows = [r for r in grades if r['condition'] == condition]
            out['proof'][condition] = proof_summary(rows, base)
            out['proof_sensitivity'][condition] = proof_summary(permissive(rows), permissive(base))
    out['training'] = {}
    out['retention'] = {}
    for condition in ['base', 'code', 'numeric']:
        path = HERE / f'elementary-{condition}-grades.json'
        if path.exists():
            grades = read(path)
            out['retention'][condition] = {'passed': sum(r['numeric_correct'] for r in grades), 'total': len(grades)}
        path = RUNTIME / f'train-{condition}/receipt.json'
        if path.exists():
            r = read(path)
            out['training'][condition] = {k: r.get(k) for k in ['status', 'global_updates', 'n_examples',
                  'unique_target_tokens', 'planned_target_tokens', 'trained_target_tokens',
                  'changed_lora_tensors', 'total_lora_tensors', 'peak_allocated_gib', 'elapsed_seconds']}
            tokenization = {x['id']: x for x in read(path.parent / 'tokenization.json')}
            order = read(path.parent / 'example-order.json')[:r['examples_processed']]
            exposure = {}
            for item in order:
                row = tokenization[item['id']]
                entry = exposure.setdefault(row['source_id'], {'examples': 0, 'target_tokens': 0})
                entry['examples'] += 1
                entry['target_tokens'] += row['target_tokens']
            out['training'][condition]['per_configuration_exposure'] = exposure
            events_path = path.parent / 'examples.jsonl'
            if events_path.exists():
                losses = {}
                for event in map(json.loads, events_path.read_text().splitlines()):
                    losses.setdefault(event['id'], []).append(event['loss'])
                repeated = [v for v in losses.values() if len(v) >= 2]
                if repeated:
                    out['training'][condition]['repeated_training_example_loss'] = {
                        'first_occurrence_mean': statistics.mean(v[0] for v in repeated),
                        'last_occurrence_mean': statistics.mean(v[-1] for v in repeated),
                        'examples_with_lower_last_loss': sum(v[-1] < v[0] for v in repeated),
                        'repeated_examples': len(repeated),
                        'scope': 'Training-fit diagnostic only; first occurrence is not necessarily at base weights.'}
    jobs = [read(p) for p in sorted((RUNTIME / 'gpu-jobs').glob('*/receipt.json'))]
    out['gpu_jobs'] = [{k: r.get(k) for k in ['status', 'elapsed_seconds', 'returncode']} |
                       {'command': r['command']} for r in jobs]
    out['gpu_job_wall_seconds_including_load'] = sum(r.get('elapsed_seconds', 0) for r in jobs)
    comparison = RUNTIME / 'program-example-comparison.json'
    if comparison.exists():
        out['program_example_comparison'] = read(comparison)
    for condition in ['code', 'numeric']:
        if condition in out['proof'] and condition in out['retention']:
            r = out['proof'][condition]
            r['candidate_positive_gate'] = (r['primary_total'] == 16
                and r['primary_pass'] - out['proof']['base']['primary_pass'] >= 4
                and sum(v > 0 for v in r['primary_net_per_configuration'].values()) >= 2
                and out['retention'][condition]['passed'] > 2)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
