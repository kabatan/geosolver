"""Strict stage-(1)-only I/O and shared serialization. No solve/refinement calls."""
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
S7 = OUT.parent
REPO = S7.parents[4]
FROZEN = Path('/tmp/mech-inv-clean/src')
EXPECTED_SOURCE = 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
READS = set()

def guard(event, args):
    if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    p = Path(os.fsdecode(args[0])).resolve()
    if p.is_relative_to(REPO):
        permitted = p.is_relative_to(OUT)
        if p.is_relative_to(S7):
            rel = p.relative_to(S7)
            permitted |= len(rel.parts) == 1 and (p.suffix == '.py' or p.name in {'classification.csv', 'README.md'})
            permitted |= len(rel.parts) == 2 and rel.parts[0] == 'inputs' and p.suffix == '.json'
            permitted |= len(rel.parts) == 3 and rel.parts[0] == 'results' and p.name in {'reference.json', 'sigma-details.json'}
        if not permitted:
            raise PermissionError('addendum blinding allowlist: ' + str(p))
    mode = args[1]
    flags = args[2]
    writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
    if writing and not p.is_relative_to(OUT) and str(p) != '/dev/null':
        raise PermissionError('addendum output-only guard: ' + str(p))
    if not writing and (p.is_relative_to(REPO) or p.is_relative_to(FROZEN)):
        READS.add(str(p))

sys.addaudithook(guard)
for name in list(os.environ):
    if name.startswith(('GEOSOLVER_ABLATE_', 'GEOSOLVER_S3_')):
        del os.environ[name]
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'
sys.path.insert(0, str(S7))
sys.path.insert(0, str(FROZEN))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

def load(path):
    return json.loads(Path(path).read_text())

def selected():
    with (S7/'classification.csv').open() as f:
        return [r for r in csv.DictReader(f) if r['raw_judgment'] == '特異' or r['base_judgment'] == '特異']

def frozen_check():
    from geosolver.runtime.integrity import source_tree_hash
    assert source_tree_hash() == EXPECTED_SOURCE

def check_manifest():
    manifest = load(OUT/'pre-run-hashes.json')
    for p, digest in manifest['files'].items():
        assert sha(p) == digest, p
    frozen_check()
    return manifest
