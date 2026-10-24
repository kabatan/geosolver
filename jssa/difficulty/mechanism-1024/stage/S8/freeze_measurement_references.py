"""Freeze existing independent reference records; never run the geometry solver."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from measurement_common import HERE, load, save, sha, utc
from measurement_exact import expression_key, serial, descriptor_key


def flatten_key(k):
    if k[0] == 'algebraic':
        return ['algebraic', descriptor_key(tuple(k[1]), k[2])]
    if k[0] == 'affine_pi':
        return ['affine_pi', descriptor_key(tuple(k[1]), k[2]), descriptor_key(tuple(k[3]), k[4])]
    raise ValueError(k)


def freeze(repo):
    assert not (HERE/'references.json').exists(), 'references already frozen'
    candidates = defaultdict(list)
    sources = {}
    def record(path, case, keys, field):
        sources[str(path)] = sha(path)
        candidates[case].append(dict(source=str(path), source_sha256=sha(path), field=field,
                                     canonical_set=keys))
    # S4.6/7b's pre-run manifest stores the independently authored reference sets,
    # not the outputs of any ablated solver. Normalize those exact descriptors.
    p = HERE.parents[1]/'run-7b/pre-run-hashes.json'
    for i,r in enumerate(load(p)['inputs']):
        if r['expected_keys']:
            record(p, r['case_id'], serial(flatten_key(json.loads(k)) for k in r['expected_keys']), f'inputs[{i}].expected_keys')
    p = HERE.parent/'S6/run/references.json'
    for k,r in load(p)['cases'].items():
        if r['available']:
            record(p, k, r['canonical_set'], f'cases.{k}')
    p = HERE.parent/'S3/run/pre-run-hashes.json'
    for i,r in enumerate(load(p)['inputs']):
        if r.get('reference_expressions'):
            record(p, r['case_id'], serial(expression_key(x) for x in r['reference_expressions']),f'inputs[{i}].reference_expressions')
    # The S3 cohort is the existing unseen-2 a/b independent, verified case manifests.
    for cohort in ('a','b'):
        p = repo/'jssa/difficulty/unseen-2'/cohort/'cases.jsonl'
        for i,line in enumerate(p.read_text().splitlines()):
            r=json.loads(line)
            if r.get('answer') and r.get('truth_status') == 'verified':
                record(p, r['id'], serial(expression_key(x) for x in r['answer']), f'line {i+1}: answer; truth_status=verified')
    cases={}
    for row in load(HERE/'assignment.json')['problems']:
        k=row['case_id']; cs=candidates[k]
        sets={json.dumps(x['canonical_set'],sort_keys=True) for x in cs}
        available=len(sets)==1
        canonical=cs[0]['canonical_set'] if available else None
        cases[k]=dict(available=available, canonical_set=canonical, provenance=cs,
                      missing_reason=None if available else 'conflicting_existing_references' if sets else 'no_existing_independent_reference',
                      set_sha256=hashlib.sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest())
    doc=dict(created_utc=utc(), cases=cases, sources_sha256=sources,
             method='S6 exact primitive minimal polynomial + ascending real root index; affine-pi coefficients normalized; exact whole-set equality. No new geometry/reference calculation.',
             missing_policy='Keep all 106 assigned cases; absent independent reference => ungradable/null, not a false result. Interrupted runs excluded/null.')
    save(HERE/'references.json',doc,True)
    save(HERE/'references-hashes.json',dict(created_utc=utc(),references_sha256=sha(HERE/'references.json'),normalizer_sha256=sha(HERE/'measurement_exact.py'),sources_sha256=sources),True)
    missing=[k for k,r in cases.items() if not r['available']]
    (HERE/'ungradable-references.md').write_text('# 採点不能の既存参照\n\n'+ ('該当なし。106問全てを既存の独立参照から固定。\n' if not missing else '\n'.join('- '+k+': '+cases[k]['missing_reason'] for k in missing)+'\n'))
    print(json.dumps(dict(cases=len(cases),available=sum(r['available'] for r in cases.values()),missing=missing)))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--repo-root',type=Path,default=HERE.parents[4]);a=p.parse_args();freeze(a.repo_root)
