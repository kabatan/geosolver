"""Evaluate the one excluded decoder diagnostic after the main dataset freezes."""
import hashlib
import json
from pathlib import Path

from execution_harness import evaluate_candidate
from pipeline import check_output, cases, raw_rows, save, sha
from prepare import HERE, ROOT


def main():
    runtime = ROOT / 'qwen/.runtime/program_self_training_20260926'
    selection = json.loads((runtime / 'selection/receipt.json').read_text())
    assert selection['status'] == 'complete'
    data_hashes = {name: sha(runtime / 'selection' / name) for name in selection['dataset_hashes']}
    assert data_hashes == selection['dataset_hashes']
    protocol = json.loads((HERE / 'decoder-diagnostic-protocol.json').read_text())
    assert protocol['training_adoption'] is False
    directory = runtime / 'decoder-diagnostic-h14'
    receipt = json.loads((directory / 'receipt.json').read_text())
    assert receipt['status'] == 'complete'
    assert receipt['jobs_sha256'] == protocol['job_sha256']
    assert all(receipt[k] == v for k, v in protocol['settings'].items())
    outputs = raw_rows(directory)
    assert len(outputs) == 1
    path, row = outputs[0]
    assert row['source_id'] == 'H14' and row['sample'] == 0
    public = [r for r in cases(HERE / 'numeric_cases_public.jsonl') if r['source_id'] == 'H14']
    private = [r for r in cases(HERE / 'numeric_cases_private.jsonl') if r['source_id'] == 'H14']
    assert len(public) == 8 and len(private) == 56
    result = check_output(path, row, public)
    if 'extraction' in result:
        code = result['extraction']['normalized_code']
        for split in ['selection', 'final']:
            result[split + '_check'] = evaluate_candidate(code, [r for r in private if r['split'] == split])
    result.update(training_adoption=False, main_datasets_already_frozen=data_hashes,
                  private_case_sha256=sha(HERE / 'numeric_cases_private.jsonl'),
                  diagnostic_protocol_sha256=sha(HERE / 'decoder-diagnostic-protocol.json'),
                  evaluator_sha256=sha(__file__))
    result['all_56_passed'] = (result['all_passed'] and all(result.get(s + '_check', {}).get('all_passed', False)
                                                        for s in ['selection', 'final']))
    save(runtime / 'decoder-diagnostic-check.json', result)
    assert data_hashes == {name: sha(runtime / 'selection' / name) for name in data_hashes}
    print(json.dumps({'status': result['status'], 'all_56_passed': result['all_56_passed'],
                      'training_adoption': False, 'tokens': result['completion_tokens']}))


if __name__ == '__main__':
    main()
