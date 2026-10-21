"""Same-core AB/BA on every newly supported derivative problem, including failures."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parent
PYTHON = Path('/home/kabatan/work/solver/.venv/bin/python')
DEST = ROOT / 'analytic-stable-paired'
DEST.mkdir(exist_ok=False)
changed = json.loads((ROOT / 'analytic-stable-scan-diff.json').read_text())
identifiers = sorted(row['id'] for row in changed if row['after'] == 'available')
baseline = [json.loads(line) for line in (ROOT.parent / 'optimization-20261011/final-public/assessment.jsonl').read_text().splitlines()]
times = {row['case_id']:row['process_wall_seconds'] for row in baseline if row['seed']==0}
identifiers.sort(key=lambda name:(-times[name],name))
write_lock = threading.Lock()


def lane(core, names):
    for name in names:
        for repeat, variants in enumerate((('baseline-source','analytic-stable-source'),('analytic-stable-source','baseline-source'))):
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
                diagnostics=solver.get('diagnostics') or {}
                row={'case':name,'variant':variant,'repeat':repeat,'core':core,'process_wall_seconds':elapsed,
                     'source_hash':solver['engine']['source_hash'],'answers':solver['answers'],'status':solver['status'],
                     'counters':diagnostics.get('counters',{}),'phase_timings':diagnostics.get('phase_timings',{})}
                with write_lock:
                    with (DEST/'records.jsonl').open('a') as stream:
                        stream.write(json.dumps(row)+'\n')
                    print(json.dumps({'case':name,'variant':variant,'repeat':repeat,'wall':elapsed}),flush=True)


with ThreadPoolExecutor(max_workers=5) as pool:
    futures=[pool.submit(lane,core,identifiers[(core-1)::5]) for core in range(1,6)]
    for future in futures:
        future.result()
