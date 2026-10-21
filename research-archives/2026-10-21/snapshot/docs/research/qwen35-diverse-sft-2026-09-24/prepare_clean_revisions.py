"""Request a short visible self-contained answer from selected model answers."""

import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
ROOT = Path("qwen/.runtime/qwen35_diverse_sft_20260924")
MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")

SOURCES = {
    "H01": (ROOT / "material-revision-en-thinking-32k/diverse-en-revision-H01-v0-0-0.json",
            "Your revised answer still shows contradictory trial algebra before the correct coordinate calculation. Present one complete, internally consistent derivation from the coordinate setup onward. Check each intersection equation and omit all false starts. Give the general relation, decisive proof, and numerical result."),
    "H07": (ROOT / "material-fresh-thinking-en-32k/diverse-en-fresh-thinking-H07-v0-0-0.json",
            "Your answer cites a derivation of the coordinates of P and Q from a hidden thought process. The visible answer must show this derivation explicitly from the equations of AN, BN, and the horizontal line through M. Keep the other general relations and their proofs, and check the segment order used in the power-of-point product."),
    "H13": (ROOT / "material-revision-en-thinking-32k/diverse-en-revision-H13-v0-0-0.json",
            "The vertical coordinate of the circle center has the wrong physical units: rederive it from perpendicularity to CK. Your assertion that the proposed circumcenter is equidistant from B and J skips the decisive intersection and distance algebra. Show it explicitly and check whether the proposed relation really follows. If it fails, correct or withdraw it."),
    "DA04": (ROOT / "material-revision-en-thinking-32k/diverse-en-revision-DA04-v0-0-0.json",
            "The statement Pow(Q, Omega)=QA^2 is invalid: QA is not generally tangent to Omega at A. The subsequent segment-order argument is also inconsistent. Rederive the relation by a valid method from the actual circles and give the full decisive proof, or state that you cannot establish it."),
}


def main():
    meta = json.loads(MODEL.read_text())
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    jobs = []
    for config, (path, feedback) in SOURCES.items():
        obj = json.loads(path.read_text())
        assert obj["finish_reason"] == "stop"
        prior = obj["final_text"].removesuffix("<|im_end|>").strip()
        assert "<|im_" not in prior
        messages = [obj["messages"][0], {"role": "assistant", "content": prior},
                    {"role": "user", "content": feedback + " Write the entire final answer in English, within about 1200 words. Do not mention hidden reasoning."}]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False,
                                               add_generation_prompt=True,
                                               enable_thinking=False)
        n_tokens = len(tokenizer.encode(prompt, add_special_tokens=False))
        assert n_tokens + 32768 <= 45056, (config, n_tokens)
        ident = f"diverse-en-clean-{config}-v0-0"
        seed = int.from_bytes(hashlib.sha256(ident.encode()).digest()[:4], "big") % (2**31)
        jobs.append({"id": ident, "source_id": config, "variant": "v0",
                     "augmentation": "self_revision_clean", "seed": seed,
                     "initial_answer_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "feedback": feedback, "prompt_tokens": n_tokens,
                     "messages": messages})
    output = HERE / "material-clean-jobs-en.json"
    output.write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"jobs": len(jobs), "maximum_prompt_tokens": max(x["prompt_tokens"] for x in jobs),
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
