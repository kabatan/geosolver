"""Run the frozen comparison after formal OPD finishes; serialize every GPU job.

No model result is used to select a training checkpoint or evaluation problem.
Long-budget retries cover the union of capped jobs in every comparison arm.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNTIME = ROOT/'qwen/.runtime'
PYTHON = ROOT/'qwen/.runtime/vllm-venv/bin/python'
GUARD = ROOT/'docs/research/program-self-training-2026-09-26/gpu_job.py'
LIBS = RUNTIME/'answer_opd_pilot_20260926/recovery-nvml59584/extracted/usr/lib/x86_64-linux-gnu'
DESKTOP = RUNTIME/'program_self_training_20260926/gpu-guard-amendment/first-launch-blocked.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--opd-study',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--preflight',action='store_true')
    args=parser.parse_args()
    study=json.loads((args.opd_study/'receipt.json').read_text())
    if study.get('status')!='complete' or study.get('global_updates')!=32:
        raise ValueError('Requires the completed fixed 32-update formal OPD experiment')
    adapters={
        'base':None,
        'code128':RUNTIME/'program_self_training_followup_20260926/train-code128/final/adapter-vllm',
        'numeric128':RUNTIME/'program_self_training_followup_20260926/train-numeric128/final/adapter-vllm',
        'opd32':Path(study['last_checkpoint'])/'adapter-vllm',
    }
    groups={'numeric':'eval-jobs-v2.json','retention':'retention-jobs.json','proof':'secondary-proof-jobs.json'}
    inputs=[Path(__file__),HERE/'generate_batch.py',HERE/'score_numeric.py',
            HERE/'execution-amendment.json',args.opd_study/'receipt.json']
    inputs.extend(HERE/name for name in groups.values())
    inputs.extend(a/'adapter_model.safetensors' for a in adapters.values() if a)
    frozen={str(p.resolve()):digest(p) for p in inputs}
    if args.preflight:
        print(json.dumps({'status':'pass','conditions':list(adapters),'groups':groups,'inputs':frozen}));return
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='running',start_unix=time.time(),inputs=frozen,completed=[],extended_jobs={})
    write(out/'receipt.json',receipt)

    def launch(group,condition,jobs,cap,context):
        if any(digest(p)!=h for p,h in frozen.items()):
            raise RuntimeError('Frozen evaluation input changed')
        label=f'{group}-{condition}-{cap}'
        target=out/label
        command=[PYTHON,HERE/'generate_batch.py','--jobs',jobs,'--out',target,
                 '--cap',str(cap),'--context',str(context),'--batch-size','4']
        if adapters[condition]:command+=['--adapter',adapters[condition]]
        guarded=['python3',GUARD,'--runtime',out/'gpu-jobs','--label',label,
                 '--recovery-libs',LIBS,'--desktop-inventory',DESKTOP,
                 '--input',jobs,'--input',HERE/'generate_batch.py','--',*command]
        with (out/f'{label}.log').open('w') as stream:
            subprocess.run([str(x) for x in guarded],stdout=stream,stderr=subprocess.STDOUT,check=True)
        result=json.loads((target/'receipt.json').read_text())
        if result['status']!='complete':raise RuntimeError(f'Incomplete evaluation: {target}')
        receipt['completed'].append(label);write(out/'receipt.json',receipt)
        print(json.dumps({'complete':label,'seconds':result['elapsed_seconds']}),flush=True)
        return target

    try:
        for group,filename in groups.items():
            jobs=HERE/filename
            results=[launch(group,c,jobs,32768,40960) for c in adapters]
            capped=set()
            for result in results:
                for path in result.glob('*-0.json'):
                    row=json.loads(path.read_text())
                    if row['finish_reason']=='length':capped.add(row['id'])
            if capped:
                subset=[j for j in json.loads(jobs.read_text()) if j['id'] in capped]
                extended_jobs=out/f'{group}-extended-jobs.json';write(extended_jobs,subset)
                receipt['extended_jobs'][group]=dict(ids=sorted(capped),jobs_sha256=digest(extended_jobs))
                write(out/'receipt.json',receipt)
                for condition in adapters:launch(group,condition,extended_jobs,81920,98304)
        receipt['status']='complete'
    except BaseException as error:
        receipt.update(status='failed',error=repr(error));raise
    finally:
        receipt['end_unix']=time.time();write(out/'receipt.json',receipt)


if __name__=='__main__':main()
