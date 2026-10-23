"""Q40b observation support; no search, input changes, or outcome selection."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import resource
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLEAN = Path('/tmp/q40b-clean')
PYTHON = Path('/tmp/q40b-env/bin/python')
RAW = Path('/tmp/q40b-raw')
OUT = HERE / 'execution'
SOURCE = 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
FROZEN = '60db4b679b04167175c51c479c87c22fa663fda0'
THREADS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
           'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS')


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    if hasattr(value, '_mpf_'):
        from mpmath import mp
        return mp.nstr(value, n=max(550, value._mpf_[3] * 30103 // 100000 + 10))
    if dataclasses.is_dataclass(value):
        return encode({f.name: getattr(value, f.name) for f in dataclasses.fields(value)})
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    if value is None or isinstance(value, (str, int, bool, float)):
        return value
    return str(value)


def write(path, value, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(encode(value), ensure_ascii=False, sort_keys=True,
                       indent=2, allow_nan=False) + '\n').encode()
    if len(data) >= 5_000_000:
        raise ValueError('receipt exceeds frozen size limit')
    if exclusive:
        with path.open('xb') as f:
            f.write(data)
    else:
        temp = path.with_name(path.name + f'.{os.getpid()}.tmp')
        with temp.open('wb') as f:
            f.write(data)
        os.replace(temp, path)


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def cpu_snapshot(start_ns=0):
    """Worker CPU plus reaped children and currently live descendant CPU.

    Linux live-process accounting has clock-tick resolution. Its sampling span
    is retained; process_time_ns is sampled immediately at verification return.
    """
    import psutil
    stamp = time.perf_counter_ns()
    own_ns = time.process_time_ns()
    dead = resource.getrusage(resource.RUSAGE_CHILDREN)
    live = []
    for child in psutil.Process().children(recursive=True):
        try:
            c = child.cpu_times()
            live.append({'pid': child.pid, 'created': child.create_time(),
                         'user_s': c.user, 'system_s': c.system,
                         'reaped_user_s': c.children_user,
                         'reaped_system_s': c.children_system,
                         'threads': child.num_threads(), 'affinity': child.cpu_affinity()})
        except psutil.Error:
            # A child reaped during sampling is accounted in RUSAGE_CHILDREN
            # on the next/end sample. Record this limitation explicitly.
            live.append({'pid': child.pid, 'race': 'exited_during_sample'})
    child_s = dead.ru_utime + dead.ru_stime
    child_s += sum(c.get('user_s', 0) + c.get('system_s', 0)
                   + c.get('reaped_user_s', 0) + c.get('reaped_system_s', 0) for c in live)
    return {'perf_ns': stamp, 'process_time_ns': own_ns,
            'own_cpu_s': (own_ns - start_ns) / 1e9,
            'reaped_children_cpu_s': dead.ru_utime + dead.ru_stime,
            'live_children': live, 'cpu_s': (own_ns - start_ns) / 1e9 + child_s,
            'sample_span_s': (time.perf_counter_ns() - stamp) / 1e9,
            'children_clock_tick_s': 1 / os.sysconf('SC_CLK_TCK')}


class FirstFigure(BaseException):
    def __init__(self, payload):
        self.payload = payload

    def __str__(self):
        return 'Q40b intentional stop at the first verified figure'


class IdentifyViolation(BaseException):
    pass
