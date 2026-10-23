"""Read-only integrity check. No engine, geometry evaluation, or execution.

Before sealing: verify internal consistency and the 5 MB bound.
After sealing: also verify every exact locked byte string.
"""
from pathlib import Path
import hashlib
import json
from collect_sources import validate

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
LIMIT=5_000_000

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p): return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def verify():
    manifest=json.loads((HERE/'manifest.json').read_text())
    cases=rows(HERE/'cases.jsonl')
    references=json.loads((HERE/'references.json').read_text())
    mappings=json.loads((HERE/'mapping.json').read_text())
    validation=json.loads((HERE/'audit/validation.json').read_text())
    substitutions=json.loads((HERE/'audit/substitution.json').read_text())
    duplicate=json.loads((HERE/'audit/duplicate-audit.json').read_text())
    scoring=json.loads((HERE/'audit/scoring-contract-check.json').read_text())
    ids=[c['id'] for c in cases]
    assert 15<=len(ids)<=20 and len(ids)==len(set(ids))==manifest['selected_count']
    assert ids==manifest['selected_ids']==[m['id'] for m in mappings]
    assert set(ids)==set(references)=={r['id'] for r in substitutions['cases']}
    assert validation['passed'] and substitutions['passed'] and duplicate['passed'] and scoring['passed']
    assert validation['cases']==len(ids) and validation['solver_run'] is False and validation['imported_engine_modules']==[]
    assert len(manifest['rows'])==480
    assert len(list((HERE/'dsl').glob('*.json')))==len(ids)
    for c in cases:
        assert c['dsl']==json.loads((HERE/c['dsl_path']).read_text())
        assert c['answer']==[references[c['id']]['geometric_value']]
        assert c['dsl']['id']==c['id']
        assert sha(HERE/c['dsl_path'])==next(r['dsl_sha256'] for r in substitutions['cases'] if r['id']==c['id'])
    imports=json.loads((HERE/'source-evidence/import-log.json').read_text())
    assert len(imports)==64 and len(list((HERE/'source-evidence').glob('*.html')))==64
    for r in imports:
        p=HERE/'source-evidence'/r['name']
        assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256']
        validate(r['name'],p.read_bytes())
    source_rows=rows(HERE/'source-evidence/statements.jsonl')
    assert len(source_rows)==len({r['id'] for r in source_rows})==480
    assert not any((HERE/n).exists() for n in ['runs','campaign','results','evaluation'])
    files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    assert all(p.stat().st_size<LIMIT for p in files)
    lockpath=HERE/'prediction.lock.json'
    if lockpath.exists():
        lock=json.loads(lockpath.read_text())
        assert lock['state']=='prediction_fixed_execution_not_authorized'
        assert lock['prediction_sha256']==sha(HERE/'prediction.md')
        for p,h in lock['artifact_sha256'].items(): assert sha(HERE/p)==h,p
        assert [r['id'] for r in lock['adopted_problems']]==ids
        for r in lock['adopted_problems']: assert sha(HERE/r['dsl_path'])==r['dsl_sha256']
        assert lock['execution']['seeds']==[301,302,303,304,305]
        assert lock['execution']['time_limit_seconds']==180 and lock['execution']['cores_per_run']==1
        assert lock['execution']['maximum_parallel_runs']==4
        assert lock['solver_execution_count_in_stage1']==0
    return dict(passed=True,cases=len(cases),source_pages=len(imports),source_problem_sections=len(source_rows),
                checked_files=len(files),largest_file_bytes=max(p.stat().st_size for p in files),
                prediction_locked=lockpath.exists(),solver_run=False)


if __name__=='__main__': print(json.dumps(verify(),ensure_ascii=False,indent=2))
