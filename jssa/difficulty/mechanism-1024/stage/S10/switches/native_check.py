"""Local PyNomad protocol isolation only; no problem input or quality output."""
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
PYTHON = '/home/kabatan/work/solver/.venv/bin/python'
PACKAGE = Path('/home/kabatan/work/solver/.venv/lib/python3.12/site-packages')
CASES = [
    ('disco_hidden', 'true', 'true', 'OBJ'),
    ('disco_plain', 'true', 'false', 'OBJ'),
    ('mads_plain', 'false', 'false', 'OBJ'),
    # Diagnostic only: not adopted into the switch, since -R adds revealing output.
    ('disco_revealing', 'true', 'false', 'OBJ-R'),
]


def worker(name, disco, hidden, output):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    import faulthandler
    faulthandler.enable()
    import PyNomad
    calls = 0
    receipt = OUT / 'native' / (name + '.json')
    params = ['DIMENSION 2', 'BB_OUTPUT_TYPE ' + output,
              'DISCO_MADS_OPTIMIZATION ' + disco, 'DISCO_MADS_HID_CONST ' + hidden,
              'DISCO_MADS_HID_CONST_OUTPUT_VALUE 1e20', 'MAX_BB_EVAL 8',
              'DISPLAY_DEGREE 0', 'SEED 0', 'ADD_SEED_TO_FILE_NAMES no']

    def save(state):
        receipt.write_text(json.dumps(dict(state=state, params=params,
                                          callback_calls=calls), indent=2) + '\n')

    def callback(point):
        nonlocal calls
        calls += 1
        save('callback_entered')
        point.setBBO(str(sum(point.get_coord(i)**2 for i in range(point.size()))).encode())
        return 1

    save('before_optimize')
    PyNomad.optimize(callback, [.5, .5], [-1., -1.], [1., 1.], params)
    save('returned')


def main():
    dest = OUT / 'native'
    dest.mkdir(exist_ok=False)
    cpu = sorted(os.sched_getaffinity(0))[-1]
    config = json.loads((OUT / 'configs.json').read_text())
    env = {k:v for k,v in os.environ.items() if not k.startswith('GEOSOLVER_ABLATE_')}
    env.update(config['thread_environment'], PYTHONDONTWRITEBYTECODE='1')
    env.pop('PYTHONPATH', None)
    jobs = []
    for case in CASES:
        command = ['nice', '-n', '15', 'taskset', '-c', str(cpu), PYTHON, '-B',
                   str(Path(__file__).resolve()), '--worker', *case]
        start = time.monotonic()
        with (dest / (case[0] + '.stdout')).open('wb') as stdout, \
             (dest / (case[0] + '.stderr')).open('wb') as stderr:
            process = subprocess.Popen(command, env=env, cwd=dest, stdout=stdout,
                                       stderr=stderr, start_new_session=True)
            timeout = False
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                timeout = True
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        jobs.append(dict(case=case[0], returncode=process.returncode,
                         outer_timeout=timeout, wall_seconds=time.monotonic()-start))
        print(case[0], process.returncode, flush=True)
    local_files = [PACKAGE / 'PyNomad.cpython-312-x86_64-linux-gnu.so',
                   PACKAGE / 'pynomadbbo-4.5.1.dist-info/METADATA',
                   OUT / 'native_check.py']
    result = dict(jobs=jobs, cpu=cpu, max_parallel=1, outer_seconds=10,
                  core_dumps=False, problem_inputs_read=False,
                  quality_compared=False, network_used=False,
                  sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in local_files})
    (dest / 'checks.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        worker(*sys.argv[2:])
    else:
        main()
