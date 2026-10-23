"""Q34: frozen local solver and complete worker, bounded/resumable jobs.

No production source is edited. Run with the repository's pinned Python 3.12.
Every output is split well below 5 MB; batch runs terminate within 175 seconds.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time
import dataio

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
            'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[key] = '1'
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'jssa/difficulty'))
import numpy as np
from geosolver import GeometryProblem
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search import scipy_multistart_backend as smb

IDS = ['AIME-2007-I-15', 'AIME-2023-I-05', 'AIME-2024-II-10', 'AIME-2025-I-02',
       'AIME-2025-I-06', 'HMMT-2007-FEB-GEO-04', 'HMMT-2009-FEB-GEO-07',
       'HMMT-2011-FEB-ALGGEO-10', 'HMMT-2014-FEB-GEO-06', 'HMMT-2022-FEB-GEO-05',
       'HMMT-2024-FEB-GEO-03', 'HMMT-2025-FEB-GEO-05']
MODES = ['native', 'native-repeat', 'down', 'up', 'sum-reverse']
SUPPLEMENT_MODES = ['mp-down', 'mp-up']
EPS = [10.0**k for k in range(-15, -1)]
VERIFY_EPS = [1e-12, 1e-8, 1e-4, 1e-2]


def utc():
    return datetime.now(timezone.utc).isoformat()


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray)):
        return [clean(v) for v in x]
    if isinstance(x, np.generic):
        return clean(x.item())
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def save(path, obj):
    path = OUT / path
    assert path.resolve().is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(clean(obj), ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n'
    assert len(data.encode()) < 4_900_000, (path, len(data))
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(data)
    tmp.replace(path)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def source_hash():
    h = hashlib.sha256()
    for f in sorted((ROOT / 'src').rglob('*.py')):
        h.update(str(f.relative_to(ROOT)).encode() + b'\0' + f.read_bytes() + b'\0')
    return h.hexdigest()


def check_lock():
    lock = json.loads((OUT / 'prediction.lock.json').read_text())
    assert sha(OUT / 'prediction.md') == lock['sha256'], 'prediction changed'
    assert source_hash() == lock['source_py_sha256'], 'frozen source changed'
    if (OUT / 'inputs.json').exists():
        receipt = json.loads((OUT / 'implementation-lock.json').read_text())
        assert sha(OUT / 'inputs.json') == receipt['inputs_sha256']


def build(inp):
    b = load_problem_bundle(GeometryProblem.model_validate(inp['dsl']).engine_document())
    return b, build_ir_evaluator(b)


def prepare():
    check_lock()
    assert not (OUT / 'inputs.json').exists(), 'do not replace prepared inputs'
    cases = {c['id']: c for c in map(json.loads, (ROOT / 'benchmarks/cases.jsonl').open())}
    inputs = []
    for cid in IDS:
        path = ROOT / f'jssa/difficulty/minima/raw-323/{cid}.json'
        old = json.loads(path.read_text())
        box = np.asarray(old['box'])
        width = box[:, 1] - box[:, 0]
        groups = []
        hits = []
        for r in old['records']:
            if r.get('cls') != 'hit':
                continue
            x = np.asarray(r['x'])
            matches = [i for i, g in enumerate(groups)
                       if np.max(np.abs((x - g['center']) / width)) <= 1e-5]
            if matches:
                ri = matches[0]
            else:
                ri = len(groups)
                groups.append({'center': x.tolist(), 'answer': r['ans'], 'old_count': 0})
            groups[ri]['old_count'] += 1
            hits.append({'k': r['k'], 'start': r['start'], 'root': ri})
        pairs = []
        for i, a in enumerate(hits):
            for b in hits[i+1:]:
                if a['root'] != b['root']:
                    dist = float(np.linalg.norm((np.asarray(a['start']) - b['start']) / width))
                    pairs.append((dist, a['k'], b['k'], a, b))
        pairs.sort(key=lambda x: x[:3])
        inp = {'id': cid, 'dsl': cases[cid]['dsl'], 'box': old['box'], 'roots': groups,
               'references': old['references'], 'old_sha256': sha(path),
               'old_file': str(path.relative_to(ROOT)),
               'candidate_pairs': [{'distance': d, 'a': a, 'b': b} for d, _, _, a, b in pairs[:80]]}
        bundle, _ = build(inp)
        assert np.array_equal(np.asarray(infer_problem_bounds(bundle)), box)
        assert len(bundle.var_names) <= len(bundle.spec.constraints)
        inp['var_names'] = list(bundle.var_names)
        inp['n_constraints'] = len(bundle.spec.constraints)
        assert 2 <= len(groups) <= 4, (cid, len(groups))
        inputs.append(inp)
    save('inputs.json', inputs)
    import scipy, sympy, mpmath
    save('implementation-lock.json', {'utc': utc(), 'experiment_sha256': sha(__file__),
         'inputs_sha256': sha(OUT / 'inputs.json'), 'source_py_sha256': source_hash(),
         'python': sys.version, 'executable': sys.executable, 'numpy': np.__version__,
         'scipy': scipy.__version__, 'sympy': sympy.__version__, 'mpmath': mpmath.__version__,
         'platform': platform.platform(), 'libc': platform.libc_ver(),
         'cpu': next((l.strip() for l in Path('/proc/cpuinfo').read_text().splitlines()
                      if l.startswith('model name')), ''), 'max_workers': 3,
         'threads': {k: os.environ[k] for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')},
         'prediction_sha256': sha(OUT / 'prediction.md')})
    print('inputs fixed', [(i['id'], len(i['roots'])) for i in inputs], flush=True)


class LocalTimeout(BaseException):
    pass


@contextmanager
def alarm(seconds):
    previous = signal.getsignal(signal.SIGALRM)
    def expired(*_):
        raise LocalTimeout()
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def label(rec, inp, tol=1e-5):
    if rec.get('kind') != 'feasible':
        return rec.get('label', 'E')
    ds = np.max(np.abs((np.asarray(rec['x']) - np.asarray([r['center'] for r in inp['roots']])) /
                       np.diff(np.asarray(inp['box']), axis=1).ravel()), axis=1)
    near = int(np.argmin(ds))
    return f'R{near}' if ds[near] <= tol else 'U'


def local(inp, bundle, ev, start, cap=80):
    telemetry = smb._SearchTelemetry()
    config = ExternalPipelineConfig.production_baseline_tier(seed=340201, total_time_budget_sec=30).search
    native, native_cap = smb.least_squares, smb._LM_MAX_NFEV
    detail = {}
    def capture(*args, **kw):
        result = native(*args, **kw)
        detail.update(status=int(result.status), nfev=int(result.nfev),
                      optimality=float(result.optimality))
        return result
    smb.least_squares, smb._LM_MAX_NFEV = capture, cap
    t0 = time.monotonic()
    r = {'label': 'E', 'kind': 'error'}
    try:
        with alarm(2):
            c = smb._collect_local_start_record(bundle=bundle, evaluator=ev,
                bounds=[tuple(v) for v in inp['box']], config=config, seed=340201,
                start_index=0, start=np.asarray(start), deadline_monotonic=t0 + 2,
                telemetry=telemetry)
            if c is not None:
                r.update(x=list(c.x_float), res=c.residual_norm_float,
                         guard=bool(c.guard_ok), hard=c.hard_feasible,
                         tags=list(c.hard_violation_tags))
                if 'out_of_bounds' in c.hard_violation_tags:
                    r.update(kind='left_box', label='F')
                elif not math.isfinite(c.residual_norm_float):
                    r.update(kind='nonfinite', label='E')
                elif c.residual_norm_float > 1e-8:
                    r.update(kind='stuck', label='F')
                elif not c.guard_ok or c.hard_feasible is False:
                    r.update(kind='wrong_branch', label='F')
                else:
                    r['kind'] = 'feasible'
                    r['label'] = label(r, inp)
    except (LocalTimeout, smb._SearchDeadlineExceeded, TimeoutError):
        r.update(kind='timeout', label='T')
    except Exception as e:
        r.update(error=type(e).__name__ + ': ' + str(e)[:180])
    finally:
        smb.least_squares, smb._LM_MAX_NFEV = native, native_cap
    r.update(detail)
    r['sec'] = time.monotonic() - t0
    return clean(r)


def locate(inp):
    bundle, ev = build(inp)
    box = np.asarray(inp['box']); low = box[:, 0]; width = box[:, 1] - low
    patches, used, attempts = [], set(), []
    for pair in inp['candidate_pairs']:
        if pair['a']['k'] in used or pair['b']['k'] in used:
            continue
        a, b = np.asarray(pair['a']['start']), np.asarray(pair['b']['start'])
        ra, rb = local(inp, bundle, ev, a), local(inp, bundle, ev, b)
        trace = [{'a': a, 'b': b, 'ra': ra, 'rb': rb}]
        attempts.append({'a_k': pair['a']['k'], 'b_k': pair['b']['k'],
                         'labels': [ra['label'], rb['label']]})
        if ra['label'] == rb['label'] or 'T' in (ra['label'], rb['label']):
            if len(attempts) >= 20:
                break
            continue
        used.update([pair['a']['k'], pair['b']['k']])
        for _ in range(12):
            mid = (a + b) / 2
            rm = local(inp, bundle, ev, mid)
            trace.append({'x': mid, 'r': rm})
            if rm['label'] == ra['label']:
                a, ra = mid, rm
            else:
                b, rb = mid, rm
        center = ((a + b) / 2 - low) / width
        fixed_center = np.clip(center, .02, .98)
        patches.append({'center': fixed_center, 'unclipped_center': center,
                        'shift': float(np.linalg.norm(center - fixed_center)),
                        'end_labels': [ra['label'], rb['label']],
                        'bracket_width': float(np.linalg.norm((a-b)/width)), 'trace': trace})
        if len(patches) == 2:
            break
    save(f'patches/{inp["id"]}.json', {'utc': utc(), 'id': inp['id'],
                                      'patches': patches, 'attempts': attempts})


def samples(inp):
    patches = json.loads((OUT / f'patches/{inp["id"]}.json').read_text())['patches']
    width = np.diff(np.asarray(inp['box']), axis=1).ravel()
    low = np.asarray(inp['box'])[:, 0]
    rows = []
    for rep in range(2):
        for patch, p in enumerate(patches):
            rng = np.random.default_rng(np.random.SeedSequence([340201 + rep, IDS.index(inp['id']), patch]))
            ys = np.asarray(p['center']) + rng.uniform(-.005, .005, (64, len(width)))
            vs = rng.normal(size=ys.shape)
            vs /= np.linalg.norm(vs, axis=1)[:, None]
            for j in range(64):
                rows.append({'i': rep*128+patch*64+j, 'rep': rep, 'patch': patch, 'j': j,
                             'start': low + ys[j]*width, 'v': vs[j]})
    return rows


def measure(inp, block, verify=False):
    bundle, ev = build(inp)
    width = np.diff(np.asarray(inp['box']), axis=1).ravel()
    selected = [s for s in samples(inp) if (s['j'] < 8 if verify else s['i']//32 == block)]
    result = []
    for s in selected:
        base = local(inp, bundle, ev, s['start'], 320 if verify else 80)
        variants = []
        for eps in VERIFY_EPS if verify else EPS:
            start = s['start'] + eps * width * s['v']
            variants.append({'eps': eps, 'actual_eps': float(np.linalg.norm((start - s['start']) / width)),
                             'same_bits': bool(np.array_equal(start, s['start'])),
                             'r': local(inp, bundle, ev, start, 320 if verify else 80)})
        row = {**s, 'base': base, 'variants': variants}
        if not verify:
            one = s['start'].copy(); coord = s['i'] % len(one)
            one[coord] = np.nextafter(one[coord], np.inf)
            row['ulp'] = {'coord': coord, 'actual_eps': float(np.linalg.norm((one-s['start'])/width)),
                          'r': local(inp, bundle, ev, one)}
            if s['j'] < 4:
                row['repeat'] = local(inp, bundle, ev, s['start'])
        result.append(row)
    folder = 'verify' if verify else 'measure'
    name = inp['id'] if verify else f'{inp["id"]}-{block:02d}'
    save(f'{folder}/{name}.json', {'id': inp['id'], 'utc': utc(), 'cap': 320 if verify else 80,
                                 'block': block, 'rows': result})


class RoundingIntervention:
    """Restore hardware rounding at the callback boundary, including exceptions."""
    def __init__(self, mode):
        self.mode = mode
        self.calls = 0
        self.lib = ctypes.CDLL(str(OUT / 'fenv.so'))
        self.lib.q34_get.restype = ctypes.c_int
        self.lib.q34_set.argtypes = [ctypes.c_int]
        self.lib.q34_constant.argtypes = [ctypes.c_int]
        self.lib.q34_constant.restype = ctypes.c_int
        self.mod = importlib.import_module('geosolver.engine.standard.evaluation.ir_evaluator')
        self.normmod = importlib.import_module('geosolver.engine.standard.evaluation.evaluate_float_residual')
        self.native = self.mod.evaluate_float_residual
        self.native_norm = self.normmod.residual_norm

    def __enter__(self):
        if self.mode in ('down', 'up', 'mp-down', 'mp-up'):
            target = self.lib.q34_constant(1 if self.mode in ('down','mp-down') else 2)
            def changed(**kw):
                from mpmath import mp
                self.calls += 1
                before = self.lib.q34_get()
                mp_before = mp._prec_rounding[1]
                assert self.lib.q34_set(target) == 0
                if self.mode in SUPPLEMENT_MODES:
                    mp._prec_rounding[1] = 'f' if self.mode == 'mp-down' else 'c'
                try:
                    return self.native(**kw)
                finally:
                    mp._prec_rounding[1] = mp_before
                    assert self.lib.q34_set(before) == 0
            self.mod.evaluate_float_residual = changed
        elif self.mode == 'sum-reverse':
            def reversed_norm(residuals):
                self.calls += 1
                vals = tuple(float(v) for v in residuals)
                try:
                    squared = sum(v**2 for v in reversed(vals))
                except OverflowError:
                    return math.hypot(*vals)
                if not math.isfinite(squared) or squared < sys.float_info.min:
                    return math.hypot(*vals)
                return math.sqrt(squared)
            self.normmod.residual_norm = reversed_norm
        return self

    def __exit__(self, *args):
        self.mod.evaluate_float_residual = self.native
        self.normmod.residual_norm = self.native_norm


def full(inp, seed, mode, repeat=False):
    from geosolver.runtime.worker import execute
    from geosolver.runtime.protocol import WorkerRequest
    request = WorkerRequest(engine_document=GeometryProblem.model_validate(inp['dsl']).engine_document(),
                            seed=seed, effective_cores=1, deadline_monotonic=time.monotonic()+30,
                            config_snapshot={'q34_mode': mode, 'time_limit_seconds': 30})
    start = utc()
    with RoundingIntervention(mode) as intervention:
        artifact = execute(request)
    data = artifact.model_dump(mode='json')
    # Preserve complete candidate evidence but split it from pipeline telemetry.
    records = data.pop('candidate_records')
    stem = f'{inp["id"]}-{seed}-{mode}'
    folder = 'full-recheck' if repeat else ('full-mp' if mode in SUPPLEMENT_MODES else 'full')
    for i in range(0, len(records), 16):
        save(f'{folder}/candidates/{stem}-{i//16:02d}.json', records[i:i+16])
    data.update(id=inp['id'], seed=seed, mode=mode, q34_started_utc=start,
                q34_finished_utc=utc(), intervention_calls=intervention.calls,
                candidate_record_count=len(records), source_py_sha256=source_hash(),
                prediction_sha256=sha(OUT / 'prediction.md'))
    save(f'{folder}/{stem}.json', data)


def rounding_audit():
    rows = []
    inputs = json.loads((OUT / 'inputs.json').read_text())
    for inp in inputs:
        probes = [np.asarray(p['a']['start']) for p in inp['candidate_pairs'][:4]]
        vals = {}
        for mode in MODES + SUPPLEMENT_MODES:
            with RoundingIntervention(mode) as intervention:
                _, ev = build(inp)
                vals[mode] = []
                for x in probes:
                    r = ev.evaluate_float_residual(list(x))
                    vals[mode].append({'vector': list(r.residual_vector), 'norm': r.residual_norm_float})
                calls = intervention.calls
            rows.append({'id': inp['id'], 'mode': mode, 'calls': calls, 'probes': vals[mode]})
    save('rounding-audit-with-mp.json', {'utc': utc(), 'rows': rows})


def jobs(stage):
    tasks = []
    for cid in IDS:
        if stage == 'locate':
            tasks.append(([stage, cid], f'patches/{cid}.json', 90))
        elif stage == 'measure':
            for block in range(8):
                tasks.append(([stage, cid, str(block)], f'measure/{cid}-{block:02d}.json', 90))
        elif stage == 'verify':
            tasks.append(([stage, cid], f'verify/{cid}.json', 90))
        elif stage == 'full':
            for seed in (340301, 340302):
                for mode in MODES:
                    tasks.append(([stage, cid, str(seed), mode], f'full/{cid}-{seed}-{mode}.json', 42))
        elif stage == 'full-mp':
            for seed in (340301, 340302):
                for mode in SUPPLEMENT_MODES:
                    tasks.append((['full', cid, str(seed), mode], f'full-mp/{cid}-{seed}-{mode}.json', 42))
    if stage == 'recheck':
        for j in json.loads((OUT / 'recheck-jobs.json').read_text()):
            cid, seed, mode = j
            tasks.append((['full', cid, str(seed), mode, 'recheck'],
                          f'full-recheck/{cid}-{seed}-{mode}.json', 42))
    return [j for j in tasks if not dataio.exists(OUT / j[1])]


def batch(stage, seconds):
    check_lock()
    assert 1 <= seconds <= 170
    todo = jobs(stage)
    started = time.monotonic(); active = []; done = 0
    logdir = OUT / 'logs'; logdir.mkdir(exist_ok=True)
    while todo or active:
        elapsed = time.monotonic() - started
        while todo and len(active) < 3 and elapsed + todo[0][2] < seconds:
            args, path, limit = todo.pop(0)
            logpath = logdir / ('-'.join(args) + '.log')
            log = logpath.open('w')
            p = subprocess.Popen([sys.executable, '-B', str(Path(__file__)), *args],
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            active.append((p, time.monotonic(), limit, args, path, log))
        remaining = []
        for p, began, limit, args, path, log in active:
            rc = p.poll()
            if rc is None and time.monotonic() - began > limit:
                os.killpg(p.pid, signal.SIGKILL); p.wait(); rc = p.returncode
            if rc is None:
                remaining.append((p, began, limit, args, path, log))
                continue
            log.close(); done += 1
            print(json.dumps({'task': args, 'rc': rc, 'saved': dataio.exists(OUT/path),
                              'sec': round(time.monotonic()-began, 2)}), flush=True)
        active = remaining
        if not active and (not todo or time.monotonic()-started+todo[0][2] >= seconds):
            break
        time.sleep(.2)
    print(json.dumps({'stage': stage, 'finished': done, 'remaining': len(jobs(stage)),
                      'seconds': round(time.monotonic()-started, 2)}), flush=True)


def main():
    cmd = sys.argv[1]
    if cmd == 'prepare':
        prepare(); return
    check_lock()
    if cmd == 'batch':
        batch(sys.argv[2], float(sys.argv[3]) if len(sys.argv)>3 else 165); return
    if cmd == 'rounding-audit':
        rounding_audit(); return
    # Each child is a single numerical stream; symbolic subprocesses inherit limits.
    resource.setrlimit(resource.RLIMIT_FSIZE, (4_900_000, 4_900_000))
    resource.setrlimit(resource.RLIMIT_CPU, (85, 90))
    try:
        os.nice(5)
    except OSError:
        pass
    inputs = json.loads((OUT / 'inputs.json').read_text())
    inp = next(i for i in inputs if i['id'] == sys.argv[2])
    if cmd == 'locate':
        locate(inp)
    elif cmd == 'measure':
        measure(inp, int(sys.argv[3]))
    elif cmd == 'verify':
        measure(inp, 0, verify=True)
    elif cmd == 'full':
        full(inp, int(sys.argv[3]), sys.argv[4], repeat=len(sys.argv)>5)
    else:
        raise ValueError(cmd)


if __name__ == '__main__':
    main()
