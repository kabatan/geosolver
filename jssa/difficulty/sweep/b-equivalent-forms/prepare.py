"""Fix corpus selection and inputs before any new solver execution."""
from __future__ import annotations
import collections
import datetime
import subprocess
from common import *
from transforms import ARMS, applicable, rewrite

POOLS = {'development': ['benchmarks/cases.jsonl'],
         'heldout_origin': ['jssa/difficulty/unseen-2/a/cases.jsonl',
                            'jssa/difficulty/unseen-2/b/cases.jsonl']}
QUOTAS = {'development': {'tangent': 3, 'angle': 3, 'length': 3, 'other': 1},
          'heldout_origin': {'tangent': 0, 'angle': 3, 'length': 4, 'other': 3}}

def main():
    assert not (BASE / 'selection.json').exists(), 'Do not overwrite a fixed selection.'
    runtime = fingerprint()
    diff = subprocess.check_output(['git', 'diff', FROZEN, '--', 'src'], cwd=ROOT)
    assert not diff
    from geosolver.problem.models import GeometryProblem
    from geosolver.problem.validation import validate
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
    selected, audit, pool_hashes = [], [], {}
    for group, paths in POOLS.items():
        eligible = []
        for path in paths:
            data = (ROOT/path).read_bytes(); pool_hashes[path] = sha(data)
            for r in [json.loads(l) for l in data.splitlines() if l.strip()]:
                d = r['dsl']; app = applicable(d)
                stratum = next((s for s in ('tangent','angle','length') if app[s]), 'other')
                reasons = []
                if r.get('truth_status') != 'verified': reasons.append('reference_not_marked_verified')
                if r.get('authoring_status') != 'runnable': reasons.append('not_marked_runnable')
                if not d['variables']: reasons.append('zero_variables')
                if not any(c.get('operator') == '=' for c in d['conditions']): reasons.append('no_equality')
                row = {'id': r['id'], 'pool': group, 'source_file': path,
                       'stratum': stratum, 'rank': rank(r['id']), 'applicable': app,
                       'dsl_hash': sha(d), 'exclusions': reasons}
                audit.append(row)
                if not reasons: eligible.append((row, r))
        for stratum, n in QUOTAS[group].items():
            bucket = sorted((x for x in eligible if x[0]['stratum'] == stratum), key=lambda x: x[0]['rank'])
            assert len(bucket) >= n, (group, stratum, len(bucket), n)
            selected += bucket[:n]
    assert len(selected) == 20 and len({r['id'] for r, _ in selected}) == 20
    rows, jobs, inputs = [], [], {}
    for row, record in selected:
        d = record['dsl']; variants = {}
        for arm in ARMS:
            transformed, changes = rewrite(d, arm)
            problem = GeometryProblem.model_validate(transformed)
            report = validate(problem)
            if not report.valid: raise ValueError((row['id'], arm, report))
            bundle = load_problem_bundle(problem.engine_document())
            entry = {'sha256': sha(transformed), 'changes': changes,
                     'same_as_base': transformed == d, 'variables': list(bundle.var_names),
                     'equalities_after_lowering': len(bundle.spec.constraints),
                     'guards_after_lowering': len(bundle.spec.guards),
                     'search_bounds': infer_problem_bounds(bundle)}
            rel = f'inputs/{row["id"]}/{arm}.json'
            save(BASE/rel, transformed); entry['path'] = rel
            variants[arm] = entry; inputs[rel] = sha((BASE/rel).read_bytes())
            # No-op formula arms are represented by the paired baseline; never
            # fabricate another independent execution or change the denominator.
            if arm != 'base' and transformed == d: entry['alias'] = 'base'
            else:
                for seed in SEEDS:
                    key = f'{row["id"]}__{arm}__s{seed}__t{LIMIT}'
                    jobs.append({'key': key, 'id': row['id'], 'pool': row['pool'],
                                 'stratum': row['stratum'], 'arm': arm, 'seed': seed,
                                 'limit': LIMIT, 'input': rel, 'input_hash': entry['sha256']})
        rows.append({**row, 'reference': record['answer'], 'truth_status': record['truth_status'],
                     'original_variables': d['variables'], 'variants': variants})
    jobs.sort(key=lambda j: rank(j['key'], 'execution_order'))
    save(BASE/'selection-audit.json', {'pool_hashes': pool_hashes, 'rows': audit})
    save(BASE/'selection.json', {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'selection_seed': SELECTION_SEED, 'rank_rule': 'sha256(4302|selection|id), ascending',
         'quotas': QUOTAS, 'runtime': runtime, 'source_git_diff_empty': True,
         'seeds': SEEDS, 'limit': LIMIT, 'max_parallel': 3, 'cases': rows})
    save(BASE/'jobs.json', {'jobs': jobs})
    save(BASE/'input-manifest.json', {'files': inputs, 'selection_sha256': sha((BASE/'selection.json').read_bytes()),
                                     'jobs_sha256': sha((BASE/'jobs.json').read_bytes())})
    print(json.dumps({'cases': len(rows), 'jobs': len(jobs),
                      'worst_wall_hours': len(jobs)*(LIMIT+5)/3/3600,
                      'selected': [{k:r[k] for k in ('id','pool','stratum')} for r in rows]}, indent=2))

if __name__ == '__main__': main()
