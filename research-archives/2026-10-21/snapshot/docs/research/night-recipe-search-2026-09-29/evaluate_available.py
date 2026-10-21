"""Finish authorized evaluations for existing arms after DX512 retry exhaustion.

This preserves every original job, cap, seed, batch, and arm order. It adds no
new comparison and cannot select a branch from the incomplete seven-arm screen.
"""
import resume
import campaign as c


def generate_available(arm, kind, jobs, unavailable):
    label = f'eval-{arm}-2026093001-{kind}-32768'
    if label in unavailable.get('unavailable_evaluations', []):
        retry = c.read(c.RUN / f'retry-{arm}-{kind}-32768.json')
        assert retry['job'] == label and retry['remaining_retries'] == 0
        assert retry['attempts_executed'] == 2
        assert retry['status'] == 'retry_exhausted_external_priority_interruption'
        c.status(state='evaluation_unavailable', job=label,
                 reason='Both allowed attempts interrupted; do not retry or substitute outputs')
        return
    c.generate(arm, kind, jobs)


def main():
    unavailable = c.read(c.RUN / 'initial-unavailable.json')
    assert unavailable['unavailable_arms'] == ['DX512']
    assert c.read(c.RUN / 'retry-DX512.json')['remaining_retries'] == 0
    c.verify_manifest()
    for arm in c.ARMS:
        if arm in unavailable['unavailable_arms']:
            continue
        setting = c.ARMS[arm]
        if setting:
            family, step = setting
            out = c.RUN / f'train/{family}-2026093001-{step}'
            receipt = c.read(out / 'final/receipt.json')
            assert receipt['status'] == 'complete' and receipt['global_updates'] == step
            assert receipt['config_sha256'] == c.sha(c.RUN / f'configs/{family}-2026093001-{step}.json')
            assert receipt['adapter_sha256'] == c.sha(out / 'final/adapter/adapter_model.safetensors')
        generate_available(arm, 'short', c.RUN / 'jobs/short.json', unavailable)
        generate_available(arm, 'retention', c.RUN / 'jobs/retention.json', unavailable)
        generate_available(arm, 'main', c.RUN / ('jobs/main24.json' if arm in ('Base', 'S128', 'X128') else 'jobs/main12.json'), unavailable)
    c.status(state='available_initial_outputs_complete', unavailable_arms=['DX512'],
             unavailable_evaluations=unavailable.get('unavailable_evaluations', []),
             next='Common-cap checks for available arms, blinded review, audit, incomplete-comparison report; no branch selection')


if __name__ == '__main__':
    main()
