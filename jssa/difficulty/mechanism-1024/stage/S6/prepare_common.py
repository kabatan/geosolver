"""S6 preparation utilities. Standard library only; never import/run the solver."""
import hashlib
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[4]
STAGE = OUT.parent
IMPL = Path('/tmp/s3-impl/src/geosolver')
EXPECTED_SOURCE_HASH = 'sha256:add5afaf829806ca3cbd11fb07b69d956102752e1c6738b0630581a3ceb121eb'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                     allow_nan=False) + '\n')


def identity(key):
    # Same identity and representative policy as S5/select_targets.py.
    key = re.sub(r'\.k\d+$', '', key).upper()
    parts = key.split('-')
    if parts[0] == 'AIME' and len(parts) == 4:
        parts[2] = {'1': 'I', '2': 'II'}.get(parts[2], parts[2])
    return '-'.join(str(int(p)) if p.isdigit() else p for p in parts)


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
    actual = 'sha256:' + digest.hexdigest()
    assert actual == EXPECTED_SOURCE_HASH, (actual, EXPECTED_SOURCE_HASH)
    return dict(root=str(IMPL), source_hash=actual, files_sha256=entries,
                algorithm='runtime/integrity.py source_tree_hash: sorted relative path + NUL + LF-normalized bytes + NUL; .py/.json/.toml; exclude engine-lock.json, frontend, __pycache__')
