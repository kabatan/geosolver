"""Additional exploratory runs on the SAME 24 problems, no replacements.

`plan long` picks conspicuous conditions using the completed short scan.
`plan fixedbox` prepares the same conditions with original heuristic boxes.
This is seed/budget replication, not a held-out confirmatory test.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import coordinates as C
import experiment as E
import analyze as A


def plan(stage):
    assert (C.BASE/'short-complete.json').exists()
    if stage=='long':
        summary=A.load(C.BASE/'short-summary.json')
        groups={r['variant']:r for r in summary['groups'] if r['group']=='all'}
        rows=A.rows('short');look={(r['id'],r['variant'],r['seed']):r for r in rows}
        scores=[]
        for name,g in groups.items():
            if name in ('scale_+0','identity_rewrite'):continue
            stable_loss=stable_gain=0
            for inp in E.selected():
                changes=[int(look[(inp['id'],name,s)]['exact_correct'])-int(look[(inp['id'],'scale_+0',s)]['exact_correct']) for s in C.SEEDS]
                stable_loss+=all(d==-1 for d in changes);stable_gain+=all(d==1 for d in changes)
            scores.append(dict(variant=name,stable_loss=stable_loss,stable_gain=stable_gain,
                 wins=g['wins'],losses=g['losses'],cost_difference=g['restricted_mean_cost']-groups['scale_+0']['restricted_mean_cost']))
        # Two scale conditions and one other coordinate condition, always plus sham.
        def score(r):return (r['stable_loss']+r['stable_gain'],r['wins']+r['losses'],abs(r['cost_difference']),r['variant'])
        scale=sorted([r for r in scores if r['variant'].startswith('scale_')],key=score,reverse=True)[:2]
        other=sorted([r for r in scores if not r['variant'].startswith('scale_')],key=score,reverse=True)[:1]
        names=['scale_+0','identity_rewrite']+[r['variant'] for r in scale+other]
        seeds=[431201,431202];budget=180
        selection=dict(exploratory=True,not_heldout_confirmation=True,source_summary_sha256=hashlib.sha256((C.BASE/'short-summary.json').read_bytes()).hexdigest(),
            rule='Baseline + sham + top 2 scale and top 1 non-scale: rank by #problems changing correctness in the same direction in both seeds; then #paired flips; then |restricted mean cost difference|; then variant name descending.',
            ranked_scores=sorted(scores,key=score,reverse=True),conditions=names,seeds=seeds,budget=budget)
        E.save(C.BASE/'long-selection.json',selection)
    elif stage=='fixedbox':
        selection=A.load(C.BASE/'long-selection.json');names=selection['conditions'];seeds=C.SEEDS;budget=15
    else:raise ValueError(stage)
    jobs=[dict(id=r['id'],variant=v,seed=s,budget=budget,stage=stage,box_mode='original' if stage=='fixedbox' else 'native')
          for r in E.selected() for v in names for s in seeds]
    jobs.sort(key=lambda j:hashlib.sha256(f'{C.SELECT_SEED}|{E.jobkey(j)}'.encode()).hexdigest())
    for n,j in enumerate(jobs):j['order']=n
    E.save(C.BASE/f'{stage}-jobs.json',jobs)
    print(json.dumps(dict(stage=stage,jobs=len(jobs),variants=names,seeds=seeds,budget=budget)))


def work(jobfile):
    j=A.load(jobfile)
    if j['box_mode']=='native':return E.work(jobfile)
    inp=next(r for r in E.selected() if r['id']==j['id'])
    _,bundle,_=E.build(inp['dsl'])
    from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
    original_box=infer_problem_bounds(bundle);names=tuple(bundle.var_names)
    modules=[importlib.import_module(n) for n in ('geosolver.problem.domain_bounds','geosolver.engine.standard.problem.analysis_plan','geosolver.engine.standard.problem.infer_problem_bounds')]
    native=modules[0].search_bounds;calls=[]
    def changed(spec):
        inferred=native(spec);active=tuple(spec.variables.resolved_names())
        applies=active==names
        calls.append(dict(variables=list(active),applied=applies,inferred=inferred,returned=original_box if applies else inferred))
        return list(original_box) if applies else inferred
    for module in modules:module.search_bounds=changed
    from geosolver.runtime import worker
    execute=worker.execute
    def observed(request):
        artifact=execute(request)
        return artifact.model_copy(update={'diagnostics':artifact.diagnostics|{'q43a_fixedbox':dict(original_box=original_box,calls=calls)}})
    worker.execute=observed
    E.work(jobfile)
    path=C.BASE/j['stage']/'records'/f'{E.jobkey(j)}.json';record=A.load(path)
    record['box_hook_calls']=len(calls);record['box_hook_applied']=sum(c['applied'] for c in calls)
    record['original_box']=original_box
    E.save(path,record)


def launch(stage):
    assert A.load(C.BASE/'equivalence-audit-v2.json')['passed']
    jobs=A.load(C.BASE/f'{stage}-jobs.json');inputs=E.selected();source=E.source_check()
    import psutil
    util=psutil.cpu_percent(interval=1,percpu=True)
    cores=sorted(os.sched_getaffinity(0),key=lambda c:(util[c],c))[:3]
    E.save(C.BASE/f'{stage}-execution.json',dict(started=E.now(),source=source,cpus=cores,jobs=len(jobs),parallelism=3,load=os.getloadavg(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    def lane(k):
        for j in jobs[k::3]:
            path=C.BASE/stage/'records'/f'{E.jobkey(j)}.json'
            if path.exists():continue
            jp=C.EXTERNAL/stage/'jobs'/f'{E.jobkey(j)}.json';E.save(jp,j)
            log=C.EXTERNAL/stage/'logs'/f'{E.jobkey(j)}.txt';log.parent.mkdir(parents=True,exist_ok=True)
            started=time.monotonic()
            with log.open('w') as f:
                proc=subprocess.Popen(['taskset','-c',str(cores[k]),E.PYTHON,'-B',str(Path(__file__).resolve()),'work',str(jp)],cwd=C.EXTERNAL,
                     env=os.environ|{'PYTHONHASHSEED':'0'},stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
                timeout=False
                try:proc.wait(timeout=j['budget']+20)
                except subprocess.TimeoutExpired:timeout=True;os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            if not path.exists():
                E.save(path,dict(**j,group=next(r['group'] for r in inputs if r['id']==j['id']),status='external_timeout' if timeout else 'worker_error',
                    exact_correct=False,actual_keys=[],elapsed=time.monotonic()-started,wall_seconds=time.monotonic()-started,cpu_seconds=None,
                    numeric_feasible=False,candidate_count=0,accepted_count=0,returncode=proc.returncode,log_path=str(log)))
            E.save(C.EXTERNAL/stage/'receipts'/f'{E.jobkey(j)}.json',dict(job=j,returncode=proc.returncode,external_timeout=timeout,
                process_wall_seconds=time.monotonic()-started,finished=E.now(),cpu=cores[k]))
            print(json.dumps(dict(stage=stage,lane=k,order=j['order'],total=len(jobs),id=j['id'],variant=j['variant'],seed=j['seed'])),flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for f in as_completed([pool.submit(lane,k) for k in range(3)]):f.result()
    E.save(C.BASE/f'{stage}-complete.json',dict(finished=E.now(),jobs=len(jobs),source=E.source_check()))


if __name__=='__main__':
    {'plan':plan,'work':work,'launch':launch}[sys.argv[1]](sys.argv[2])
