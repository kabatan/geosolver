"""Run only the frozen two-arm H14 diagnostic; never rewrite existing assets."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
D = Path(__file__).resolve().parent
C = ROOT / 'docs/research/qwen35-external-teacher-2026-09-25/projection-bridge-candidate'
J = ROOT / 'docs/research/qwen35-external-teacher-2026-09-25/heldout-near-transfer/followup-bridge-eval'
R = ROOT / 'qwen/.runtime/research_direction_audit_20260925'
DRIVERS = ROOT / 'docs/research/qwen35-diverse-sft-2026-09-24'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def main():
    os.chdir(ROOT)
    R.mkdir(exist_ok=False)
    jobs = []
    for name in ['eval_jobs.json', 'eval_jobs_second_seed.json']:
        jobs.extend(x for x in json.loads((J/name).read_text()) if x['source_id'] == 'H14')
    assert len(jobs) == 4 and len({x['id'] for x in jobs}) == 4
    jobpath = D / 'bridge-pilot-jobs.json'
    assert not jobpath.exists()
    write(jobpath, jobs)
    spec0 = json.loads((ROOT/'docs/research/qwen35-external-teacher-2026-09-24/train-protocol-low-dose.json').read_text())
    hashes = json.loads((C/'candidate-hashes.json').read_text())['sha256']
    freeze = {'created_unix': time.time(), 'scope': 'two-arm H14 exploratory pilot',
              'protocol_sha256': sha(D/'BRIDGE_PILOT_PROTOCOL.md'),
              'runner_sha256': sha(Path(__file__)), 'jobs_sha256': sha(jobpath),
              'source_jobs': {n: sha(J/n) for n in ['eval_jobs.json', 'eval_jobs_second_seed.json']},
              'datasets': {}, 'train_driver_sha256': sha(DRIVERS/'train.py'),
              'generate_driver_sha256': sha(DRIVERS/'generate.py')}
    for arm in ['treatment', 'control']:
        rel = f'rotation-3/train-{arm}.json'
        dataset = C/rel
        assert sha(dataset) == hashes[rel]
        rows = json.loads(dataset.read_text())
        assert len(rows) == 38 and len({r['source'] for r in rows}) == 34
        assert 'H14' not in {r['source'] for r in rows}
        spec = spec0 | {'dataset': str(dataset), 'dataset_sha256': sha(dataset),
                       'eval_jobs': str(jobpath), 'eval_jobs_sha256': sha(jobpath),
                       'n_examples': 38, 'n_configurations': 34, 'epochs': 1,
                       'planned_updates': 38, 'study_arm': f'bounded_h14_bridge_{arm}',
                       'checkpoint': 'one fixed epoch; no output-based checkpoint selection'}
        assert spec['lr'] == 1e-5 and spec['seed'] == 2026092431
        write(D/f'bridge-train-{arm}.json', spec)
        freeze['datasets'][arm] = {'sha256':sha(dataset),'protocol_sha256':sha(D/f'bridge-train-{arm}.json')}
    write(D/'BRIDGE_PILOT_FREEZE.json', freeze)
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    # Sequential GPU access; logs never expose raw generated answers before blinding.
    for arm in ['treatment', 'control']:
        with (R/f'train-{arm}.log').open('w') as log:
            subprocess.run([sys.executable, str(DRIVERS/'train.py'), '--protocol',
                            str(D/f'bridge-train-{arm}.json'), '--out', str(R/f'train-{arm}')],
                           env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        rec = json.loads((R/f'train-{arm}/receipt.json').read_text())
        print(json.dumps({'arm':arm,'training_status':rec['status'],'updates':rec['updates']}), flush=True)
    for arm in ['treatment', 'control']:
        subprocess.run([sys.executable, str(DRIVERS/'generate.py'), '--jobs', str(jobpath),
                        '--out', str(R/f'eval-{arm}'), '--adapter', str(R/f'train-{arm}/adapter'),
                        '--samples','1','--cap','32768','--context','45056',
                        '--temperature','1','--top-p','.95','--top-k','20','--presence-penalty','1.5'],
                       env=env, check=True)
        rec = json.loads((R/f'eval-{arm}/receipt.json').read_text())
        print(json.dumps({'arm':arm,'eval_status':rec['status'],'seconds':rec['elapsed_seconds']}),flush=True)

if __name__ == '__main__':
    main()
