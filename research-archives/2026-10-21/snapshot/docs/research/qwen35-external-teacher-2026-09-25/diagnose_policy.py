"""Small teacher-forced diagnostics for external-teacher LoRA adapters.

This is a mechanism probe, not a proof or transfer evaluator. It uses common
prefixes for every model and records exact model/data hashes in its receipt.
"""

import argparse
import hashlib
import json
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")
TRAIN = Path("docs/research/qwen35-external-teacher-2026-09-24/train.json")
BASE_NUMERIC = Path("qwen/.runtime/qwen35_diverse_sft_20260924/eval-numeric-base-en-32k")
BASE_PROOF = Path("qwen/.runtime/qwen35_diverse_sft_20260924/eval-proof-base-en-32k")

RELATIONS = {
    "H01": (
        "AP=AM-(BC/2)^2/AM.",
        "AP=sqrt(AM^2-(BC/2)^2).",
    ),
    "H02": (
        "Z1Z2=|D1D2|*AM/AK.",
        "Z1Z2=|D1D2|*AK/AM.",
    ),
    "H13": (
        "CZ=BK/(2*sin(angle ACB)).",
        "CZ=BK*sin(angle ACB)/2.",
    ),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--high", required=True)
    p.add_argument("--low", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    meta = json.loads(MODEL.read_text())
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    train = {x["source"]: x for x in json.loads(TRAIN.read_text())}
    model = AutoModelForCausalLM.from_pretrained(
        meta["snapshot"], dtype=torch.bfloat16, device_map="cuda",
        attn_implementation="sdpa", local_files_only=True)
    model = PeftModel.from_pretrained(model, args.high, adapter_name="high")
    model.load_adapter(args.low, adapter_name="low", is_trainable=False)
    model.eval()
    torch.cuda.reset_peak_memory_stats()

    def prompt_ids(content):
        rendered = tokenizer.apply_chat_template(
            [{"role": "user", "content": content}], tokenize=False,
            add_generation_prompt=True, enable_thinking=False)
        return tokenizer.encode(rendered, add_special_tokens=False)

    def logits(ids, arm):
        model.set_adapter("high" if arm == "base" else arm)
        with torch.no_grad():
            x = torch.tensor([ids], device="cuda")
            if arm == "base":
                with model.disable_adapter():
                    y = model(input_ids=x, use_cache=False, logits_to_keep=1).logits[0, -1]
            else:
                y = model(input_ids=x, use_cache=False, logits_to_keep=1).logits[0, -1]
        return y.float()

    rows = []
    for key, (correct, false) in RELATIONS.items():
        # Check whether the adapter actually raised likelihood of its own
        # admitted teacher, independently of free-generation correctness.
        teacher_prompt = prompt_ids(train[key]["prompt"])
        teacher_answer = tokenizer.encode(train[key]["answer"], add_special_tokens=False)
        for arm in ("base", "high", "low"):
            model.set_adapter("high" if arm == "base" else arm)
            with torch.no_grad():
                x = torch.tensor([teacher_prompt + teacher_answer], device="cuda")
                if arm == "base":
                    with model.disable_adapter():
                        output = model(input_ids=x, use_cache=False,
                                       logits_to_keep=len(teacher_answer)+1)
                else:
                    output = model(input_ids=x, use_cache=False,
                                   logits_to_keep=len(teacher_answer)+1)
                l = output.logits[0, :-1].float()
                target = torch.tensor(teacher_answer, device="cuda")
                lp = torch.log_softmax(l, dim=-1).gather(1, target[:, None])[:, 0]
            rows.append(dict(kind="teacher_answer_nll", config=key, arm=arm,
                             tokens=len(teacher_answer), mean_nll=float(-lp.mean())))

        problem = train[key]["prompt"].split("\n\n", 1)[-1]
        content = (
            "For the following geometry construction, state only the general "
            "relation that gives the requested quantity. Write an equation, "
            "without a numerical substitution or explanation.\n\n" + problem
        )
        ids = prompt_ids(content)
        for arm in ("base", "high", "low"):
            for label, relation in (("true", correct), ("false", false)):
                answer = tokenizer.encode(relation, add_special_tokens=False)
                model.set_adapter("high" if arm == "base" else arm)
                with torch.no_grad():
                    x = torch.tensor([ids + answer], device="cuda")
                    if arm == "base":
                        with model.disable_adapter():
                            output = model(input_ids=x, use_cache=False,
                                           logits_to_keep=len(answer)+1)
                    else:
                        output = model(input_ids=x, use_cache=False,
                                       logits_to_keep=len(answer)+1)
                    l = output.logits[0, :-1].float()
                    target = torch.tensor(answer, device="cuda")
                    lp = torch.log_softmax(l, dim=-1).gather(1, target[:, None])[:, 0]
                rows.append(dict(kind="relation_nll", config=key, arm=arm,
                                 label=label, tokens=len(answer),
                                 mean_nll=float(-lp.mean()), total_nll=float(-lp.sum())))

        # This gives the correct relation in the prompt and therefore probes
        # recognition, not unaided relation selection.
        a, b = (correct, false) if key != "H02" else (false, correct)
        choice = ("Which relation is valid for the construction below? Reply "
                  "with A or B only.\n\n" + problem + "\n\nA. " + a + "\nB. " + b)
        choice_ids = prompt_ids(choice)
        a_id = tokenizer.encode("A", add_special_tokens=False)
        b_id = tokenizer.encode("B", add_special_tokens=False)
        assert len(a_id) == len(b_id) == 1
        for arm in ("base", "high", "low"):
            lp = torch.log_softmax(logits(choice_ids, arm), dim=-1)
            rows.append(dict(kind="relation_choice", config=key, arm=arm,
                             correct_option="B" if key == "H02" else "A",
                             logprob_A=float(lp[a_id[0]]), logprob_B=float(lp[b_id[0]])))

    common_prefixes = [
        ("numeric-H01", BASE_NUMERIC / "diverse-en-eval-H01-d1-0-0.json"),
        ("proof-EV02", BASE_PROOF / "diverse-en-proof-EV02-0.json"),
    ]
    for name, path in common_prefixes:
        item = json.loads(path.read_text())
        prompt = item["prompt_ids"]
        answer = item["completion_ids"]
        for prefix_len in (0, 128, 256, 512, 768, 1024):
            assert len(answer) >= prefix_len
            ids = prompt + answer[:prefix_len]
            lp = {}
            for arm in ("base", "high", "low"):
                lp[arm] = torch.log_softmax(logits(ids, arm), dim=-1)
                rows.append(dict(kind="eos_hazard", prompt=name, arm=arm,
                                 prefix_tokens=prefix_len,
                                 eos_logprob=float(lp[arm][tokenizer.eos_token_id])))
            base_p = lp["base"].exp()
            for arm in ("high", "low"):
                rows.append(dict(kind="base_to_adapter_kl", prompt=name, arm=arm,
                                 prefix_tokens=prefix_len,
                                 kl_nats=float((base_p * (lp["base"]-lp[arm])).sum())))

    output = {
        "model_revision": meta["revision"],
        "model_metadata_sha256": sha(MODEL),
        "dataset_sha256": sha(TRAIN),
        "base_numeric_sha256": sha(common_prefixes[0][1]),
        "base_proof_sha256": sha(common_prefixes[1][1]),
        "high_adapter_sha256": sha(Path(args.high) / "adapter_model.safetensors"),
        "low_adapter_sha256": sha(Path(args.low) / "adapter_model.safetensors"),
        "driver_sha256": sha(__file__),
        "peak_gpu_allocated_gib": torch.cuda.max_memory_allocated()/2**30,
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"rows": len(rows), "peak_gpu_allocated_gib": output["peak_gpu_allocated_gib"]}))


if __name__ == "__main__":
    main()
