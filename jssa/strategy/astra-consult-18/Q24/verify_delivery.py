"""Read-only consistency/hash checks; --write records a Q24-only receipt."""
import argparse
import ast
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from static_features import features, predict

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def rows(name):return list(csv.DictReader((OUT/name).open()))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--write',action='store_true');args=ap.parse_args()
    checked={}
    for name in ('rule-lock.json','prediction-lock.json'):
        lock=json.loads((OUT/name).read_text())
        for f,info in lock['files'].items():assert sha(OUT/f)==info['sha256'],f
        checked[name]=len(lock['files'])
    core=(OUT/'preregistration-core.md').read_bytes()
    assert (OUT/'preregistration.md').read_bytes().startswith(core)
    man=json.loads((OUT/'unseen26-input-manifest.json').read_text())
    assert sha(ROOT/man['audit']['path'])==man['audit']['sha256']
    predictions=rows('unseen26-predictions.csv')
    assert len(predictions)==26
    by_id={r['id']:r for r in predictions};assert len(by_id)==26
    for rec in man['inputs']:
        p=ROOT/rec['path'];assert sha(p)==rec['sha256']
        dsl=json.loads(p.read_text());f=features(dsl);pred=predict(f,'R1_mechanism')
        row=by_id[rec['id']]
        for key,value in f.items():
            if isinstance(value,(list,dict)):assert json.loads(row[key])==value,(rec['id'],key)
            else:assert row[key]==str(value),(rec['id'],key)
        for key,value in pred.items():assert row[key]==value,(rec['id'],key)
        assert row['full_solver_secondary']==pred['local']
        assert row['dsl_sha256']==rec['sha256']
    summary=json.loads((OUT/'unseen26-summary.json').read_text())
    for key in ('local','exact','direction','full_solver_secondary'):
        assert dict(Counter(r[key] for r in predictions))==summary[key]
    dev=rows('development.csv');ps=rows('development-predictions-all.csv')
    assert len(dev)==323 and len(ps)==969
    assert len({(r['id'],r['rule']) for r in ps})==969
    assert not {r['id'] for r in dev}.intersection(by_id)
    assert sum(int(r['n_starts']) for r in dev)==55097
    assert sum(int(r['hits']) for r in dev)==31851
    expected=[r for r in ps if (r['local_judged']=='True' and r['local_correct']=='False') or (r['exact_judged']=='True' and r['exact_correct']=='False')]
    assert expected==rows('development-errors-all.csv')
    assert len([r for r in expected if r['rule']=='R1_mechanism'])==115
    src=rows('source-msolve-cases.csv');nonmatch=[r for r in src if r['msolve_class']!='answer_set_matches']
    assert len(nonmatch)==122 and sum(int(r['geo_matched'])>0 for r in nonmatch)==121
    source_audit=json.loads((OUT/'source-audit.json').read_text())
    for filename,expected_blob in [('source-msolve-cases.csv',source_audit['recorded_git_blob_sha1']),('source-msolve-README.md',source_audit['README_verification']['recorded_git_blob_sha1'])]:
        b=(OUT/filename).read_bytes();actual=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();assert actual==expected_blob
    relative_links=0
    for p in OUT.glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if '://' in target or target.startswith('#'):continue
            assert (p.parent/target.split('#')[0]).exists(),(p.name,target)
            relative_links+=1
    pyfiles=list(OUT.glob('*.py'))
    allowed={'ast','argparse','collections','copy','csv','datetime','functools','hashlib','io','json','math','pathlib','re','statistics','time','static_features'}
    for p in pyfiles:
        tree=ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):assert all(x.name.split('.')[0] in allowed for x in n.names),p.name
            elif isinstance(n,ast.ImportFrom):assert n.module.split('.')[0] in allowed,p.name
            elif isinstance(n,ast.Call) and isinstance(n.func,ast.Name):assert n.func.id not in {'eval','exec','compile','__import__'},p.name
    files=[p for p in OUT.iterdir() if p.is_file()]
    assert max(p.stat().st_size for p in files)<10_000_000
    if (OUT/'SHA256SUMS').exists():
        for line in (OUT/'SHA256SUMS').read_text().splitlines():
            expected_hash,name=line.split('  ',1);assert sha(OUT/name)==expected_hash,name
    report={'status':'PASS','frozen_hash_checks':checked,'core_preserved':True,
            'unseen_input_hashes_and_AST_predictions':26,'unseen_result_data_used':False,
            'development_cases':323,'all_candidate_prediction_rows':969,'R1_error_rows':115,
            'raw_start_total':55097,'raw_hit_total':31851,'source121of122_recount':True,
            'source_CSV_and_README_blob_hashes':True,'relative_markdown_links_checked':relative_links,
            'python_AST_and_import_audit_files':len(pyfiles),'no_individual_file_over_10MB':True}
    if args.write:(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
