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
        with tempfile.TemporaryDirectory(prefix='s8-storage-contract-') as td:
            root=Path(td);(root/'receipts').mkdir()
            j=dict(queue_index=0)
            with patch('measurement_runtime.storage_available',return_value=False):
                self.assertFalse(execute([j],root,dict(slot_cpus=[0],raw_root=td),1))
            self.assertEqual(list((root/'receipts').iterdir()),[])

    def test_rotation_filter_alias(self):
        plan=load(HERE/'run-plan.json')['jobs'];configs=load(HERE/'configs.json')['configurations'];rows=load(HERE/'assignment.json')['problems']
        expected=[]
        for r in rows:
            for seed in [601,602,603]:
                off=(r['sha256_rank']+seed-601)%12
                for c in configs[off:]+configs[:off]:expected.append((r['case_id'],seed,c['name']))
        self.assertEqual([(j['case_id'],j['seed'],j['configuration']) for j in plan],expected)
        for machine in ['superpc','winpc']:
            jobs=driver.select_jobs(machine,driver.CUMULATIVE)
            self.assertEqual(len(jobs),1113);self.assertEqual(len({j['case_id'] for j in jobs}),53)
            self.assertEqual(jobs,[j for j in plan if j['machine'].lower()==machine and j['configuration'] in driver.CUMULATIVE])
        self.assertEqual(driver.select_jobs('winpc',['N+1']),driver.select_jobs('winpc',['C1']))

    def test_environment(self):
        cfg=load(HERE/'configs.json')
        for c in cfg['configurations']:
            e=environment(c['name'],Path('/some/base'),cfg,dict(GEOSOLVER_UNKNOWN='poison',GEOSOLVER_ABLATE_NO_NOMAD='poison',PYTHONPATH='bad',OMP_NUM_THREADS='7',PYTHONHOME='bad'))
            self.assertEqual({k:v for k,v in e.items() if k.startswith('GEOSOLVER_')},c['environment'])
            self.assertEqual(e['PYTHONPATH'],'/some/base/src');self.assertNotIn('PYTHONHOME',e)
            self.assertTrue(all(e[k]=='1' for k in cfg['thread_environment']))

    def test_subprocess_fifo_resume_timeout_tree_and_interrupt(self):
        with tempfile.TemporaryDirectory(prefix='s8-contract-') as td:
            root=Path(td);out=root/'out';out.mkdir();(out/'receipts').mkdir();raw=root/'raw';raw.mkdir()
            cpu=sorted(os.sched_getaffinity(0))[0]
            freeze=dict(base_src=str(root),repo_root=str(root),python=sys.executable,source_hash='mock',python_sha256=sha(Path(sys.executable).resolve()),raw_root=str(raw),slot_cpus=[cpu],memory_mib=4096,address_space_mib=16384)
            jobs=[dict(queue_index=i,case_id='mock',machine='superPC',dsl_path='no-solver',configuration='N',seed=601,time_limit_seconds=t,cores=1,input_sha256='mock') for i,t in enumerate([1,.35,1,1])]
            def command(j):
                if j['queue_index']==1:
                    script="import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); open('child.pid','w').write(str(p.pid)); time.sleep(30)"
                else:script="import os,json,time; print(json.dumps(dict(env={k:v for k,v in os.environ.items() if k.startswith('GEOSOLVER_')},affinity=sorted(os.sched_getaffinity(0))))); time.sleep(.08)"
                return [sys.executable,'-B','-c',script]
            self.assertTrue(execute(jobs[:3],out,freeze,1,command_factory=command))
            ends=[load(out/'receipts'/f'{i:04d}.end.json') for i in range(3)]
            self.assertEqual([e['state'] for e in ends],['completed','timeout','completed'])
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
        with tempfile.TemporaryDirectory(prefix='s8-parallel-contract-') as td:
            root=Path(td);out=root/'out';out.mkdir();(out/'receipts').mkdir();raw=root/'raw';raw.mkdir()
            cpus=sorted(os.sched_getaffinity(0))[:8]
            freeze=dict(base_src=str(root),repo_root=str(root),python=sys.executable,source_hash='mock',python_sha256=sha(Path(sys.executable).resolve()),raw_root=str(raw),slot_cpus=cpus,memory_mib=4096,address_space_mib=16384)
            jobs=[dict(queue_index=i,case_id='parallel-mock',machine='superPC',dsl_path='no-solver',configuration='BASE',seed=601,time_limit_seconds=3,cores=1,input_sha256='mock') for i in range(len(cpus)+2)]
            self.assertTrue(execute(jobs,out,freeze,len(cpus),command_factory=lambda j:[sys.executable,'-B','-c','import time; time.sleep(.15)']))
            session=load(next(out.glob('execution-session-*.json')))
            self.assertEqual(session['max_active'],len(cpus))
            self.assertEqual([load(out/'receipts'/f'{i:04d}.start.json')['cpu'] for i in range(len(cpus))],cpus)
            for p in (out/'receipts').glob('*.end.json'):
                r=load(p);self.assertEqual(r['state'],'completed');self.assertEqual(r['resource_violations'],[])
            logs=ChunkLog(root,'rotation');logs.write(b'a'*4_100_000);logs.close()
            self.assertEqual(sorted(p.stat().st_size for p in root.glob('rotation.*')),[100000,2000000,2000000])

    def test_grade_cost_null_failure_exact(self):
        from measurement_exact import expression_key,serial
        with tempfile.TemporaryDirectory(prefix='s8-grade-contract-') as td:
            p=Path(td)/'result.json';save(p,dict(answers=[dict(kind='algebraic',value=dict(minimal_polynomial=['1','-2'],real_root_index=0))],engine=dict(source_hash='mock'),status='solved'))
            refs=dict(cases=dict(mock=dict(available=True,canonical_set=serial([expression_key('2')]),set_sha256='fixed')))
            j=dict(case_id='mock');r=dict(state='completed',exit_code=0,wall_seconds=.1,total_wall_through_cleanup_seconds=.11,result_path=str(p),files={'result.json':dict(sha256=sha(p))})
            self.assertEqual(grade_one(j,r,refs,'mock')['C_seed'],.11)
            self.assertEqual(grade_one(j,dict(r,state='timeout'),refs,'mock')['C_seed'],180)
            self.assertIsNone(grade_one(j,dict(r,state='interrupted'),refs,'mock')['C_seed'])
            self.assertIsNone(grade_one(j,dict(r,state='not_started'),refs,'mock')['ok'])
            refs['cases']['mock']['available']=False
            self.assertIsNone(grade_one(j,r,refs,'mock')['C_seed'])

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Contracts)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    save(HERE/'measurement-contract-results.json',dict(created_utc=utc(),passed=result.wasSuccessful(),tests_run=result.testsRun,
        mock_only=True,solver_calls=0,tested_files_sha256=driver.tested_hashes()))
    raise SystemExit(0 if result.wasSuccessful() else 1)
