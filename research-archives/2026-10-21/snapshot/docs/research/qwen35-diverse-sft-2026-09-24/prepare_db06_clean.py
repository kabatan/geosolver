"""Ask for a corrected, explicit visible DB06 proof using only error flags."""

import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
SOURCE = Path("qwen/.runtime/qwen35_diverse_sft_20260924/material-targeted-en-32k/diverse-en-targeted-DB06-v0-0-0.json")
MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")


def main():
    meta = json.loads(MODEL.read_text())
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    obj = json.loads(SOURCE.read_text())
    prior = obj["final_text"].removesuffix("<|im_end|>").strip()
    feedback = ("The diagonal-square identity in your proof has an extra factor of two before the sum of vertex-vector norms. "
                "Recheck the full vector expansion. Also, the angle-ratio derivation for Y is missing; show it explicitly "
                "from the stated angles rather than invoking symmetry. Give one concise, self-contained corrected proof "
                "and numerical application in English. Withdraw any relation that fails these checks.")
    messages = [obj["messages"][0], {"role": "assistant", "content": prior},
                {"role": "user", "content": feedback}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False,
                                           add_generation_prompt=True, enable_thinking=False)
    n_tokens = len(tokenizer.encode(prompt, add_special_tokens=False))
    assert n_tokens + 32768 <= 45056
    ident = "diverse-en-clean-DB06-v0-0"
    seed = int.from_bytes(hashlib.sha256(ident.encode()).digest()[:4], "big") % (2**31)
    job = {"id": ident, "source_id": "DB06", "variant": "v0",
           "augmentation": "self_revision_clean", "seed": seed,
           "initial_answer_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
           "feedback": feedback, "prompt_tokens": n_tokens, "messages": messages}
    output = HERE / "material-db06-clean-job-en.json"
    output.write_text(json.dumps([job], ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"prompt_tokens": n_tokens,
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
