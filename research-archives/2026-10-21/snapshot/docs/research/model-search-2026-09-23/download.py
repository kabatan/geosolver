import json,time
from pathlib import Path
from huggingface_hub import HfApi,snapshot_download
D=Path(__file__).resolve().parent
models={'qwen35_4b':'Qwen/Qwen3.5-4B','qwen35_9b':'Qwen/Qwen3.5-9B','phi4_mini':'microsoft/Phi-4-mini-reasoning','mimo7b':'XiaomiMiMo/MiMo-7B-RL','nemotron9b':'nvidia/NVIDIA-Nemotron-Nano-9B-v2'}
for key,repo in models.items():
 p=D/(key+'-model.json')
 if p.exists() and json.loads(p.read_text()).get('status')=='complete':continue
 t=time.monotonic();info=HfApi().model_info(repo);rev=info.sha
 rec={'model_id':repo,'revision':rev,'status':'downloading','license':getattr(info.card_data,'license',None)}
 p.write_text(json.dumps(rec,indent=2)+'\n');print(key,rev,flush=True)
 try:
  path=snapshot_download(repo,revision=rev,allow_patterns=['*.json','*.safetensors','*.model','*.jinja','*.txt','README.md','LICENSE*'],max_workers=4)
  rec.update(status='complete',snapshot=path,download_seconds=time.monotonic()-t)
 except Exception as e:rec.update(status='failed',error=repr(e),download_seconds=time.monotonic()-t)
 p.write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(rec),flush=True)
