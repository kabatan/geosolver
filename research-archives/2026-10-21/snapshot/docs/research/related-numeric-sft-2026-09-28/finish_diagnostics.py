"""Run the preregistered conditional probe after all generation releases the GPU."""
import json, subprocess, time
from pathlib import Path
import run_pipeline as op

P, R, O = op.P, op.R, op.O

def main():
    while not (O/'generation-complete.json').exists():
        time.sleep(5)
    subprocess.run([str(R/'.venv/bin/python'), str(P/'analyze.py')], check=True, cwd=R)
    summary = op.read(O/'numeric-scores.json')['summary']
    base = summary['base']['trained_example']['correct']
    condition = all(summary[a]['trained_example']['correct'] <= base for a in ['sft-a','sft-b'])
    op.write(O/'digit-probe-decision.json', {
        'base_trained_correct': base,
        'sft_trained_correct': {a: summary[a]['trained_example']['correct'] for a in ['sft-a','sft-b']},
        'run_probe': condition,
        'basis': 'DIGIT_LOSS_DIAGNOSTIC.md; trained-example numerical accuracy in both SFT seeds <= base',
        'unix': time.time(),
    })
    if condition:
        for arm in ['base','sft-a']:
            label = f'{arm}-digit-probe'
            args = [op.PY, P/'probe_digit_loss.py', '--config', P/'config-sft-a-32.json', '--out', O/label]
            if arm != 'base':
                args += ['--adapter', O/'sft-a-train128/final/adapter']
            op.run(args, label, True, [P/'DIGIT_LOSS_DIAGNOSTIC.md', P/'probe_digit_loss.py', O/'train.json', O/'data-provenance.json'])
    subprocess.run([str(R/'.venv/bin/python'), str(P/'report_metrics.py')], check=True, cwd=R)
    op.write(O/'automatic-diagnostics-complete.json', {'status':'complete', 'digit_probe_executed':condition, 'unix':time.time()})

if __name__ == '__main__':
    main()
