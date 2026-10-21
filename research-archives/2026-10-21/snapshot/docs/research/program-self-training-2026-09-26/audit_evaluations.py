"""Check completed evaluation provenance without inspecting answer content."""
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNTIME = ROOT / 'qwen/.runtime/program_self_training_20260926'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(directory, jobs_path, settings, adapter=None):
    receipt = read(directory / 'receipt.json')
    assert receipt['status'] == 'complete', directory
    jobs = read(jobs_path)
    assert receipt['jobs_sha256'] == sha(jobs_path)
    assert all(receipt[k] == v for k, v in settings.items())
    assert receipt['adapter'] == (str(adapter.resolve()) if adapter else None)
    rows = []
    for path in sorted(directory.glob('*.json')):
        row = read(path)
        if isinstance(row, dict) and 'final_text' in row:
            rows.append((path, row))
    expected = {(j['id'], s) for j in jobs for s in range(settings['samples'])}
    assert len(rows) == len(expected)
    assert {(r['id'], r['sample']) for _, r in rows} == expected
    job_by_id = {j['id']: j for j in jobs}
    for _, row in rows:
        assert row['messages'] == job_by_id[row['id']]['messages']
        assert row['source_id'] == job_by_id[row['id']]['source_id']
    return {
        'status': 'complete', 'outputs': len(rows),
        'finish_reasons': dict(Counter(r['finish_reason'] for _, r in rows)),
        'completion_tokens': sum(len(r['completion_ids']) for _, r in rows),
        'per_source_finish': {
            source: dict(Counter(r['finish_reason'] for _, r in rows if r['source_id'] == source))
            for source in sorted({r['source_id'] for _, r in rows})},
        'receipt_sha256': sha(directory / 'receipt.json'),
        'raw_sha256': {p.name: sha(p) for p, _ in rows},
        'generation_driver_sha256': receipt['driver_sha256'],
        'model_metadata_sha256': receipt['model_metadata_sha256'],
    }


def main():
    settings = dict(samples=1, cap=32768, context=40960, temperature=0.7,
                    top_p=0.95, top_k=20, presence_penalty=0.2, thinking=False)
    old = ROOT / 'qwen/.runtime/answer_opd_pilot_20260926/eval-base'
    result = {'base': audit(old, HERE / 'eval-jobs.json', settings)}
    for arm in ['code', 'numeric']:
        directory = RUNTIME / f'eval-{arm}'
        if (directory / 'receipt.json').exists() and read(directory / 'receipt.json')['status'] == 'complete':
            adapter = RUNTIME / f'train-{arm}/final/adapter-vllm'
            training = read(RUNTIME / f'train-{arm}/receipt.json')
            assert training['status'] == 'complete' and training['global_updates'] == 32
            assert sha(adapter / 'adapter_model.safetensors') == training['vllm_adapter_sha256']
            result[arm] = audit(directory, HERE / 'eval-jobs.json', settings, adapter)
            for k in ['generation_driver_sha256', 'model_metadata_sha256']:
                assert result[arm][k] == result['base'][k]
    (HERE / 'evaluation-integrity.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: {f: v[f] for f in ['outputs', 'finish_reasons', 'completion_tokens']}
                      for k, v in result.items()}))


if __name__ == '__main__':
    main()
