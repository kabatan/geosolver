"""Repair inference naming, verify its effect, and rerun all fixed H14 jobs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

D=Path(__file__).resolve().parent
ROOT=D.parents[2]
R=ROOT/'qwen/.runtime/research_direction_audit_20260925'
MAP=ROOT/'docs/research/qwen35-sft-pilot-2026-09-24/map_vllm_adapter.py'
GEN=ROOT/'docs/research/qwen35-diverse-sft-2026-09-24/generate.py'
os.chdir(ROOT)
env=dict(os.environ,PYTHONPATH=str(ROOT))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
freeze={'created_unix':time.time(),'repair_driver_sha256':sha(Path(__file__)),
        'effect_driver_sha256':sha(D/'check_bridge_effect.py'),'mapping_driver_sha256':sha(MAP),
        'incident_sha256':sha(D/'MAPPING_INCIDENT.md'),'original_freeze_sha256':sha(D/'BRIDGE_PILOT_FREEZE.json'),
        'mapped_adapters':{}}
for arm in ['treatment','control']:
    source=R/f'train-{arm}/adapter'
    target=R/f'train-{arm}/adapter-vllm'
    if not target.exists():
        subprocess.run([sys.executable,str(MAP),'--source',str(source),'--target',str(target)],env=env,check=True)
    from safetensors import safe_open
    import torch
    with safe_open(source/'adapter_model.safetensors',framework='pt',device='cpu') as a, safe_open(target/'adapter_model.safetensors',framework='pt',device='cpu') as b:
        assert len(a.keys())==len(b.keys())==400
        for key in a.keys():
            mapped=key.replace('base_model.model.model.layers.','base_model.model.model.language_model.layers.',1)
            assert torch.equal(a.get_tensor(key),b.get_tensor(mapped))
    freeze['mapped_adapters'][arm]={'tensor_value_equality':400,'sha256':sha(target/'adapter_model.safetensors')}
(D/'BRIDGE_MAPPING_FREEZE_v2.json').write_text(json.dumps(freeze,indent=2)+'\n')
with (R/'check-effect-v2.log').open('w') as log:
    subprocess.run([sys.executable,str(D/'check_bridge_effect.py')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
print('Mapped inference effect verified for both adapters.',flush=True)
for arm in ['treatment','control']:
    subprocess.run([sys.executable,str(GEN),'--jobs',str(D/'bridge-pilot-jobs.json'),
                    '--out',str(R/f'eval-mapped-{arm}'),'--adapter',str(R/f'train-{arm}/adapter-vllm'),
                    '--samples','1','--cap','32768','--context','45056',
                    '--temperature','1','--top-p','.95','--top-k','20','--presence-penalty','1.5'],env=env,check=True)
    rec=json.loads((R/f'eval-mapped-{arm}/receipt.json').read_text())
    print(json.dumps({'arm':arm,'status':rec['status'],'seconds':rec['elapsed_seconds']}),flush=True)
