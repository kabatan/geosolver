"""At most eight isolated single-core processes; exclusive receipts prohibit reruns."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from queue import Queue
import signal
import subprocess
from select_targets import save,sha

OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text())
for p,h in {**M['files'],**M['source_files']}.items(): assert sha(Path(p))==h,p
CPUS=Queue()
for cpu in M['cpus']: CPUS.put(cpu)
(OUT/'results').mkdir(exist_ok=True)
def run(task):
    key=task['case_id'];cpu=CPUS.get()
    env={k:v for k,v in os.environ.items() if not k.startswith(('GEOSOLVER_', 'TANGENCY_', 'PYTHONPATH'))}
    env.update(M['threads']);env['PYTHONDONTWRITEBYTECODE']='1'
    folder=OUT/'results'/key;folder.mkdir(exist_ok=True)
    with (folder/'worker.log').open('x') as stream:
        process=None
        try:
            process=subprocess.Popen([M['python'],'-B',str(OUT/'worker.py'),key,str(cpu)],
                stdout=stream,stderr=subprocess.STDOUT,env=env,start_new_session=True)
            rc=process.wait(timeout=600)
            print(key,'returncode',rc,flush=True)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait()
            if not (folder/'result.json').exists():
                save(folder/'result.json',dict(case_id=key,status='reference_unavailable',type='参照解なし',
                    prediction='',reason='600秒の問題全体上限',elapsed_seconds=600))
            print(key,'timeout',flush=True)
        finally: CPUS.put(cpu)
with ThreadPoolExecutor(max_workers=M['parallel']) as pool: list(pool.map(run,M['items']))
for p,h in {**M['files'],**M['source_files']}.items(): assert sha(Path(p))==h,p
print('All stage (1) workers completed; stage (2) never invoked.',flush=True)
