"""At most eight one-core child process groups; never retries ordinary solve."""
import concurrent.futures
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text())
def batch(cpu,tasks):
    for task in tasks:
        key=task['case_id'];folder=OUT/'results'/key
        if (folder/'result.json').exists():
            continue
        assert not (folder/'started.json').exists(),('refuse retry',key)
        env=os.environ|M['threads']|dict(PYTHONDONTWRITEBYTECODE='1')
        t=time.monotonic()
        with open(os.devnull,'w') as quiet:
            child=subprocess.Popen([M['python'],str(OUT/'worker.py'),key,str(cpu)],env=env,stdout=quiet,stderr=quiet,start_new_session=True)
            try: child.wait(timeout=610)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL);child.wait()
            finally:
                try: os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError: pass
        if not (folder/'result.json').exists():
            folder.mkdir(exist_ok=True,parents=True)
            (folder/'result.json').write_text(json.dumps(dict(case_id=key,status='worker_failed',type='実行失敗',reason=f'worker exited {child.returncode}; no retry',elapsed_seconds=time.monotonic()-t,stage_2_executed=False),ensure_ascii=False,indent=2)+'\n')
        result=json.loads((folder/'result.json').read_text())
        print(key,result['status'],round(time.monotonic()-t,1),flush=True)
if __name__=='__main__':
    assert M['parallel']<=8
    with concurrent.futures.ThreadPoolExecutor(max_workers=M['parallel']) as pool:
        futures=[pool.submit(batch,cpu,M['items'][i::M['parallel']]) for i,cpu in enumerate(M['cpus'])]
        for f in futures: f.result()
