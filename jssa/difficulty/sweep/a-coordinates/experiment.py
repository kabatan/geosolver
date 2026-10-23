"""Bounded Q43a experiments. Source is imported read-only by absolute path."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import coordinates as C

sys.dont_write_bytecode=True
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[name]='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ['PYTHONPATH']=str(C.ROOT/'src')+os.pathsep+str(C.ROOT)
sys.path[:0]=[str(C.ROOT/'src'),str(C.ROOT)]
PYTHON='/home/kabatan/work/solver/.venv/bin/python'


def now(): return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if path.is_relative_to(C.BASE): assert len(data.encode())<5_000_000
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(data);tmp.replace(path)


def source_check():
    import geosolver
    from geosolver.runtime.integrity import source_tree_hash,verify_engine_lock,installed_dependencies
    assert Path(geosolver.__file__).parent==C.ROOT/'src/geosolver'
    assert source_tree_hash()==C.EXPECTED
    assert verify_engine_lock()[0]
    assert not subprocess.check_output(['git','diff',C.FROZEN,'--','src'],cwd=C.ROOT)
    return dict(import_file=geosolver.__file__,source_hash=source_tree_hash(),engine_lock=verify_engine_lock(),
                dependencies=installed_dependencies(),python=sys.executable,cwd=os.getcwd(),at=now())


def build(dsl):
    from geosolver import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    doc=GeometryProblem.model_validate(dsl).engine_document()
    b=load_problem_bundle(doc)
    return doc,b,build_ir_evaluator(b)


def reference_keys(answer):
    from geosolver.exact import describe_exact
    values=answer if isinstance(answer,list) else [answer]
    parts=[]
    for v in values:
        s=str(v).replace('π','pi')
        s=re.sub(r'√(\d+)',r'sqrt(\1)',s)
        s=re.sub(r'\s*\(\d+個\)','',s)
        s=re.sub(r'(?<=\d)(?=sqrt\(|root\(|pi\b|\()', '*', s)
        parts.extend(s.split(',') if 'RootOf' not in s else [s])
    return sorted({json.dumps(describe_exact(v.strip()).canonical_key(),separators=(',',':')) for v in parts})


def selected(): return json.loads((C.BASE/'inputs.json').read_text())


def prepare():
    assert not (C.BASE/'inputs.json').exists(),'selection already frozen'
    src=source_check();rows=C.universe();chosen=[]
    for group in ('development','unseen2026'):
        eligible=sorted([r for r in rows if r['group']==group and r['eligible']],key=lambda r:r['rank'])
        assert len(eligible)>=12
        chosen+=eligible[:12]
    inputs=[]
    for r in chosen:
        c=r['case'];dsl=c['dsl']
        # No solving or prior-result lookup occurs in selection.
        inputs.append(dict(id=c['id'],group=r['group'],source=r['source'],rank=r['rank'],dsl=dsl,
                           dsl_sha256=C.digest(dsl),answer=c['answer'],reference_keys=reference_keys(c['answer'])))
    save(C.BASE/'inputs.json',inputs)
    with (C.BASE/'selection-universe.csv').open('w') as f:
        fields=['group','source','id','eligible','exclusion','rank','selected'];w=csv.DictWriter(f,fields);w.writeheader()
        ids={r['id'] for r in chosen}
        for r in rows:w.writerow({k:r.get(k,r['id'] in ids) for k in fields})
    save(C.BASE/'manifest.json',dict(created=now(),source=src,frozen_commit=C.FROZEN,selection_seed=C.SELECT_SEED,
         selection_rule='For each cohort: statically supported DSL, 1..8 variables; rank SHA256(f"431024|{group}|{id}") ascending, first 12. No results read.',
         cohorts={g:dict(total=sum(r['group']==g for r in rows),eligible=sum(r['group']==g and r['eligible'] for r in rows),selected=12) for g in ('development','unseen2026')},
         variants=C.variants(),seeds=C.SEEDS,short_budget_seconds=15,parallelism=3,threads=1,external=str(C.EXTERNAL),
         semantics='p_new=s*R*(p-anchor)+translation; scalar search parameters and target units unchanged; lengths /s, areas and dot products /s²; zero-residual incidence operations are also converted back. No search-space affine reparameterization.',
         unseen_caveat='new2026 is held out from solver development; already used in earlier research. It is not untouched confirmation data.',
         paths={p:hashlib.sha256((C.ROOT/p).read_bytes()).hexdigest() for p in ['benchmarks/cases.jsonl','jssa/difficulty/new2026/cases.jsonl']},
         scripts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (C.BASE/'coordinates.py',Path(__file__))}))
    print(json.dumps(dict(status='selection_locked',cases=len(inputs),variants=len(C.variants()),jobs=len(inputs)*len(C.variants())*len(C.SEEDS))))


def audit():
    import numpy as np
    from mpmath import mp
    from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    results=[]
    for i,inp in enumerate(selected()):
        _,b,e=build(inp['dsl']);box=np.asarray(infer_problem_bounds(b))
        rng=np.random.default_rng([C.SELECT_SEED,i]);xs=[box[:,0]+rng.random(len(box))*(box[:,1]-box[:,0]) for _ in range(3)]
        for v in C.variants():
            fr=C.Frame(inp['dsl'],v);dsl=fr.transform();_,bb,ee=build(dsl)
            assert b.var_names==bb.var_names
            maxerr=mp.mpf(0);ncompare=0;bad=[];sign_diff=0
            with mp.workdps(80),high_precision_mode():
                for x in xs:
                    vals=[mp.mpf(repr(float(z))) for z in x]
                    a=e.evaluation_store.get(vals);z=ee.evaluation_store.get(vals)
                    # Compare original public equations, not lowered residual encodings.
                    originals=[c[k] for c in inp['dsl']['conditions'] for k in ('left','right') if k in c]+[inp['dsl']['target']]
                    altered=[c[k] for c in dsl['conditions'] for k in ('left','right') if k in c]+[dsl['target']]
                    for aa,zz in zip(originals,altered,strict=True):
                        try:
                            aval=a.evaluate(str(aa));zval=z.evaluate(str(zz))
                            er=abs(aval-zval)/max(1,abs(aval));maxerr=max(maxerr,er);ncompare+=1
                            if er>mp.mpf('1e-45'):bad.append(dict(a=str(aa),z=str(zz),av=str(aval),zv=str(zval)))
                        except Exception as ex:
                            # Invalid random diagrams are retained and counted, not replaced.
                            bad.append(dict(evaluation_error=type(ex).__name__,a=str(aa)))
                    # Verify every materializable Point, with the exact affine map.
                    a.materialize(tuple(a.plan.sources),partial=True);z.materialize(tuple(z.plan.sources),partial=True)
                    s=a.evaluate(v['s']);co=a.evaluate(v['c']);si=a.evaluate(v['q']);tx=a.evaluate(v['t'][0]);ty=a.evaluate(v['t'][1])
                    ax=a.evaluate(fr.anchor[0]);ay=a.evaluate(fr.anchor[1])
                    for name,p in a.completed.items():
                        q=z.completed.get(name)
                        if hasattr(p,'x') and hasattr(p,'y') and q is not None:
                            px=s*(co*(p.x-ax)-si*(p.y-ay))+tx;py=s*(si*(p.x-ax)+co*(p.y-ay))+ty
                            er=max(abs(q.x-px),abs(q.y-py))/max(1,abs(px),abs(py));maxerr=max(maxerr,er);ncompare+=1
                            if er>mp.mpf('1e-45'):bad.append(dict(point=name,error=str(er)))
            mismatch=[r for r in bad if 'evaluation_error' not in r]
            results.append(dict(id=inp['id'],variant=v['name'],comparisons=ncompare,max_relative_error=float(maxerr),
                                evaluation_errors=len(bad)-len(mismatch),mismatches=mismatch[:5],box_same=box.tolist()==[list(p) for p in infer_problem_bounds(bb)]))
        print(json.dumps(dict(audit_id=inp['id'],done=i+1)),flush=True)
    save(C.BASE/'equivalence-audit.json',dict(source=source_check(),precision=80,random_points_per_problem=3,
         seed=C.SELECT_SEED,rows=results,passed=all(not r['mismatches'] for r in results)))
    assert all(not r['mismatches'] for r in results),'equivalence audit mismatch'


def jobkey(j):return f"{j['id']}__{j['variant']}__{j['seed']}__{j['budget']}"


def work(jobfile):
    j=json.loads(Path(jobfile).read_text());source=source_check()
    inp=next(r for r in selected() if r['id']==j['id']);v=next(r for r in C.variants() if r['name']==j['variant'])
    dsl=C.transform(inp['dsl'],v)
    from geosolver import GeometryProblem
    from geosolver.runtime.worker import execute
    from geosolver.runtime.protocol import WorkerRequest
    start=time.monotonic();cpu=time.process_time()
    request=WorkerRequest(engine_document=GeometryProblem.model_validate(dsl).engine_document(),seed=j['seed'],effective_cores=1,
                          deadline_monotonic=time.monotonic()+j['budget'],config_snapshot=dict(q43a=j,time_limit_seconds=j['budget']))
    artifact=execute(request);data=artifact.model_dump(mode='json')
    data.update(q43a_job=j,q43a_source=source,q43a_dsl_sha256=C.digest(dsl),q43a_wall_seconds=time.monotonic()-start,q43a_cpu_seconds=time.process_time()-cpu)
    dest=C.EXTERNAL/j['stage']/'raw'/f'{jobkey(j)}.json.gz';dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,'wt') as f:json.dump(data,f,ensure_ascii=False)
    actual=sorted({json.dumps(a.canonical_key(),separators=(',',':')) for a in artifact.answers})
    record=dict(**j,group=inp['group'],status=artifact.solver_status or artifact.status,termination=artifact.termination_reason,
                exact_correct=actual==inp['reference_keys'],actual_keys=actual,expected_keys=inp['reference_keys'],
                answer_values=artifact.exact_candidates,missing=sorted(set(inp['reference_keys'])-set(actual)),extra=sorted(set(actual)-set(inp['reference_keys'])),
                elapsed=artifact.elapsed_seconds,wall_seconds=data['q43a_wall_seconds'],cpu_seconds=data['q43a_cpu_seconds'],
                numeric_feasible=artifact.numeric_feasible,candidate_count=len(artifact.candidate_records),
                accepted_count=sum(r.get('accepted',False) for r in artifact.candidate_records),
                phases=artifact.phase_timings,counters=artifact.counters,error=data['error'],source_hash=source['source_hash'],raw_path=str(dest),
                raw_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
    save(C.BASE/j['stage']/'records'/f'{jobkey(j)}.json',record)
    print(json.dumps({k:record[k] for k in ('id','variant','seed','exact_correct','status','elapsed')}),flush=True)


def launch(stage):
    assert json.loads((C.BASE/'equivalence-audit.json').read_text())['passed']
    src=source_check(); inputs=selected()
    if stage=='short':
        jobs=[dict(id=r['id'],variant=v['name'],seed=s,budget=15,stage=stage) for r in inputs for v in C.variants() for s in C.SEEDS]
        # Deterministic shuffle mixes conditions, seeds and cohorts in wall time.
        jobs.sort(key=lambda j:hashlib.sha256(f'{C.SELECT_SEED}|{jobkey(j)}'.encode()).hexdigest())
    else:jobs=json.loads((C.BASE/f'{stage}-jobs.json').read_text())
    for n,j in enumerate(jobs):j['order']=n
    save(C.BASE/f'{stage}-jobs.json',jobs)
    C.EXTERNAL.mkdir(parents=True,exist_ok=True)
    import psutil
    util=psutil.cpu_percent(interval=1,percpu=True);eligible=sorted(os.sched_getaffinity(0))
    cores=sorted(eligible,key=lambda c:(util[c],c))[:3]
    save(C.BASE/f'{stage}-execution.json',dict(started=now(),source=src,cpus=cores,load=os.getloadavg(),jobs=len(jobs),parallelism=3))
    # Separate lanes: exactly one CPU per process, process groups for watchdogs.
    def lane(k):
        for j in jobs[k::3]:
            p=C.BASE/stage/'records'/f'{jobkey(j)}.json'
            if p.exists():continue
            jp=C.EXTERNAL/stage/'jobs'/f'{jobkey(j)}.json';save(jp,j)
            log=C.EXTERNAL/stage/'logs'/f'{jobkey(j)}.txt';log.parent.mkdir(parents=True,exist_ok=True)
            started=time.monotonic()
            with log.open('w') as f:
                env=os.environ|{'PYTHONHASHSEED':'0'}
                proc=subprocess.Popen(['taskset','-c',str(cores[k]),PYTHON,'-B',str(Path(__file__).resolve()),'work',str(jp)],
                                      cwd=C.EXTERNAL,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
                timeout=False
                try:proc.wait(timeout=j['budget']+20)
                except subprocess.TimeoutExpired:
                    timeout=True;os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            if not p.exists():
                save(p,dict(**j,group=next(r['group'] for r in inputs if r['id']==j['id']),status='external_timeout' if timeout else 'worker_error',
                     exact_correct=False,actual_keys=[],elapsed=time.monotonic()-started,wall_seconds=time.monotonic()-started,
                     cpu_seconds=None,numeric_feasible=False,candidate_count=0,accepted_count=0,returncode=proc.returncode,log_path=str(log)))
            save(C.EXTERNAL/stage/'receipts'/f'{jobkey(j)}.json',dict(job=j,returncode=proc.returncode,external_timeout=timeout,
                 process_wall_seconds=time.monotonic()-started,finished=now(),cpu=cores[k]))
            print(json.dumps(dict(stage=stage,lane=k,order=j['order'],total=len(jobs),id=j['id'],variant=j['variant'],seed=j['seed'])),flush=True)
    with ThreadPoolExecutor(max_workers=3) as ex:
        for f in as_completed([ex.submit(lane,k) for k in range(3)]):f.result()
    save(C.BASE/f'{stage}-complete.json',dict(finished=now(),jobs=len(jobs),source=source_check()))


if __name__=='__main__':
    cmd=sys.argv[1]
    if cmd=='prepare':prepare()
    elif cmd=='audit':audit()
    elif cmd=='work':work(sys.argv[2])
    elif cmd=='launch':launch(sys.argv[2])
    else:raise ValueError(cmd)
