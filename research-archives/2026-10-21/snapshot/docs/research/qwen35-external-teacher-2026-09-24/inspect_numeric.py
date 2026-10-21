"""Conservative exact-value screen for frozen numeric generations."""

import argparse
import json
from pathlib import Path

from qwen.answer_check import answers_equal, extract_answer

LABELS = Path("benchmarks/humpty_configurations_v2/eval_variants.jsonl")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--generations", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    labels = {(row["id"], row["variant"]): row["answer_exact"]
              for row in (json.loads(line) for line in LABELS.read_text().splitlines())}
    rows = []
    for path in sorted(args.generations.glob("*.json")):
        if path.name in ("receipt.json", "manual-grades.json"):
            continue
        generation = json.loads(path.read_text())
        key = generation["source_id"], generation["variant"]
        parsed = extract_answer(generation["raw_text"])
        rows.append({"config": key[0], "variant": key[1],
                     "sample": generation["sample"], "expected": labels[key],
                     "parsed": parsed, "exact_screen": answers_equal(parsed, labels[key]),
                     "finish": generation["finish_reason"],
                     "tokens": len(generation["completion_ids"]),
                     "source_path": str(path),
                     "tail": generation["final_text"][-400:]})
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"outputs": len(rows),
                      "parser_correct": sum(row["exact_screen"] is True for row in rows),
                      "parser_unresolved": sum(row["exact_screen"] is None for row in rows),
                      "truncated": sum(row["finish"] == "length" for row in rows),
                      "max_tokens": max((row["tokens"] for row in rows), default=0)}))


if __name__ == "__main__":
    main()
