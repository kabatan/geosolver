#!/usr/bin/env python3
"""CPU-only reaggregation of frozen grades; does not regrade or run a model."""

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
RUNTIME = ROOT / "qwen/.runtime/qwen35_external_teacher_20260925"
TARGETS = {"H03", "H04", "H08", "H14", "H15"}
PROJECTION = {"H03", "H04", "H14"}
FIELDS = ("exact", "relation", "proof", "use", "complete")


def read_json(path):
    return json.loads(path.read_text())


def fingerprint(path):
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def counts(rows):
    return {
        "n_outputs": len(rows),
        "source_ids": sorted({r["source_id"] for r in rows}),
        **{key: sum(bool(row[key]) for row in rows) for key in FIELDS},
        "exact_but_incomplete": sum(r["exact"] and not r["complete"] for r in rows),
        "finish_reasons": dict(Counter(r["finish_reason"] for r in rows)),
    }


def main():
    sources = {}
    experiment_counts = {}
    all_rows = []
    for name, directory in (
        ("fresh1_first_pass", "scored-near-transfer-first-pass"),
        ("fresh1_second_decoding_seed", "scored-near-transfer-repeat1"),
        ("fresh2_data_form", "scored-fresh2"),
    ):
        path = RUNTIME / directory / "joined-grades.json"
        sources[name] = fingerprint(path)
        rows = read_json(path)
        for row in rows:
            assert row["complete"] == all(row[k] for k in FIELDS[:-1])
        experiment_counts[name] = {}
        for arm in sorted({r["condition"] for r in rows}):
            arm_rows = [r for r in rows if r["condition"] == arm]
            experiment_counts[name][arm] = {
                "heldout": counts([r for r in arm_rows if r["source_id"] in TARGETS]),
                "retention": counts([r for r in arm_rows if r["source_id"] not in TARGETS]),
                "by_source_id": {
                    sid: counts([r for r in arm_rows if r["source_id"] == sid])
                    for sid in sorted({r["source_id"] for r in arm_rows})
                },
            }
        all_rows.extend(dict(row, experiment=name) for row in rows)

    combined = {
        "all_targets": counts([r for r in all_rows if r["source_id"] in TARGETS]),
        "projection_cluster": counts([r for r in all_rows if r["source_id"] in PROJECTION]),
        "hidden_projection_targets": counts([r for r in all_rows if r["source_id"] in {"H03", "H14"}]),
        "retention": counts([r for r in all_rows if r["source_id"] not in TARGETS]),
    }

    thinking_path = ROOT / "docs/research/qwen35-external-teacher-2026-09-25/thinking-comparison-blind/THINKING_JOINED_SCORES.json"
    sources["thinking"] = fingerprint(thinking_path)
    thinking_rows = read_json(thinking_path)["rows"]
    thinking = {}
    for arm in sorted({r["arm"] for r in thinking_rows}):
        rows = [r for r in thinking_rows if r["arm"] == arm]
        thinking[arm] = {
            "n_attempts": len(rows),
            "final_answers": sum(r["answer_present"] for r in rows),
            "exact": sum(r["exact_value_correct"] for r in rows),
            "complete_proof": sum(r["complete_proof"] for r in rows),
            "generated_tokens": sum(r["completion_tokens"] for r in rows),
            "finish_reasons": dict(Counter(r["finish_reason"] for r in rows)),
            "by_source_id": {
                sid: {
                    "attempts": sum(r["source_id"] == sid for r in rows),
                    "exact": sum(r["exact_value_correct"] for r in rows if r["source_id"] == sid),
                    "complete_proof": sum(r["complete_proof"] for r in rows if r["source_id"] == sid),
                }
                for sid in sorted({r["source_id"] for r in rows})
            },
        }

    policy_path = ROOT / "qwen/.runtime/qwen35_external_teacher_20260924/policy-diagnostic-high-low.json"
    sources["teacher_forcing_policy_probe"] = fingerprint(policy_path)
    policy_rows = read_json(policy_path)["rows"]
    policy = {
        "teacher_answer_nll": [r for r in policy_rows if r["kind"] == "teacher_answer_nll"],
        "first_token_kl": [r for r in policy_rows if r["kind"] == "base_to_adapter_kl" and r["prefix_tokens"] == 0],
    }

    fresh3 = {}
    for name in ("eval-fresh3-base-en-32k", "eval-fresh3-six-source-variants-en-32k", "eval-fresh3-six-source-repeat-en-32k"):
        directory = RUNTIME / name
        path = directory / "receipt.json"
        fresh3[name] = {
            "exists": directory.exists(),
            "n_saved_outputs": len(list(directory.glob("diverse*.json"))),
            "receipt": read_json(path) if path.exists() else None,
        }
        if path.exists():
            sources[name] = fingerprint(path)

    result = {
        "scope": "Descriptive reaggregation of existing frozen grades; no new model inference and no regrading.",
        "limitations": [
            "Output counts are not independent construction or training-seed counts.",
            "Pooled conditions diagnose metric disagreement and failure location; they do not estimate a common intervention effect.",
            "H03/H04/H14 are three construction IDs within one projection lemma cluster.",
            "Thinking uses a different prompt template and inference budget from non-Thinking.",
            "Base Thinking H04 has a documented strict sensitivity grade: total proof count would be 0 instead of 1.",
            "Fresh3 partial outputs are not graded or inspected here; absence of a score is not an experimental failure.",
        ],
        "sources": sources,
        "by_experiment_and_arm": experiment_counts,
        "pooled_diagnostic_counts": combined,
        "thinking": thinking,
        "teacher_forcing_policy_probe": policy,
        "fresh3_status": fresh3,
        "exact_but_incomplete_target_rows": [r for r in all_rows if r["source_id"] in TARGETS and r["exact"] and not r["complete"]],
    }
    destination = OUT / "reaggregated.json"
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"pooled_diagnostic_counts": combined, "thinking": thinking, "output": str(destination)}, indent=2))


if __name__ == "__main__":
    main()
