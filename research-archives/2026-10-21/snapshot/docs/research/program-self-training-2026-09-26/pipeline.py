"""Candidate collection, numerical-only repair feedback and frozen SFT datasets.

Run with /usr/bin/python3 for the minimal bubblewrap execution runtime.
No generated candidate is executed in this process.
"""
import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from execution_harness import extract_program, evaluate_candidate
from prepare import HERE, SOURCES, program_prompt, numeric_prompt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def cases(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def raw_rows(directory):
    return [(p, x) for p in sorted(Path(directory).glob('*.json'))
            if isinstance(x := read(p), dict) and 'final_text' in x]


def clean_assistant(text):
    text = text.rstrip()
    if text.endswith('<|im_end|>'):
        text = text[:-len('<|im_end|>')].rstrip()
    return text


def check_output(path, row, selected_cases):
    record = {'id': row['id'], 'sample': row['sample'], 'source_id': row['source_id'],
              'raw_file': str(path.resolve()), 'raw_sha256': sha(path),
              'finish_reason': row['finish_reason'], 'completion_tokens': len(row['completion_ids'])}
    try:
        extracted = extract_program(row['final_text'], row['finish_reason'])
    except (ValueError, SyntaxError) as exc:
        record.update(status='format_failure', error=str(exc), all_passed=False)
        return record
    record['extraction'] = extracted
    record['raw_check'] = evaluate_candidate(extracted['code'], selected_cases)
    record['normalized_check'] = evaluate_candidate(extracted['normalized_code'], selected_cases)
    raw = record['raw_check']['events']; normalized = record['normalized_check']['events']
    differences = [abs(a['execution']['value'] - b['execution']['value'])
                   for a, b in zip(raw, normalized)
                   if a['execution']['status'] == b['execution']['status'] == 'ok']
    record['max_raw_normalized_difference'] = max(differences, default=None)
    record['normalization_equivalent'] = all(
        a['execution']['status'] == b['execution']['status'] == 'ok'
        and abs(a['execution']['value'] - b['execution']['value']) <=
        1e-12 + 1e-12 * abs(a['execution']['value']) for a, b in zip(raw, normalized))
    record['all_passed'] = (record['raw_check']['all_passed']
                            and record['normalized_check']['all_passed']
                            and record['normalization_equivalent'])
    record['status'] = 'public_pass' if record['all_passed'] else 'public_failure'
    return record


def public_stage(args):
    started = time.monotonic()
    rows = cases(args.public)
    assert all(x['split'] in ('visible', 'repair') for x in rows)
    outputs = raw_rows(args.raw)
    assert read(Path(args.raw) / 'receipt.json')['status'] == 'complete'
    assert len(outputs) == 32, 'Initial collection must contain all8 configurations×4samples.'
    assert len({(x['id'], x['sample']) for _, x in outputs}) == 32
    assert Counter(x['source_id'] for _, x in outputs) == Counter({s: 4 for s in SOURCES})
    assert all(x['sample'] in range(4) for _, x in outputs)
    records, repairs = [], []
    for path, row in outputs:
        source = row['source_id']
        subset = [x for x in rows if x['source_id'] == source]
        record = check_output(path, row, subset)
        record['candidate_id'] = f"{row['id']}-{row['sample']}"
        records.append(record)
        save(Path(args.out) / 'public-checks.json', records)
        if not record['all_passed']:
            by_id = {x['case_id']: x for x in subset}
            feedback = []
            if 'normalized_check' in record:
                for event in record['normalized_check']['events']:
                    if event['passed']:
                        continue
                    x = by_id[event['case_id']]
                    execution = event['execution']
                    feedback.append({'givens': x['givens'], 'expected': x['answer'],
                                     'actual': execution.get('value'),
                                     'status': execution['status'],
                                     'error': execution.get('error', execution.get('stderr', ''))[:1200]})
                    if len(feedback) == 4:
                        break
            text = (
                'Your first candidate did not pass the numerical checks. This is the only repair attempt. '
                'Correct your own program using the numerical evidence and geometry specification. '
                'No general formula or repaired solution is supplied. Return one complete closed Python '
                'code block defining solve(givens), with no comments, docstrings or prose.\n\n'
                + 'Format/extraction error: ' + record.get('error', 'none')
                + '\nRaw/normalized execution equivalent: ' + str(record.get('normalization_equivalent'))
                + '\nObserved failures:\n' + json.dumps(feedback, ensure_ascii=False, sort_keys=True)
                + '\nAdditional observed numerical cases:\n'
                + '\n'.join(json.dumps({'givens': x['givens'], 'output': x['answer']}, sort_keys=True)
                            for x in subset if x['split'] == 'repair'))
            repairs.append({'id': 'repair-' + record['candidate_id'], 'source_id': source,
                            'parent_candidate_id': record['candidate_id'], 'parent_raw_sha256': record['raw_sha256'],
                            'evaluation_role': 'program_candidate_repair',
                            'seed': 2026102700 + SOURCES.index(source) * 4 + row['sample'],
                            'messages': row['messages'] + [{'role': 'assistant', 'content': clean_assistant(row['final_text'])},
                                                         {'role': 'user', 'content': text}]})
        print(json.dumps({'candidate': record['candidate_id'], 'status': record['status']}), flush=True)
    save(Path(args.out) / 'repair-jobs.json', repairs)
    save(Path(args.out) / 'receipt.json', {'status': 'complete', 'public_cases_sha256': sha(args.public),
         'initial_raw_dir': str(Path(args.raw).resolve()), 'candidates': len(records),
         'public_pass': sum(x['all_passed'] for x in records), 'repair_jobs': len(repairs),
         'repair_jobs_sha256': sha(Path(args.out) / 'repair-jobs.json'), 'elapsed_seconds': time.monotonic()-started})


def select_stage(args):
    started = time.monotonic()
    all_cases = cases(args.private)
    public = cases(args.public)
    initial = read(Path(args.initial_checks) / 'public-checks.json')
    expected_repairs = read(Path(args.initial_checks) / 'repair-jobs.json')
    repaired = raw_rows(args.repairs) if args.repairs else []
    if args.repairs:
        assert read(Path(args.repairs) / 'receipt.json')['status'] == 'complete'
    assert len(repaired) == len(expected_repairs)
    assert len({x['id'] for _, x in repaired}) == len(repaired)
    assert {x['id'] for _, x in repaired} == {x['id'] for x in expected_repairs}
    repair_map = {x['parent_candidate_id']: (p, x) for p, x in repaired}
    records = []
    for old in initial:
        identity, source = old['candidate_id'], old['source_id']
        if old['all_passed']:
            row = dict(old); row['origin'] = 'initial'
        else:
            path, raw = repair_map[identity]
            row = check_output(path, raw, [x for x in public if x['source_id'] == source])
            row.update(candidate_id=identity, origin='repair', initial_raw_sha256=old['raw_sha256'])
        row['accepted'] = False
        if row['all_passed']:
            subset = [x for x in all_cases if x['source_id'] == source and x['split'] == 'selection']
            assert len(subset) == 24
            row['selection_check'] = evaluate_candidate(row['extraction']['normalized_code'], subset)
            row['accepted'] = row['selection_check']['all_passed']
        records.append(row)
        save(Path(args.out) / 'selection-records.json', records)
        print(json.dumps({'candidate': identity, 'origin': row['origin'], 'accepted': row['accepted']}), flush=True)
    selected, hashes = [], set()
    counts = Counter()
    for row in sorted(records, key=lambda x: (SOURCES.index(x['source_id']), x['candidate_id'])):
        key = (row['source_id'], row.get('extraction', {}).get('normalized_sha256'))
        if row['accepted'] and key not in hashes and counts[row['source_id']] < 2:
            selected.append(row); hashes.add(key); counts[row['source_id']] += 1
    supported = [s for s in SOURCES if counts[s]]
    code_data = [{'id': x['candidate_id'], 'source_id': x['source_id'], 'kind': 'code',
                  'messages': [{'role': 'user', 'content': program_prompt(x['source_id'])}],
                  'target': '```python\n' + x['extraction']['normalized_code'].rstrip() + '\n```',
                  'provenance': {'raw_sha256': x['raw_sha256'],
                                 'normalized_code_sha256': x['extraction']['normalized_sha256'],
                                 'candidate_origin': x['origin']}} for x in selected]
    numeric_data = [{'id': x['case_id'], 'source_id': x['source_id'], 'kind': 'numeric',
                    'messages': [{'role': 'user', 'content': numeric_prompt(x['source_id'], x['givens'])}],
                    'target': format(x['answer'], '.17g')}
                   for x in public if x['source_id'] in supported]
    save(Path(args.out) / 'accepted-candidates.json', selected)
    save(Path(args.out) / 'train-code.json', code_data)
    save(Path(args.out) / 'train-numeric.json', numeric_data)
    receipt = {'status': 'complete', 'selection_gate_pass': len(supported) >= 4,
               'supported_configurations': supported, 'selected_programs': len(code_data),
               'selected_programs_per_configuration': dict(counts),
               'initial_trajectories': len(initial), 'repairs': len(repaired),
               'accepted_trajectories': sum(x['accepted'] for x in records),
               'private_final_outcomes_used': False,
               'private_cases_sha256': sha(args.private), 'public_cases_sha256': sha(args.public),
               'dataset_hashes': {name: sha(Path(args.out) / name)
                                  for name in ('accepted-candidates.json', 'train-code.json', 'train-numeric.json')},
               'elapsed_seconds': time.monotonic()-started}
    save(Path(args.out) / 'receipt.json', receipt)
    print(json.dumps(receipt), flush=True)


def final_check(args):
    all_cases = cases(args.private)
    records = []
    if args.accepted:
        selected = read(args.accepted)
        inputs = [(x['candidate_id'], x['source_id'], x['extraction']) for x in selected]
        provenance = {'accepted_file_sha256': sha(args.accepted), 'training_dataset_already_frozen': True}
    else:
        inputs = []
        raw = raw_rows(args.raw)
        receipt = read(Path(args.raw) / 'receipt.json')
        assert receipt['status'] == 'complete'
        assert len(raw) == 8 * receipt['samples']
        assert Counter(x['source_id'] for _, x in raw) == Counter({s: receipt['samples'] for s in SOURCES})
        assert len({(x['id'], x['sample']) for _, x in raw}) == len(raw)
        for path, row in raw:
            try:
                extracted = extract_program(row['final_text'], row['finish_reason'])
            except (ValueError, SyntaxError) as exc:
                extracted = {'error': str(exc), 'status': 'format_failure'}
            extracted['raw_file_sha256'] = sha(path)
            inputs.append((f"{row['id']}-{row['sample']}", row['source_id'], extracted))
        provenance = {'raw_dir': str(Path(args.raw).resolve())}
    for identity, source, extracted in inputs:
        subset = [x for x in all_cases if x['source_id'] == source and x['split'] == 'final']
        assert len(subset) == 24
        row = {'id': identity, 'source_id': source, 'extraction': extracted, 'all_passed': False}
        if 'normalized_code' in extracted:
            row['check'] = evaluate_candidate(extracted['normalized_code'], subset)
            row['all_passed'] = row['check']['all_passed']
        records.append(row)
        save(args.out, {'status': 'running', **provenance, 'records': records})
    result = {'status': 'complete', **provenance, 'private_cases_sha256': sha(args.private),
              'programs': len(records), 'passed_programs': sum(x['all_passed'] for x in records),
              'records': records}
    save(args.out, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('public'); p.add_argument('--raw', required=True); p.add_argument('--public', required=True); p.add_argument('--out', required=True)
    p = sub.add_parser('select'); p.add_argument('--private', required=True); p.add_argument('--public', required=True)
    p.add_argument('--initial-checks', required=True); p.add_argument('--repairs'); p.add_argument('--out', required=True)
    p = sub.add_parser('final'); p.add_argument('--private', required=True)
    group = p.add_mutually_exclusive_group(required=True); group.add_argument('--accepted'); group.add_argument('--raw')
    p.add_argument('--out', required=True)
    args = parser.parse_args()
    {'public': public_stage, 'select': select_stage, 'final': final_check}[args.command](args)
