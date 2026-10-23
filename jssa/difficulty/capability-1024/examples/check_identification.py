"""Identification only, using a saved refined value and frozen 60db4b6 code."""
import pathlib,json,subprocess,sys,os,resource,time
ROOT=pathlib.Path(__file__).resolve().parents[4]; OUT=pathlib.Path(__file__).resolve().parent
if '--child' in sys.argv:
 from mpmath import mp
 from geosolver.exact.polynomial_search import find_minimal_polynomial
 p=ROOT/'jssa/difficulty/unseen-2/a/execution/runs/AIME-2014-II-10/301.json'
 d=json.loads(p.read_text());c=d['diagnostic_evidence']['candidate_records']['first_6'][0]
 results=[]
 for digits in [50,120,350]:
  for bound in [10**8,10**14]:
   with mp.workdps(digits+40):
    value=mp.mpf(c['answer_hp']);t=time.monotonic()
    coeff=find_minimal_polynomial(value,precision=digits,max_degree=2,max_coeff=bound,max_steps=20000)
    results.append(dict(precision_dps=digits,max_coeff=bound,degree_cap=2,coefficients=coeff,seconds=time.monotonic()-t))
 print(json.dumps({'saved_candidate_id':c['candidate_id'],'input_precision_dps':c['answer_precision_dps'],'input_uncertainty':c['answer_uncertainty'],'trials':results},indent=2));sys.exit()
clean='/tmp/q6e1-clean'
assert subprocess.check_output(['git','-C',clean,'rev-parse','HEAD'],text=True).strip()=='60db4b679b04167175c51c479c87c22fa663fda0'
assert not subprocess.check_output(['git','-C',clean,'status','--porcelain'],text=True).strip()
env=os.environ.copy();env.update(PYTHONPATH=clean+'/src',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
def lim():
 os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(1024<<20,1024<<20));resource.setrlimit(resource.RLIMIT_CPU,(15,15))
r=subprocess.run(['/tmp/q38-58e3993-venv/bin/python',str(pathlib.Path(__file__).resolve()),'--child'],cwd=clean,env=env,capture_output=True,text=True,timeout=18,preexec_fn=lim)
(OUT/'evidence/identification.json').write_text(r.stdout)
print(r.returncode,r.stdout,r.stderr)
