"""Q43b: isolated experiment utilities; never modifies geosolver."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
EXTERNAL = Path('/tmp/q43b-20261024-d461234c')
FROZEN = '60db4b679b04167175c51c479c87c22fa663fda0'
SOURCE = 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
SELECTION_SEED = 4302
SEEDS = (43021, 43022)
LIMIT = 45
THREADS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
           'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
os.environ['PYTHONPATH'] = str(ROOT / 'src') + ':' + str(ROOT)
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['PYTHONHASHSEED'] = '0'
for name in THREADS:
    os.environ[name] = '1'

def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def sha(x):
    return hashlib.sha256(x if isinstance(x, bytes) else canonical(x).encode()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temp.replace(path)

def fingerprint():
    import geosolver
    from geosolver.runtime.integrity import source_tree_hash, installed_dependencies, verify_engine_lock
    assert Path(geosolver.__file__).resolve().parent == ROOT / 'src/geosolver'
    assert source_tree_hash() == SOURCE
    assert verify_engine_lock()[0]
    return {'import': geosolver.__file__, 'source_hash': SOURCE,
            'python': sys.executable, 'dependencies': installed_dependencies()}

def rank(identifier, purpose='selection'):
    return hashlib.sha256(f'{SELECTION_SEED}|{purpose}|{identifier}'.encode()).hexdigest()
