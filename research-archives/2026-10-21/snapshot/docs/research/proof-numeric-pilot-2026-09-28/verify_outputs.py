"""Verify completed artifacts before unblinding; never changes a grade."""
import hashlib
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'qwen/.runtime/proof_numeric_pilot_20260928'


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    for filename in ['freeze.json','execution-freeze.json']+(['coordinate-freeze.json'] if (OUT/'coordinate-completion.json').exists() else []):
        for path,digest in read(OUT/filename)['sha256'].items():assert sha(Path(path))==digest,path
    meta=ROOT/'docs/research/qwen35-self-materials-2026-09-23/model.json'
    gen=ROOT/'docs/research/transfer-reanalysis-2026-09-26/generate_batch.py'
    adapter=OUT/'train128/final/adapter-vllm/adapter_model.safetensors'
    counts=[]
    sources=[('proof',OUT/'proof-jobs.json'),('numeric',OUT/'data/numeric-jobs.json')]
    if (OUT/'coordinate-completion.json').exists():sources.append(('coordinate',OUT/'coordinate-jobs.json'))
    for kind,source in sources:
        jobs=read(source)
        assert len(jobs)=={'proof':8,'numeric':12,'coordinate':2}[kind]
        assert len({j['id'] for j in jobs})==len(jobs)
        assert len({j['seed'] for j in jobs})==len(jobs)
        if kind=='proof':
            protocol=(ROOT/'docs/research/proof-numeric-pilot-2026-09-28/PROTOCOL.md').read_text()
            prompt=protocol.split('## 固定した証明prompt\n\n',1)[1].strip()
            assert all(j['messages']==[{'role':'user','content':prompt}] for j in jobs)
        extension=OUT/f'{kind}-extension-jobs.json'
        extended={j['id'] for j in read(extension)} if extension.exists() else set()
        actual_capped=set()
        for arm in ['base','sft']:
            for suffix,jobs_path,cap,context in [('',source,32768,40960)]+([('-81k',extension,81920,98304)] if extended else []):
                rows=read(jobs_path);folder=OUT/f'{arm}-{kind}{suffix}';receipt=read(folder/'receipt.json')
                expected={'status':'complete','completed_jobs':len(rows),'jobs_sha256':sha(jobs_path),
                    'model_revision':read(meta)['revision'],'model_metadata_sha256':sha(meta),'driver_sha256':sha(gen),
                    'cap':cap,'context':context,'batch_size':4,'samples':1,'temperature':.7,
                    'top_p':.95,'top_k':20,'presence_penalty':.2,'enable_thinking':False,
                    'adapter_sha256':sha(adapter) if arm=='sft' else None}
                for k,v in expected.items():assert receipt[k]==v,(folder,k,receipt[k],v)
                assert len(list(folder.glob('AP01-*-0.json')))==len(rows)
                tokens=[];length=[]
                for job in rows:
                    path=folder/f"{job['id']}-0.json";r=read(path)
                    for k,v in job.items():assert r[k]==v,(path,k)
                    assert r['finish_reason'] in ['stop','length']
                    assert len(r['completion_ids'])<=cap
                    assert bool(r['adapter'])==(arm=='sft')
                    counterpart=OUT/f"{'sft' if arm=='base' else 'base'}-{kind}{suffix}"/path.name
                    assert r['prompt_ids']==read(counterpart)['prompt_ids']
                    if r['finish_reason']=='length':
                        length.append(job['id'])
                        if not suffix:actual_capped.add(job['id'])
                    tokens.append(len(r['completion_ids']))
                counts.append({'arm':arm,'kind':kind,'cap':cap,'count':len(rows),'length_jobs':length,
                               'tokens_total':sum(tokens),'tokens_min':min(tokens),'tokens_max':max(tokens),
                               'tokens_median':statistics.median(tokens),'elapsed_seconds':receipt['elapsed_seconds']})
        assert actual_capped==extended,(kind,actual_capped,extended)
    final=read(OUT/'train128/final/receipt.json')
    assert final['global_updates']==final['optimizer_step_min']==final['optimizer_step_max']==128
    assert final['dataset_sha256']==sha(OUT/'data/train.json')
    assert final['vllm_adapter_sha256']==sha(adapter)
    order=read(OUT/'train128/example-order.json')
    assert len(order)==512 and {r['epoch'] for r in order}=={0,1}
    assert all(sum(r['id']==k for r in order)==2 for k in {r['id'] for r in order})
    key=read(OUT/'blind-private-key.json')
    for cid,row in key.items():
        source=Path(row['source']);assert sha(source)==row['source_sha256']
        blind=read(OUT/'blind'/f'{cid}.json');r=read(source)
        assert blind['raw_text']==r['raw_text'] and blind['messages']==r['messages']
    coordinate_cases=0
    if (OUT/'coordinate-completion.json').exists():
        coord_key=read(OUT/'coordinate-private-key.json')
        assert len(coord_key)==4
        for cid,row in coord_key.items():
            source=Path(row['source']);assert sha(source)==row['source_sha256']
            blind=read(OUT/'coordinate-review'/f'{cid}.json');r=read(source)
            assert blind['raw_text']==r['raw_text'] and blind['messages']==r['messages']
        coordinate_cases=len(coord_key)
    result={'status':'pass','generation_runs':counts,'global_training_updates':128,
            'training_examples_presented':512,'unique_training_examples':256,
            'training_seconds':sum(read(OUT/name/'receipt.json')['elapsed_seconds'] for name in ['train32','train128']),
            'data_generation_seconds':read(OUT/'data/receipt.json')['elapsed_seconds'],
            'numeric_label_audit':read(OUT/'data-audit.json'),'blinded_cases_verified':len(key)+coordinate_cases}
    (OUT/'integrity-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
