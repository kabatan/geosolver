"""A single fresh reference solve; no stage (2) execution or result access."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
REPO=OUT.parents[4]
def guard(event,args):
    if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):
        return
    p=Path(os.fsdecode(args[0])).absolute()
    stage=OUT.parent
    try: rel=p.relative_to(stage)
    except ValueError: rel=None
    if rel is not None:
        if rel.parts[0] in ('S1','S2','S2-addendum','S6') or (rel.parts[0] in ('S3','S5') and len(rel.parts)>1 and rel.parts[1]=='run'):
            raise PermissionError('blinding guard: '+str(p))
    if 'per-candidate.csv' in p.name or 'exact-strong' in str(p):
        raise PermissionError('blinding guard: '+str(p))
sys.addaudithook(guard)
M=json.loads((OUT/'pre-run-hashes.json').read_text())
sys.path.insert(0,M['frozen_source'])
for name in list(os.environ):
    if name.startswith('GEOSOLVER_ABLATE_') or name.startswith('GEOSOLVER_S3_'):
        del os.environ[name]
os.environ.update(M['threads'])
import helpers as h
from measure import measure
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import boundary_float_to_mpf,BoundaryOrigin


def run(key,cpu):
    os.sched_setaffinity(0,{int(cpu)})
    resource.setrlimit(resource.RLIMIT_FSIZE,(2_999_999,2_999_999))
    started=time.monotonic()
    folder=OUT/'results'/key
    folder.mkdir(parents=True,exist_ok=True)
    with (folder/'started.json').open('x') as f:
        json.dump(dict(pid=os.getpid(),cpu=cpu,started=time.time()),f)
    result=dict(case_id=key,status='reference_unavailable',reason='',type='参照解なし')
    def timeout(*_): raise TimeoutError('per-problem 600-second limit')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(598)
    phase='input'
    try:
        assert h.source_tree_hash()==M['source_hash']
        task=next(t for t in M['items'] if t['case_id']==key)
        path=Path(task['input'])
        assert hashlib.sha256(path.read_bytes()).hexdigest()==task['sha256']
        item=json.loads(path.read_text())
        bundle=h.load_problem_bundle(h.GeometryProblem.model_validate(item['dsl']).engine_document())
        result.update(n_variables=len(bundle.var_names),has_tangency=bool(h.inventory(item,bundle)))
        if not bundle.var_names:
            result.update(status='excluded_no_variables',type='探索変数なし',reason='凍結版bundleの探索変数が0個')
            return
        phase='ordinary_solve'
        # Full diagnostics are never persisted or inspected. Only coordinates
        # of the first verified witness and first search points are observed.
        with open(os.devnull,'w') as quiet, contextlib.redirect_stdout(quiet),contextlib.redirect_stderr(quiet):
            item['selection']=h.fresh_solve(item,folder)
        if item['selection'] is None:
            result['reason']='凍結版通常solve(seed 0, 180秒)の1回で最終検証通過図なし'
            return
        phase='reference'
        if not item['reference_expressions']:
            result['reason']='独立参照式なし: '+str(item.get('reference_parse_error'))
            return
        evaluator=h.build_ir_evaluator(bundle)
        ref=h.make_reference(item,bundle,evaluator,folder)
        h.save(folder/'reference.json',ref)
        if ref['status']!='ok':
            result['reason']=ref['reason']
            return
        result.update(reference_status='ok',status='measurement_unavailable',type='計測不可')
        phase='fixed_divisors'
        with h.mp.workdps(700):
            points=[[boundary_float_to_mpf(v,origin=BoundaryOrigin.INITIAL_POINT) for v in p] for p in item['selection']['initial_points']]
        assert points,'no first-search candidates available for fixed-divisor rule'
        scales=h.fixed_scales(item,bundle,points)
        h.save(folder/'scales.json',scales)
        phase='jacobian_svd'
        details,summary=measure(item,bundle,evaluator,ref,scales,points)
        h.save(folder/'sigma-details.json',details)
        result.update(summary,status='ok')
    except BaseException as e:
        result.update(reason=repr(e),failed_phase=phase,traceback=traceback.format_exc())
    finally:
        signal.alarm(0)
        result['elapsed_seconds']=time.monotonic()-started
        result['stage_2_executed']=False
        h.save(folder/'result.json',result)
        print(key,result['status'],result['reason'],flush=True)

if __name__=='__main__':
    run(*sys.argv[1:3])
