"""Premises-only public-solver teacher generation. No proof/goal file is read."""
from __future__ import annotations
from fractions import Fraction
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import time

from geosolver import GeometryProblem, SolveOptions, solve, validate

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'qwen/.runtime/proof_numeric_pilot_20260928/data'
SEED = 2026092801
DERIVED = [
    ('M', 'Midpoint(B,C)'), ('N', 'Midpoint(C,A)'), ('P', 'Midpoint(A,B)'),
    ('D', 'IntersectLines(PerpendicularBisector(A,B),Line(A,M))'),
    ('E', 'IntersectLines(PerpendicularBisector(A,C),Line(A,M))'),
    ('F', 'IntersectLines(Line(B,D),Line(C,E))'),
]
POINTS = ['A', 'B', 'C'] + [name for name, _ in DERIVED]
INTERSECTIONS = {name for name, expr in DERIVED if expr.startswith('IntersectLines(')}
POOL = [p + q for p, q in itertools.combinations(POINTS, 2)
        if {p, q} & INTERSECTIONS]
CONDITIONS = [
    {'predicate': 'AcuteTriangle(A,B,C)'},
    {'left': 'Dot(Vector(A,D),Vector(A,M))', 'operator': '>', 'right': 0},
    {'left': 'Dot(Vector(A,E),Vector(A,M))', 'operator': '>', 'right': 0},
    {'left': 'Area(A,F,B)+Area(B,F,C)+Area(C,F,A)', 'operator': '=', 'right': 'Area(A,B,C)'},
    *[{'left': expr, 'operator': '>', 'right': 0}
      for expr in ['Area(A,F,B)', 'Area(B,F,C)', 'Area(C,F,A)']],
]
PREMISES = ('Let ABC be an acute scalene triangle. Let M, N, and P be the midpoints '
            'of BC, CA, and AB, respectively. The perpendicular bisectors of AB '
            'and AC meet the ray AM at D and E, respectively. The lines BD and CE '
            'meet at F, which lies strictly inside triangle ABC.')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def task_for(cid, sides, query):
    a, b, c = sides
    x = Fraction(c*c + a*a - b*b, 2*a)
    h2 = c*c - x*x
    pairs = [('A', f'Point({x},sqrt({h2}))'), ('B', 'Point(0,0)'), ('C', f'Point({a},0)')] + DERIVED
    return GeometryProblem(id=cid, variables=[],
        constructions=[{'name': n, 'expression': e} for n, e in pairs],
        conditions=CONDITIONS, target=f'Distance({query[0]},{query[1]})')


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    rng = random.Random(SEED)
    seen = set()
    shapes, train, heldout, rejects = [], [], [], []
    attempts = 0
    while len(shapes) < 72:
        attempts += 1
        assert attempts <= 20000, 'bounded sampling exhausted'
        sides = [rng.randint(5, 40) for _ in range(3)]
        ordered = sorted(sides)
        signature = tuple(str(Fraction(v, ordered[-1])) for v in ordered)
        if len(set(sides)) != 3 or ordered[-1]**2 >= ordered[0]**2 + ordered[1]**2:
            rejects.append({'attempt': attempts, 'sides': sides, 'reason': 'not_acute_scalene'})
            continue
        if signature in seen:
            rejects.append({'attempt': attempts, 'sides': sides, 'reason': 'similar_shape'})
            continue
        seen.add(signature)
        index = len(shapes)
        split = 'train' if index < 64 else 'heldout'
        queries = rng.sample(POOL, 4 if split == 'train' else 1)
        rows = []
        all_ok = True
        for qi, query in enumerate(queries):
            cid = f'AP01-{split}-{index:03d}-{query}'
            task = task_for(cid, sides, query)
            valid = validate(task)
            assert valid.valid, valid
            result = solve(task, SolveOptions(time_limit_seconds=180, cores=1, seed=0))
            record = {'id': cid, 'attempt': attempts, 'query': query, 'sides_BC_CA_AB': sides,
                      'signature': signature, 'problem': task.model_dump(mode='json'),
                      'result': result.model_dump(mode='json')}
            write(OUT / f'solver-attempt{attempts:04d}-q{qi}.json', record)
            if result.status != 'solved' or len(result.answers) != 1:
                rejects.append({'attempt': attempts, 'sides': sides, 'reason': 'solver_premise_or_label_failure',
                                'query': query, 'status': result.status})
                all_ok = False
                break
            value = float(result.answers[0].decimal)
            assert math.isfinite(value) and value > 0
            a, b, c = sides
            prompt = (PREMISES + f' The side lengths are AB={c}, BC={a}, and CA={b}. '
                      f'Find the length of {query}. Give the requested length as a decimal '
                      'rounded to six digits after the decimal point.')
            rows.append({'id': cid, 'source_id': 'AP01', 'kind': 'numeric', 'shape_index': index,
                         'query': query, 'sides_BC_CA_AB': sides, 'signature': signature,
                         'messages': [{'role': 'user', 'content': prompt}],
                         'target': f'{value:.6f}', 'solver_value': result.answers[0].decimal,
                         'solver_receipt': str(OUT / f'solver-attempt{attempts:04d}-q{qi}.json')})
        if not all_ok:
            continue
        shapes.append({'index': index, 'split': split, 'sides_BC_CA_AB': sides,
                       'signature': signature, 'queries': queries})
        (train if split == 'train' else heldout).extend(rows)
        print(json.dumps({'accepted_shapes': len(shapes), 'train_rows': len(train),
                          'heldout_rows': len(heldout), 'seconds': time.monotonic()-started}), flush=True)
        write(OUT / 'progress.json', {'shapes': shapes, 'rejects': rejects, 'attempts': attempts})
    assert len(train) == 256 and len(heldout) == 8
    probes = [next(row for row in train if row['shape_index'] == index) for index in range(4)]
    export = [{k: row[k] for k in ['id', 'source_id', 'kind', 'messages', 'target']} for row in train]
    write(OUT / 'train.json', export)
    write(OUT / 'train-provenance.json', train)
    diagnostic = []
    for index, row in enumerate(heldout + probes):
        diagnostic.append(dict(row, original_id=row['id'], id=f'AP01-num-{index:02d}',
                               split='heldout' if index < 8 else 'train_probe', seed=2026092830+index))
    write(OUT / 'numeric-private-key.json', diagnostic)
    write(OUT / 'numeric-jobs.json', [{k: row[k] for k in ['id', 'source_id', 'messages', 'seed', 'split']}
                                    for row in diagnostic])
    write(OUT / 'receipt.json', {'status': 'complete', 'seed': SEED, 'script_sha256': digest(__file__),
        'elapsed_seconds': time.monotonic()-started, 'train_rows': 256, 'heldout_rows': 8,
        'train_shapes': 64, 'heldout_shapes': 8, 'attempts': attempts, 'query_pool': POOL,
        'shapes': shapes, 'rejects': rejects, 'train_sha256': digest(OUT / 'train.json'),
        'teacher_source': 'geosolver public solve; full-shape direct evaluation',
        'scope': 'premises manually formalized once; all instances/queries/labels automatically generated'})


if __name__ == '__main__':
    main()
