"""One-token vLLM control: base and LoRA log probabilities in one engine."""
import os
os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
import argparse
import json
from pathlib import Path

from transformers import AutoTokenizer
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest

from qwen.common import now, write_json

HERE = Path(__file__).resolve().parent
MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")


def main(args):
    meta = json.loads(MODEL.read_text())
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    prompts = {
        "train-H01": json.loads((HERE / "train-multiconfig.json").read_text())[0]["prompt"],
        "eval-EV02": json.loads((HERE / "proof-eval-jobs.json").read_text())[0]["prompt"],
    }
    llm = LLM(model=meta["snapshot"], dtype="bfloat16", max_model_len=4096,
              max_num_seqs=1, max_num_batched_tokens=1024, gpu_memory_utilization=0.8,
              enforce_eager=True, language_model_only=True, enable_lora=True,
              max_lora_rank=32, seed=2026092401)
    request = LoRARequest("self_sft", 1, str(Path(args.adapter).resolve()))
    rows = []
    for name, prompt in prompts.items():
        rendered = tokenizer.apply_chat_template([{"role": "user", "content": prompt}],
                                                 tokenize=False, add_generation_prompt=True,
                                                 enable_thinking=False)
        ids = tokenizer.encode(rendered, add_special_tokens=False)
        params = SamplingParams(temperature=0, max_tokens=1, logprobs=20)
        base = llm.generate([{"prompt_token_ids": ids}], params)[0].outputs[0]
        lora = llm.generate([{"prompt_token_ids": ids}], params, lora_request=request)[0].outputs[0]
        bp = {int(k): float(v.logprob) for k,v in base.logprobs[0].items()}
        lp = {int(k): float(v.logprob) for k,v in lora.logprobs[0].items()}
        shared = set(bp) & set(lp)
        rows.append(dict(id=name, base_token=base.token_ids[0], adapter_token=lora.token_ids[0],
                         common_top_tokens=len(shared),
                         max_abs_common_logprob_difference=max(abs(bp[k]-lp[k]) for k in shared),
                         top1_base_logprob=bp[base.token_ids[0]],
                         top1_adapter_logprob=lp[lora.token_ids[0]]))
    write_json(args.out, dict(created_utc=now(), adapter=args.adapter, rows=rows))
    print(json.dumps(rows), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--adapter", required=True)
    p.add_argument("--out", required=True)
    main(p.parse_args())
