"""Audit immutable inputs, full training chains, model identity, and evaluation."""
import collections,json,statistics,time
from pathlib import Path
import run_study as op
P,R,O=op.P,op.R,op.O

def main():
    checks=[]
    for file,digest in op.read(O/'freeze.json')['sha256'].items():assert op.sha(Path(file))==digest,file
    checks.append('Every frozen input, config, driver, and prior-checkpoint hash matches')
    chains={'correct':[op.OLD/'sft-a-train32',op.OLD/'sft-a-train128',O/'correct-train512'],
            'shuffled':[O/'shuffled-train32',O/'shuffled-train128',O/'shuffled-train512']}
    training={};orders={}
    for arm,chain in chains.items():
        dataset=op.read(O/f'train-{arm}.json');dataset_hash=op.sha(O/f'train-{arm}.json')
        events=[];stage_seconds=0;last_receipt=None
        for stage,steps in zip(chain,[32,128,512],strict=True):
            r=op.read(stage/'receipt.json');final=op.read(stage/'final/receipt.json')
            assert r['status']==final['status']=='complete'
            assert r['global_updates']==final['global_updates']==r['optimizer_step_min']==r['optimizer_step_max']==steps
            assert r['dataset_sha256']==dataset_hash and r['training_parameters']['seed']==2026092701
            assert r['driver_sha256']==op.sha(op.TRAIN)
            assert r['loss_mask']=='assistant target including EOS only'
            assert final['adapter_sha256']==op.sha(stage/'final/adapter/adapter_model.safetensors')
            assert final['vllm_adapter_sha256']==op.sha(stage/'final/adapter-vllm/adapter_model.safetensors')
            assert final['optimizer_sha256']==op.sha(stage/'final/optimizer.pt')
            if last_receipt:
                assert r['optimizer_state_loaded'] is True
                assert r['prior_adapter_sha256']==last_receipt['adapter_sha256']
                assert r['prior_optimizer_sha256']==last_receipt['optimizer_sha256']
                assert r['training_parameters']==last_receipt['training_parameters']
            else:assert r['optimizer_state_loaded'] is False
            last_receipt=final;stage_seconds+=r['elapsed_seconds']
            local=[json.loads(line) for line in (stage/'examples.jsonl').read_text().splitlines()]
            assert len(local)==r['examples_processed']
            events+=local
        assert [r['position'] for r in events]==list(range(2048))
        order=op.read(chain[-1]/'example-order.json')
        assert [(r['id'],r['epoch']) for r in events]==[(r['id'],r['epoch']) for r in order]
        assert set(r['id'] for r in events)==set(r['id'] for r in dataset)
        counts=collections.Counter(r['id'] for r in events)
        assert set(counts.values())=={25,26}
        first={};last={}
        for r in events:first.setdefault(r['id'],r['loss']);last[r['id']]=r['loss']
        orders[arm]=[(r['id'],r['epoch']) for r in order]
        training[arm]={'global_updates':512,'examples_presented':len(events),'presentations_min':min(counts.values()),
                       'presentations_max':max(counts.values()),'target_tokens':sum(r['target_tokens'] for r in events),
                       'first_presentation_mean_ce':statistics.mean(first.values()),'last_presentation_mean_ce':statistics.mean(last.values()),
                       'chain_training_seconds':stage_seconds,'final_adapter_sha256':last_receipt['adapter_sha256']}
    assert orders['correct']==orders['shuffled']
    checks.append('Both 32→128→512 chains: optimizer/adapters/order checked; identical 2048 presentation IDs')
    assert op.read(O/'fit-generation-complete.json')['status']=='complete'
    scores=op.read(O/'fit-scores.json');jobs={j['id']:j for j in op.read(O/'fit-jobs.json')};caps=op.read(O/'final-cap-by-job.json')
    assert len(jobs)==110 and len(scores['rows'])==440
    for arm in op.ARMS:
        rows=[r for r in scores['rows'] if r['arm']==arm]
        assert {r['job_id'] for r in rows}==set(jobs)
        for row in rows:
            path=Path(row['file']);raw=op.read(path);receipt=op.read(path.parent/'receipt.json');job=jobs[row['job_id']]
            assert row['file_sha256']==op.sha(path)
            assert receipt['status']=='complete' and receipt['driver_sha256']==op.sha(op.DRIVER)
            assert row['cap']==receipt['cap']==caps.get(row['job_id'],32768)
            assert raw['messages']==job['messages'] and raw['seed']==job['seed']
            assert raw['revision']==receipt['model_revision']=='c202236235762e1c871ad0ccb60c8ee5ba337b9a'
            adapter=op.ADAPTERS[arm]
            assert receipt['adapter']==raw['adapter']==(str(adapter) if adapter else None)
            assert receipt['adapter_sha256']==(op.sha(adapter/'adapter_model.safetensors') if adapter else None)
            for k,v in {'temperature':0.,'top_p':1.,'top_k':-1,'presence_penalty':0.,'enable_thinking':False,'batch_size':4}.items():assert receipt[k]==v
        checks.append(f'{arm}: all 110 outputs, identities, prompts, seeds, caps, and decoding match')
    previous=list(jobs.values())
    for old,new in [(32768,81920),(81920,131072)]:
        suffix='' if old==32768 else '-'+str(old)
        needed={j['id'] for j in previous if any(op.read(O/f'{a}-fit{suffix}'/(j['id']+'-0.json'))['finish_reason']=='length' for a in op.ARMS)}
        file=O/f'fit-extension-{new}-jobs.json';next_jobs=op.read(file) if file.exists() else []
        assert needed=={j['id'] for j in next_jobs}
        previous=next_jobs
    checks.append('Adaptive extensions exactly match the union of unfinished responses')
    computation=[]
    for file in sorted(op.SH.glob('dose-control-*-20260928/receipt.json')):
        r=op.read(file);assert r['status']=='complete'
        computation.append({'stage':file.parent.name,'seconds':r['elapsed_seconds']})
    result={'status':'complete','unix':time.time(),'checks':checks,'training':training,
            'new_guarded_wall_seconds':sum(x['seconds'] for x in computation),'computation':computation,
            'fit_scores_sha256':op.sha(O/'fit-scores.json'),'transfer_gate':scores['transfer_gate']}
    op.write(O/'integrity-audit.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
