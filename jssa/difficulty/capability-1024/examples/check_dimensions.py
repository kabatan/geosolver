"""Replay saved polynomial inputs, one CPU, bounded Singular runs. No scoring."""
import pathlib, subprocess, os, resource, json, time
OUT=pathlib.Path(__file__).resolve().parent
RAW=pathlib.Path('/tmp/q6e1-run/raw/msolve')
IDS=['AIME-2005-I-01','AIME-2012-I-14','HMMT-2011-FEB-GUTS-01','HMMT-2019-FEB-GUTS-17','HMMT-2023-FEB-GUTS-03']
def limits():
 os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(1536<<20,1536<<20));resource.setrlimit(resource.RLIMIT_CPU,(22,22))
for id in IDS:
 lines=(RAW/id/'in.ms').read_text().splitlines();variables=lines[0];eq='\n'.join(lines[2:]).rstrip(',\n')
 code=f'ring R=0,({variables}),dp;\nideal I={eq};\nideal G=std(I);\nprint("DIM");print(dim(G));print("GB");print(G);\nquit;\n'
 p=OUT/'evidence'/f'{id}.sing';p.write_text(code)
 t=time.monotonic()
 try:
  r=subprocess.run(['/tmp/q6-tools/bin/Singular','-q',str(p)],capture_output=True,text=True,timeout=25,preexec_fn=limits)
  log=r.stdout+r.stderr;rc=r.returncode
 except subprocess.TimeoutExpired as e: log=(e.stdout or b'').decode()+'\nTIMEOUT';rc=None
 (OUT/'evidence'/f'{id}.log').write_text(log)
 print(id,rc,round(time.monotonic()-t,3),log[:300],flush=True)
