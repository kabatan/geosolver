"""Only synthetic subprocesses: no solver/EngineRunner calls."""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import psutil
from measurement_common import HERE, load, save, sha, utc
from measurement_runtime import environment, execute, pending_jobs
from measurement_grade import grade_one
import driver


class Contracts(unittest.TestCase):
    def test_internal_environment_and_storage_stop(self):
        from measurement_runtime import environment_matches
        from unittest.mock import patch
        expected={'GEOSOLVER_ABLATE_NO_NOMAD':'1','OMP_NUM_THREADS':'1'}
        self.assertTrue(environment_matches(dict(expected,GEOSOLVER_MEMORY_LIMIT_BYTES='123',GEOSOLVER_SYMBOLIC_PARENT='42'),expected))
        self.assertFalse(environment_matches(dict(expected,GEOSOLVER_ABLATE_NO_NOMAD='0'),expected))
        self.assertFalse(environment_matches(dict(expected,GEOSOLVER_UNKNOWN='1'),expected))
        with tempfile.TemporaryDirectory(prefix='s10b-storage-contract-') as td:
            root=Path(td);(root/'receipts').mkdir()
            j=dict(queue_index=0)
            with patch('measurement_runtime.storage_available',return_value=False):
                self.assertFalse(execute([j],root,dict(slot_cpus=[0],raw_root=td),1))
            self.assertEqual(list((root/'receipts').iterdir()),[])

    def test_rotation_filter_alias(self):
        from select_problems import jobs_for,selection
        plan=load(HERE/'run-plan.json')['jobs'];rows=load(HERE/'assignment.json')['problems']
        self.assertEqual(plan,jobs_for(rows));self.assertEqual(len(plan),768)
        self.assertEqual(selection(HERE.parents[5])[0],rows)
        self.assertEqual(len(driver.select_jobs('superpc',driver.CUMULATIVE)),768)
        self.assertEqual(driver.select_jobs('superpc',['B005_006']),driver.select_jobs('superpc',['B056']))
        from collections import Counter
        self.assertEqual(Counter((j['configuration'],j['seed']) for j in plan),{(c,s):64 for c in driver.CUMULATIVE for s in [701,702,703]})

    def test_environment(self):
        cfg=load(HERE/'configs.json')
        for c in cfg['configurations']:
            e=environment(c['name'],Path('/some/base'),cfg,dict(GEOSOLVER_UNKNOWN='poison',GEOSOLVER_ABLATE_NO_NOMAD='poison',PYTHONPATH='bad',OMP_NUM_THREADS='7',PYTHONHOME='bad',SEARCH_MODE='poison',S10B_JOB_TOKEN='poison',PYTHONUSERBASE='bad'))
            self.assertEqual({k:v for k,v in e.items() if k.startswith('GEOSOLVER_') or k=='SEARCH_MODE'},c['environment'])
            self.assertEqual(e['PYTHONPATH'],str(HERE)+os.pathsep+'/some/base/src');self.assertNotIn('PYTHONHOME',e);self.assertNotIn('PYTHONUSERBASE',e);self.assertNotIn('S10B_JOB_TOKEN',e)
            self.assertTrue(all(e[k]=='1' for k in cfg['thread_environment']))

    def test_subprocess_fifo_resume_timeout_tree_and_interrupt(self):
        with tempfile.TemporaryDirectory(prefix='s10b-contract-') as td:
            root=Path(td);out=root/'out';out.mkdir();(out/'receipts').mkdir();raw=root/'raw';raw.mkdir()
            cpu=sorted(os.sched_getaffinity(0))[0]
            freeze=dict(base_src=str(root),repo_root=str(root),python=sys.executable,source_hash='mock',python_sha256=sha(Path(sys.executable).resolve()),raw_root=str(raw),slot_cpus=[cpu],memory_mib=4096,address_space_mib=16384)
            jobs=[dict(queue_index=i,case_id='mock',machine='superPC',dsl_path='no-solver',configuration='B046',seed=701,time_limit_seconds=t,cores=1,input_sha256='mock') for i,t in enumerate([1,.35,1,1])]
            def command(j):
                if j['queue_index']==1:
                    script="import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); open('child.pid','w').write(str(p.pid)); time.sleep(30)"
                else:script="import os,json,time; print(json.dumps(dict(env={k:v for k,v in os.environ.items() if k.startswith('GEOSOLVER_')},affinity=sorted(os.sched_getaffinity(0)),mode=os.environ.get('SEARCH_MODE'),threads={k:os.environ[k] for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']}))); time.sleep(.12)"
                return [sys.executable,'-B','-c',script]
            from unittest.mock import patch
            with patch.dict(os.environ,{'GEOSOLVER_UNKNOWN':'poison','GEOSOLVER_ABLATE_NO_NOMAD':'1','SEARCH_MODE':'poison','OMP_NUM_THREADS':'7'}):
                self.assertTrue(execute(jobs[:3],out,freeze,1,command_factory=command))
            ends=[load(out/'receipts'/f'{i:04d}.end.json') for i in range(3)]
            self.assertEqual([e['state'] for e in ends],['completed','timeout','completed'])
            import json
            payload=json.loads((raw/'0000/stdout.log.0000').read_text())
            self.assertEqual(payload['env'],{'GEOSOLVER_ABLATE_NO_NOMAD_GUARD_PENALTY':'1'})
            self.assertIsNone(payload['mode']);self.assertEqual(payload['affinity'],[cpu])
            self.assertTrue(all(v=='1' for v in payload['threads'].values()))
            self.assertTrue(all(not e['resource_violations'] for e in ends))
            child=int((root/'child.pid').read_text())
            self.assertTrue(not psutil.pid_exists(child) or psutil.Process(child).status()==psutil.STATUS_ZOMBIE)
            before={str(p):sha(p) for p in (out/'receipts').glob('*')}
            self.assertEqual(pending_jobs(jobs[:3],out),[])
            self.assertTrue(execute(jobs[:3],out,freeze,1,command_factory=lambda j:self.fail('retry')))
            self.assertEqual(before,{str(p):sha(p) for p in (out/'receipts').glob('*')})
            j=jobs[3];save(out/'receipts'/'0003.start.json',dict(**j,start_utc=utc(),result_path=str(raw/'none')),True)
            self.assertEqual(pending_jobs(jobs,out),[])
            self.assertEqual(load(out/'receipts'/'0003.end.json')['state'],'interrupted_prior_start_no_retry')
            # Stop after one launch: record interrupted; next not-started remains pending.
            stopout=root/'stop';stopout.mkdir();(stopout/'receipts').mkdir();stopraw=root/'stopraw';stopraw.mkdir()
            f=dict(freeze,raw_root=str(stopraw));t0=time.monotonic()
            self.assertFalse(execute(jobs,stopout,f,1,stop=lambda:time.monotonic()-t0>.04,command_factory=command))
            self.assertEqual(load(stopout/'receipts'/'0000.end.json')['state'],'interrupted')
            self.assertEqual([j['queue_index'] for j in pending_jobs(jobs,stopout)],[1,2,3])

    def test_parallel_slots_and_bounded_logs(self):
        from measurement_runtime import ChunkLog
        with tempfile.TemporaryDirectory(prefix='s10b-parallel-contract-') as td:
            root=Path(td);out=root/'out';out.mkdir();(out/'receipts').mkdir();raw=root/'raw';raw.mkdir()
            cpus=sorted(os.sched_getaffinity(0))[:2]
            freeze=dict(base_src=str(root),repo_root=str(root),python=sys.executable,source_hash='mock',python_sha256=sha(Path(sys.executable).resolve()),raw_root=str(raw),slot_cpus=cpus,memory_mib=4096,address_space_mib=16384)
            jobs=[dict(queue_index=i,case_id='parallel-mock',machine='superPC',dsl_path='no-solver',configuration='B0',seed=701,time_limit_seconds=3,cores=1,input_sha256='mock') for i in range(len(cpus)+2)]
            self.assertTrue(execute(jobs,out,freeze,len(cpus),command_factory=lambda j:[sys.executable,'-B','-c','import time; time.sleep(.15)']))
            session=load(next(out.glob('execution-session-*.json')))
            self.assertEqual(session['max_active'],len(cpus))
            self.assertEqual([load(out/'receipts'/f'{i:04d}.start.json')['cpu'] for i in range(len(cpus))],cpus)
            for p in (out/'receipts').glob('*.end.json'):
                r=load(p);self.assertEqual(r['state'],'completed');self.assertEqual(r['resource_violations'],[])
            logs=ChunkLog(root,'rotation');logs.write(b'a'*2_000_017);logs.close()
            self.assertEqual(sorted(p.stat().st_size for p in root.glob('rotation.*')),[17,2000000])

    def test_grade_cost_null_failure_exact(self):
        from measurement_exact import expression_key,serial
        with tempfile.TemporaryDirectory(prefix='s10b-grade-contract-') as td:
            p=Path(td)/'result.json';save(p,dict(answers=[dict(kind='algebraic',value=dict(minimal_polynomial=['1','-2'],real_root_index=0))],engine=dict(source_hash='mock'),status='solved'))
            refs=dict(cases=dict(mock=dict(available=True,canonical_set=serial([expression_key('2')]),set_sha256='fixed')))
            j=dict(case_id='mock');r=dict(state='completed',exit_code=0,wall_seconds=.1,total_wall_through_cleanup_seconds=.11,result_path=str(p),files={'result.json':dict(sha256=sha(p))})
            self.assertEqual(grade_one(j,r,refs,'mock')['C_seed'],.11)
            self.assertEqual(grade_one(j,dict(r,state='timeout'),refs,'mock')['C_seed'],180)
            self.assertIsNone(grade_one(j,dict(r,state='interrupted'),refs,'mock')['C_seed'])
            self.assertIsNone(grade_one(j,dict(r,state='not_started'),refs,'mock')['ok'])
            refs['cases']['mock']['available']=False
            self.assertIsNone(grade_one(j,r,refs,'mock')['C_seed'])

    def test_mads_bridge_and_cli_worker_contract(self):
        from types import SimpleNamespace
        from s10_worker import install
        from solver_entry import install as install_cli
        class Config:
            @staticmethod
            def production_baseline_tier(**kw):return kw
        w=SimpleNamespace(ExternalPipelineConfig=Config);install(w,'mads')
        self.assertEqual(w.ExternalPipelineConfig.production_baseline_tier(seed=701,total_time_budget_sec=178),
            dict(seed=701,total_time_budget_sec=178,global_search_mode='mads'))
        self.assertEqual(Config.production_baseline_tier(seed=701),dict(seed=701))
        w=SimpleNamespace(ExternalPipelineConfig=Config);install(w,None);self.assertIs(w.ExternalPipelineConfig,Config)
        with self.assertRaises(ValueError):install(w,'poison')
        class Runner:
            def __init__(self,**kw):self.kw=kw
        module=SimpleNamespace(EngineRunner=Runner);install_cli(module)
        self.assertEqual(module.EngineRunner().kw,dict(worker_module='s10_worker',memory_limit_bytes=None))

    def test_supervisor_resumes_detached_mock_driver(self):
        from argparse import Namespace
        from supervise_superpc import supervise
        with tempfile.TemporaryDirectory(prefix='s10b-supervisor-contract-') as td:
            root=Path(td);out=root/'out';raw=root/'raw'
            a=Namespace(output=out,raw_root=raw,repo_root=root,base_src=root,python=sys.executable,max_parallel=1)
            def command(mode):return [sys.executable,'-B',str(HERE/'mock_supervisor_driver.py'),mode,str(out)]
            self.assertEqual(supervise(a,command_factory=command,grade_factory=lambda:command('grade')),0)
            r=load(out/'supervisor-status.json')
            self.assertEqual(r['state'],'complete');self.assertEqual([x['command'] for x in r['history']],['run','resume'])
            self.assertEqual([x['exit_code'] for x in r['history']],[9,0])
            self.assertTrue(load(out/'mock-grade-only.json')['mock'])
            self.assertEqual(supervise(a,command_factory=lambda c:self.fail('restart complete')),0)

    def test_supervisor_cleans_only_its_owned_mock(self):
        import subprocess
        from supervise_superpc import cleanup_owned
        with tempfile.TemporaryDirectory(prefix='s10b-orphan-contract-') as td:
            out=Path(td)/'owned';other=Path(td)/'other'
            e=dict(os.environ,S10B_JOB_TOKEN=str(out.resolve())+':7')
            a=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(5)'],env=e)
            b=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(5)'],env=dict(e,S10B_JOB_TOKEN=str(other.resolve())+':1'))
            try:
                killed=cleanup_owned(out);self.assertIn(a.pid,killed);self.assertIsNone(b.poll())
                a.wait(timeout=2)
            finally:
                for child in [a,b]:
                    if child.poll() is None:child.kill()
                    child.wait(timeout=2)

    def test_problem_majority_and_cost(self):
        from measurement_grade import problem_summary
        rows=[dict(ok=True,C_seed=.1,seed=701),dict(ok=True,C_seed=.2,seed=702),dict(ok=False,C_seed=180,seed=703)]
        r=problem_summary('mock','a','B0',rows)
        self.assertTrue(r['solved']);self.assertAlmostEqual(r['C'],60.1)
        rows[1]=dict(ok=None,C_seed=None,seed=702)
        r=problem_summary('mock','a','B0',rows);self.assertIsNone(r['solved']);self.assertIsNone(r['C'])

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Contracts)
    test_names=[test.id() for test in suite]
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    save(HERE/'measurement-contract-results.json',dict(created_utc=utc(),passed=result.wasSuccessful(),tests_run=result.testsRun,test_names=test_names,
        mock_only=True,solver_calls=0,max_parallel_subprocess_slots=2,
        failures=[str(x[0]) for x in result.failures],errors=[str(x[0]) for x in result.errors],tested_files_sha256=driver.tested_hashes()))
    raise SystemExit(0 if result.wasSuccessful() else 1)
