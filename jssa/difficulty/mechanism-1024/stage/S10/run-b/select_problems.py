"""Deterministic S10B selection and queue generation; no solver imports/calls."""
import csv
import hashlib
from collections import Counter
from pathlib import Path
from measurement_common import HERE, load, save, sha

GROUPS={'a':14,'b':14,'c':14,'e':14,'no_failure':8}
ARMS=['B0','B046','B056','BMADS']
SOURCE_HASH='sha256:2cb435fc35950aafaf6bb2e3a40df30a7415c9fdc65d3ff4b8d969c361ecac75'

def selection(repo):
    p=repo/'jssa/difficulty/false-attractors/per-problem.csv'
    rows=list(csv.DictReader(p.open())); assert len(rows)==292
    corpus={r['id']:r for r in map(__import__('json').loads,(repo/'benchmarks/cases.jsonl').read_text().splitlines())}
    assert len(corpus)==323 and {r['id'] for r in rows} <= corpus.keys()
    problems=[]
    for group,count in GROUPS.items():
        pool=sorted((r['id'] for r in rows if r['main_cause']==group), key=lambda k:(hashlib.sha256(('S10B|'+k).encode()).hexdigest(),k))
        for rank,k in enumerate(pool[:count]):
            path=Path('benchmarks')/corpus[k]['dsl_path']
            assert load(repo/path)==corpus[k]['dsl']
            problems.append(dict(case_id=k,main_cause=group,group_rank=rank,sha256_rank=len(problems),
                selection_sha256=hashlib.sha256(('S10B|'+k).encode()).hexdigest(),
                machine='superPC',dsl_path=str(path),input_sha256=sha(repo/path)))
    assert len(problems)==len({r['case_id'] for r in problems})==64
    return problems,dict(Counter(r['main_cause'] for r in rows))

def jobs_for(problems):
    jobs=[]
    for r in problems:
        for seed in (701,702,703):
            offset=(r['sha256_rank']+seed-701)%4
            for name in ARMS[offset:]+ARMS[:offset]:
                jobs.append(dict(queue_index=len(jobs),case_id=r['case_id'],main_cause=r['main_cause'],machine=r['machine'],
                    dsl_path=r['dsl_path'],input_sha256=r['input_sha256'],seed=seed,configuration=name,time_limit_seconds=180,cores=1))
    return jobs

def main(repo):
    rows,counts=selection(repo)
    inputs=['jssa/difficulty/false-attractors/per-problem.csv','benchmarks/cases.jsonl',
        'jssa/difficulty/false-attractors/preregistration.md','jssa/difficulty/mechanism-1024/stage/S10/preregistration-17.md',
        'jssa/difficulty/mechanism-1024/stage/S10/switches/configs.json',
        'jssa/difficulty/mechanism-1024/stage/S10/switches/design.md','jssa/difficulty/mechanism-1024/stage/S8/groups-env.md']
    provenance={n:sha(repo/n) for n in inputs}
    save(HERE/'assignment.json',dict(rule='Within Q15 main_cause, SHA256(UTF-8("S10B|"+case_id)), ascending hex; ties case_id; no newline. Group order a,b,c,e,no_failure.',
        development_corpus=323,q15_classified_variable_cases=292,q15_pool_counts=counts,
        excluded_unclassified_31='Q15 has no rows for zero-variable cases; do not invent main causes.',
        counts=dict(Counter(r['main_cause'] for r in rows)),provenance_sha256=provenance,problems=rows),True)
    with (HERE/'selected-problems.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    cfg=load(HERE.parent/'switches/configs.json')
    save(HERE/'configs.json',dict(source_hash=SOURCE_HASH,aliases={'B005_006':'B056'},configurations=[
        dict(name=k,environment=cfg['arms'][{'B056':'B005_006'}.get(k,k)] if k!='BMADS' else {'SEARCH_MODE':'mads'}) for k in ARMS],
        thread_environment=cfg['thread_environment'],
        search_mode_adapter='SEARCH_MODE=mads is driver-only, consumed by s10_worker.py; neither BASE1 nor S10 source reads a SEARCH_MODE env var.'),True)
    save(HERE/'run-plan.json',dict(execution_authorized=False,prepared_only=True,seeds=[701,702,703],
        rotation='S8 rule adapted to 4 arms: (zero-based problem rank + seed - 701) % 4; fixed FIFO; each problem, then seed, then rotated configurations.',
        jobs=jobs_for(rows)),True)
    save(HERE/'selection-hashes.json',dict(inputs_sha256=provenance,script_sha256=sha(HERE/'select_problems.py'),
        outputs_sha256={n:sha(HERE/n) for n in ['assignment.json','selected-problems.csv','configs.json','run-plan.json']}),True)
    print(__import__('json').dumps(dict(selected=len(rows),groups=dict(Counter(r['main_cause'] for r in rows)),jobs=len(jobs_for(rows)))))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--repo-root',type=Path,default=HERE.parents[5]);main(p.parse_args().repo_root.resolve())
