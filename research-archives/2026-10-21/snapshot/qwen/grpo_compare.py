"""Paired evaluation identity checks, numeric summaries, and blind proof packets."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

from .answer_check import final_text
from .common import file_hash, write_json


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def paired(base, trained):
    def index(rows):
        result = {}
        for row in rows:
            key = tuple(
                row[k] for k in ("id", "variant", "prompt_sha256", "label_sha256", "sample")
            )
            if key in result:
                raise ValueError("Duplicate evaluation identity")
            result[key] = row
        return result

    a, b = index(base), index(trained)
    if not a or a.keys() != b.keys():
        raise ValueError("Base/trained evaluation inputs or sample counts differ")
    for key in a:
        for field in ("seed", "parser_version", "completion_cap", "prompt_ids"):
            if a[key][field] != b[key][field]:
                raise ValueError(f"Evaluation protocol mismatch: {field}")
        for field in ("route", "logprobs_mode"):
            if a[key].get(field) != b[key].get(field):
                raise ValueError(f"Evaluation protocol mismatch: {field}")
    return [(a[k], b[k]) for k in sorted(a)]


def numeric(pairs):
    counts = {}
    for a, b in pairs:
        c = counts.setdefault(a["id"], {"base": 0, "trained": 0, "n": 0})
        c["base"] += a["verdict"] is True
        c["trained"] += b["verdict"] is True
        c["n"] += 1
    differences = [(c["trained"] - c["base"]) / c["n"] for c in counts.values()]
    rng = random.Random(20260923)
    draws = sorted(
        sum(rng.choices(differences, k=len(differences))) / len(differences) for _ in range(20000)
    )
    return {
        "configurations": len(counts),
        "per_configuration": counts,
        "delta_pp": 100 * sum(differences) / len(differences),
        "exploratory_config_bootstrap_95_pp": [100 * draws[499], 100 * draws[19499]],
        "limitation": "Repeated answers are not independent problems. Related configurations "
        "also remain dependent; this is descriptive evidence, not a proof-transfer test.",
    }


def blind(pairs, output):
    if (output / "blinded.jsonl").exists():
        raise ValueError("Existing blinded packet is immutable")
    pool = [
        (model, r) for pair in pairs for model, r in zip(("base", "trained"), pair, strict=True)
    ]
    random.Random(2026092301).shuffle(pool)
    records, key = [], {}
    for i, (model, r) in enumerate(pool, 1):
        rid = f"R{i:04}"
        records.append(
            {
                "review_id": rid,
                "id": r["id"],
                "problem": r["problem"],
                "final_answer": final_text(r["raw_text"]),
                "finish_reason": r["finish_reason"],
            }
        )
        key[rid] = {"model": model, "id": r["id"], "sample": r["sample"]}
    path = output / "blinded.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    write_json(output / "identity_key.json", key)
    write_json(
        output / "protocol.json",
        {
            "blinded_sha256": file_hash(path),
            "identity_key_sha256": file_hash(output / "identity_key.json"),
            "categories": [
                "complete",
                "local_error",
                "core_gap",
                "mathematical_error",
                "special_case",
                "no_final",
            ],
            "required_grade_fields": [
                "review_id",
                "category",
                "method",
                "auxiliary_relation_proved",
                "evidence",
            ],
            "rubric": "Complete general proofs only. Coordinate proofs are fully valid. Naming "
            "Humpty/Dumpty without justifying the core property is not a complete proof. "
            "Record local errors, core gaps and auxiliary constructions separately. "
            "Hints are separate conditions, not new independent tasks.",
            "reviewer_independence": (
                "Record who graded and whether they previously saw these responses."
            ),
        },
    )


def freeze_and_unblind(output):
    protocol = json.loads((output / "protocol.json").read_text())
    if file_hash(output / "blinded.jsonl") != protocol["blinded_sha256"]:
        raise ValueError("Blinded packet was modified")
    records = read_rows(output / "blinded.jsonl")
    grades_path = output / "grades.jsonl"
    grades = read_rows(grades_path)
    if len(grades) != len(records) or {g["review_id"] for g in grades} != {
        r["review_id"] for r in records
    }:
        raise ValueError("Complete unique grades are required before unblinding")
    for g in grades:
        if (
            any(k not in g for k in protocol["required_grade_fields"])
            or g["category"] not in protocol["categories"]
            or not g["evidence"]
            or not isinstance(g["auxiliary_relation_proved"], bool)
        ):
            raise ValueError("Invalid grade or missing evidence")
    freeze = {"grades_sha256": file_hash(grades_path), "blinded_sha256": protocol["blinded_sha256"]}
    frozen_path = output / "grades_freeze.json"
    if frozen_path.exists() and json.loads(frozen_path.read_text()) != freeze:
        raise ValueError("Grades changed after unblinding")
    write_json(frozen_path, freeze)
    if file_hash(output / "identity_key.json") != protocol["identity_key_sha256"]:
        raise ValueError("Blinding identity key was modified")
    key = json.loads((output / "identity_key.json").read_text())
    counts = {}
    for g in grades:
        who = key[g["review_id"]]
        c = counts.setdefault(who["id"], {}).setdefault(who["model"], Counter())
        c[g["category"]] += 1
        c["auxiliary_relation_proved"] += g["auxiliary_relation_proved"]
    write_json(output / "proof_summary.json", {"by_problem": counts, **freeze})


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("mode", choices=["numeric", "proof", "freeze-unblind"])
    ap.add_argument("--base")
    ap.add_argument("--trained")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if args.mode == "freeze-unblind":
        freeze_and_unblind(out)
        return
    pairs = paired(read_rows(args.base), read_rows(args.trained))
    sources = {"base": file_hash(args.base), "trained": file_hash(args.trained)}
    source_path = out / "sources.json"
    if source_path.exists() and json.loads(source_path.read_text()) != sources:
        raise ValueError("Existing comparison uses different responses")
    write_json(source_path, sources)
    if args.mode == "numeric":
        write_json(out / "numeric_summary.json", numeric(pairs))
    else:
        blind(pairs, out)


if __name__ == "__main__":
    main()
