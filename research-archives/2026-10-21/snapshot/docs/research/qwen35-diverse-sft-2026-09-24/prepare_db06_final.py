"""Remove exploratory algebra from the model's corrected DB06 proof."""

import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
SOURCE = Path("qwen/.runtime/qwen35_diverse_sft_20260924/material-db06-clean-en-32k/diverse-en-clean-DB06-v0-0-0.json")
MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")


def main():
    meta = json.loads(MODEL.read_text())
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    obj = json.loads(SOURCE.read_text())
    prior = obj["final_text"].removesuffix("<|im_end|>").strip()
    feedback = ("Your revised answer contains an incorrect first sine substitution for Y, followed by a corrected calculation. "
                "It also calls the quadrilateral side-diagonal identity standard without finishing the vector expansion. "
                "Write one short final solution only: retain the valid X and corrected Y angle ratios, "
                "derive the vector identity by fully expanding both sides, and apply the numbers. "
                "Omit all false starts, doubts, and unproved references. Write in English.")
    messages = [obj["messages"][0], {"role": "assistant", "content": prior},
                {"role": "user", "content": feedback}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False,
                                           add_generation_prompt=True, enable_thinking=False)
    n_tokens = len(tokenizer.encode(prompt, add_special_tokens=False))
    assert n_tokens + 32768 <= 45056
    ident = "diverse-en-final-DB06-v0-0"
    seed = int.from_bytes(hashlib.sha256(ident.encode()).digest()[:4], "big") % (2**31)
    job = {"id": ident, "source_id": "DB06", "variant": "v0",
           "augmentation": "self_revision_final", "seed": seed,
           "initial_answer_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
           "feedback": feedback, "prompt_tokens": n_tokens, "messages": messages}
    output = HERE / "material-db06-final-job-en.json"
    output.write_text(json.dumps([job], ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"prompt_tokens": n_tokens,
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
