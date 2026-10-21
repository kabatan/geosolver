"""Direct HF forward check of base versus a saved LoRA adapter on fixed prompts."""
import argparse
import json
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from qwen.common import file_hash, now, write_json

HERE = Path(__file__).resolve().parent
MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")


def main(args):
    meta = json.loads(MODEL.read_text())
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    examples = json.loads((HERE / "train-multiconfig.json").read_text())
    eval_jobs = json.loads((HERE / "proof-eval-jobs.json").read_text())
    prompts = {"train-H01": examples[0]["prompt"], "eval-EV02": eval_jobs[0]["prompt"]}
    model = AutoModelForCausalLM.from_pretrained(meta["snapshot"], dtype=torch.bfloat16,
                                                device_map="cuda", attn_implementation="sdpa",
                                                local_files_only=True).eval()

    def logits(prompt):
        rendered = tokenizer.apply_chat_template([{"role": "user", "content": prompt}],
                                                 tokenize=False, add_generation_prompt=True,
                                                 enable_thinking=False)
        ids = tokenizer.encode(rendered, add_special_tokens=False)
        with torch.no_grad():
            return model(input_ids=torch.tensor([ids], device="cuda"),
                         use_cache=False, logits_to_keep=1).logits[0, -1].float().cpu()

    base = {id: logits(prompt) for id, prompt in prompts.items()}
    model = PeftModel.from_pretrained(model, args.adapter, is_trainable=False).eval()
    rows = []
    for id, prompt in prompts.items():
        adapted = logits(prompt)
        original = base[id]
        delta = adapted - original
        rows.append(dict(id=id, max_abs_logit_difference=float(delta.abs().max()),
                         mean_abs_logit_difference=float(delta.abs().mean()),
                         changed_logits=int(torch.count_nonzero(delta)),
                         base_top1=int(original.argmax()), adapter_top1=int(adapted.argmax())))
    write_json(args.out, dict(created_utc=now(), adapter=args.adapter,
                              adapter_sha256=file_hash(Path(args.adapter) / "adapter_model.safetensors"),
                              model_revision=meta["revision"], rows=rows))
    print(json.dumps(rows), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--adapter", required=True)
    p.add_argument("--out", required=True)
    main(p.parse_args())
