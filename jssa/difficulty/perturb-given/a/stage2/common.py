"""Q40a instrumentation. All numerical product code comes from the clean checkout."""
from __future__ import annotations

import os
import sys
from pathlib import Path

CLEAN = Path('/tmp/q40a-clean')
SITE = Path('/home/kabatan/work/solver/.venv/lib/python3.12/site-packages')
EXTERNAL = Path('/tmp/q40a-execution')
HERE = Path(__file__).resolve().parent
PLAN = EXTERNAL / 'plan'
FROZEN = '60db4b679b04167175c51c479c87c22fa663fda0'
COMMIT = 'e50c0002dc55b242d13c9edb6ec5f781a45ccda8'
SOURCE_HASH = 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
SEEDS = (404001, 404002, 404003)
VARIANTS = ('original', 'e3_plus', 'e3_minus', 'e2_plus', 'e2_minus', 'e1_random')
THREAD_ENV = {name: '1' for name in (
    'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
    'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS')}
os.environ.update(THREAD_ENV)
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True
# -S deliberately skips the shared environment's editable-install .pth.
assert sys.flags.no_site, 'Invoke with -S; never process the shared editable .pth'
sys.path[:0] = [str(CLEAN / 'src'), str(SITE)]
assert not any(p.endswith('/solver/src') for p in sys.path)

import hashlib
import json
import math
from datetime import datetime, timezone


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean_json(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, 'tolist'):
        return clean_json(value.tolist())
    return value


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(clean_json(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def starts(case_id, seed, bounds):
    import numpy as np
    points = []
    for k in range(200):
        point = []
        for j, (lo, hi) in enumerate(bounds):
            digest = hashlib.sha256(f'Q40|4040|start|{seed}|{case_id}|{k}|{j}'.encode()).digest()
            q = int.from_bytes(digest[:8], 'big') >> 12
            point.append(float(lo) + ((q + .5) / 2**52) * (float(hi) - float(lo)))
        points.append(point)
    return np.array(points)


def schedule(case_id):
    for seed in SEEDS:
        for k in range(200):
            order = sorted(VARIANTS, key=lambda v: sha(f'Q40|4040|order|{seed}|{case_id}|{k}|{v}'.encode()))
            for position, variant in enumerate(order):
                yield seed, k, variant, position


def assemble(case_id, variant):
    from geosolver.problem.models import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    problem = GeometryProblem.model_validate(read(PLAN / 'dsl' / case_id / (variant + '.json')))
    bundle = load_problem_bundle(problem.engine_document())
    evaluator = build_ir_evaluator(bundle)
    return bundle, evaluator


def verify_source():
    import subprocess
    import geosolver
    from geosolver.runtime.integrity import source_tree_hash
    assert Path.cwd() == CLEAN, Path.cwd()
    assert Path(geosolver.__file__).resolve().parent == CLEAN / 'src/geosolver'
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=CLEAN, text=True).strip() == FROZEN
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=CLEAN, text=True).strip()
    manifest = read(PLAN / 'source-manifest.json')
    for name, record in manifest['files'].items():
        data = (CLEAN / name).read_bytes()
        assert sha(data) == record['sha256'] and len(data) == record['bytes'], name
    actual_files = {str(p.relative_to(CLEAN)) for p in (CLEAN / 'src').rglob('*') if p.is_file()}
    assert actual_files == set(manifest['files']), actual_files - set(manifest['files'])
    actual = source_tree_hash()
    assert actual == SOURCE_HASH, actual
    return actual
