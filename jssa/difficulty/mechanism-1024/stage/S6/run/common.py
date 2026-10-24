"""S6 preregistration 13: fixed paths, hashing, and exclusive JSON receipts."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
S6 = HERE.parent
REPO = S6.parents[4]
IMPL = Path('/tmp/s3-impl/src/geosolver')
SOURCE = 'sha256:add5afaf829806ca3cbd11fb07b69d956102752e1c6738b0630581a3ceb121eb'
PYTHON = '/home/kabatan/work/solver/.venv/bin/python'
THREADS = {k: '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
    'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS', 'OMP_THREAD_LIMIT')}

def utc():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def load(path):
    return json.loads(Path(path).read_text())

def save(path, value, exclusive=False):
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    assert len(data.encode()) < 3_000_000, str(path)
    with Path(path).open('x' if exclusive else 'w') as f:
        f.write(data)
        f.flush()
        import os
        os.fsync(f.fileno())

def progress(message):
    with (HERE / 'progress.md').open('a') as f:
        f.write(f'- {utc()} {message}\n')
        f.flush()

def source_manifest():
    digest = hashlib.sha256()
    entries = {}
    for p in sorted(IMPL.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or 'frontend' in p.parts:
            continue
        relative = str(p.relative_to(IMPL))
        entries[relative] = sha(p)
        if p.suffix in {'.py', '.json', '.toml'} and p.name != 'engine-lock.json':
            digest.update(relative.encode() + b'\0' + p.read_bytes().replace(b'\r\n', b'\n') + b'\0')
    return 'sha256:' + digest.hexdigest(), entries
