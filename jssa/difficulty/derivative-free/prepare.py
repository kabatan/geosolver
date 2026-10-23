"""Select cases and seal answer-free search inputs; no optimization is run."""
import csv
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
FROZEN = '60db4b679b04167175c51c479c87c22fa663fda0'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(path, data):
    text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    assert len(text.encode()) < 5_000_000
    path.write_text(text)

def main():
    assert not (OUT / 'prediction.lock.json').exists()
    subprocess.run(['git', 'diff', '--exit-code', FROZEN, '--', 'src'], cwd=ROOT, check=True, capture_output=True)
    old = list(csv.DictReader((ROOT / 'jssa/strategy/astra-consult-18/Q27f/selected-case-validation.csv').open()))
    hard = sorted(r['id'] for r in old if r['p2_qualifies'] == 'True')
    assert len(hard) == 21
    census = list(csv.DictReader((ROOT / 'jssa/strategy/astra-consult-18/Q27d/census-both-seeds.csv').open()))
    controls = []
    for d in range(1, 8):
        pool = [r for r in census if int(r['d']) == d and r['id'] not in hard and int(r['m']) >= d]
        pool.sort(key=lambda r: (-min(float(r['p']), float(r['p1'])), hashlib.sha256(r['id'].encode()).hexdigest()))
        controls.append(pool[0]['id'])
    lookup = {r['id']: r for r in census}
    cases = {c['id']: c for c in map(json.loads, (ROOT/'benchmarks/cases.jsonl').read_text().splitlines())}
    (OUT/'inputs').mkdir(exist_ok=True)
    (OUT/'grading').mkdir(exist_ok=True)
    selected = []
    for case_id in hard + controls:
        case = cases[case_id]
        doc = GeometryProblem.model_validate(case['dsl']).engine_document()
        bundle = load_problem_bundle(doc)
        bounds = np.asarray(infer_problem_bounds(bundle), dtype=float)
        assert np.all(np.isfinite(bounds)) and np.all(bounds[:,1] > bounds[:,0])
        starts = []
        identity = int.from_bytes(hashlib.sha256(case_id.encode()).digest()[:4], 'little')
        for seed in [32001, 32002]:
            rng = np.random.default_rng(np.random.SeedSequence([seed, identity]))
            for k in range(8):
                x = bounds[:,0] + rng.random(len(bounds)) * (bounds[:,1] - bounds[:,0])
                starts.append({'seed': seed, 'k': k, 'x': x.tolist()})
        # The optimizer gets DSL and starts only; references stay in a separate path.
        dump(OUT/'inputs'/f'{case_id}.json', {'id': case_id, 'dsl': case['dsl'], 'bounds': bounds.tolist(), 'var_names': list(bundle.var_names), 'starts': starts})
        dump(OUT/'grading'/f'{case_id}.json', {'id':case_id, 'answer':case['answer']})
        r = lookup[case_id]
        selected.append({'id':case_id,'group':'hard' if case_id in hard else 'control','n_vars':len(bounds),'n_constraints':len(bundle.spec.constraints),'historical_method':'Powell' if len(bounds)>len(bundle.spec.constraints) else 'LM','p0':float(r['p']),'p1':float(r['p1']),'input_sha256':sha(OUT/'inputs'/f'{case_id}.json')})
    dump(OUT/'selection.json', selected)
    with (OUT/'selection.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(selected[0])); w.writeheader(); w.writerows(selected)
    paths = subprocess.check_output(['git','ls-files','src'],cwd=ROOT,text=True).splitlines()
    dump(OUT/'source-manifest.json', {'commit': FROZEN, 'files': {p: sha(ROOT/p) for p in paths}, 'src_diff_from_commit':False})
    print(json.dumps({'hard':len(hard),'controls':controls,'historical_powell':[r['id'] for r in selected if r['historical_method']=='Powell'],'starts_per_case':16}, ensure_ascii=False))

if __name__ == '__main__':
    main()
