"""EOS-loss ablation on the fixed external-teacher Qwen3.5-9B answers."""
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

import argparse
import gc
import importlib.metadata
import json
import random
import time
from pathlib import Path

import torch
from peft import LoraConfig, TaskType, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

from qwen.common import file_hash, now, write_json

MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")


def main(args):
    spec = json.loads(Path(args.protocol).read_text())
    source = Path(spec["dataset"])
    assert file_hash(source) == spec["dataset_sha256"]
    assert file_hash(spec["eval_jobs"]) == spec["eval_jobs_sha256"]
    meta = json.loads(MODEL.read_text())
    assert meta["revision"] == spec["model_revision"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    receipt = dict(status="running", start_utc=now(), updates=0,
                   protocol_sha256=file_hash(args.protocol), driver_sha256=file_hash(__file__),
                   dataset_sha256=file_hash(source), model_revision=meta["revision"],
                   versions={n: importlib.metadata.version(n) for n in ("torch", "transformers", "peft")})
    write_json(out / "receipt.json", receipt)
    start = time.monotonic()
    try:
        random.seed(spec["seed"])
        torch.manual_seed(spec["seed"])
        torch.cuda.manual_seed_all(spec["seed"])
        tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
        data = []
        for row in json.loads(source.read_text()):
            answer = row["answer"].strip()
            assert "<|im_" not in answer and "<think>" not in answer and "</think>" not in answer
            prompt = tokenizer.apply_chat_template(
                [{"role": "user", "content": row["prompt"]}], tokenize=False,
                add_generation_prompt=True, enable_thinking=False)
            full = tokenizer.apply_chat_template(
                [{"role": "user", "content": row["prompt"]},
                 {"role": "assistant", "content": answer}], tokenize=False,
                enable_thinking=False)
            assert full.startswith(prompt), row["id"]
            # The Qwen chat template places a newline after <|im_end|>.
            # Predict through EOS, excluding that trailing separator newline.
            answer_text = full[len(prompt):].rstrip()
            prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
            answer_ids = tokenizer.encode(answer_text, add_special_tokens=False)
            assert answer_ids[-1] == tokenizer.eos_token_id and len(answer_ids) > 20
            assert len(prompt_ids) + len(answer_ids) <= spec["max_sequence_tokens"], row["id"]
            data.append(dict(id=row["id"], source=row["source"], prompt=prompt_ids, answer=answer_ids))
        assert len(data) == spec["n_examples"]
        assert len(set(x["source"] for x in data)) == spec["n_configurations"]
        write_json(out / "tokenization.json", [dict(id=x["id"], source=x["source"],
                   prompt_tokens=len(x["prompt"]), answer_tokens=len(x["answer"])) for x in data])
        receipt.update(n_examples=len(data), n_configurations=spec["n_configurations"],
                       answer_tokens_per_epoch=sum(len(x["answer"]) for x in data),
                       max_sequence_tokens=max(len(x["prompt"])+len(x["answer"]) for x in data),
                       loss_mask="Predict assistant answer except final EOS")
        model = AutoModelForCausalLM.from_pretrained(
            meta["snapshot"], dtype=torch.bfloat16, device_map="cuda",
            attn_implementation="sdpa", local_files_only=True)
        model = get_peft_model(model, LoraConfig(
            r=spec["lora_rank"], lora_alpha=spec["lora_alpha"],
            lora_dropout=0.0, target_modules=spec["modules"], bias="none",
            task_type=TaskType.CAUSAL_LM))
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
        model.train()
        trainable = [p for p in model.parameters() if p.requires_grad]
        assert trainable and all("lora_" in n for n,p in model.named_parameters() if p.requires_grad)
        receipt["trainable_parameters"] = sum(p.numel() for p in trainable)
        before = {n: p.detach().float().cpu().clone() for n,p in model.named_parameters() if p.requires_grad}
        optimizer = torch.optim.AdamW(trainable, lr=spec["lr"], weight_decay=0)
        torch.cuda.reset_peak_memory_stats()
        train_start = time.monotonic()
        for epoch in range(spec["epochs"]):
            order = list(range(len(data)))
            random.Random(spec["seed"]+epoch).shuffle(order)
            for idx in order:
                row = data[idx]
                tick = time.monotonic()
                ids = torch.tensor([row["prompt"]+row["answer"]], dtype=torch.long, device="cuda")
                target = torch.tensor(row["answer"][:-1], dtype=torch.long, device="cuda")
                optimizer.zero_grad(set_to_none=True)
                output = model(input_ids=ids, use_cache=False, logits_to_keep=len(row["answer"])+1)
                logits = output.logits[0, :-2, :].float()
                assert logits.shape[0] == len(target)
                loss = torch.nn.functional.cross_entropy(logits, target)
                assert torch.isfinite(loss)
                loss.backward()
                norm = torch.nn.utils.clip_grad_norm_(trainable, spec["grad_clip"])
                assert torch.isfinite(norm)
                optimizer.step()
                torch.cuda.synchronize()
                receipt["updates"] += 1
                event = dict(update=receipt["updates"], epoch=epoch, id=row["id"],
                             loss=float(loss.detach()), grad_norm=float(norm),
                             seconds=time.monotonic()-tick)
                with (out / "updates.jsonl").open("a") as f:
                    f.write(json.dumps(event)+"\n")
                print(json.dumps(event), flush=True)
                del output, logits, loss, ids, target
        receipt.update(training_seconds=time.monotonic()-train_start,
                       peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
                       peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30,
                       changed_tensors=sum(not torch.equal(before[n], p.detach().float().cpu())
                                           for n,p in model.named_parameters() if n in before))
        assert receipt["changed_tensors"] > 0
        del optimizer, before
        gc.collect()
        torch.cuda.empty_cache()
        model.eval()
        check = torch.tensor([data[0]["prompt"]], dtype=torch.long, device="cuda")
        with torch.no_grad():
            expected = model(input_ids=check, use_cache=False, logits_to_keep=1).logits[:,-1,:].float().cpu()
        model.save_pretrained(out / "adapter")
        tokenizer.save_pretrained(out / "tokenizer")
        # Promote newly allocated adapter weights before loading to preserve FP32 LoRA.
        expected_weights = {n.replace(".default.", ".reloaded."): p.detach().cpu().clone()
                            for n,p in model.named_parameters() if "lora_" in n}
        model.delete_adapter("default")
        model.add_adapter("reloaded", LoraConfig.from_pretrained(out / "adapter"))
        for n,p in model.named_parameters():
            if ".reloaded." in n:
                p.data = p.data.float()
        model.load_adapter(out / "adapter", adapter_name="reloaded", is_trainable=False)
        model.set_adapter("reloaded")
        model.eval()
        receipt["reload_equal_tensors"] = sum(torch.equal(expected_weights[n],p.detach().cpu())
                                               for n,p in model.named_parameters() if n in expected_weights)
        assert receipt["reload_equal_tensors"] == len(expected_weights)
        with torch.no_grad():
            actual = model(input_ids=check, use_cache=False, logits_to_keep=1).logits[:,-1,:].float().cpu()
        receipt["reload_max_abs_logit_difference"] = float((expected-actual).abs().max())
        assert torch.allclose(expected, actual, atol=1e-4, rtol=1e-4)
        receipt.update(status="complete", adapter_sha256=file_hash(out / "adapter/adapter_model.safetensors"))
    except BaseException as error:
        receipt.update(status="failed", error=repr(error))
        raise
    finally:
        receipt.update(end_utc=now(), elapsed_seconds=time.monotonic()-start)
        write_json(out / "receipt.json", receipt)
        print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--out", required=True)
    main(parser.parse_args())
