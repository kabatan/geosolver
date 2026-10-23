"""Exact set scoring and small summaries. Raw artifacts remain outside the repo."""
from __future__ import annotations
import argparse
import ast
import collections
import csv
import math
import re
import statistics
import subprocess
from common import *
from transforms import ARMS

def frozen_reference_parser():
    payload = subprocess.check_output(['git','show',f'{FROZEN}:benchmarks/research_runner.py'], cwd=ROOT)
    tree = ast.parse(payload)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'reference_expressions')
    ns = {'ast':ast,'re':re,'CampaignError':ValueError}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<frozen reference parser>', 'exec'), ns)
    return ns['reference_expressions'], sha(payload)

def expected_keys(selection):
    path = BASE/'reference-keys.json'
    if path.exists(): return read(path)['keys']
    from geosolver.exact import describe_exact
    parser, runner_hash = frozen_reference_parser()
    keys = {r['id']:sorted({canonical(describe_exact(x).canonical_key())
                            for reference in (r['reference'] if isinstance(r['reference'],list) else [r['reference']])
                            for x in parser(str(reference))}) for r in selection['cases']}
    save(path, {'frozen_runner_sha256':runner_hash, 'keys':keys,
                'rule':'ExactAnswer.canonical_key whole-set equality; references never sent to workers'})
    return keys

def close(a, b, tol=1e-7):
    return len(a) == len(b) and all(abs(x-y) <= tol*max(1,abs(x),abs(y)) for x,y in zip(a,b))

def same_diagrams(a, b):
    return all(any(close(x,y) for y in b) for x in a) and all(any(close(x,y) for x in a) for y in b)

def number(x):
    try:
        y = float(x)
        return y if math.isfinite(y) else None
    except (ValueError, TypeError, OverflowError): return None

def extract(raw, case, expected):
    from pydantic import TypeAdapter
    from geosolver.problem.models import ExactAnswer
    job = raw['job']; result = raw.get('solver_result') or {}; diag = result.get('diagnostics') or {}
    adapter = TypeAdapter(ExactAnswer)
    keys = sorted({canonical(adapter.validate_python(a).canonical_key()) for a in result.get('answers',[])})
    status = result.get('status','missing')
    normal = status in ('solved', 'no_answer_found')
    numeric = diag.get('numeric_feasible', False)
    diagrams, coordinates, accepted = [], [], 0
    names = raw.get('variables',[])
    base_names = case['variants']['base']['variables']
    candidates = diag.get('candidate_records') or []
    for c in candidates:
        if not c.get('accepted'): continue
        accepted += 1
        values = dict(zip(names,c['x_hp'],strict=True))
        projected = [number(values[n]) for n in base_names]
        if any(x is None for x in projected): continue
        if not any(close(projected, other) for other in diagrams):
            diagrams.append(projected)
            coordinates.append({'values':{n:values[n] for n in base_names},
                                'answer':c.get('answer_hp'), 'candidate_uid':c['candidate_uid']})
    info = diag.get('process_info') or {}
    summary = diag.get('pipeline_summary') or {}
    rawpath = EXTERNAL/'runs'/f'{job["key"]}.json'
    row = {**job, 'alias':False, 'status':status, 'matched':normal and keys==expected,
           'actual':keys, 'expected':expected, 'extra':sorted(set(keys)-set(expected)),
           'missing':sorted(set(expected)-set(keys)), 'numeric_feasible':bool(numeric),
           'accepted_records':accepted, 'diagram_count':len(diagrams), 'diagrams':diagrams,
           'projected_coordinates':coordinates, 'candidate_records':len(candidates),
           'wall_seconds':raw.get('wall_seconds'), 'solver_elapsed':result.get('elapsed_seconds'),
           'cpu_seconds':info.get('cpu_seconds'), 'peak_rss_bytes':info.get('peak_rss_bytes'),
           'termination_reason':result.get('termination_reason'),
           'error':result.get('error'), 'phase_timings':diag.get('phase_timings',{}),
           'evaluations':(diag.get('counters') or {}).get('evaluation_count'),
           'source_hash':raw.get('runtime',{}).get('source_hash'),
           'raw_path':str(rawpath), 'raw_sha256':sha(rawpath.read_bytes()),
           'raw_bytes':rawpath.stat().st_size}
    assert row['source_hash'] == SOURCE
    if result.get('engine'): assert result['engine']['source_hash'] == SOURCE
    return row

def median(values):
    values = [x for x in values if x is not None]
    return statistics.median(values) if values else None

def summarize(rows, selection, complete):
    bykey = {(r['id'],r['arm'],r['seed']):r for r in rows if r['limit']==LIMIT}
    available = []
    for case in selection['cases']:
        for arm in ARMS:
            for seed in SEEDS:
                key = (case['id'],arm,seed)
                if key in bykey:
                    available.append(bykey[key]); continue
                if case['variants'][arm].get('alias') == 'base':
                    base = bykey.get((case['id'],'base',seed))
                    if base: available.append({**base,'arm':arm,'alias':True})
    lookup = {(r['id'],r['arm'],r['seed']):r for r in available}
    aggregate = {}
    for arm in ARMS:
        rs = [r for r in available if r['arm']==arm]
        changes, gains, losses, figchanges = [], [], [], []
        ratios = []
        for r in rs:
            b = lookup.get((r['id'],'base',r['seed']))
            if b is None: continue
            if r['actual'] != b['actual']: changes.append([r['id'],r['seed']])
            if r['matched'] and not b['matched']: gains.append([r['id'],r['seed']])
            if b['matched'] and not r['matched']: losses.append([r['id'],r['seed']])
            if not same_diagrams(r['diagrams'],b['diagrams']): figchanges.append([r['id'],r['seed']])
            if r['wall_seconds'] and b['wall_seconds']: ratios.append(r['wall_seconds']/b['wall_seconds'])
        aggregate[arm] = {'n':len(rs), 'independent_runs':sum(not r['alias'] for r in rs),
            'correct':sum(r['matched'] for r in rs), 'numeric_feasible':sum(r['numeric_feasible'] for r in rs),
            'any_diagram':sum(bool(r['diagrams']) for r in rs),
            'median_wall':median(r['wall_seconds'] for r in rs),
            'median_cpu':median(r['cpu_seconds'] for r in rs), 'median_paired_wall_ratio':median(ratios),
            'by_seed':{str(s):sum(r['matched'] for r in rs if r['seed']==s) for s in SEEDS},
            'by_pool':{p:{'correct':sum(r['matched'] for r in rs if r['pool']==p),
                          'n':sum(r['pool']==p for r in rs)} for p in ('development','heldout_origin')},
            'by_stratum':{p:{'correct':sum(r['matched'] for r in rs if r['stratum']==p),
                             'n':sum(r['stratum']==p for r in rs)} for p in ('angle','length','tangent','other')},
            'statuses':dict(collections.Counter(r['status'] for r in rs)),
            'changed_answers':changes,'gains':gains,'losses':losses,'changed_diagrams':figchanges}
    cases = []
    for case in selection['cases']:
        item = {'id':case['id'],'pool':case['pool'],'stratum':case['stratum'],'arms':{}}
        for arm in ARMS:
            rs = [lookup[(case['id'],arm,s)] for s in SEEDS if (case['id'],arm,s) in lookup]
            item['arms'][arm] = [{'seed':r['seed'],'matched':r['matched'],'answers':r['actual'],
                'diagrams':r['diagram_count'],'wall':r['wall_seconds'],'cpu':r['cpu_seconds'],
                'status':r['status'],'alias':r['alias']} for r in rs]
        cases.append(item)
    return {'complete':complete,'actual_runs':len(rows),'expanded_rows':len(available),
            'arms':aggregate,'cases':cases}, available

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true')
    args=parser.parse_args(); fingerprint()
    selection=read(BASE/'selection.json'); keys=expected_keys(selection)
    cases={r['id']:r for r in selection['cases']}; jobs=read(BASE/'jobs.json')['jobs']
    cache_path=EXTERNAL/'analysis-cache.json'; cache=read(cache_path) if cache_path.exists() else {}
    for job in jobs:
        p=EXTERNAL/'runs'/f'{job["key"]}.json'
        if p.exists() and job['key'] not in cache:
            raw=read(p); assert raw['job']==job
            cache[job['key']]=extract(raw,cases[job['id']],keys[job['id']])
    save(cache_path,cache)
    rows=[cache[j['key']] for j in jobs if j['key'] in cache]
    complete=len(rows)==len(jobs)
    if not args.partial: assert complete, (len(rows),len(jobs))
    summary,expanded=summarize(rows,selection,complete)
    destination=EXTERNAL/'partial-summary.json' if args.partial else BASE/'summary.json'
    save(destination,summary)
    if not args.partial:
        # Full coordinates and per-candidate logs stay external; rounded figure
        # signatures and exact sets make the repository summary independently readable.
        small=[{k:v for k,v in r.items() if k not in ('projected_coordinates',)} for r in expanded]
        save(BASE/'per-run.json',small)
        with (BASE/'per-run.csv').open('w') as f:
            fields=['id','pool','stratum','arm','seed','alias','matched','status','numeric_feasible',
                    'diagram_count','wall_seconds','cpu_seconds','peak_rss_bytes','termination_reason']
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(expanded)
    print(json.dumps({'complete':complete,'runs':len(rows),'arms':{a:{k:v for k,v in d.items()
         if k in ('n','correct','median_wall','by_seed','statuses')} for a,d in summary['arms'].items()}},indent=2))

if __name__=='__main__':main()
