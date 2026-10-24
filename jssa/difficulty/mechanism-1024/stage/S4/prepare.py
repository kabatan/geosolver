"""Freeze inputs and code before any S4 numerical measurements."""
import hashlib
import json
import os
import pickle
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[4]
FROZEN = Path('/tmp/mech-inv-clean/src')
FINAL = Path('/tmp/mechanism-7b-lkdjle5l/final/src')
sys.dont_write_bytecode = True
sys.path.insert(0, str(FROZEN))
from geosolver.runtime.integrity import source_tree_hash

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

assert not (OUT / 'pre-run-hashes.json').exists()
root = Path(tempfile.mkdtemp(prefix='mechanism-S4-'))
s1 = OUT.parent / 'S1'
old = json.loads((s1 / 'pre-run-hashes.json').read_text())
files = {p for p in OUT.glob('*.py')} | {OUT / 'rules.md', OUT.parent / 'S3/preregistration-11.md',
    s1 / 'pre-run-hashes.json', s1 / 'per-problem.csv', s1 / 'rules.md', s1 / 'prepare.py',
    s1 / 'worker.py', s1 / 'repair_references.py', OUT.parent / 'S2/worker.py',
    REPO / 'benchmarks/cases.jsonl', REPO / 'benchmarks/research_runner.py'}
files.update(p for p in (REPO / 'jssa/results/tangency-signed').rglob('*') if p.is_file())
items = []
for task in old['inputs']:
    k = task['case_id']
    directory = Path(old['scratch']) / 'runs' / k
    selection = None
    for arm in ['BASE', 'NO_RESIDUAL_REWRITE']:
        vp = directory / (arm + '.verification.json')
        files.add(vp)
        result = json.loads(vp.read_text())
        witness = next((r for r in result['rows'] if r['final_pass']), None)
        if selection is None and witness:
            pp = directory / (arm + '.refined.pkl')
            files.add(pp)
            candidates = pickle.loads(pp.read_bytes())
            candidate = candidates[witness['rank']]
            assert candidate.candidate_uid == witness['candidate_uid']
            from mpmath import mp
            selection = dict(arm=arm, rank=witness['rank'], candidate_uid=candidate.candidate_uid,
                values=[mp.nstr(v, 710) for v in candidate.x_hp], witness=witness)
    source = Path(task['input_copy'])
    files.update([source, Path(task['dsl_path'])])
    assert sha(source) == task['sha256'] == sha(Path(task['dsl_path']))
    item = dict(case_id=k, dsl=json.loads(source.read_text()), selection=selection,
                reference_expressions=task['reference_expressions'])
    ip = root / (k + '.input.json')
    ip.write_text(json.dumps(item, ensure_ascii=False, indent=2)+'\n')
    files.add(ip)
    items.append(dict(case_id=k, input=str(ip), selected=None if selection is None else
                      {a:selection[a] for a in ['arm','rank','candidate_uid']}))
manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), scratch=str(root),
    frozen_source=str(FROZEN), final_source=str(FINAL), source_hash=source_tree_hash(),
    source_files={str(p):sha(p) for src in [FROZEN,FINAL] for p in sorted(src.rglob('*'))
                  if p.is_file() and '__pycache__' not in p.parts},
    files={str(p):sha(p) for p in sorted(files)}, items=items, python=sys.executable,
    cpus=sorted(os.sched_getaffinity(0))[:2], parallel=2,
    threads={k:'1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']})
assert manifest['source_hash']=='sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
(OUT / 'pre-run-hashes.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
print(root)
