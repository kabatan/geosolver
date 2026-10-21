"""Error-only revisions for numerically promising distinct configurations."""

import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
SOURCE = Path("qwen/.runtime/qwen35_diverse_sft_20260924/material-original-en-32k")
MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")

FEEDBACK = {
    "DA02": "Your previous cyclicity argument uses equal angles on opposite sides incorrectly, and the decisive vector calculation is missing. Re-derive a useful general relation from the construction and prove the decisive step explicitly. If your proposed relation fails, withdraw it.",
    "DA03": "Your own counterexample conflicts with your proposed general formula. Do not retain a disproved formula or assume the pivotal similarity. Find a valid construction-specific relation, prove it, and apply the numerical data, or state that you cannot do so.",
    "DA07": "The equal homothety ratios in your previous answer were assumed, and the exact derivation was missing. Establish them from the definitions or replace the relation with one you can prove. Give a complete concise solution.",
    "DA08": "The right angle at T was assumed and not proved. Derive the decisive relation from the stated circle and tangent construction, or withdraw the claim. Then calculate the requested value only if justified.",
    "DB01": "The addition of the two lengths and the trigonometric simplification in your previous answer were guessed. Re-derive the center-distance relation from the exact construction with all decisive steps shown, or say it cannot be established.",
    "DB06": "Your midpoint claim was unproved and the intermediate arithmetic conflicts with the final formula. Check the configuration from first principles, give a valid general relation and full proof, then use the numerical data.",
    "DB08": "You asserted a polar relation and a tangent conclusion without deriving them, and identified two different lines as coincident. Rework the proof from the circle equations or a valid geometric argument, or withdraw the proposed relation.",
    "DB10": "The claimed concyclicity is invalid for the interior point, and the point on the median was merely assumed. Re-derive a true relation from the construction and prove its decisive step explicitly before calculating.",
    "DB16": "The circumcenter being a midpoint was argued only from an isosceles special case and continuity. Prove the proposed relation for the general configuration by equations or geometry, or replace it with a correct one.",
}


def main():
    meta = json.loads(MODEL.read_text())
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    jobs = []
    for config, feedback in FEEDBACK.items():
        path = SOURCE / f"diverse-en-material-{config}-v0-0-0.json"
        obj = json.loads(path.read_text())
        assert obj["finish_reason"] == "stop"
        prior = obj["final_text"].removesuffix("<|im_end|>").strip()
        assert "<|im_" not in prior
        messages = [obj["messages"][0], {"role": "assistant", "content": prior},
                    {"role": "user", "content": feedback + " Write the entire revised answer in English. Keep it concise and self-contained; do not mention hidden reasoning."}]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False,
                                               add_generation_prompt=True, enable_thinking=False)
        n_tokens = len(tokenizer.encode(prompt, add_special_tokens=False))
        assert n_tokens + 32768 <= 45056, (config, n_tokens)
        ident = f"diverse-en-targeted-{config}-v0-0"
        seed = int.from_bytes(hashlib.sha256(ident.encode()).digest()[:4], "big") % (2**31)
        jobs.append({"id": ident, "source_id": config, "variant": "v0",
                     "augmentation": "error_only_self_revision", "seed": seed,
                     "initial_answer_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "feedback": feedback, "prompt_tokens": n_tokens,
                     "messages": messages})
    output = HERE / "material-targeted-jobs-en.json"
    output.write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"jobs": len(jobs), "maximum_prompt_tokens": max(x["prompt_tokens"] for x in jobs),
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
