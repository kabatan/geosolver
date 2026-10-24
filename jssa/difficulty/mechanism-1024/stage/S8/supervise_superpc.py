"""Detached campaign owner: resume only unstarted jobs, never retry a started slot."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from measurement_common import HERE, load, save, utc

OUT=HERE/'run-superpc'
PYTHON='/home/kabatan/work/solver/.venv/bin/python'
ARGS=['--machine','superpc','--configs','N','C1','C2','C3','C4','C5','BASE','--max-parallel','8',
      '--base-src','/tmp/mechanism-7b-lkdjle5l/final','--repo-root',str(HERE.parents[4]),'--python',PYTHON]

def main():
 save(OUT/'supervisor-status.json',dict(pid=os.getpid(),started_utc=utc(),state='starting'),True)
 history=[]
 while True:
  if shutil.disk_usage('/tmp').free<6*1024**3:
   save(OUT/'supervisor-status.json',dict(pid=os.getpid(),state='storage_stop',history=history,utc=utc()));return 2
  cmd='resume' if (OUT/'measurement-freeze.json').exists() else 'run'
  with (OUT/'driver.log').open('ab',buffering=0) as log:
   p=subprocess.Popen([PYTHON,'-B',str(HERE/'driver.py'),cmd,*ARGS],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   save(OUT/'supervisor-status.json',dict(pid=os.getpid(),driver_pid=p.pid,state='running',command=cmd,history=history,utc=utc()))
   code=p.wait()
  history.append(dict(command=cmd,driver_pid=p.pid,exit_code=code,end_utc=utc()))
  fpath=OUT/'measurement-freeze.json'
  if not fpath.exists():
   save(OUT/'supervisor-status.json',dict(pid=os.getpid(),state='preflight_failed',history=history,utc=utc()));return 1
  f=load(fpath);ends=[load(x) for x in (OUT/'receipts').glob('*.end.json')]
  if len(ends)==len(f['jobs']):break
  if code==0 or shutil.disk_usage('/tmp').free<6*1024**3 or any(x['state']=='interrupted_environment_storage' for x in ends):
   save(OUT/'supervisor-status.json',dict(pid=os.getpid(),state='stopped_incomplete',ends=len(ends),history=history,utc=utc()));return 2
  # Unexpected driver death: resume, whose receipt logic skips all prior starts.
  time.sleep(1)
 with (OUT/'grade.log').open('wb') as log:
  code=subprocess.call([PYTHON,'-B',str(HERE/'driver.py'),'grade',*ARGS],stdout=log,stderr=subprocess.STDOUT)
  if code==0:code=subprocess.call([PYTHON,'-B',str(HERE/'report_superpc.py')],stdout=log,stderr=subprocess.STDOUT)
 save(OUT/'supervisor-status.json',dict(pid=os.getpid(),state='complete' if code==0 else 'grading_failed',ends=len(ends),history=history,utc=utc()))
 return code

if __name__=='__main__':sys.exit(main())
