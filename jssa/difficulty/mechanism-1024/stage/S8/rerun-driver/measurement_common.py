"""S6 common utilities, with portable roots and atomic/exclusive receipts."""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIMIT = 3_000_000

def utc():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def load(path):
    return json.loads(Path(path).read_text())

def save(path, obj, exclusive=False):
    path = Path(path)
    data = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode()
    if len(data) >= LIMIT:
        raise ValueError(f'file exceeds limit: {path}')
    fd, tmp = tempfile.mkstemp(prefix='.receipt-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if exclusive:
            os.link(tmp, path)
        else:
            os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def progress(out, message):
    with (out/'progress.md').open('a') as f:
        f.write(f'- {utc()} {message}\n')
        f.flush()
