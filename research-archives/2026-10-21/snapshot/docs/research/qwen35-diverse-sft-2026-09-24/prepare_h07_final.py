"""One more error-only self-revision of the H07 answer."""

import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
SOURCE = Path("qwen/.runtime/qwen35_diverse_sft_20260924/material-clean-en-32k/diverse-en-clean-H07-v0-0-0.json")
MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")


def main():
    meta = json.loads(MODEL.read_text())
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    obj = json.loads(SOURCE.read_text())
    prior = obj["final_text"].removesuffix("<|im_end|>").strip()
    feedback = ("Your visible answer contains a false arithmetic detour: from OM^2=10 and MF^2=9, "
                "x_M^2 is not 7. The x-coordinate of M is unnecessary to find PQ. "
                "Remove that detour entirely, derive P and Q using a symbolic x-coordinate for N, "
                "and present one concise, complete proof and numerical calculation in English. "
                "Recheck every displayed equality. Do not refer to hidden reasoning.")
    messages = [obj["messages"][0], {"role": "assistant", "content": prior},
                {"role": "user", "content": feedback}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False,
                                           add_generation_prompt=True, enable_thinking=False)
    n_tokens = len(tokenizer.encode(prompt, add_special_tokens=False))
    assert n_tokens + 32768 <= 45056
    ident = "diverse-en-final-H07-v0-0"
    seed = int.from_bytes(hashlib.sha256(ident.encode()).digest()[:4], "big") % (2**31)
    job = {"id": ident, "source_id": "H07", "variant": "v0",
           "augmentation": "self_revision_final", "seed": seed,
           "initial_answer_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
           "feedback": feedback, "prompt_tokens": n_tokens, "messages": messages}
    output = HERE / "material-h07-final-job-en.json"
    output.write_text(json.dumps([job], ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"prompt_tokens": n_tokens,
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
