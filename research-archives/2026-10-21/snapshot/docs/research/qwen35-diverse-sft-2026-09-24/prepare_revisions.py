"""Create English self-revision jobs using only the model's prior answer and error flags."""

import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
SOURCE = Path("qwen/.runtime/qwen35_diverse_sft_20260924/material-original-en-32k")
MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")

FEEDBACK = {
    "H01": "Your answer contains a false fixed-ratio claim before the later coordinate work and includes contradictory rechecks. Give one concise, internally consistent final solution. State a general relation, prove its decisive step, and use it to find the requested value. Do not copy mistaken exploratory passages.",
    "H02": "The final numerical value in your previous answer fails direct verification, and the proposed length transfer was assumed. Re-examine the construction and derive any useful general relation and the final value rigorously. No correct value or target relation is supplied.",
    "H07": "Your previous numerical calculation is useful, but the stated general relation has an incomplete condition and symbolic derivation. Derive a valid general relation from the construction before using the given values. If you cannot prove one, say so.",
    "H12": "The assertion that P, Q, and V are collinear is the decisive step, but the previous answer did not derive it from the circle and bisector construction. Give a complete proof of your proposed relation before using the numerical data, or say that you cannot prove it.",
    "H13": "Your coordinate calculation for the given values appears useful, but the final broad coordinate formula was inferred from one instance and was not proved. State only a general relation that follows from the construction, prove it, and use it for the requested value. Remove false starts.",
    "H14": "The conclusion that the requested area is zero fails direct verification. Re-examine the constructed point R and any proposed collinearity. Give a rigorously derived useful relation and value; no correct value is supplied.",
    "H15": "The final numerical value fails direct verification, and the circumcenter relation was not established. Derive a valid relation from the stated reflections and intersections before calculating, or say that you cannot solve the problem.",
    "DA04": "Your numerical value and proposed relation are useful, but the radical-axis slope is incorrect and the decisive chord-length identity is asserted rather than derived. Rework the proof from the construction, show the decisive algebra or geometry, and use the relation for the numerical value. Do not assume an unproved identity.",
    "DA05": "The final numerical value in your previous answer fails direct verification, and the vector or midpoint relation is not derived from the two tangent circles. Re-examine the construction and give a valid general relation with its proof and numerical application. No target relation or answer is supplied.",
    "DA15": "Your claim that A, F, and O are collinear and the resulting final distance fail direct verification. Re-examine the perpendicular-bisector construction. Derive a true useful general relation, prove the decisive step, and apply the numerical data. No correct relation or value is supplied.",
    "DA17": "Your final number may be useful, but the metric identity is asserted without proof. In your inversion argument, a circle through the inversion center cannot map to another circle. Rework the decisive step with valid geometry or algebra, then provide a concise relation, proof, and numerical application.",
    "DB04": "Your coordinate setup derives a promising relation between the bisector intersections and the tangent angle, but noncollinearity of B,E,F does not imply E and F lie on opposite sides of A. Rework the proof of the circumradius without that unjustified order assumption; show the decisive step for every allowed configuration.",
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
                    {"role": "user", "content": feedback + " Write the entire revised answer in English."}]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False,
                                               add_generation_prompt=True,
                                               enable_thinking=True)
        n_tokens = len(tokenizer.encode(prompt, add_special_tokens=False))
        assert n_tokens + 32768 <= 45056, (config, n_tokens)
        ident = f"diverse-en-revision-{config}-v0-0"
        seed = int.from_bytes(hashlib.sha256(ident.encode()).digest()[:4], "big") % (2**31)
        jobs.append({"id": ident, "source_id": config, "variant": "v0",
                     "augmentation": "self_revision", "seed": seed,
                     "initial_answer_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "feedback": feedback, "prompt_tokens": n_tokens,
                     "messages": messages})
    output = HERE / "material-revision-jobs-en.json"
    output.write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"jobs": len(jobs), "maximum_prompt_tokens": max(x["prompt_tokens"] for x in jobs),
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
