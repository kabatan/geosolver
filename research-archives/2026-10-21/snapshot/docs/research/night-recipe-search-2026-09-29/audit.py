"""Mechanical campaign audit: frozen inputs, checkpoints, and paired prompts."""
import json,collections
from pathlib import Path
from campaign import RUN,ROOT,read,write,sha,verify_manifest
def main():
    verify_manifest();training=[];generation=[]
    for p in sorted((RUN/'train').glob('*/receipt.json')):
        r=read(p);assert r['status']=='complete',(p,r['status']);final=p.parent/'final';f=read(final/'receipt.json')
        for key,name in [('adapter_sha256','adapter/adapter_model.safetensors'),('vllm_adapter_sha256','adapter-vllm/adapter_model.safetensors'),('optimizer_sha256','optimizer.pt')]:assert r[key]==f[key]==sha(final/name)
        assert r['global_updates']==r['planned_updates']==r['optimizer_step_min']==r['optimizer_step_max']
        assert r['saved_adapter_tensors_verified']==r['vllm_adapter_tensors_verified']==r['optimizer_state_entries']==400
        assert r['changed_lora_tensors']==400 and r['cpu_check']['status']=='pass'
        training.append(dict(path=str(p),global_updates=r['global_updates'],dataset_sha256=r['dataset_sha256'],processed_order_sha256=r['processed_order_sha256'],seed=r['training_parameters']['seed'],elapsed_seconds=r['elapsed_seconds'],peak_allocated_gib=r['peak_allocated_gib'],planned_target_tokens=r['planned_target_tokens'],trained_target_tokens=r['trained_target_tokens']))
    paired=collections.defaultdict(list)
    for d in sorted((RUN/'outputs').iterdir()):
        r=read(d/'receipt.json');files=list(d.glob('*-0.json'))
        assert r['status']=='complete' and len(files)==r['completed_jobs'],(d,r['status'])
        assert r['model_revision']=='c202236235762e1c871ad0ccb60c8ee5ba337b9a'
        assert r['batch_size']==4 and r['samples']==1 and r['enable_thinking'] is False
        if r['adapter']:assert r['adapter_sha256']==sha(Path(r['adapter'])/'adapter_model.safetensors')
        arm,seed,kind,*_=d.name.split('-')
        for p in files:
            out=read(p);assert out['revision']==r['model_revision'];assert out['finish_reason'] in ('stop','length');assert len(out['completion_ids'])<=r['cap']
            assert 'target' not in out and 'answer_exact' not in out
            paired[(kind,out['id'],r['cap'])].append(dict(arm=arm,seed=out['seed'],messages=out['messages'],prompt_ids=out['prompt_ids'],batch_start=out['batch_start']))
        generation.append(dict(directory=str(d),n=len(files),elapsed_seconds=r['elapsed_seconds'],cap=r['cap'],jobs_sha256=r['jobs_sha256'],adapter_sha256=r['adapter_sha256']))
    for key,group in paired.items():
        reference={k:group[0][k] for k in ['seed','messages','prompt_ids','batch_start']}
        for row in group[1:]:assert {k:row[k] for k in reference}==reference,(key,row['arm'],'unequal paired input or batching')
    result=dict(status='pass',frozen_files=len(read(RUN/'frozen-manifest.json')['sha256']),training=training,generation=generation,paired_comparisons=len(paired),total_output_files=sum(g['n'] for g in generation),note='Equal per-job prompts/token IDs/seeds/batch position verified across each compared kind and cap. Numerical and reasoning grades are separate.')
    write(RUN/'mechanical-audit.json',result);print(json.dumps(dict(status='pass',checkpoints=len(training),generation_runs=len(generation),output_files=result['total_output_files'],paired_comparisons=len(paired))))
if __name__=='__main__':main()
