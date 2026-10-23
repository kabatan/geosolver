"""Orchestrate unchanged exact code; keep raw evidence outside repository."""
import concurrent.futures,json,os,pathlib,resource,subprocess,sys,time,threading
from datetime import datetime,timezone
import psutil
ROOT=pathlib.Path(__file__).resolve().parents[4]
OUT=pathlib.Path(__file__).resolve().parent
CLEAN=pathlib.Path('/tmp/q6e1-clean'); RUN=pathlib.Path('/tmp/q6e1-run')
PY='/tmp/q38-58e3993-venv/bin/python'; CODE=RUN/'benchmarks/exact_comparison/run_exact.py'
RAW=RUN/'raw'; RAW.mkdir(exist_ok=True)
ENV=os.environ.copy();ENV.update(PATH='/tmp/q6-tools/bin:'+ENV['PATH'],PYTHONPATH=str(CLEAN/'src'),EXACT_MEM_GB='8',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONNOUSERSITE='1')
CPUS=[7,12,2,6]; assert set(CPUS)<=os.sched_getaffinity(0)
STOP=threading.Event(); LOCK=threading.Lock()
def now():return datetime.now(timezone.utc).isoformat()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def event(v):
 with LOCK:
  with (OUT/'events.jsonl').open('a') as f:f.write(json.dumps(v,ensure_ascii=False)+'\n')
  print(json.dumps(v,ensure_ascii=False),flush=True)
def sampler():
 while not STOP.is_set():
  with (OUT/'load.jsonl').open('a') as f:f.write(json.dumps({'utc':now(),'load':os.getloadavg(),'memory_available':psutil.virtual_memory().available,'swap_free':psutil.swap_memory().free})+'\n')
  STOP.wait(30)
def child(cpu):
 os.sched_setaffinity(0,{cpu});resource.setrlimit(resource.RLIMIT_AS,(8<<30,8<<30));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def one(cid,solver,cpu):
 d=RAW/solver/cid;d.mkdir(parents=True,exist_ok=True); recfile=d/'result.json'
 assert not recfile.exists(),f'No implicit rerun: {cid} {solver}'
 env=ENV.copy();env['EXACT_CAPTURE_DIR']=str(d)
 cmd=[PY,str(CODE),cid,'fresh',solver,'600',str(recfile)]
 receipt={'id':cid,'solver':solver,'started_utc':now(),'cpu':cpu,'cmd':cmd,'cwd':str(CLEAN),'memory_address_space_bytes':8<<30,'timeout_seconds':600}
 save(d/'start.json',receipt);event({'event':'start','id':cid,'solver':solver,'utc':receipt['started_utc']})
 t=time.monotonic()
 with (d/'driver.log').open('w') as log:
  p=subprocess.Popen(cmd,cwd=CLEAN,env=env,stdout=log,stderr=subprocess.STDOUT,preexec_fn=lambda:child(cpu),start_new_session=True)
  peak=0; children=[]
  while p.poll() is None:
   try:
    proc=psutil.Process(p.pid);tree=[proc]+proc.children(recursive=True)
    peak=max(peak,sum(q.memory_info().rss for q in tree if q.is_running()))
   except psutil.Error:pass
   if time.monotonic()-t>1500:
    import signal
    os.killpg(p.pid,signal.SIGKILL);receipt['outer_timeout']=True;break
   time.sleep(.25)
  rc=p.wait()
 receipt.update(finished_utc=now(),process_wall_seconds=time.monotonic()-t,returncode=rc,peak_tree_rss_bytes=peak,result_present=recfile.exists())
 save(d/'receipt.json',receipt)
 if recfile.exists():
  rec=json.loads(recfile.read_text());save(OUT/'records'/f'{cid}.{solver}.json',rec)
 else:rec={}
 event({'event':'finish','id':cid,'solver':solver,'rc':rc,'status':rec.get('solve_status',rec.get('status','no_result')),'matches':rec.get('answer_set_matches'),'wall':receipt['process_wall_seconds']})
 return cid,rec
if __name__=='__main__':
 (OUT/'records').mkdir(exist_ok=True)
 sampler_thread=threading.Thread(target=sampler,daemon=True);sampler_thread.start()
 ids=(RUN/'ids.txt').read_text().splitlines();start=now()
 results={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  futures=[pool.submit(one,cid,'msolve',CPUS[i%4]) for i,cid in enumerate(ids)]
  for fut in concurrent.futures.as_completed(futures):cid,rec=fut.result();results[cid]=rec
 nonfinite=[cid for cid in ids if results[cid].get('solve_status')=='positive_dimensional']
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  futures=[pool.submit(one,cid,'elim',CPUS[i%4]) for i,cid in enumerate(nonfinite)]
  for fut in concurrent.futures.as_completed(futures):fut.result()
 STOP.set();sampler_thread.join()
 save(OUT/'execution.json',{'started_utc':start,'finished_utc':now(),'msolve_attempts':len(ids),'singular_elimination_attempts':len(nonfinite),'automatic_retries':0,'raw_path':str(RAW)})
