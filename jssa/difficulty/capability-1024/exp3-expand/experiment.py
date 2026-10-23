"""Preregistration 6 experiment 3. Only orchestration/storage, no solver edits.

Every batch is four (or the final two) 188-second-watchdog runs, no retries.
Run with the pinned environment's Python; imports only the clean frozen checkout.
"""
from __future__ import annotations
import argparse, concurrent.futures, datetime, fcntl, gzip, hashlib, importlib.util
import json, os, platform, shutil, subprocess, sys, tempfile, time, traceback
from pathlib import Path

OUT = Path(__file__).resolve().parent
WORK = OUT.parents[3]
CLEAN = Path('/tmp/q6e3-clean')
RAW = Path('/tmp/q6e3-raw')
INPUT = OUT / 'inputs'
EXPECTED = 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
sys.dont_write_bytecode = True
sys.path[:0] = [str(CLEAN / 'src'), str(CLEAN)]
os.environ.update(PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=f'{CLEAN}/src:{CLEAN}')
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
from benchmarks import research_runner as rr

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p, data):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    value=json.dumps(data,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n'
    if len(value.encode())>=5_000_000: raise ValueError('oversized repository artifact')
    with tempfile.NamedTemporaryFile(mode='w',dir=p.parent,delete=False) as f:
        f.write(value); f.flush(); os.fsync(f.fileno()); temp=f.name
    os.replace(temp,p)
def module(name, path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def git(*args,cwd=CLEAN): return subprocess.check_output(['git',*args],cwd=cwd)

def gate():
    assert git('rev-parse','HEAD').decode().strip()=='60db4b679b04167175c51c479c87c22fa663fda0'
    assert not git('status','--porcelain'), 'clean checkout changed'
    fp=rr.runtime_fingerprint()
    from geosolver.runtime.integrity import verify_engine_lock
    assert fp['source_hash']==EXPECTED and not fp['issues'] and verify_engine_lock()[0],fp
    assert Path(rr.__file__).resolve()==CLEAN/'benchmarks/research_runner.py'
    assert (rr.CANONICAL_TIME_LIMIT_SECONDS,rr.CANONICAL_CORES)==(180,1)
    assert not any(k.startswith('GEOSOLVER_ABLATE_') for k in os.environ)
    return fp

def prepare():
    assert not (OUT/'plan.json').exists()
    fp=gate()
    prereg=WORK/'jssa/difficulty/capability-1024/preregistration-6.md'
    assert prereg.read_bytes()==git('show','70443d65:jssa/difficulty/capability-1024/preregistration-6.md',cwd=WORK)
    remote=git('for-each-ref','--contains','70443d65','--format=%(refname)','refs/remotes',cwd=WORK).decode().splitlines()
    assert remote
    INPUT.mkdir(); RAW.mkdir(exist_ok=False)
    snapshots={}
    def snapshot(source, dest):
        target=INPUT/dest; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(source,target)
        snapshots[str(target.relative_to(OUT))]=sha(target)
    snapshot(prereg,'preregistration-6.md')
    snapshot(WORK/'jssa/difficulty/expand_k.py','expand_k.py')
    expand=module('expansion',INPUT/'expand_k.py')
    cases=[]; manifest=[]
    point_heads={'Midpoint','Intersect','IntersectLines','FootOfPerpendicular','Circumcenter','Incenter','Centroid','Orthocenter','Reflect','Rotate','PointOnSegment','PointOnLine','PointOnCircle','ContactPoint','IncircleContactPoint','Center'}
    from geosolver.problem.models import GeometryProblem
    from geosolver.problem.ir.parser import load_ir
    from geosolver.problem.domain_bounds import search_bounds
    import sympy as sp
    px,py,qx,qy,mx,my=sp.symbols('px py qx qy mx my')
    proof=sp.solve([mx-px-(qx-mx),my-py-(qy-my)],(mx,my))
    assert proof=={mx:(px+qx)/2,my:(py+qy)/2}
    for group in 'ab':
        base=WORK/f'jssa/difficulty/unseen-2/{group}'
        lock=read(base/'prediction.lock.json')
        for name in ['prediction.lock.json','cases.jsonl']+(['score.py','references.json','per-run.csv'] if group=='a' else ['audit/static.json','results.jsonl','per-problem.csv','analyze_stage2.py']):
            snapshot(base/name,f'{group}/{name}')
        for case in [json.loads(line) for line in (base/'cases.jsonl').read_text().splitlines() if line.strip()]:
            cid=case['id']; p=base/case['dsl_path']; dsl=read(p)
            locked=next(c for c in lock['adopted_problems'] if c['id']==cid)
            expected=locked.get('dsl_sha256') or lock['artifacts_sha256'][case['dsl_path']]
            assert sha(p)==expected and case['dsl']==dsl
            snapshot(p,f'{group}/dsl/{cid}.json')
            picks=expand.eligible(dsl); new=expand.expand(dsl,len(picks),picks)
            assert len(new['variables'])==len(set(new['variables']))
            assert new['conditions'][:len(dsl['conditions'])]==dsl['conditions']
            assert new['target']==dsl['target']
            picked={i for i,_,_ in picks}
            assert all(c==new['constructions'][i] for i,c in enumerate(dsl['constructions']) if i not in picked)
            assert all(expand.head_args(dsl['constructions'][i]['expression'])[0]=='Midpoint' for i,_,_ in picks)
            save(OUT/f'expanded-dsl/{cid}.json',new)
            unsupported=[]
            for i,c in enumerate(dsl['constructions']):
                head,_=expand.head_args(c['expression'])
                if i not in picked and head not in {'Point','Line','Circle'}:
                    unsupported.append({**c,'kind':head,'point_returning':head in point_heads,'reason':'fixed eligible()/rule_for() returned no rule; retained byte-equivalent construction'})
            bounds={}
            for arm,d in [('BASE',dsl),('EXPAND',new)]:
                ir=load_ir(GeometryProblem.model_validate(d).engine_document())
                bounds[arm]=dict(zip(ir.variables.resolved_names(),search_bounds(ir)))
            item={'case_id':cid,'group':group,'original_sha256':sha(p),'expanded_sha256':sha(OUT/f'expanded-dsl/{cid}.json'),
                  'original_variables':len(dsl['variables']),'expanded_variables':len(new['variables']),'expanded_points':len(picks),
                  'replacements':[{'index':i,'name':name,'original':dsl['constructions'][i]['expression'],'equations':rule} for i,name,rule in picks],
                  'retained_nonprimitive_constructions':unsupported,'unexpandable_point_count':sum(c['point_returning'] for c in unsupported),
                  'equivalence':'unconditional midpoint uniqueness; all original conditions, guards, target and unexpanded constructions preserved; eliminate appended coordinates to recover original' if picks else 'identical except id suffix .k0',
                  'search_bounds':bounds,'static_parse_compile_pass':True}
            manifest.append(item); cases.append({'case_id':cid,'group':group})
    assert len(cases)==34
    save(OUT/'expanded-dsl/manifest.json',manifest)
    save(OUT/'expanded-dsl/equivalence.json',{'method':'symbolic elimination of generic midpoint equations, plus structural identity/parse checks for each problem; no optimization or solver execution',
        'generic_unique_solution':{str(k):str(v) for k,v in proof.items()},'degeneracy_assumptions_needed':False,
        'original_constraints_guards_target_preserved':True,'all_34_static_checks_passed':True,
        'limitations':'Mathematical real solution sets are equivalent. Finite search boxes and numerical behavior are not claimed equivalent. Explicit Point coordinate formulas are retained, as required by unchanged expand_k.py.'})
    import psutil
    loads=psutil.cpu_percent(interval=2,percpu=True)
    cpus=sorted(rr._independent_cpus(),key=lambda c:(loads[c],c))[:4]
    pairs=[{**c,'seed':seed,'problem_index':i} for seed in (311,312,313) for i,c in enumerate(cases)]
    batches=[]
    for offset in range(0,len(pairs),4):
        group=pairs[offset:offset+4]
        for wave in range(2):
            tasks=[]
            for lane,pair in enumerate(group):
                arms=['BASE','EXPAND'] if pair['problem_index']%2==0 else ['EXPAND','BASE']
                tasks.append({**pair,'arm':arms[wave],'cpu':cpus[lane],'wave':wave,'lane':lane})
            batches.append(tasks)
    save(OUT/'plan.json',{'created_at_utc':now(),'preregistration_commit':'70443d65e5db5375959777216cd05bf7c2626f89','preregistration_commit_utc':'2026-10-23T18:06:13Z',
        'push_evidence':{'user_report':True,'local_remote_tracking_contains_commit':remote},'runtime':fp,'source_tree':git('rev-parse','HEAD:src').decode().strip(),
        'python':sys.executable,'platform':platform.platform(),'uname':list(platform.uname()),'hostname':platform.node(),'cpus':cpus,'cpu_load_percent':loads,'initial_load':os.getloadavg(),
        'snapshots_sha256':snapshots,'cases':cases,'batches':batches,'total_runs':204,'cores_per_run':1,'max_parallel':4,'solver_limit_seconds':180,'outer_watchdog_seconds':188,
        'missing_policy':'no answer; retained in fixed 102 per arm denominator; counted separately','automatic_retry':False,
        'arm_order':'alternate by fixed problem index, identical across seeds; corresponding arms have the same CPU and same wave size',
        'timing_primary':'median EXPAND/BASE solver elapsed_seconds over same case and same seed with both matched; process wall ratio also reported',
        'external_raw_directory':str(RAW),'orchestrator_sha256':sha(__file__)})
    print(json.dumps({'runs':204,'batches':len(batches),'cpus':cpus,'changed_problems':sum(m['expanded_points']>0 for m in manifest),'expanded_points':sum(m['expanded_points'] for m in manifest),'unexpandable_points':sum(m['unexpandable_point_count'] for m in manifest),'runtime':fp},ensure_ascii=False),flush=True)

def scorer(raw,group):
    if group=='a': return module('q30a_score',INPUT/'a/score.py').assess(raw)
    refs={r['id']:r['canonical_keys'] for r in read(INPUT/'b/audit/static.json')['geometric_references']}
    # Exact Q30b analyze_stage2.collect() expression, using its frozen keys and runner.
    outcome=rr.read_run_outcome(raw); actual=rr._answer_keys(raw.get('solver_result') or {})
    return dict(matched=bool(outcome['normal_completion'] and actual==refs[raw['case_id']]),actual_exact_keys=actual,expected_exact_keys=refs[raw['case_id']],n_answers=len(actual),**outcome)

def store(path,raw):
    group='a' if raw['case_id'].startswith('AIME') else 'b'
    assessment=scorer(raw,group)
    external=RAW/Path(path).relative_to(OUT/'execution')
    external=external.with_suffix('.json.gz'); external.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(external,'wt') as f: json.dump(raw,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    result=raw.get('solver_result'); diag=(result or {}).get('diagnostics') or {}; pipeline=diag.get('pipeline_summary') or {}; assembly=pipeline.get('exact_assembly') or {}
    kept={k:diag[k] for k in ['process_info','phase_timings','counters','rejection_tags','numeric_feasible','exact_identified'] if k in diag}
    kept['pipeline_summary']={'exact_assembly':{k:assembly[k] for k in ['numeric_feasible_count','rejection_tags'] if k in assembly},'verification_records':[True] if pipeline.get('verification_records') else []}
    compact={k:v for k,v in raw.items() if k not in ['solver_result','process']}
    compact['solver_result']={**{k:v for k,v in result.items() if k!='diagnostics'},'diagnostics':kept} if result else None
    compact['process']={k:v for k,v in raw['process'].items() if k not in ['stdout','stderr']}
    compact['streams']={k:{'sha256':hashlib.sha256(raw['process'][k].encode()).hexdigest(),'characters':len(raw['process'][k]),'excerpt':raw['process'][k][:2000]} for k in ['stdout','stderr']}
    assert assessment==scorer(compact,group) and rr.read_run_outcome(raw)==rr.read_run_outcome(compact)
    compact['assessment']=assessment
    compact['external_raw']={'path':str(external),'sha256':sha(external),'gzip_bytes':external.stat().st_size,'all_answers_retained':True,'score_preserved':True}
    save(path,compact)

def worker(task):
    cid,seed,arm,cpu=[task[k] for k in ['case_id','seed','arm','cpu']]
    dest=OUT/'execution'/arm; life=dest/f'lifecycle/{cid}/{seed}.json'; path=dest/f'runs/{cid}/{seed}.json'
    assert not life.exists() and not path.exists(), 'never retry an attempted run'
    os.sched_setaffinity(0,{cpu})
    receipt={**task,'started_at_utc':now(),'load_start':os.getloadavg()}; save(life,receipt)
    dsl_path=INPUT/f'{task["group"]}/dsl/{cid}.json' if arm=='BASE' else OUT/f'expanded-dsl/{cid}.json'
    record=rr.CaseRecord(cid,dsl_path,read(dsl_path),'preregistration-6-exp3',(),'runnable','verified',cid)
    rr._atomic_json=store
    try: rr._run_one(record,seed,dest,cpu)
    except BaseException: receipt['runner_exception']=traceback.format_exc()[-6000:]
    receipt.update(finished_at_utc=now(),load_end=os.getloadavg(),record_present=path.exists())
    if path.exists():
        raw=read(path); receipt.update(record_sha256=sha(path),assessment=raw.get('assessment'),external_raw=raw.get('external_raw'))
    else: receipt['record_missing']=True
    save(life,receipt)
    return receipt

def batch(n):
    plan=read(OUT/'plan.json'); assert sha(__file__)==plan['orchestrator_sha256']; gate()
    assert all(sha(OUT/p)==h for p,h in plan['snapshots_sha256'].items())
    for item in read(OUT/'expanded-dsl/manifest.json'):
        assert sha(OUT/f'expanded-dsl/{item["case_id"]}.json')==item['expanded_sha256']
    directory=OUT/'batches'; directory.mkdir(exist_ok=True)
    with (directory/'guard').open('a') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert all((directory/f'{i:02d}-complete.json').exists() for i in range(1,n))
        start=directory/f'{n:02d}-start.json'; assert not start.exists(), 'batch already attempted'
        tasks=plan['batches'][n-1]
        save(start,{'batch':n,'started_at_utc':now(),'load':os.getloadavg(),'tasks':tasks})
        print(json.dumps({'batch':n,'tasks':tasks,'load':os.getloadavg()}),flush=True)
        import multiprocessing
        receipts=[]
        with concurrent.futures.ProcessPoolExecutor(max_workers=len(tasks),mp_context=multiprocessing.get_context('spawn')) as pool:
            futures={pool.submit(worker,t):t for t in tasks}
            for future in concurrent.futures.as_completed(futures):
                try: receipt=future.result()
                except BaseException: receipt={**futures[future],'record_missing':True,'worker_exception':traceback.format_exc()[-6000:]}
                receipts.append(receipt)
                a=receipt.get('assessment') or {}
                print(json.dumps({k:receipt.get(k) for k in ['case_id','seed','arm','record_missing','runner_exception']}|{'matched':a.get('matched'),'status':a.get('status'),'wall':a.get('wall_seconds')}),flush=True)
        save(directory/f'{n:02d}-complete.json',{'batch':n,'finished_at_utc':now(),'load':os.getloadavg(),'all_workers_joined':True,'receipts':receipts})

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('action',choices=['prepare','batch','gate']); parser.add_argument('number',type=int,nargs='?'); args=parser.parse_args()
    if args.action=='prepare': prepare()
    elif args.action=='batch': batch(args.number)
    else: print(json.dumps(gate()))
