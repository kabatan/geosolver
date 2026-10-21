"""Verify the paired program-generation comparison from recorded provenance."""
import json
from pathlib import Path
from audit_evaluations import HERE, RUNTIME, audit, read, sha


def main():
    settings = dict(samples=4, cap=32768, context=73728, temperature=0.7,
                    top_p=0.95, top_k=20, presence_penalty=0.2, thinking=False)
    initial = read(HERE / 'candidate-jobs.json')
    probe = read(HERE / 'program-probe-jobs.json')
    assert [(j['source_id'], j['seed']) for j in initial] == [(j['source_id'], j['seed']) for j in probe]
    result = {'initial_with_examples': audit(RUNTIME / 'candidates-initial-long', HERE / 'candidate-jobs.json', settings),
              'base_without_examples': audit(RUNTIME / 'program-probe-base-long', HERE / 'program-probe-jobs.json', settings)}
    for arm in ['code', 'numeric']:
        directory = RUNTIME / f'program-probe-{arm}'
        if (directory / 'receipt.json').exists() and read(directory / 'receipt.json')['status'] == 'complete':
            adapter = RUNTIME / f'train-{arm}/final/adapter-vllm'
            training = read(RUNTIME / f'train-{arm}/receipt.json')
            assert sha(adapter / 'adapter_model.safetensors') == training['vllm_adapter_sha256']
            result[arm] = audit(directory, HERE / 'program-probe-jobs.json', settings | {'samples': 1}, adapter)
    for value in result.values():
        for k in ['generation_driver_sha256', 'model_metadata_sha256']:
            assert value[k] == result['initial_with_examples'][k]
    result['comparison_scope'] = 'The same source/seed pairs and max output budget. Example comparison uses four samples per source in each condition. Post-SFT comparison uses only base sample zero, not best-of-four. One-versus-four sampling can differ in numerical batching; this is a small mechanism diagnostic.'
    (HERE / 'program-probe-integrity.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: {f: v[f] for f in ['outputs', 'finish_reasons', 'completion_tokens']}
                      for k, v in result.items() if isinstance(v, dict)}))


if __name__ == '__main__':
    main()
