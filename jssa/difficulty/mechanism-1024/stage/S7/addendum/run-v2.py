"""Four isolated, CPU-pinned workers; reuse only existing completed receipts."""
from common import *
from concurrent.futures import ThreadPoolExecutor
import subprocess
import time

def task(args):
    key, cpu = args
    path = OUT/'results'/f'{key}.json'
    if path.exists():
        assert load(path)['status'] == 'ok'
        return key, 'existing'
    result = subprocess.run([sys.executable, str(OUT/'worker-v2.py'), key, str(cpu)],
                            cwd=OUT, capture_output=True, text=True, timeout=900)
    if result.returncode:
        raise RuntimeError(key+' '+result.stderr[-5000:])
    assert load(path)['status'] == 'ok'
    return key, result.stdout.strip()

if __name__ == '__main__':
    manifest = check_manifest()
    (OUT/'results').mkdir(exist_ok=True)
    cpus = sorted(os.sched_getaffinity(0))[:4]
    assert len(cpus) == 4
    start = time.monotonic()
    # Executor slots are assigned a fixed CPU by partition, avoiding shared affinity.
    groups = [manifest['case_ids'][i::4] for i in range(4)]
    def group(i):
        for key in groups[i]:
            result = task((key, cpus[i]))
            print(*result, flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(group, range(4)))
    save(OUT/'execution.json', dict(status='ok', parallel_max=4, cpus=cpus, elapsed_seconds=time.monotonic()-start,
                                  cases=len(manifest['case_ids']), stage_2_executed=False))
