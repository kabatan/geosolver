"""Q21a: read-only evaluation of saved endpoints; never starts an optimizer."""
from __future__ import annotations

import ast
import csv
import gzip
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'src'))
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'

from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator

DIAGRAM = {'OnSegment', 'OnLine', 'OnCircle', 'Collinear', 'AreConcyclic',
           'ConvexPolygon', 'SimplePolygon', 'AssumeConvex'}
METRIC = {'Distance', 'Angle', 'Area', 'Radius', 'Perpendicular', 'Parallel',
          'AcuteTriangle', 'ObtuseTriangle', 'RightTriangle', 'Dot'}
CONTACT = {'IsTangent'}
TOL = 1e-8


def no_search(*a, **kw):
    raise RuntimeError('Q21a forbids optimization')


def protect():
    import scipy.optimize as opt
    from geosolver.engine.standard.search import scipy_multistart_backend as smb
    opt.least_squares = opt.minimize = no_search
    smb._collect_local_start_record = smb.least_squares = smb.minimize = no_search


def read_csv(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def dump(path, value):
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def write_csv(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def parse(expr):
    try:
        return ast.parse(str(expr), mode='eval').body
    except (SyntaxError, ValueError):
        return None


def callname(node):
    return node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else ''


def calls(expr):
    n = parse(expr)
    return {callname(c) for c in ast.walk(n) if isinstance(c, ast.Call)} if n else set()


def iszero(expr):
    return str(expr).strip() in ('0', '0.0', '-0')


def equation_kind(left, right):
    """Conservative syntax-assisted semantic tags, not a complete classifier."""
    name = callname(parse(left))
    allcalls = calls(left) | calls(right)
    if name in DIAGRAM and iszero(right):
        return 'diagram'
    if name == 'Distance' and iszero(right):
        return 'diagram_distance_zero'
    if name in CONTACT and iszero(right):
        return 'exact_contact'
    if allcalls & DIAGRAM or allcalls & {'And', 'Or', 'Not'}:
        return 'unclassified_mixed'
    if allcalls & CONTACT:
        return 'unclassified_mixed'
    if allcalls & METRIC:
        return 'metric'
    return 'unclassified_algebra'


def guard_kind(source):
    n = parse(source)
    name = callname(n)
    if name in DIAGRAM:
        return 'diagram'
    if name in {'And', 'Or', 'Not', 'Assume'} and n.args:
        kinds = {guard_kind(ast.unparse(a)) for a in n.args}
        return next(iter(kinds)) if len(kinds) == 1 else 'unclassified_mixed'
    if name.startswith('Assume') and name in {'AssumeGt', 'AssumeGe', 'AssumeLt', 'AssumeLe', 'AssumeNe', 'AssumeEq'} and len(n.args) == 2:
        a, b = (ast.unparse(x) for x in n.args)
        an = callname(n.args[0])
        if an in {'Distance', 'Area'} and iszero(b):
            return 'diagram_nondegenerate'
        names = calls(a) | calls(b)
        if names & DIAGRAM:
            return 'unclassified_mixed'
        if names & METRIC:
            return 'metric_comparison'
        return 'unclassified_coordinate'
    if name in {'AcuteTriangle', 'ObtuseTriangle', 'RightTriangle'}:
        return 'metric_comparison'
    return 'unclassified_other'


def numstate(value, tol):
    if value is None or not math.isfinite(value):
        return 'unknown'
    return 'met' if value <= tol else 'unmet'


def norm_subset(vals, indices):
    if not indices:
        return None
    v = [vals[i] for i in indices]
    return math.hypot(*v) if all(math.isfinite(x) for x in v) else None


def groupstate(vals, indices):
    if not indices:
        return 'absent'
    return numstate(norm_subset(vals, indices), TOL)


def main():
    protect()
    started = time.monotonic()
    basin_path = ROOT / 'jssa/difficulty/minima/basins-323.csv'
    cases_path = ROOT / 'benchmarks/cases.jsonl'
    human_path = ROOT / 'jssa/difficulty/ghost-1023/human_feat.csv'
    basins = [r for r in read_csv(basin_path) if int(r['n_vars']) >= 1]
    cases = {d['id']: d for d in map(json.loads, cases_path.read_text().splitlines())}
    humans = {d['case_id']: d for d in read_csv(human_path)}
    manifest = {'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'analysis_plan_sha256': sha(HERE / 'analysis-plan.md'),
                'script_sha256': sha(Path(__file__)),
                'files': {str(p.relative_to(ROOT)): sha(p) for p in [basin_path, cases_path, human_path]},
                'src_py_sha256': hashlib.sha256(''.join(str(p.relative_to(ROOT)) + sha(p) for p in sorted((ROOT / 'src').rglob('*.py'))).encode()).hexdigest()}
    dump(HERE / 'input-manifest.json', manifest)
    totals = Counter()
    cross = Counter()
    eqtypes = Counter()
    guardtypes = Counter()
    tagcounts = Counter()
    semantic = Counter()
    sensitivity = Counter()
    perproblem, constraints, guards, annotations = [], [], [], []
    audits = Counter()
    samples = []

    # Failure details are compressed; successes retain the original raw data as provenance.
    with gzip.open(HERE / 'endpoints.jsonl.gz', 'wt') as dest:
        for ci, row in enumerate(sorted(basins, key=lambda r: r['id'])):
            cid = row['id']
            rawpath = ROOT / 'jssa/difficulty/minima/raw-323' / (cid + '.json')
            qpath = ROOT / 'jssa/difficulty/false-attractors/classified' / (cid + '.jsonl.gz')
            raw = json.loads(rawpath.read_text())
            with gzip.open(qpath, 'rt') as f:
                qdata = {r['k']: r for r in map(json.loads, f) if r['source'] == 'raw0' and r['arm'] == 'B'}
            manifest['files'][str(rawpath.relative_to(ROOT))] = sha(rawpath)
            manifest['files'][str(qpath.relative_to(ROOT))] = sha(qpath)
            b = load_problem_bundle(GeometryProblem.model_validate(cases[cid]['dsl']).engine_document())
            ev = build_ir_evaluator(b)
            ek = [equation_kind(c, t) for c, t in zip(b.spec.constraints, b.targets)]
            gk = [guard_kind(g) for g in b.spec.guards]
            eqtypes.update(ek)
            guardtypes.update(gk)
            ix_m = [i for i, k in enumerate(ek) if k in ('metric', 'exact_contact')]
            ix_d = [i for i, k in enumerate(ek) if k.startswith('diagram')]
            ix_u = [i for i, k in enumerate(ek) if k.startswith('unclassified')]
            for i, (c, t, k) in enumerate(zip(b.spec.constraints, b.targets, ek)):
                constraints.append({'id': cid, 'row': i, 'expression': c, 'target': t, 'semantic': k})
            for i, (s, k) in enumerate(zip(b.spec.guards, gk)):
                guards.append({'id': cid, 'row': i, 'source': s, 'semantic': k})
            pc = Counter()
            firsthit = True
            assert len(raw['records']) == int(row['n_starts'])
            assert sum(r['cls'] == 'hit' for r in raw['records']) / len(raw['records']) == float(row['p'])
            assert len(qdata) == sum(r['cls'] != 'hit' for r in raw['records'])
            audits['basin_match_cases'] += 1
            for r in raw['records']:
                totals['records'] += 1
                if r['cls'] == 'hit':
                    totals['hit'] += 1
                    pc['hit'] += 1
                    if firsthit:
                        rr = ev.evaluate_float_residual(r['x'])
                        hh = ev.evaluate_float_hard_feasibility(r['x'], include_margins=False)
                        gg = ev.evaluate_guard(r['x'])
                        ok = rr.is_finite and rr.residual_norm_float <= TOL and hh.hard_feasible and gg[0]
                        audits['hit_controls'] += 1
                        audits['hit_control_mismatch'] += int(not ok)
                        firsthit = False
                    continue
                totals['failed'] += 1
                pc['failed'] += 1
                q = qdata[r['k']]
                assert q['cls'] == r['cls']
                audits['q15_join_rows'] += 1
                residual = None
                hval, gval = None, None
                err = ''
                gv, ht = [], []
                vals = [math.nan] * len(ek)
                try:
                    rr = ev.evaluate_float_residual(r['x'])
                    vals = rr.residual_vector
                    residual = rr.residual_norm_float if rr.is_finite else None
                    gg = ev.evaluate_guard(r['x'])
                    gval, gv = gg[0], list(gg[1])
                    hh = ev.evaluate_float_hard_feasibility(r['x'], include_margins=False)
                    hval, ht = bool(hh.hard_feasible), list(dict.fromkeys(hh.failure_tags))
                except Exception as ex:
                    err = type(ex).__name__ + ': ' + str(ex)[:300]
                qres = q.get('residual')
                if qres is not None and math.isfinite(qres) and residual is not None:
                    audits['q15_finite_residual_pairs'] += 1
                    if abs(qres - residual) > 1e-12 * max(1, abs(qres)):
                        audits['q15_residual_mismatch'] += 1
                if q.get('hard_feasible') is not None and hval is not None:
                    audits['q15_hard_pairs'] += 1
                    audits['q15_hard_mismatch'] += int(q['hard_feasible'] != hval)
                es = numstate(residual, TOL)
                hs = 'pass' if hval is True else 'fail' if hval is False else 'unknown'
                cross[(r['cls'], es, hs)] += 1
                pc[f'{es}_{hs}'] += 1
                for tol in (1e-10, 1e-8, 1e-6):
                    sensitivity[(tol, numstate(residual, tol), hs)] += 1
                tagcounts.update(ht)
                vtypes, unknown_tags = set(), []
                for v in gv:
                    m = re.match(r'guard\[(\d+)\] returned False$', v)
                    if m:
                        vtypes.add(gk[int(m.group(1))])
                    else:
                        unknown_tags.append(v)
                for v in ht:
                    if ':line_not_distinct' in v or ':triangle_degenerate' in v or ':intersection_not_distinct' in v:
                        vtypes.add('diagram_numeric_margin')
                    elif v.startswith('intersection_selection_trace:'):
                        vtypes.add('selector_trace_unclassified')
                    elif not v.startswith('guard['):
                        unknown_tags.append(v)
                ms, ds, us = (groupstate(vals, z) for z in (ix_m, ix_d, ix_u))
                # diagram_unmet is a positive observation, never an imputed cause.
                diagram_unmet = ds == 'unmet' or any(k.startswith('diagram') for k in vtypes)
                metric_unmet = ms == 'unmet' or 'metric_comparison' in vtypes
                semantic[(ms, ds, us, diagram_unmet, metric_unmet)] += 1
                pc['metric_unmet_observed'] += int(metric_unmet)
                pc['diagram_unmet_observed'] += int(diagram_unmet)
                pc['metric_rows_met_diagram_unmet'] += int(ms == 'met' and diagram_unmet)
                pc['unclassified_or_evaluation_issue'] += int(bool(unknown_tags) or any(k.startswith('unclassified') for k in vtypes) or us in ('unmet', 'unknown'))
                entry = {'id': cid, 'k': r['k'], 'saved_class': r['cls'], 'residual': residual,
                         'equalities': es, 'hard': hs, 'guard': gval, 'inside_box': q.get('inside_box'),
                         'metric_rows': ms, 'diagram_rows': ds, 'unclassified_rows': us,
                         'metric_norm': norm_subset(vals, ix_m), 'diagram_norm': norm_subset(vals, ix_d),
                         'metric_unmet_observed': metric_unmet, 'diagram_unmet_observed': diagram_unmet,
                         'violated_guard_semantics': sorted(vtypes), 'guard_violations': gv,
                         'hard_failure_tags': ht, 'unknown_tags': unknown_tags, 'error': err,
                         'q15_degenerate': q.get('a'), 'q15_escape': q.get('b'), 'q15_boundary': q.get('c')}
                dest.write(json.dumps(clean(entry), ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n')
                if len(samples) < 20 and diagram_unmet and ms == 'met':
                    samples.append(entry)
            h = humans.get(cid, {})
            perproblem.append({'id': cid, 'n_vars': row['n_vars'], 'records': len(raw['records']),
                               'p': row['p'], 'human': h.get('human', ''), 'contest': h.get('contest', ''),
                               'metric_rows_n': len(ix_m), 'diagram_rows_n': len(ix_d), 'unclassified_rows_n': len(ix_u),
                               'guard_diagram_n': sum(k.startswith('diagram') for k in gk),
                               'guard_metric_n': sum(k.startswith('metric') for k in gk),
                               'guard_unknown_n': sum(k.startswith('unclassified') for k in gk), **pc})
            if ci % 25 == 0 or ci == len(basins) - 1:
                print(f'{ci + 1}/{len(basins)} problems; {totals["failed"]} failures; {time.monotonic()-started:.1f}s', flush=True)

    write_csv(HERE / 'per-problem.csv', perproblem)
    write_csv(HERE / 'constraint-taxonomy.csv', constraints)
    write_csv(HERE / 'guard-taxonomy.csv', guards)
    write_csv(HERE / 'endpoint-cross-tab.csv', [{'saved_class': k[0], 'equalities': k[1], 'hard': k[2], 'n': v} for k, v in sorted(cross.items())])
    write_csv(HERE / 'sensitivity.csv', [{'tolerance': k[0], 'equalities': k[1], 'hard': k[2], 'n': v} for k, v in sorted(sensitivity.items())])
    write_csv(HERE / 'semantic-cross-tab.csv', [{'metric_rows': k[0], 'diagram_rows': k[1], 'unclassified_rows': k[2], 'diagram_unmet': k[3], 'metric_unmet': k[4], 'n': v} for k, v in sorted(semantic.items())])
    write_csv(HERE / 'hard-tags.csv', [{'tag': k, 'n': v} for k, v in tagcounts.most_common()])
    summary = {'totals': totals, 'problems': len(basins), 'equation_types': eqtypes, 'guard_types': guardtypes,
               'elapsed_seconds': time.monotonic()-started, 'audits': audits,
               'new_local_searches': 0, 'workers': 1,
               'human_available': sum(bool(r['human']) for r in perproblem),
               'metric_rows_met_diagram_unmet': sum(r.get('metric_rows_met_diagram_unmet', 0) for r in perproblem),
               'metric_unmet_observed': sum(r.get('metric_unmet_observed', 0) for r in perproblem),
               'diagram_unmet_observed': sum(r.get('diagram_unmet_observed', 0) for r in perproblem)}
    dump(HERE / 'summary.json', summary)
    dump(HERE / 'examples.json', samples)
    dump(HERE / 'input-manifest.json', manifest)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
