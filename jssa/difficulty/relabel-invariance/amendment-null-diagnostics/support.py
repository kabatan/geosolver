"""Shared, solver-free checks for the Q38 null-diagnostics amendment."""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
REPO = BASE.parents[2]
CLEAN = Path('/tmp/q38-58e3993-clean')
PYTHON = Path('/tmp/q38-58e3993-venv/bin/python')
EXTERNAL = Path('/tmp/q38-58e3993-repaired-execution')
SOURCE_HASH = 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
FROZEN = '60db4b679b04167175c51c479c87c22fa663fda0'
EXECUTION_COMMIT = '58e399315f259699e99cc1b190aa46c78d573e5a'
ORIGINAL_GRADER_SHA256 = 'b9ddace01355d8ac4e5c0ae75f61c4543c976d46bc430e8a44203926e42f4b81'
OLD_LINE = '    diagnostics = result.get("diagnostics", {})\n'
NEW_LINE = '    diagnostics = result.get("diagnostics") or {}\n'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n',
                    encoding='utf-8')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def plan():
    return read(BASE / 'execution-plan.json')


def destination(batch, campaigns=EXTERNAL / 'campaigns'):
    return Path(batch['destination'].replace('<external-results-root>', str(campaigns)))


def check_patch():
    old = CLEAN / 'benchmarks/research_runner.py'
    new = REPO / 'benchmarks/research_runner.py'
    require(sha(old) == ORIGINAL_GRADER_SHA256, 'Frozen runner changed')
    text = old.read_text(encoding='utf-8')
    require(text.count(OLD_LINE) == 1, 'Unexpected old diagnostics assignment')
    require(new.read_bytes() == text.replace(OLD_LINE, NEW_LINE).encode('utf-8'),
            'Grader must differ by exactly the one registered line')
    return {'before_sha256': sha(old), 'after_sha256': sha(new),
            'changed_lines': 1, 'only_function_changed': 'read_run_outcome'}


def check_original_lock(base):
    lock = read(base / 'prediction.lock.json')
    for name, entry in lock['files'].items():
        path = base / name
        require(sha(path) == entry['sha256'] and path.stat().st_size == entry['bytes'],
                f'Original lock mismatch: {path}')
    for mapping, digest in [('files', 'file_manifest_sha256'),
                            ('all_transformed_dsl_sha256', 'all_transformed_dsl_manifest_sha256')]:
        require(hashlib.sha256(canonical(lock[mapping])).hexdigest() == lock[digest],
                f'Original manifest mismatch: {mapping}')
    for mapping in ('transformation_rules_sha256', 'all_transformed_dsl_sha256'):
        for name, digest in lock[mapping].items():
            require(sha(base / name) == digest, f'Original input changed: {name}')
    require(sha(base / 'prediction.md') == lock['prediction_sha256'], 'Prediction changed')
    return {'files': len(lock['files']), 'prediction_lock_sha256': sha(base / 'prediction.lock.json')}


def check_supplement_lock():
    lock = read(HERE / 'prediction-supplement.lock.json')
    for name, entry in lock['files'].items():
        path = REPO / name
        require(sha(path) == entry['sha256'] and path.stat().st_size == entry['bytes'],
                f'Supplement lock mismatch: {name}')
    require(hashlib.sha256(canonical(lock['files'])).hexdigest() == lock['file_manifest_sha256'],
            'Supplement manifest mismatch')
    require(sha(HERE / 'prediction-supplement.md') == lock['prediction_sha256'],
            'Supplement text changed')
    return {'files': len(lock['files']), 'lock_sha256': sha(HERE / 'prediction-supplement.lock.json')}


def inventory(root):
    return {str(p.relative_to(root)): {'sha256': sha(p), 'bytes': p.stat().st_size}
            for p in sorted(root.rglob('*')) if p.is_file()}


def install_no_solver_guard(*, allow_processes=False):
    """Stop before a solver entrypoint body or any unapproved process spawn.

    Import-only preflight's controller allows its explicit git/Python probes;
    each probe, and the complete rescoring process, forbids process spawning.
    """
    state = {'solver_calls': 0, 'blocked_solver_entry_attempts': [],
             'blocked_process_attempts': [], 'process_spawning_forbidden': not allow_processes}

    def profile(frame, event, arg):
        if event != 'call':
            return
        module = frame.f_globals.get('__name__') or ''
        name = frame.f_code.co_name
        forbidden = (
            (module == 'geosolver.application.service' and name == 'solve')
            or (module == 'geosolver.engine.runner' and name == 'run')
            or (module == 'geosolver.runtime.worker' and name in {'execute', 'main'})
            or (module.startswith('geosolver.engine.standard.orchestration.')
                and name.startswith('run_'))
            or (frame.f_code.co_filename.endswith('research_runner.py')
                and name in {'run_campaign', '_run_one'})
            or (frame.f_code.co_filename.endswith('stage2.py')
                and name in {'start', 'batch_run'})
        )
        if forbidden:
            state['blocked_solver_entry_attempts'].append(f'{module}.{name}')
            raise RuntimeError('Solver execution is forbidden in this stage')

    def audit(event, args):
        if not allow_processes and (event in {'subprocess.Popen', 'os.system', 'os.fork',
                                              'os.forkpty', 'os.posix_spawn', 'os.exec'}
                                    or event.startswith('os.spawn')):
            state['blocked_process_attempts'].append(event)
            raise RuntimeError('Process spawning is forbidden in this solver-free process')

    sys.setprofile(profile)
    threading.setprofile(profile)
    sys.addaudithook(audit)
    return state


def load_grader():
    check_patch()
    sys.path.insert(0, str(CLEAN / 'src'))
    name = 'q38_amended_research_runner'
    spec = importlib.util.spec_from_file_location(name, REPO / 'benchmarks/research_runner.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def check_guard(state):
    require(state['solver_calls'] == 0 and not state['blocked_solver_entry_attempts']
            and not state['blocked_process_attempts'], f'Zero-call guard violation: {state}')
