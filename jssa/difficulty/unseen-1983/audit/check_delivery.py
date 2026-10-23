"""Check final audit rows, citations, hashes and sizes. No solver/results access."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import re

HERE=Path(__file__).resolve().parent
BASE=HERE.parent

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    with (HERE/'audit.csv').open(newline='') as f:
        rows=list(csv.DictReader(f))
    with (HERE/'exclusions.csv').open(newline='') as f:
        exclusions=list(csv.DictReader(f))
    summary=json.loads((HERE/'summary.json').read_text())
    selected={r['id'] for r in map(json.loads,(BASE/'cases.jsonl').read_text().splitlines())}
    assert len(rows)==len({r['id'] for r in rows})==54
    assert {r['id'] for r in rows}==selected
    assert Counter(r['verdict'] for r in rows)==summary['verdict_counts']
    assert {r['id'] for r in exclusions}=={r['id'] for r in rows if r['verdict']=='除外候補'}
    assert len(exclusions)==27
    assert all(r['solver_results_seen']=='False' and r['solver_run']=='False' and r['ast_ok']=='True' for r in rows)
    for r in rows:
        assert sha(HERE/r['dsl_file'])==r['dsl_sha256']
        for kind in ['statement','answer']:
            path=r[f'primary_{kind}_file']
            if path:
                assert sha(HERE/path)==r[f'primary_{kind}_sha256']
        if r['verdict']=='合格':
            assert r['primary_statement_file'] and r['primary_answer_file']
        if r['proposed_fix']:
            assert (HERE/r['proposed_fix']).is_file()
    snapshot=json.loads((HERE/'input-snapshot.json').read_text())
    assert not any(p.startswith('sealed/') for p in snapshot)
    changed=[p for p,h in snapshot.items() if sha(BASE/p)!=h]
    assert changed==[],changed
    text=(HERE/'audit.md').read_text()
    assert len(re.findall(r'^### (?:AIME|HMMT)-',text,re.M))==54
    broken=[]
    for link in re.findall(r'\]\(([^)]+)\)',text):
        if link.startswith(('http://','https://','#')) or link=='delivery-checks.json':
            continue
        if not (HERE/link).exists():
            broken.append(link)
    assert not broken,broken
    artifacts={}
    for p in sorted(HERE.rglob('*')):
        rel=p.relative_to(HERE)
        if p.is_file() and rel.parts[0]!='primary' and str(rel)!='delivery-checks.json':
            assert p.stat().st_size<20*1024*1024,p
            artifacts[str(rel)]={'sha256':sha(p),'bytes':p.stat().st_size}
    output=dict(passed=True,case_count=54,verdict_counts=dict(Counter(r['verdict'] for r in rows)),
                exclusions_count=27,primary_answer_count=sum(bool(r['primary_answer']) for r in rows),
                original_files_checked=len(snapshot),original_files_changed=changed,
                markdown_case_sections=54,broken_local_links=broken,
                maximum_artifact_bytes=max(v['bytes'] for v in artifacts.values()),
                total_artifact_bytes_excluding_primary_and_this_receipt=sum(v['bytes'] for v in artifacts.values()),
                artifacts=artifacts,solver_run=False,local_search_run=False,solver_results_seen=False,
                network_used=False,git_commit=False,git_push=False)
    (HERE/'delivery-checks.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k!='artifacts'},ensure_ascii=False))

if __name__=='__main__':
    main()
