"""Mechanical triage only; never treats numeric equality as proof validity."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from qwen.answer_check import answers_equal, extract_answer, parse_numeric

SOURCES = (
    Path("benchmarks/humpty_configurations_v2/training_variants.jsonl"),
    Path("benchmarks/humpty_configurations_v2/eval_variants.jsonl"),
)
PROTOCOL = Path(__file__).resolve().parent / "protocol-english-32k.json"


def extract_english_answer(raw_text):
    direct = extract_answer(raw_text)
    if direct is not None:
        return direct
    final = raw_text.rsplit("</think>", 1)[-1]
    matches = list(re.finditer(r"(?im)(?:exact value|final value|final answer)\*{0,2}\s*[:：]\*{0,2}\s*(?:\*\*)?([^\n*<]+)", final))
    if matches:
        candidate = matches[-1].group(1).strip().rstrip(" .")
        try:
            return str(parse_numeric(candidate))
        except Exception:
            # Some English answers place a displayed equation after the label.
            section = final[matches[-1].start():]
            equalities = re.findall(r"=\s*([^$\n]+)", section)
            for expression in reversed(equalities):
                try:
                    return str(parse_numeric(expression.strip()))
                except Exception:
                    pass
    # English prose often wraps only the value in bold after "is".
    for expression in reversed(re.findall(r"(?i)\bis(?:\s+exactly)?\s+\*\*([^*\n]+)\*\*", final[-1200:])):
        try:
            return str(parse_numeric(expression.strip()))
        except Exception:
            pass
    for expression in reversed(re.findall(r"(?i)exact value of [^\n]{0,80}? is\s+([^\s.<>]+)", final[-1200:])):
        try:
            return str(parse_numeric(expression.strip()))
        except Exception:
            pass
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    args = parser.parse_args()
    frozen = json.loads(PROTOCOL.read_text())["source_sha256"]
    for source in SOURCES:
        assert hashlib.sha256(source.read_bytes()).hexdigest() == frozen[str(source)], source
    truth = {(row["id"], row["variant"]): row["answer_exact"]
             for source in SOURCES for line in source.read_text().splitlines()
             if (row := json.loads(line))}
    rows = []
    for path in sorted(Path(args.phase).glob("*-*.json")):
        if path.name in ("receipt.json", "token-preflight.json"):
            continue
        obj = json.loads(path.read_text())
        if "source_id" not in obj:
            continue
        expected = truth[(obj["source_id"], obj["variant"])]
        got = extract_english_answer(obj["raw_text"])
        rows.append({"id": path.stem, "config": obj["source_id"],
                     "variant": obj["variant"], "augmentation": obj["augmentation"],
                     "cjk_chars": len(re.findall(r"[ぁ-んァ-ン一-龥]", obj["final_text"])),
                     "finish": obj["finish_reason"],
                     "tokens": len(obj["completion_ids"]),
                     "expected": expected, "extracted": got,
                     "numeric_equal": answers_equal(got, expected),
                     "final_chars": len(obj["final_text"]),
                     "tail": obj["final_text"].replace("\n", " ")[-450:]})
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
