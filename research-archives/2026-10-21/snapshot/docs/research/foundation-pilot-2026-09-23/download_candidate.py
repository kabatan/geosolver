"""Pin and download only the newly authorized R1-0528 8B candidate."""
import json,time
from pathlib import Path
from huggingface_hub import HfApi,snapshot_download

D=Path(__file__).resolve().parent
p=D/'r1_8b-model.json'
assert not p.exists(), 'Do not overwrite a pinned model record'
t=time.monotonic()
repo='deepseek-ai/DeepSeek-R1-0528-Qwen3-8B'
info=HfApi().model_info(repo)
rec={'model_id':repo,'revision':info.sha,'status':'downloading','license':getattr(info.card_data,'license',None)}
p.write_text(json.dumps(rec,indent=2)+'\n')
try:
    rec['snapshot']=snapshot_download(repo,revision=info.sha,allow_patterns=['*.json','*.safetensors','*.model','*.jinja','*.txt','README.md','LICENSE*'],max_workers=4)
    rec['status']='complete'
except Exception as e:
    rec.update(status='failed',error=repr(e));raise
finally:
    rec['elapsed_seconds']=time.monotonic()-t
    p.write_text(json.dumps(rec,indent=2)+'\n')
    print(json.dumps(rec),flush=True)
