"""Q43c: fixed, target-only exploratory sweep (no product mutations)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
# Product imports must never resolve through the concurrently edited worktree.
ROOT = Path('/tmp/q43c-clean')
PYTHON = Path('/home/kabatan/work/solver/.venv/bin/python')
RAW = Path('/tmp/q43c-swap-target-clean-20261024')
FROZEN = '60db4b679b04167175c51c479c87c22fa663fda0'
SOURCE = 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
SELECTION_SEED = 431024
SEEDS = [43101, 43102]
KINDS = ['original', 'length', 'area', 'angle', 'ratio']
THREADS = {k: '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}


def environment():
    return os.environ | THREADS | {'PYTHONPATH': str(ROOT / 'src') + ':' + str(ROOT), 'PYTHONDONTWRITEBYTECODE': '1'}


def activate():
    sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rank(salt, text):
    return hashlib.sha256(f'{SELECTION_SEED}:{salt}:{text}'.encode()).hexdigest()


def verify_source():
    activate()
    import geosolver
    from geosolver.runtime.integrity import source_tree_hash, verify_engine_lock
    assert Path(geosolver.__file__).resolve().parent == ROOT / 'src/geosolver'
    actual = source_tree_hash()
    assert actual == SOURCE, actual
    assert verify_engine_lock()[0]
    return {'import_file': geosolver.__file__, 'source_hash': actual}
