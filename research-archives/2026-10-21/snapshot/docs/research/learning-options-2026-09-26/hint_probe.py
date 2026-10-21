"""Small paired inference diagnostic, not training or a transfer experiment."""
import os
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
os.environ.setdefault('VLLM_USE_FLASHINFER_SAMPLER', '0')
os.environ.setdefault('PYTORCH_ALLOC_CONF', 'expandable_segments:True')
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'qwen/.runtime/learning_options_20260926/hint_probe'

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def prepare():
    sources = ROOT/'docs/research/qwen35-external-teacher-2026-09-24/train.json'
    labels = ROOT/'benchmarks/humpty_configurations_v2/training_problems.jsonl'
    teachers = {r['source']:r for r in json.loads(sources.read_text())}
    answers = {r['id']:r['answer_exact'] for r in map(json.loads, labels.read_text().splitlines())}
    jobs = []
    instruction = ('Solve this geometry problem, showing a mathematically valid derivation '
                   'of the exact answer. Coordinates, vectors, or synthetic geometry are all '
                   'allowed. Justify the decisive geometric claims; numerical agreement alone '
                   'is not a proof. Write in English.\n\n')
    for i, name in enumerate(['H04','H07','DA05','H14']):
        # Existing teacher answers are NOT read into model-facing prompts.
        original = teachers[name]['prompt']
        assert '\n\n' in original
        problem = original.split('\n\n',1)[1]
        for condition in ['no_hint','numeric_hint']:
            prompt = instruction + problem
            if condition == 'numeric_hint':
                prompt += ('\n\nAn independent numerical computation gives the exact final '
                           f'answer {answers[name]}. No geometric relation or derivation is supplied. '
                           'Use this only as an endpoint check; do not assume an unproved '
                           'relation just because it yields this value.')
            jobs.append(dict(id=f'{name}-{condition}',source=name,condition=condition,
                             problem=problem,prompt=prompt,seed=2026092611+i,
                             reference=answers[name]))
    protocol = dict(scope='Paired answer-hint inference diagnostic; zero weight updates',
        n=8,configurations=4,samples_per_condition=1,
        selection='Four reused development configurations, chosen before generation: two with prior self-proof material and two difficult cases. Not a random sample.',
        source_labels='Existing audited numeric labels, not newly generated solver outputs',
        max_output_tokens=32768,max_context=45056,max_num_seqs=2,
        sampling=dict(temperature=1.0,top_p=.95,top_k=20,presence_penalty=1.5),
        enable_thinking=False,watchdog_seconds=2700,
        outcomes=['complete valid derivation','decisive claim proved','finish reason','tokens','time'],
        exclusions='Do not count hinted numeric-answer accuracy as improvement. No human correction of generated reasoning. Truncation is reported, not silently excluded.',
        limitation='One sample per condition; prompt conditioning is not a weight-learning or causal population effect.',
        sources_sha256=digest(sources),labels_sha256=digest(labels),driver_sha256=digest(__file__))
    HERE.mkdir(exist_ok=True,parents=True)
    for name,value in [('hint-probe-jobs.json',jobs),('hint-probe-protocol.json',protocol)]:
        p=HERE/name
        assert not p.exists(),p
        p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'prepared':8,'jobs_sha256':digest(HERE/'hint-probe-jobs.json')}))

def worker():
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    protocol=json.loads((HERE/'hint-probe-protocol.json').read_text())
    jobs=json.loads((HERE/'hint-probe-jobs.json').read_text())
    meta=json.loads((ROOT/'docs/research/foundation-pilot-2026-09-23/qwen35_9b-model.json').read_text())
    tok=AutoTokenizer.from_pretrained(meta['snapshot'],local_files_only=True)
    model=LLM(model=meta['snapshot'],dtype='bfloat16',kv_cache_dtype='auto',
        max_model_len=45056,max_num_seqs=2,max_num_batched_tokens=1024,
        gpu_memory_utilization=.85,enforce_eager=True,enable_prefix_caching=False,
        language_model_only=True,seed=2026092611)
    for offset in range(0,len(jobs),2):
        group=jobs[offset:offset+2]
        texts=[tok.apply_chat_template([{'role':'user','content':r['prompt']}],
            tokenize=False,add_generation_prompt=True,enable_thinking=False) for r in group]
        ids=[tok.encode(t,add_special_tokens=False) for t in texts]
        assert all(len(x)+32768<=45056 for x in ids)
        params=[SamplingParams(n=1,seed=r['seed'],max_tokens=32768,**protocol['sampling']) for r in group]
        started=time.monotonic()
        outputs=model.generate([{'prompt_token_ids':x} for x in ids],params)
        elapsed=time.monotonic()-started
        for row,token_ids,text,result in zip(group,ids,texts,outputs):
            assert list(result.prompt_token_ids)==token_ids
            c=result.outputs[0]
            record=row|dict(model_revision=meta['revision'],raw_text=tok.decode(c.token_ids,skip_special_tokens=False),
                completion_ids=list(c.token_ids),prompt_ids=token_ids,prompt_text=text,
                tokens=len(c.token_ids),finish_reason=c.finish_reason,paired_batch_seconds=elapsed)
            (OUT/(row['id']+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps({k:record[k] for k in ['id','tokens','finish_reason','paired_batch_seconds']}),flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--worker',action='store_true');args=ap.parse_args()
    if args.prepare:return prepare()
    if args.worker:return worker()
    from qwen.grpo_run import run_worker
    OUT.mkdir(exist_ok=False,parents=True)
    receipt=dict(status='running',updates=0,driver_sha256=digest(__file__),
        jobs_sha256=digest(HERE/'hint-probe-jobs.json'),protocol_sha256=digest(HERE/'hint-probe-protocol.json'))
    start=time.monotonic()
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    try:
        run_worker([sys.executable,str(Path(__file__).resolve()),'--worker'],OUT/'generate.log',2700)
        receipt['status']='complete'
    except BaseException as exc:
        receipt.update(status='failed',error=repr(exc));raise
    finally:
        receipt['elapsed_seconds']=time.monotonic()-start
        (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
