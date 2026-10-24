"""Freeze stage (1), select existing verified diagrams without looking at answers."""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from select_targets import OUT, REPO, identity, save, sha

FROZEN = Path('/tmp/mech-inv-clean/src')
SOURCE = 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
sys.dont_write_bytecode = True
sys.path.insert(0, str(FROZEN))
sys.path.insert(1, str(REPO))
from geosolver.runtime.integrity import source_tree_hash, installed_dependencies
from geosolver.application.service import problem_hash
from geosolver.problem.models import GeometryProblem
from benchmarks.research_runner import reference_expressions


def existing_selection(result):
    diag = result.get('diagnostics') or {}
    summary = diag.get('pipeline_summary') or {}
    candidates = diag.get('candidate_records') or []
    witness = next((v for v in summary.get('verification_records', []) if v.get('verified') and v.get('values')), None)
    if witness is None:
        for c in candidates:
            witness = next((v for v in c.get('verification_history', []) if v.get('verified') and v.get('values')), None)
            if witness:
                break
    if witness is None:
        return None
    initial = {}
    for c in candidates:
        s = c.get('source')
        if s and s.get('x_float') is not None:
            initial.setdefault(s.get('candidate_uid', str(s['x_float'])),s['x_float'])
    if not initial:
        # Exact assemblies may retain the source when the final candidate list does not.
        for row in summary.get('exact_candidate_records', []):
            s = row.get('candidate', {}).get('source')
            if s and s.get('x_float') is not None:
                initial.setdefault(s.get('candidate_uid',str(s['x_float'])),s['x_float'])
    return dict(arm='existing_frozen',rank=0,candidate_uid=witness.get('candidate_uid'),
                values=witness['values'],witness=witness,initial_points=list(initial.values()),
                initial_selected_count=summary.get('search',{}).get('selected_candidates'))


def main():
    assert not (OUT/'pre-run-hashes.json').exists()
    assert source_tree_hash() == SOURCE
    selection = json.loads((OUT/'targets.json').read_text())
    targets = selection['targets']
    records = {}
    files = {OUT/'targets.json', OUT/'selection-audit.json', OUT.parent/'S3/contacts.json',
             OUT.parent/'S3/preregistration-12.md', OUT.parent/'S4/prepare.py',
             OUT.parent/'S4/worker.py', OUT.parent/'S4/sigma_min.py', OUT.parent/'S4/pre-run-hashes.json',
             REPO/'benchmarks/research_runner.py'} | set(OUT.glob('*.py')) | {OUT/'README.md'}
    for root in ['benchmarks','jssa/difficulty/unseen-2/a','jssa/difficulty/unseen-2/b',
                 'jssa/difficulty/unseen-1983','jssa/difficulty/new2026']:
        p = REPO/root/'cases.jsonl'; files.add(p)
        for row in map(json.loads,p.read_text().splitlines()):
            records.setdefault(identity(row['id']),row)
    # Search only persisted per-run public solve results, lexical order; source and exact
    # GeometryProblem hash must match. No target-value/digit selection, no S3/S5 results.
    paths = subprocess.check_output(['rg','--files','jssa/difficulty'],cwd=REPO,text=True).splitlines()
    by_id = {t['case_id']:t for t in targets}
    expected = {t['case_id']:problem_hash(GeometryProblem.model_validate_json((REPO/t['dsl_path']).read_text())) for t in targets}
    found, inspected = {}, []
    for rel in sorted(paths):
        p = Path(rel)
        if '/runs/' not in rel or p.suffix != '.json' or p.parent.name not in by_id or '/stage/S3/' in rel or '/stage/S5/' in rel:
            continue
        key = p.parent.name
        if key in found:
            continue
        try:
            raw = json.loads((REPO/p).read_text())
            result = raw.get('solver_result',raw)
            if not isinstance(result,dict): continue
            if result.get('engine',{}).get('source_hash') != SOURCE or result.get('problem_hash') != expected[key]: continue
            # Recorded altered modes/ablations are not ordinary frozen solve results.
            if raw.get('execution_contract_issues'): continue
            selected = existing_selection(result)
            inspected.append(dict(path=rel,sha256=sha(REPO/p),case_id=key,has_verified_diagram=selected is not None))
            if selected is not None:
                found[key] = selected | dict(origin=rel,origin_sha256=sha(REPO/p),problem_hash=expected[key])
                files.add(REPO/p)
        except (ValueError,AttributeError,TypeError):
            continue
    (OUT/'inputs').mkdir(exist_ok=True)
    items = []
    for t in targets:
        p = REPO/t['dsl_path']; assert sha(p) == t['sha256'];files.add(p)
        row = records.get(identity(t['case_id']))
        refs = [] if row is None else row.get('answer',[])
        refs = refs if isinstance(refs,list) else [refs]
        expressions, ref_error = [], None
        try:
            expressions = [e for r in refs for e in reference_expressions(str(r))]
        except Exception as e:
            ref_error = repr(e)
        item = dict(case_id=t['case_id'],dsl=json.loads(p.read_text()),dsl_path=t['dsl_path'],
            selection=found.get(t['case_id']),reference_expressions=expressions,reference_parse_error=ref_error)
        ip = OUT/'inputs'/(t['case_id']+'.json');save(ip,item);files.add(ip)
        items.append(dict(case_id=t['case_id'],input=str(ip),existing_diagram=item['selection'] is not None))
    save(OUT/'diagram-selection-audit.json',dict(rule='lexical persisted runs; exact source/problem hash; first verified diagram, no answer selection',inspected=inspected))
    files.add(OUT/'diagram-selection-audit.json')
    source_files = {str(p):sha(p) for p in sorted(FROZEN.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    save(OUT/'pre-run-hashes.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),
        frozen_commit='60db4b6',frozen_source=str(FROZEN),source_hash=SOURCE,
        python=sys.executable,python_version=sys.version,dependencies=installed_dependencies(),
        cpus=sorted(os.sched_getaffinity(0))[:8],parallel=min(8,len(os.sched_getaffinity(0))),
        threads={k:'1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS']},
        per_problem_seconds=600,solve_seconds=180,reference_closure_seconds=180,
        solve_seed=0,solve_retries=0,reference_dps=620,reference_agreement_digits=300,
        jacobian_dps=200,step_exponents=[70,60],comparison_stage_2_executed=False,
        source_files=source_files,files={str(p):sha(p) for p in sorted(files)},items=items))
    print('Frozen:',len(items),'problems;',len(found),'existing verified diagrams;',len(items)-len(found),'single fresh solves required')

if __name__ == '__main__': main()
