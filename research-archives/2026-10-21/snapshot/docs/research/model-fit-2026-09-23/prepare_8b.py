"""Adaptive, bounded 8B screen; official snapshot only, no training."""
import os
os.environ.pop('HF_HUB_OFFLINE',None)
os.environ['HF_HUB_ENABLE_HF_TRANSFER']='0'
import json,time
from pathlib import Path
from huggingface_hub import HfApi,snapshot_download
from qwen.common import write_json,file_hash,now
D=Path(__file__).resolve().parent
begin=time.monotonic();model='Qwen/Qwen3-8B';info=HfApi().model_info(model)
record={'model_id':model,'revision':info.sha,'start_utc':now(),'status':'downloading','reason':'Adaptive model-capacity screen after both 4B variants failed DA03 and original failed standard similarity proof. Selected B06, DA05, DA15 before viewing 2507 results for DA05/DA15.','updates':0}
assert not (D/'8b-model.json').exists()
write_json(D/'8b-model.json',record)
try:
 loc=Path(snapshot_download(model,revision=info.sha,allow_patterns=['*.json','*.safetensors','*.jinja','*.txt','*.model'],max_workers=4))
 record['snapshot']=str(loc);record['status']='complete';record['files']={p.name:{'bytes':p.stat().st_size,'blob':str(p.resolve())} for p in loc.iterdir() if p.is_file()}
finally:
 record['elapsed_seconds']=time.monotonic()-begin;record['end_utc']=now();write_json(D/'8b-model.json',record)
jobs=json.loads((D/'jobs.json').read_text());jobs=[j for j in jobs if j['id'] in ['B06','DA05_unassisted','DA15_unassisted']]
assert len(jobs)==3
write_json(D/'8b-jobs.json',jobs)
write_json(D/'8b-protocol.json',{'frozen_utc':now(),'model_revision':info.sha,'jobs_sha256':file_hash(D/'8b-jobs.json'),'samples':2,'max_completion':32512,'context':32768,'dtype':'float16','native_kv':True,'max_seqs':2,'max_worker_seconds':2700,'training_eligible':False,'adaptive':True,'updates':0,'limits':'Only three shared problems, not full 56-answer suite; no pooled model-wide accuracy comparison. Same temperature/top_p/top_k/seed rule, fewer max concurrent sequences for VRAM. If setup or watchdog fails, report incomplete; no unbounded expansion.'})
print(json.dumps({k:record[k] for k in ['model_id','revision','status','elapsed_seconds']}),flush=True)
