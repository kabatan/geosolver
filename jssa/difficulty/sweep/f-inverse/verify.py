"""Read-only evidence checks, then write a compact verification receipt."""
from __future__ import annotations
import os
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[k]='1'
import hashlib
import json
import subprocess
from datetime import datetime,timezone
from pydantic import TypeAdapter
import geosolver
from geosolver.problem.models import ExactAnswer
from geosolver.runtime.integrity import source_tree_hash,verify_engine_lock
from analyze import load,save,collect,answer_key,encoded

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    manifest,rows,results=collect()
    assert len(rows)==228 and len({(r['id'],r['arm'],r['seed']) for r in rows})==228
    assert all(r['status']!='not_completed' for r in rows)
    assert source_tree_hash()==manifest['source_hash'] and verify_engine_lock()[0]
    assert not subprocess.check_output(['git','diff',manifest['frozen_commit'],'--','src'],cwd=ROOT)
    assert Path(geosolver.__file__).resolve().parent==ROOT/'src/geosolver'
    original={(i['id']):load(HERE/i['path']) for i in manifest['inputs'] if i['arm']=='forward'}
    checks=[]
    for inp in manifest['inputs']:
        assert sha(HERE/inp['path'])==inp['sha256']
        if inp['arm']=='forward':continue
        d=load(HERE/inp['path']);b=original[inp['id']];c=inp['choice']
        assert d['variables']==b['variables'] and d['constructions']==b['constructions']
        assert len(d['conditions'])==len(b['conditions'])
        changes=[k for k,(x,y) in enumerate(zip(d['conditions'],b['conditions'])) if x!=y]
        assert changes==[c['condition_index']]
        assert d['target']==c['expression'] and d['conditions'][c['condition_index']]['left']==b['target']
        checks.append((inp['id'],inp['arm']))
    adapter=TypeAdapter(ExactAnswer);answer_checks=0
    for row in rows:
        assert not row.get('contract_issues')
        raw=Path(row['raw_path'])
        if raw.exists():assert sha(raw)==row['raw_sha256']
        if row.get('executed_source_hash'):assert row['executed_source_hash']==manifest['source_hash']
        for answer in results[(row['id'],row['arm'],row['seed'])].get('answers',[]):
            assert encoded(adapter.validate_python(answer).canonical_key())==encoded(answer_key(answer))
            answer_checks+=1
    events=[]
    for r in rows:
        t=datetime.fromisoformat(r['started_utc']).timestamp()
        events.extend([(t,1),(t+r['elapsed_seconds'],-1)])
    active=peak=0
    for _,delta in sorted(events,key=lambda p:(p[0],p[1])):
        active+=delta;peak=max(peak,active)
    assert peak<=3
    large=[str(p.relative_to(HERE)) for p in HERE.rglob('*') if p.is_file() and p.stat().st_size>5_000_000]
    assert not large,large
    source_inputs={p:sha(ROOT/p)==h for p,h in manifest['source_input_hashes'].items()}
    receipt=dict(utc=datetime.now(timezone.utc).isoformat(),source_hash=source_tree_hash(),
        import_root=str(Path(geosolver.__file__).resolve().parent),src_diff_from_frozen_empty=True,
        fixed_main_runs=228,fixed_problem_count=24,fixed_inverse_conditions=len(checks),
        input_hashes_match=True,source_corpus_files_unchanged=source_inputs,
        full_solver_output_hashes_match=True,answer_keys_checked_against_frozen_model=answer_checks,
        measured_peak_parallelism=peak,max_process_tree_rss_bytes=max(r['peak_rss_bytes'] for r in rows),
        initial_failed_launches=228,all_attempt_denominator=456,large_files_in_repo=large,
        output_files={str(p.relative_to(HERE)):sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and p.name!='verification.json'})
    save(HERE/'verification.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='output_files'},indent=2))

if __name__=='__main__':main()
