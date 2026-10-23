"""Exploratory two-axis audit after Hamami et al.; evaluates, never searches."""
from __future__ import annotations

import ast
import csv
import gzip
import itertools
import json
import math
import re
import time
from collections import Counter
import analyze as a


def equation_type(expr, target):
    old = a.equation_kind(expr, target)
    name = a.callname(a.parse(expr))
    if name == 'OnSegment' and a.iszero(target):
        return 'unknown_incidence_and_order'
    if name == 'AreConcyclic' and a.iszero(target):
        return 'exact_metric'
    if name == 'Area' and a.iszero(target):
        return 'exact_axis_unknown'
    if old in ('diagram', 'diagram_distance_zero', 'exact_contact'):
        return 'exact_topological'
    if old == 'metric':
        return 'exact_metric'
    return 'unknown_algebra'


def guard_type(expr):
    n = a.parse(expr)
    name = a.callname(n)
    if name in ('AssumeConvex', 'AssumeNoSelfIntersecting'):
        return 'coexact_topological'
    if name == 'AssumeAcute':
        return 'coexact_metric'
    if name in ('And', 'Or', 'Not', 'Assume') and n.args:
        kinds = {guard_type(ast.unparse(x)) for x in n.args}
        return next(iter(kinds)) if len(kinds) == 1 and name != 'Not' else 'unknown_mixed'
    if name in ('AssumeGt', 'AssumeLt', 'AssumeNe') and len(n.args) == 2:
        left, right = map(ast.unparse, n.args)
        if a.callname(n.args[0]) in ('Distance', 'Area') and a.iszero(right):
            return 'coexact_topological'
        names = a.calls(left) | a.calls(right)
        if names & a.METRIC and not names & (a.DIAGRAM | a.CONTACT):
            return 'coexact_metric'
        return 'unknown_coordinate_or_mixed'
    return 'unknown_guard'


def main():
    a.protect()
    start = time.monotonic()
    source = json.loads((a.HERE / 'input-manifest.json').read_text())
    assert a.sha(a.HERE / 'analyze.py') == source['script_sha256']
    src_digest = __import__('hashlib').sha256(''.join(str(p.relative_to(a.ROOT)) + a.sha(p)
                     for p in sorted((a.ROOT / 'src').rglob('*.py'))).encode()).hexdigest()
    assert src_digest == source['src_py_sha256']
    cases = {r['id']: r for r in map(json.loads, (a.ROOT / 'benchmarks/cases.jsonl').read_text().splitlines())}
    eqrows = a.read_csv(a.HERE / 'constraint-taxonomy.csv')
    grows = a.read_csv(a.HERE / 'guard-taxonomy.csv')
    for r in eqrows:
        r['first_pass_tag'] = r.pop('semantic')
        r['two_axis_type'] = equation_type(r['expression'], r['target'])
    for r in grows:
        r['first_pass_tag'] = r.pop('semantic')
        r['two_axis_type'] = guard_type(r['source'])
    a.write_csv(a.HERE / 'two-axis-constraints.csv', eqrows)
    a.write_csv(a.HERE / 'two-axis-guards.csv', grows)
    results, perproblem = [], []
    total = Counter()
    with gzip.open(a.HERE / 'endpoints.jsonl.gz', 'rt') as f:
        for cid, rows in itertools.groupby(map(json.loads, f), key=lambda r: r['id']):
            rawpath = a.ROOT / 'jssa/difficulty/minima/raw-323' / (cid + '.json')
            assert a.sha(rawpath) == source['files'][str(rawpath.relative_to(a.ROOT))]
            raw = {r['k']: r for r in json.loads(rawpath.read_text())['records']}
            b = a.load_problem_bundle(a.GeometryProblem.model_validate(cases[cid]['dsl']).engine_document())
            ev = a.build_ir_evaluator(b)
            et = [equation_type(c, t) for c, t in zip(b.spec.constraints, b.targets)]
            gt = [guard_type(g) for g in b.spec.guards]
            ix_e = [i for i, t in enumerate(et) if t.startswith('exact')]
            ix_m = [i for i, t in enumerate(et) if t == 'exact_metric']
            ix_t = [i for i, t in enumerate(et) if t == 'exact_topological']
            ix_u = [i for i, t in enumerate(et) if t.startswith('unknown')]
            pc = Counter()
            for r in rows:
                rr = ev.evaluate_float_residual(raw[r['k']]['x'])
                residual = rr.residual_norm_float if rr.is_finite else None
                assert (residual is None) == (r['residual'] is None)
                if residual is not None:
                    assert abs(residual - r['residual']) <= 1e-12 * max(1, abs(residual))
                    total['finite_norm_crosschecks'] += 1
                es, ms, ts, us = (a.groupstate(rr.residual_vector, ix) for ix in (ix_e, ix_m, ix_t, ix_u))
                failed_types = set()
                unknown = us in ('unmet', 'unknown') or es == 'unknown'
                for s in r['guard_violations']:
                    match = re.fullmatch(r'guard\[(\d+)\] returned False', s)
                    if match:
                        failed_types.add(gt[int(match.group(1))])
                    else:
                        unknown = True
                unknown |= any(t.startswith('unknown') for t in failed_types) or bool(r['unknown_tags'])
                co = any(t.startswith('coexact') for t in failed_types)
                item = {'id': cid, 'k': r['k'], 'exact_rows': es, 'exact_metric_rows': ms,
                        'exact_topological_rows': ts, 'unknown_rows': us,
                        'coexact_guard_unmet_observed': co,
                        'coexact_metric_guard_unmet_observed': 'coexact_metric' in failed_types,
                        'coexact_topological_guard_unmet_observed': 'coexact_topological' in failed_types,
                        'unclassified_or_evaluation_issue': bool(unknown),
                        'numeric_margin_present': 'diagram_numeric_margin' in r['violated_guard_semantics']}
                results.append(item)
                for key, value in {'failed': True, 'exact_unmet': es == 'unmet',
                                   'exact_metric_unmet': ms == 'unmet',
                                   'exact_topological_unmet': ts == 'unmet',
                                   'coexact_guard_unmet': co,
                                   'both_exact_and_coexact_unmet': es == 'unmet' and co,
                                   'known_exact_met_coexact_unmet': es == 'met' and co,
                                   'unclassified_or_evaluation_issue': bool(unknown)}.items():
                    pc[key] += int(value)
                    total[key] += int(value)
            perproblem.append({'id': cid, **pc})
    assert total['failed'] == 23246
    a.write_csv(a.HERE / 'two-axis-endpoints.csv', results)
    a.write_csv(a.HERE / 'two-axis-per-problem.csv', perproblem)
    output = {'status': 'exploratory second annotation; no new search; non-causal partial categories',
              'constraints': Counter(r['two_axis_type'] for r in eqrows),
              'guards': Counter(r['two_axis_type'] for r in grows), 'totals': total,
              'new_local_searches': 0, 'workers': 1, 'elapsed_seconds': time.monotonic()-start,
              'plan_sha256': a.sha(a.HERE / 'semantic-v2-plan.md'),
              'script_sha256': a.sha(a.HERE / 'semantic_v2.py'),
              'source_paper_sha256': a.sha(a.HERE / 'hamami-2020-preprint.pdf')}
    a.dump(a.HERE / 'two-axis-summary.json', output)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
