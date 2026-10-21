import json,os,subprocess,time,sys
from pathlib import Path
root=Path(__file__).resolve().parent
runtime=Path('/home/kabatan/work/solver/.venv/bin/python')
cases=['AIME-2022-II-11','AIME-2020-I-15','HMMT-2007-FEB-GEO-04','HMMT-2025-FEB-GEO-09','AIME-2010-II-14','HMMT-2025-FEB-GEO-05','JMO-2014-PRE-04','HMMT-2009-FEB-GEO-04','aime-2002-2-14','JMO-2024-PRE-09','AIME-2015-I-07','HMMT-2018-FEB-GEO-10']
if len(sys.argv)>1: cases=sys.argv[1:]
for index,case in enumerate(cases):
 variants=['baseline-source','refinement-source']
 if index%2: variants.reverse()
 for variant in variants:
  env=os.environ.copy();env['PYTHONPATH']=str(root/variant/'src')
  for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:env[name]='1'
  output=root/'refinement-source'/f'paired-{variant}-{case}.json'
  start=time.monotonic();result=subprocess.run([str(runtime),'-m','geosolver.application.cli','solve',str(root/variant/'benchmarks/dsl'/(case+'.json')),'--time-limit-seconds','180','--cores','1','--seed','0','--output',str(output)],env=env,cwd=root/variant,capture_output=True,text=True,timeout=190)
  outer=time.monotonic()-start
  if result.returncode:raise RuntimeError(result.stderr)
  solver=json.loads(output.read_text());diagnostics=solver.get('diagnostics') or {};summary=diagnostics.get('pipeline_summary') or {}
  print(json.dumps({'case':case,'variant':variant,'outer_wall':outer,'solver_wall':solver['elapsed_seconds'],'source_hash':solver['engine']['source_hash'],'status':solver['status'],'answers':solver['answers'],'phases':diagnostics.get('phase_timings'),'counters':diagnostics.get('counters'),'accepted_records':summary.get('exact_assembly',{}).get('accepted_count'),'verification_records':len(summary.get('verification_records',[])),'history_counts':[len(x['candidate']['verification_history']) for x in summary.get('exact_candidate_records',[])]}),flush=True)
