"""One bounded DB06 retry using only the model's own verified midpoint passage."""

import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
SOURCE = Path("qwen/.runtime/qwen35_diverse_sft_20260924/material-db06-final-en-32k/diverse-en-final-DB06-v0-0-0.json")
MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")


def main():
    meta = json.loads(MODEL.read_text())
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    obj = json.loads(SOURCE.read_text())
    marker = "**Derivation of the Vector Identity:**"
    prior = obj["final_text"][:obj["final_text"].index(marker)].strip()
    feedback = ("The midpoint proof above is useful. Complete the entire solution concisely, including the final number. "
                "For the diagonal-midpoint vector identity, explicitly expand (i) the squared norm of A+C-B-D, "
                "(ii) the four squared sides, and (iii) the two squared diagonals. "
                "Match all vertex norm and dot-product coefficients before stating the identity. "
                "Do not include trial calculations or an unproved reference. Write only a clean English answer.")
    messages = [obj["messages"][0], {"role": "assistant", "content": prior},
                {"role": "user", "content": feedback}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False,
                                           add_generation_prompt=True, enable_thinking=False)
    n_tokens = len(tokenizer.encode(prompt, add_special_tokens=False))
    assert n_tokens + 32768 <= 45056
    ident = "diverse-en-compact-DB06-v0-0"
    seed = int.from_bytes(hashlib.sha256(ident.encode()).digest()[:4], "big") % (2**31)
    job = {"id": ident, "source_id": "DB06", "variant": "v0",
           "augmentation": "self_revision_compact", "seed": seed,
           "initial_answer_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
           "prior_visible_span": [0, obj["final_text"].index(marker)],
           "feedback": feedback, "prompt_tokens": n_tokens, "messages": messages}
    output = HERE / "material-db06-compact-job-en.json"
    output.write_text(json.dumps([job], ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"prompt_tokens": n_tokens,
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
