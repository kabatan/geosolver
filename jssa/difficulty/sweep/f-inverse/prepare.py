"""Q43f: outcome-blind input selection and inverse construction, no solving."""
from __future__ import annotations
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[key] = '1'
import sympy as sp
import geosolver
from geosolver import GeometryProblem, validate
from geosolver.exact import describe_exact
from geosolver.runtime.integrity import source_tree_hash, verify_engine_lock

FROZEN = '60db4b679b04167175c51c479c87c22fa663fda0'
HASH = 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
SELECT_SEED = 20261024
SOLVER_SEEDS = [0, 1, 2]
LIMIT_SECONDS = 90
SOURCES = [('development', 'benchmarks/cases.jsonl', 12),
           ('unseen_a', 'jssa/difficulty/unseen-2/a/cases.jsonl', 6),
           ('unseen_b', 'jssa/difficulty/unseen-2/b/cases.jsonl', 6)]

def sha(data):
    return hashlib.sha256(data).hexdigest()

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + '\n')

def names(expr):
    return {n.id for n in ast.walk(ast.parse(str(expr), mode='eval')) if isinstance(n, ast.Name)}

def normalize(expr):
    s = str(expr).replace('−', '-').replace('π', 'pi')
    s = re.sub(r'\\sqrt\{([^}]*)\}', r'sqrt(\1)', s)
    s = re.sub(r'√(\d+)', r'sqrt(\1)', s)
    s = re.sub(r'(?<=\d)(?=sqrt\(|pi\b|\()', '*', s)
    return str(sp.sympify(s))

def constant(expr):
    if names(expr) - {'pi', 'sqrt'}:
        return None
    try:
        value = sp.sympify(str(expr))
        if value.free_symbols or value.is_real is not True or value == 0:
            return None
        return str(value)
    except Exception:
        return None

def choices(dsl):
    # Transitive syntactic dependence excludes values already built into fixed points.
    deps = {str(v): {str(v)} for v in dsl['variables']}
    for c in dsl['constructions']:
        deps[c['name']] = set().union(*(deps.get(n, set()) for n in names(c['expression'])))
    out = []
    for i, row in enumerate(dsl['conditions']):
        if row.get('operator') != '=':
            continue
        for fixed, varying in [('right', 'left'), ('left', 'right')]:
            value = constant(row[fixed])
            if value is None:
                continue
            dep = set().union(*(deps.get(n, set()) for n in names(row[varying])))
            if not dep:
                continue
            expression = str(row[varying])
            category = ('angle' if 'Angle(' in expression else 'area' if 'Area(' in expression
                        else 'ratio' if '/' in expression else 'length' if 'Distance(' in expression else 'scalar')
            out.append(dict(condition_index=i, varying_side=varying, expression=expression,
                            given=value, dependencies=sorted(dep), category=category))
    return out

def rank(group, identifier, suffix=''):
    return sha(f'{SELECT_SEED}:{group}:{identifier}{suffix}'.encode())

def prepare():
    assert not (HERE / 'manifest.json').exists(), 'inputs already fixed; do not overwrite'
    assert subprocess.check_output(['git', 'diff', FROZEN, '--', 'src'], cwd=ROOT) == b''
    assert Path(geosolver.__file__).resolve().parent == ROOT / 'src/geosolver'
    assert source_tree_hash() == HASH and verify_engine_lock()[0]
    selected, audit, inputs, source_hashes = [], [], [], {}
    for group, source, count in SOURCES:
        data = (ROOT / source).read_bytes()
        source_hashes[source] = sha(data)
        eligible = []
        for case in map(json.loads, data.decode().splitlines()):
            opts = choices(case['dsl'])
            refs = case.get('answer')
            refs = refs if isinstance(refs, list) else [refs]
            reason = None
            try:
                if len(refs) != 1:
                    raise ValueError('requires_single_reference')
                ref = normalize(refs[0])
                describe_exact(ref)
                if names(ref) - {'pi', 'sqrt'}:
                    raise ValueError('reference_not_elementary_DSL')
            except Exception as exc:
                reason = str(exc)
            if not opts:
                reason = 'no_variable_dependent_nonzero_numeric_equality'
            item = dict(group=group, id=case['id'], rank=rank(group, case['id']),
                        eligible=reason is None, reason=reason, n_choices=len(opts))
            audit.append(item)
            if reason is None:
                eligible.append((item['rank'], case, opts, ref))
        assert len(eligible) >= count, (group, len(eligible))
        for _, case, opts, ref in sorted(eligible, key=lambda x: x[0])[:count]:
            opts = sorted(opts, key=lambda c: rank(group, case['id'], f':condition:{c["condition_index"]}'))[:4]
            case_info = dict(id=case['id'], group=group, source=source, original_answer=ref,
                             original_target=case['dsl']['target'], n_variables=len(case['dsl']['variables']),
                             choices=opts, problem_statement=case.get('problem_statement'))
            selected.append(case_info)
            arms = [('forward', copy.deepcopy(case['dsl']), ref, None)]
            for option in opts:
                inverse = copy.deepcopy(case['dsl'])
                idx = option['condition_index']
                inverse['conditions'][idx] = dict(left=case['dsl']['target'], operator='=', right=ref)
                inverse['target'] = option['expression']
                arms.append((f'inverse-{idx:02}', inverse, option['given'], option))
            for arm, dsl, refvalue, option in arms:
                # No bound, positivity, branch, or nondegeneracy condition is removed.
                report = validate(GeometryProblem.model_validate(dsl))
                if not report.valid:
                    raise ValueError((case['id'], arm, report.model_dump()))
                path = HERE / 'inputs' / case['id'] / (arm + '.json')
                dump(path, dsl)
                inputs.append(dict(id=case['id'], group=group, arm=arm, path=str(path.relative_to(HERE)),
                                   sha256=sha(path.read_bytes()), reference=refvalue,
                                   reference_key=describe_exact(refvalue).canonical_key(), choice=option))
    dump(HERE / 'selection-audit.json', audit)
    dump(HERE / 'selection.json', selected)
    dump(HERE / 'manifest.json', dict(created_utc=datetime.now(timezone.utc).isoformat(),
        frozen_commit=FROZEN, source_hash=HASH, imported_source=str(Path(geosolver.__file__).resolve()),
        src_diff_empty=True, selection_seed=SELECT_SEED, solver_seeds=SOLVER_SEEDS,
        seconds_per_run=LIMIT_SECONDS, max_parallel=3, source_input_hashes=source_hashes,
        selected_problem_count=len(selected), inputs=inputs,
        run_count=len(inputs)*len(SOLVER_SEEDS), raw_directory='/tmp/q43f-inverse-20261024',
        selection_rule='For each group sort eligible IDs by SHA256(f"20261024:{group}:{id}"); take 12/6/6. Up to 4 choices sorted by SHA256 with :condition:{index} suffix.',
        eligibility='Single elementary exact reference; nonzero numeric equality; other side transitively depends on a free variable. Selection uses inputs only.',
        limitations=['Unseen means corpus origin; other concurrent experiments may already use these problems.',
                    'Inverse reference is a known solution, not proof of uniqueness or a full answer set.',
                    'Unselected problems are not run or used for this exploratory result.']))
    print(json.dumps(dict(problems=len(selected), arms=len(inputs), runs=len(inputs)*3,
                         selected=[(s['id'],len(s['choices'])) for s in selected]),ensure_ascii=False))

if __name__ == '__main__':
    prepare()
