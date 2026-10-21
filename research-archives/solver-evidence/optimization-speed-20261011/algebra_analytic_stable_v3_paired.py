"""Independent V3 same-core ABBA: 24 development inputs, 96 fresh CLI processes."""
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parent
PYTHON = Path('/home/kabatan/work/solver/.venv/bin/python')
DEST = ROOT / 'algebra-analytic-stable-v3-paired'
DEST.mkdir(exist_ok=False)
changed = json.loads((ROOT / 'analytic-stable-scan-diff.json').read_text())
identifiers = sorted(row['id'] for row in changed if row['after'] == 'available')
baseline = [json.loads(line) for line in (ROOT.parent / 'optimization-20261011/final-public/assessment.jsonl').read_text().splitlines()]
times = {row['case_id']:row['process_wall_seconds'] for row in baseline if row['seed']==0}
identifiers.sort(key=lambda name:(-times[name],name))
assert len(identifiers) == 24
expected_hashes = {
    'baseline-source': 'sha256:f92ee9ba5bea9b124f19e79e95d89e47e66252fede326bb1a569eb1d318e969b',
    'analytic-stable-v3-source': 'sha256:2ff72df3d13e50ba6f586a4a57fb50ee519b0036a5c538b76e05039d49e9856a',
}
identities = {}
for variant, expected in expected_hashes.items():
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT / variant / 'src')
    value = subprocess.check_output([str(PYTHON), '-c',
        'import json; from geosolver.runtime.integrity import engine_identity_hashes; print(json.dumps(engine_identity_hashes()))'],
        env=env, cwd=ROOT / variant, text=True)
    identities[variant] = json.loads(value)
    assert identities[variant]['source_hash'] == expected, identities[variant]
inputs = {}
for name in identifiers:
    digests = [hashlib.sha256((ROOT / variant / 'benchmarks/dsl' / f'{name}.json').read_bytes()).hexdigest()
               for variant in expected_hashes]
    assert len(set(digests)) == 1, name
    inputs[name] = digests[0]
manifest = {'started_at': datetime.now(timezone.utc).isoformat(), 'cases': identifiers,
            'input_sha256': inputs, 'engine_identities': identities, 'cores': [10, 11], 'jobs': 2,
            'time_limit_seconds': 180, 'seed': 0, 'cores_per_solve': 1,
            'order_per_case': ['baseline-source', 'analytic-stable-v3-source', 'analytic-stable-v3-source', 'baseline-source'],
            'fresh_process_count': 96, 'python': str(PYTHON), 'selection': '24 newly available derivative plans in frozen analytic-stable-scan-diff.json; development only'}
(DEST / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
write_lock = threading.Lock()


def lane(core, names):
    for name in names:
        for repeat, variants in enumerate((('baseline-source','analytic-stable-v3-source'),('analytic-stable-v3-source','baseline-source'))):
            for variant in variants:
                env=os.environ.copy()
                env['PYTHONPATH']=str(ROOT/variant/'src')
                for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
                    env[key]='1'
                output=DEST/f'{name}--{variant}--{repeat}.json'
                start=time.monotonic()
                result=subprocess.run(['taskset','-c',str(core),str(PYTHON),'-m','geosolver.application.cli','solve',
                    str(ROOT/variant/'benchmarks/dsl'/f'{name}.json'),'--time-limit-seconds','180','--cores','1','--seed','0','--output',str(output)],
                    env=env,cwd=ROOT/variant,capture_output=True,text=True,timeout=190)
                elapsed=time.monotonic()-start
                if result.returncode:
                    raise RuntimeError(result.stderr)
                solver=json.loads(output.read_text())
                assert solver['engine']['source_hash'] == expected_hashes[variant]
                diagnostics=solver.get('diagnostics') or {}
                row={'case':name,'variant':variant,'repeat':repeat,'core':core,'process_wall_seconds':elapsed,
                     'source_hash':solver['engine']['source_hash'],'answers':solver['answers'],'status':solver['status'],
                     'counters':diagnostics.get('counters',{}),'phase_timings':diagnostics.get('phase_timings',{})}
                with write_lock:
                    with (DEST/'records.jsonl').open('a') as stream:
                        stream.write(json.dumps(row)+'\n')
                    print(json.dumps({'case':name,'variant':variant,'repeat':repeat,'wall':elapsed}),flush=True)


with ThreadPoolExecutor(max_workers=2) as pool:
    futures=[pool.submit(lane,core,identifiers[(core-10)::2]) for core in range(10,12)]
    for future in futures:
        future.result()
