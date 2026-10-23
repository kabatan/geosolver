"""Summaries include every scheduled job, including errors and timeouts."""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
import statistics
from pathlib import Path

import coordinates as C


def load(path):return json.loads(Path(path).read_text())


def save(path,obj):
    data=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    assert len(data.encode())<5_000_000
    Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(data)


def key(j):return f"{j['id']}__{j['variant']}__{j['seed']}__{j['budget']}"


def rows(stage,complete=True):
    jobs=load(C.BASE/f'{stage}-jobs.json');out=[]
    for j in jobs:
        p=C.BASE/stage/'records'/f'{key(j)}.json'
        if p.exists():out.append(load(p))
        elif complete:out.append(dict(**j,status='missing_artifact',exact_correct=False,elapsed=j['budget'],actual_keys=[]))
    return out


def csvsave(path,rs,fields):
    with Path(path).open('w') as f:
        w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader()
        for r in rs:w.writerow({k:json.dumps(v,ensure_ascii=False,separators=(',',':')) if isinstance(v,(list,dict)) else v for k,v in r.items() if k in fields})


def summarize(stage):
    rr=rows(stage);inputs=load(C.BASE/'inputs.json');lookup={(r['id'],r['variant'],r['seed']):r for r in rr}
    variants=list(dict.fromkeys(j['variant'] for j in load(C.BASE/f'{stage}-jobs.json')))
    seeds=sorted({r['seed'] for r in rr});aggregates=[];problems=[]
    groups=['all','development','unseen2026'];groupmap={r['id']:r['group'] for r in inputs}
    for group in groups:
        for v in variants:
            rs=[r for r in rr if r['variant']==v and (group=='all' or groupmap[r['id']]==group)]
            delta=[];wins=losses=same=0;time_ratios=[]
            for r in rs:
                b=lookup.get((r['id'],'scale_+0',r['seed']))
                if b is None:continue
                d=int(r['exact_correct'])-int(b['exact_correct']);delta.append(d);wins+=d>0;losses+=d<0;same+=d==0
                if r['exact_correct'] and b['exact_correct']:time_ratios.append(r['elapsed']/max(.001,b['elapsed']))
            aggregates.append(dict(group=group,variant=v,n=len(rs),correct=sum(r['exact_correct'] for r in rs),
                numeric_feasible=sum(r.get('numeric_feasible',False) for r in rs),errors=sum(r['status'] in ('external_timeout','worker_error','missing_artifact','failed') for r in rs),
                extra_answer_runs=sum(bool(r.get('extra')) for r in rs),wins=wins,losses=losses,
                percentage_point_change=100*sum(delta)/len(delta) if delta else None,
                median_elapsed=statistics.median([r['elapsed'] for r in rs]) if rs else None,
                restricted_mean_cost=statistics.mean([min(r['elapsed'],r['budget']) if r['exact_correct'] else r['budget'] for r in rs]) if rs else None,
                median_paired_time_ratio=statistics.median(time_ratios) if time_ratios else None,
                by_seed={str(s):dict(n=sum(r['seed']==s for r in rs),correct=sum(r['seed']==s and r['exact_correct'] for r in rs)) for s in seeds}))
    for inp in inputs:
        rs=[r for r in rr if r['id']==inp['id']]
        rates={v:sum(r['exact_correct'] for r in rs if r['variant']==v) for v in variants}
        patterns={str(s):''.join('1' if lookup[(inp['id'],f'scale_{k:+d}',s)]['exact_correct'] else '0' for k in range(-6,7)) for s in seeds
                  if all((inp['id'],f'scale_{k:+d}',s) in lookup for k in range(-6,7))}
        nonmonotone={s:('01' in p and '10' in p) for s,p in patterns.items()}
        switches={s:sum(a!=b for a,b in zip(p,p[1:])) for s,p in patterns.items()}
        distinct_sets={tuple(r.get('actual_keys',[])) for r in rs}
        problems.append(dict(id=inp['id'],group=inp['group'],n=len(rs),correct=sum(r['exact_correct'] for r in rs),
             counts_by_variant=rates,scale_patterns=patterns,scale_switches=switches,nonmonotone=nonmonotone,
             nonmonotone_all_seeds=bool(nonmonotone) and all(nonmonotone.values()),
             all_variants_correct=all(r['exact_correct'] for r in rs),all_variants_failed=not any(r['exact_correct'] for r in rs),
             distinct_answer_sets=len(distinct_sets),distinct_nonempty_answer_sets=len([s for s in distinct_sets if s])))
    result=dict(stage=stage,jobs=len(rr),statuses=dict(collections.Counter(r['status'] for r in rr)),
        correct=sum(r['exact_correct'] for r in rr),groups=aggregates,problems=problems,
        nonmonotone_both=sum(r['nonmonotone_all_seeds'] for r in problems),
        all_correct=sum(r['all_variants_correct'] for r in problems),all_failed=sum(r['all_variants_failed'] for r in problems))
    save(C.BASE/f'{stage}-summary.json',result)
    csvsave(C.BASE/f'{stage}-per-run.csv',rr,['id','group','variant','seed','budget','order','status','termination','exact_correct','numeric_feasible','elapsed','wall_seconds','cpu_seconds','candidate_count','accepted_count','actual_keys','answer_values','missing','extra','raw_path','raw_sha256','log_path'])
    csvsave(C.BASE/f'{stage}-aggregate.csv',aggregates,list(aggregates[0]))
    csvsave(C.BASE/f'{stage}-per-problem.csv',problems,list(problems[0]))
    print(json.dumps({k:result[k] for k in ('stage','jobs','correct','statuses','nonmonotone_both','all_correct','all_failed')}))
    for r in aggregates:
        if r['group']=='all':print(json.dumps(r))


def progress(stage):
    rs=rows(stage,complete=False);jobs=load(C.BASE/f'{stage}-jobs.json')
    print(json.dumps(dict(stage=stage,finished=len(rs),planned=len(jobs),correct=sum(r['exact_correct'] for r in rs),statuses=dict(collections.Counter(r['status'] for r in rs)))))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['progress','summarize']);ap.add_argument('stage');a=ap.parse_args()
    (progress if a.command=='progress' else summarize)(a.stage)
