"""Exactly the preregistration-13 union. Reads JSON/text; no solver imports."""
import ast
import json
from pathlib import Path
from prepare_common import OUT, REPO, STAGE, identity, save, sha


def main():
    contacts_path = STAGE / 'S3/contacts.json'
    s5_path = STAGE / 'S5/targets.json'
    contacts = json.loads(contacts_path.read_text())['cases']
    s5 = json.loads(s5_path.read_text())['targets']
    assert len(contacts) == 12 and len(s5) == 32
    scanned, development = {}, {}
    for p in sorted((REPO / 'benchmarks/dsl').rglob('*.json')):
        relative = str(p.relative_to(REPO))
        scanned[relative] = sha(p)
        d = json.loads(p.read_text())
        if not isinstance(d, dict) or 'constructions' not in d:
            continue
        has_token = 'IsTangent' in p.read_text()
        rows = []
        for index, condition in enumerate(d['conditions']):
            if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == 'IsTangent'
                   for k in ('left', 'right', 'predicate') if k in condition
                   for n in ast.walk(ast.parse(str(condition[k]), mode='eval'))):
                rows.append(index)
        if has_token:
            assert rows, f'IsTangent outside conditions: {relative}'
            development.setdefault(identity(d['id']), []).append(dict(
                path=relative, dsl_id=d['id'], sha256=sha(p), condition_indices=rows))
    assert sum(map(len, development.values())) == 24
    targets = {}
    for c in contacts:
        key = identity(c['case_id'])
        occurrences = development[key]
        matching = [o for o in occurrences if o['sha256'] == c['input_sha256']]
        assert len(matching) == 1
        chosen = matching[0]
        targets[key] = dict(case_id=c['case_id'], identity=key,
                            dsl_path=chosen['path'], sha256=chosen['sha256'],
                            memberships=['S3/contacts.json'], occurrences=list(occurrences))
    for t in s5:
        key = identity(t['case_id'])
        assert key not in targets  # S5 excluded the fixed S1/S3 twelve.
        assert sha(REPO / t['dsl_path']) == t['sha256']
        targets[key] = dict(case_id=t['case_id'], identity=key,
                            dsl_path=t['dsl_path'], sha256=t['sha256'],
                            memberships=['S5/targets.json'], occurrences=t['occurrences'])
    remaining = []
    for key, occurrences in sorted(development.items()):
        if key not in targets:
            chosen = occurrences[0]
            targets[key] = dict(case_id=chosen['dsl_id'], identity=key,
                                dsl_path=chosen['path'], sha256=chosen['sha256'],
                                memberships=[], occurrences=occurrences)
            remaining.append(key)
        targets[key]['memberships'].append('benchmarks/dsl:IsTangent')
    for t in targets.values():
        for o in t['occurrences']:
            assert sha(REPO / o['path']) == o['sha256']
        assert sha(REPO / t['dsl_path']) == t['sha256']
    save('targets.json', dict(stage='S6 preparation only', target_count=len(targets),
         selection='union(S3 contacts 12, S5 targets 32, benchmarks/dsl IsTangent 24); no outcome-based additions/exclusions',
         deduplication='S5 identity normalization; prefer S3 exact input hash, then S5 representative, then lexical development path',
         source_counts=dict(S3=12, S5=32, development_IsTangent_files=24,
                            development_remaining=len(remaining)),
         development_remaining_identities=remaining,
         selection_script_sha256=sha(Path(__file__)),
         source_files_sha256={str(p.relative_to(REPO)): sha(p) for p in
             [contacts_path, s5_path, STAGE / 'S5/select_targets.py',
              STAGE / 'S3/preregistration-13.md']},
         targets=[targets[k] for k in sorted(targets)]))
    save('selection-audit.json', dict(scanned_development_files_sha256=scanned,
         development_IsTangent=development, selected_identities=sorted(targets),
         exclusions=[], solver_executed=False))
    print(f'S6 selected {len(targets)} unique problems; development remainder {len(remaining)}')


if __name__ == '__main__':
    main()
