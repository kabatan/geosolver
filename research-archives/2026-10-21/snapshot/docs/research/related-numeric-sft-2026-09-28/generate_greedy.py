"""Checkpointed, batched generation for the shared transfer evaluation.

No answer keys are read. Each job has an independent fixed sampling seed.
The same batching and decoding settings must be used in every comparison arm.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")
ROOT = Path(__file__).resolve().parents[3]
META = ROOT / "docs/research/qwen35-self-materials-2026-09-23/model.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--adapter", type=Path)
    ap.add_argument("--cap", type=int, default=32768)
    ap.add_argument("--context", type=int, default=40960)
    ap.add_argument("--batch-size", type=int, default=4)
    args = ap.parse_args()
    if args.batch_size not in (1, 2, 4) or (args.cap, args.context) not in ((32768,40960),(81920,98304),(131072,147456)):
        raise ValueError("Unregistered generation bounds")
    jobs = json.loads(args.jobs.read_text())
    assert jobs and len({j['id'] for j in jobs}) == len(jobs)
    assert all('answer_exact' not in j and 'target' not in j for j in jobs)
    meta = json.loads(META.read_text())
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='running', start_unix=time.time(), driver_sha256=digest(__file__),
                   jobs_sha256=digest(args.jobs), model_metadata_sha256=digest(META),
                   model_revision=meta['revision'], adapter=str(args.adapter.resolve()) if args.adapter else None,
                   adapter_sha256=digest(args.adapter/'adapter_model.safetensors') if args.adapter else None,
                   cap=args.cap, context=args.context, batch_size=args.batch_size, samples=1,
                   temperature=0.0, top_p=1.0, top_k=-1, presence_penalty=0.0,
                   enable_thinking=False, completed_jobs=0)
    write(out/'receipt.json', receipt); started=time.monotonic()
    try:
        from transformers import AutoTokenizer
        from vllm import LLM, SamplingParams
        from vllm.lora.request import LoRARequest
        tokenizer=AutoTokenizer.from_pretrained(meta['snapshot'],local_files_only=True)
        options=dict(model=meta['snapshot'],dtype='bfloat16',kv_cache_dtype='auto',
                     max_model_len=args.context,max_num_seqs=args.batch_size,
                     max_num_batched_tokens=1024,gpu_memory_utilization=0.82,
                     enforce_eager=True,enable_prefix_caching=False,
                     language_model_only=True,seed=2026092419)
        if args.adapter: options.update(enable_lora=True,max_lora_rank=8)
        engine=LLM(**options)
        lora=LoRARequest('study_adapter',1,str(args.adapter.resolve())) if args.adapter else None
        for start in range(0,len(jobs),args.batch_size):
            group=jobs[start:start+args.batch_size]; inputs=[]
            for job in group:
                prompt=tokenizer.apply_chat_template(job['messages'],tokenize=False,add_generation_prompt=True,enable_thinking=False)
                ids=tokenizer.encode(prompt,add_special_tokens=False)
                assert len(ids)+args.cap <= args.context
                inputs.append({'prompt_token_ids':ids})
            params=[SamplingParams(n=1,temperature=0.0,top_p=1.0,top_k=-1,presence_penalty=0.0,
                                   max_tokens=args.cap,seed=j['seed']) for j in group]
            tick=time.monotonic()
            outputs=engine.generate(inputs,params,lora_request=lora)
            elapsed=time.monotonic()-tick
            for job,prompt,result in zip(group,inputs,outputs,strict=True):
                assert list(result.prompt_token_ids)==prompt['prompt_token_ids']
                assert len(result.outputs)==1
                output=result.outputs[0]; ids=list(output.token_ids)
                raw=tokenizer.decode(ids,skip_special_tokens=False)
                write(out/f"{job['id']}-0.json",dict(job,sample=0,model=meta['model_id'],revision=meta['revision'],
                      adapter=receipt['adapter'],prompt_ids=prompt['prompt_token_ids'],raw_text=raw,
                      final_text=raw.split('</think>',1)[-1] if '</think>' in raw else raw,
                      completion_ids=ids,finish_reason=output.finish_reason,
                      elapsed_group_seconds=elapsed,batch_start=start))
                receipt['completed_jobs']+=1
                print(json.dumps({'id':job['id'],'finish':output.finish_reason,'tokens':len(ids),'batch_seconds':elapsed}),flush=True)
            write(out/'receipt.json',receipt)
        receipt['status']='complete'
    except BaseException as error:
        receipt.update(status='failed',error=repr(error)); raise
    finally:
        receipt.update(end_unix=time.time(),elapsed_seconds=time.monotonic()-started)
        write(out/'receipt.json',receipt)


if __name__=='__main__':
    main()
