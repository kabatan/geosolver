"""Freeze existing independent answer sets; no solving, coordinates, or numerical derivation."""
import ast
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from measurement_common import HERE,load,save,sha,utc
from measurement_exact import expression_key,serial,descriptor_key


def freeze(repo):
    assert not (HERE/'references.json').exists(),'references already frozen'
    sys.path.insert(0,str(repo))
    from benchmarks.research_runner import reference_expressions
    selected={r['case_id']:r for r in load(HERE/'assignment.json')['problems']}
    candidates=defaultdict(list);rejected=defaultdict(list);sources={}
    def source(path):
        sources[str(path)]=sha(path)
        return load(path)
    def record(path,k,canonical,field,**extra):
        if k not in selected:return
        candidates[k].append(dict(source=str(path),source_sha256=sources[str(path)],field=field,canonical_set=canonical,**extra))
    def expressions(path,k,values,field,**extra):
        if k not in selected or not values:return
        try:
            exprs=[e for v in values for e in reference_expressions(str(v))]
            # Decimal approximations must never become exact rational references.
            if any(isinstance(n,ast.Constant) and isinstance(n.value,float) for e in exprs for n in ast.walk(ast.parse(e,mode='eval'))):
                raise ValueError('approximate decimal reference, no independent exact descriptor')
            keys=serial(expression_key(e) for e in exprs)
            record(path,k,keys,field,expressions=exprs,original_values=values,**extra)
        except Exception as e:rejected[k].append(dict(source=str(path),field=field,reason=f'{type(e).__name__}: {e}'))
    # Existing S6 normalized exact sets; no new normalization needed.
    path=HERE.parents[1]/'S6/run/references.json'
    for k,r in source(path)['cases'].items():
        if r['available']:record(path,k,r['canonical_set'],f'cases.{k}.canonical_set')
    path=HERE.parents[2]/'run-7b/pre-run-hashes.json'
    for i,r in enumerate(source(path)['inputs']):
        if r['case_id'] not in selected or not r.get('expected_keys'):continue
        if r['sha256']!=selected[r['case_id']]['input_sha256']:
            rejected[r['case_id']].append(dict(source=str(path),reason='input_hash_mismatch'));continue
        def flatten(text):
            k=json.loads(text)
            if k[0]=='algebraic':return ['algebraic',descriptor_key(tuple(k[1]),k[2])]
            if k[0]=='affine_pi':return ['affine_pi',descriptor_key(tuple(k[1]),k[2]),descriptor_key(tuple(k[3]),k[4])]
            raise ValueError(k)
        record(path,r['case_id'],serial(flatten(k) for k in r['expected_keys']),f'inputs[{i}].expected_keys')
    for path in [HERE.parents[1]/'S3/run/pre-run-hashes.json',Path('/tmp/mechanism-S1-1m9aomj8/manifest.json')]:
        if not path.is_file():continue
        for i,r in enumerate(source(path)['inputs']):
            k=r['case_id']
            if k not in selected:continue
            if r.get('sha256') and r['sha256']!=selected[k]['input_sha256']:
                rejected[k].append(dict(source=str(path),reason='input_hash_mismatch'));continue
            expressions(path,k,r.get('reference_expressions'),f'inputs[{i}].reference_expressions')
    # Corpus answer is the independent official/source-audited set used by S1/7b,
    # not a solver result. Legacy rows default to verified in research_runner._load_cases.
    path=repo/'benchmarks/cases.jsonl';sources[str(path)]=sha(path)
    for i,line in enumerate(path.read_text().splitlines()):
        r=json.loads(line);k=r['id']
        if k not in selected:continue
        if r.get('truth_status','verified')!='verified':
            rejected[k].append(dict(source=str(path),reason='truth_status_not_verified'));continue
        values=r.get('answer',[]);values=values if isinstance(values,list) else [values]
        expressions(path,k,values,f'line {i+1}.answer',truth_status=r.get('truth_status','legacy_verified_default'),
            truth_basis=r.get('truth_basis',r.get('source')),input_sha256=selected[k]['input_sha256'])
    sources[str(repo/'benchmarks/research_runner.py')]=sha(repo/'benchmarks/research_runner.py')
    cases={}
    for k,row in selected.items():
        cs=candidates[k];sets={json.dumps(c['canonical_set'],sort_keys=True) for c in cs};available=len(sets)==1
        canonical=cs[0]['canonical_set'] if available else None
        cases[k]=dict(available=available,canonical_set=canonical,provenance=cs,rejected_candidates=rejected[k],
            input_sha256=row['input_sha256'],main_cause=row['main_cause'],
            missing_reason=None if available else 'conflicting_existing_references' if sets else 'no_existing_independent_exact_reference',
            set_sha256=hashlib.sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest())
    save(HERE/'references.json',dict(created_utc=utc(),cases=cases,sources_sha256=sources,
        method='S8 exact primitive minimal polynomial and ascending real-root index; existing official/source-audited answers only, notation normalization only; no new reference solving. Reject decimal approximations.',
        missing_policy='Keep all 64 cases and 768 jobs. Absent/conflicting exact reference => ok/solved/C null, never failure/180.'),True)
    save(HERE/'references-hashes.json',dict(references_sha256=sha(HERE/'references.json'),normalizer_sha256=sha(HERE/'measurement_exact.py'),
        freezer_sha256=sha(HERE/'freeze_measurement_references.py'),sources_sha256=sources),True)
    missing=[k for k,r in cases.items() if not r['available']]
    save(HERE/'ungradable-references.json',dict(count=len(missing),cases=[dict(case_id=k,reason=cases[k]['missing_reason'],rejected_candidates=cases[k]['rejected_candidates']) for k in missing]),True)
    (HERE/'ungradable-references.md').write_text('# 採点不能の独立参照\n\n'+ ('該当なし。\n' if not missing else '\n'.join('- '+k+': '+cases[k]['missing_reason'] for k in missing)+'\n'))
    print(json.dumps(dict(cases=len(cases),available=sum(r['available'] for r in cases.values()),missing=missing),ensure_ascii=False))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--repo-root',type=Path,default=HERE.parents[5]);freeze(p.parse_args().repo_root.resolve())
