"""At most two single-core workers; exclusive receipts prevent reruns."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
from queue import Queue

OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text())
CPUS=Queue()
for cpu in M['cpus']: CPUS.put(cpu)
def worker(pair):
    i,task=pair
    key=task['case_id']
    env={k:v for k,v in os.environ.items() if not k.startswith('GEOSOLVER_ABLATE_')}
    env.update(M['threads']); env['PYTHONDONTWRITEBYTECODE']='1'
    log=Path(M['scratch'])/(key+'.log')
    cpu=CPUS.get()
    with log.open('x') as stream:
        try:
            p=subprocess.run([M['python'],'-B',str(OUT/'worker.py'),key,str(cpu)],
                             stdout=stream,stderr=subprocess.STDOUT,env=env,timeout=250)
            print(key,p.returncode,flush=True)
        except subprocess.TimeoutExpired:
            print(key,'timeout',flush=True)
        finally:
            CPUS.put(cpu)
with ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(worker,enumerate(M['items'])))
