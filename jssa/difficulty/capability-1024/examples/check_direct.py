"""One externally 10-second-limited, one-core frozen replay to recover compacted direct-path evidence."""
import subprocess,os,pathlib,resource,json,time
O=pathlib.Path(__file__).resolve().parent;R=O.parents[3];C='/tmp/q6e1-clean'
assert subprocess.check_output(['git','-C',C,'rev-parse','HEAD'],text=True).strip().startswith('60db4b6')
assert not subprocess.check_output(['git','-C',C,'status','--porcelain'],text=True).strip()
env=os.environ.copy();env.update(PYTHONPATH=C+'/src',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
def lim():
 os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(1024<<20,1024<<20));resource.setrlimit(resource.RLIMIT_CPU,(8,8))
p=O/'evidence/direct-replay.json'
cmd=['/tmp/q38-58e3993-venv/bin/python','-m','geosolver.application.cli','solve',str(R/'jssa/difficulty/unseen-2/b/dsl/HMMT-2024-FEB-GUTS-04.json'),'--time-limit-seconds','180','--cores','1','--seed','301','--output',str(p)]
t=time.monotonic();r=subprocess.run(cmd,cwd=C,env=env,capture_output=True,text=True,timeout=10,preexec_fn=lim)
(O/'evidence/direct-replay-receipt.json').write_text(json.dumps(dict(command=cmd,cwd=C,commit='60db4b6',returncode=r.returncode,wall_seconds=time.monotonic()-t,stdout=r.stdout,stderr=r.stderr,additional_run=True),indent=2)+'\n')
print(r.returncode,r.stderr)
if p.exists():
 d=json.loads(p.read_text());print(d['status'],d.get('elapsed_seconds'));print(d['diagnostics']['pipeline_summary']['search']);print(d['diagnostics']['candidate_records'][0]['candidate_key'])
