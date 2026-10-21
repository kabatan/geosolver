"""Reproducible CPU rescoring and model-label-hidden proof review for exp01.

Historical answers are never evaluated against newly repaired problem text.
The original outputs are read-only; every new artifact has its own path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

from .answer_check import PARSER_VERSION, answers_equal, extract_answer, final_text

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "qwen/.runtime/exp01"

HISTORICAL_ISSUES = {
    "H07": {
        "status": "wrong_label",
        "reason": "E=AP∩BQ implies E=N; label is for E=AC∩BD",
        "as_written_answer": "32/15",
    },
    "H08": {
        "status": "invalid_witness",
        "reason": "Original/scaled witness is isosceles despite the scalene condition; "
        "not certified as a valid evaluation instance",
    },
    "H14": {
        "status": "ambiguous_construction",
        "reason": "diameter-circle prose differs from verified circles",
    },
    "DA09": {"status": "missing_definition", "reason": "I and branch condition PA<PB deleted"},
    "DB15": {"status": "missing_question", "reason": "DTを求めよ deleted"},
    "H13": {
        "status": "extra_hint",
        "reason": "Z,A,C collinearity supplied unlike the approved task",
    },
    "HX01": {
        "status": "extra_hint",
        "reason": "J,A,L collinearity and midpoint-circle incidence supplied",
    },
}


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def compare_numeric(records):
    """Descriptive configuration-cluster bootstrap, not independent answer trials."""
    comparisons = {}
    for subset in ["all", "eligible_subset"]:
        counts = {}
        for model, rows in records.items():
            for row in rows:
                if subset == "eligible_subset" and not row["eligible_for_clean_subset"]:
                    continue
                stats = counts.setdefault(row["id"], {}).setdefault(model, [0, 0])
                stats[0] += row["verdict"] is True
                stats[1] += 1
        differences = []
        for models in counts.values():
            base, trained = models["baseline"], models["trained"]
            if base[1] != trained[1]:
                raise ValueError("Unequal per-configuration evaluation counts")
            differences.append(trained[0] / trained[1] - base[0] / base[1])
        rng = random.Random(20260922)
        bootstrap = sorted(
            sum(rng.choices(differences, k=len(differences))) / len(differences)
            for _ in range(20000)
        )
        comparisons[subset] = {
            "n_configurations": len(counts),
            "per_configuration_counts": counts,
            "equal_configuration_delta_pp": 100 * sum(differences) / len(differences),
            "configuration_bootstrap_95_percentile_pp": [
                100 * bootstrap[499],
                100 * bootstrap[19499],
            ],
            "limitation": "Exploratory interval; related configurations may remain dependent. "
            "Eligible subset is a post-hoc data-quality exclusion, not a new held-out test. "
            "No claim about the maximum possible effect or about proof transfer.",
        }
    return comparisons


def rescore(exp, output):
    records = {}
    sources = {}
    for model in ("baseline", "trained"):
        path = exp / f"{model}_dev.jsonl"
        sources[path.name] = sha(path)
        result = []
        for line_number, row in enumerate(load_jsonl(path), 1):
            got = extract_answer(row["raw_text"])
            verdict = answers_equal(got, row["answer_exact"])
            issue = HISTORICAL_ISSUES.get(row["id"])
            result.append(
                {
                    "id": row["id"],
                    "sample": row["sample"],
                    "source_line": line_number,
                    "source_file": path.name,
                    "raw_text_sha256": hashlib.sha256(row["raw_text"].encode()).hexdigest(),
                    "previous_verdict": row["verdict"],
                    "extracted_answer": got,
                    "answer_exact": row["answer_exact"],
                    "verdict": verdict,
                    "finish_reason": row["finish_reason"],
                    "issue": issue,
                    "eligible_for_clean_subset": issue is None,
                    "as_written_verdict": answers_equal(got, issue["as_written_answer"])
                    if issue and "as_written_answer" in issue
                    else None,
                }
            )
        records[model] = result
        write_jsonl(output / f"{model}_dev_rescored.jsonl", result)
    summary = {
        "parser_version": PARSER_VERSION,
        "source_hashes": sources,
        "historical_issues": HISTORICAL_ISSUES,
        "scope": "Existing historical outputs, not outputs on the repaired dev set.",
        "models": {},
    }
    for model, rows in records.items():
        eligible = [r for r in rows if r["eligible_for_clean_subset"]]
        summary["models"][model] = {
            "all": {"correct": sum(r["verdict"] is True for r in rows), "n": len(rows)},
            "eligible_subset": {
                "correct": sum(r["verdict"] is True for r in eligible),
                "n": len(eligible),
            },
            "unparsed": sum(r["verdict"] is None for r in rows),
            "rescued_correct": [
                {"id": r["id"], "sample": r["sample"]}
                for r in rows
                if r["verdict"] is True and r["previous_verdict"] is not True
            ],
            "changed_verdicts": sum(r["verdict"] != r["previous_verdict"] for r in rows),
        }
    summary["comparison"] = compare_numeric(records)
    write_json(output / "numeric_rescore_summary.json", summary)
    return summary


def prepare_blind_review(exp, output):
    """Freeze the random order before grading; never print the identity key."""
    blind_path, key_path = output / "proof_blinded.jsonl", output / "proof_identity_key.json"
    if blind_path.exists() or key_path.exists():
        if not (blind_path.exists() and key_path.exists()):
            raise ValueError("Incomplete existing blind bundle")
        return
    prompts = {
        r["id"]: r.get("problem", r.get("prompt")) for r in load_jsonl(exp / "proof_prompts.jsonl")
    }
    pool = []
    for model in ("baseline", "trained"):
        for line_number, row in enumerate(load_jsonl(exp / f"{model}_proof.jsonl"), 1):
            pool.append((model, line_number, row))
    random.Random(20260922017).shuffle(pool)
    blind, key = [], {}
    for index, (model, line_number, row) in enumerate(pool, 1):
        review_id = f"P{index:03}"
        text = final_text(row["raw_text"])
        blind.append(
            {
                "review_id": review_id,
                "task_id": row["id"],
                "problem": prompts[row["id"]],
                "final_answer": text,
                "has_final_answer": text is not None,
                "finish_reason": row["finish_reason"],
            }
        )
        key[review_id] = {
            "model": model,
            "sample": row["sample"],
            "task_id": row["id"],
            "source_line": line_number,
            "source_file": f"{model}_proof.jsonl",
            "raw_text_sha256": hashlib.sha256(row["raw_text"].encode()).hexdigest(),
        }
    write_jsonl(blind_path, blind)
    write_json(key_path, key)
    write_json(
        output / "proof_review_protocol.json",
        {
            "rubric_version": "proof-v2-20260922",
            "categories": {
                "complete": "General proof; core relation justified; "
                "ordinary standard theorems allowed.",
                "local_error": "A specified local algebra/notation repair "
                "completes an otherwise general proof.",
                "core_gap": "Missing/circular core relation or an unsupported inference.",
                "special_case": "Only particular numerical triangles, with invalid generalization.",
                "no_final": "No completed final answer.",
            },
            "additional_fields": ["method", "auxiliary_relation_proved", "evidence", "uncertainty"],
            "all_grades_required_before_unblinding": True,
            "blinded_sha256": sha(blind_path),
            "limitation": "The reviewer previously saw selected exp01 answers "
            "and the earlier audit. "
            "Model labels are hidden for this pass; "
            "this is not an independent human-blinded study.",
        },
    )


def aggregate_proofs(output):
    # Read the identity key only after a complete, frozen set of grades exists.
    blind = load_jsonl(output / "proof_blinded.jsonl")
    grades_path = output / "proof_grades_blinded.jsonl"
    grades = load_jsonl(grades_path)
    ids = {r["review_id"] for r in blind}
    if len(grades) != len(ids) or {r["review_id"] for r in grades} != ids:
        raise ValueError("Complete unique grades for every blinded answer are required")
    protocol = json.loads((output / "proof_review_protocol.json").read_text())
    freeze = json.loads((output / "proof_grades_freeze.json").read_text())
    if freeze["grades_sha256"] != sha(grades_path):
        raise ValueError("Grades differ from the frozen review")
    if protocol["blinded_sha256"] != sha(output / "proof_blinded.jsonl"):
        raise ValueError("Blinded responses differ from the frozen review")
    for grade in grades:
        if grade["category"] not in protocol["categories"] or not grade["evidence"]:
            raise ValueError("Every grade requires a valid category and evidence")
    key = json.loads((output / "proof_identity_key.json").read_text())
    by_task = {}
    enriched = []
    for grade in grades:
        identity = key[grade["review_id"]]
        enriched.append({**identity, **grade})
        counts = by_task.setdefault(identity["task_id"], {}).setdefault(
            identity["model"], Counter()
        )
        counts[grade["category"]] += 1
        counts["auxiliary_relation_proved"] += bool(grade["auxiliary_relation_proved"])
    summary = {
        "grades_sha256": sha(grades_path),
        "n_answers": len(grades),
        "by_task": by_task,
        "scope": "Exploratory mathematical review; hints remain separate conditions.",
        "blinding_limitation": json.loads((output / "proof_review_protocol.json").read_text())[
            "limitation"
        ],
    }
    write_jsonl(output / "proof_grades_unblinded.jsonl", enriched)
    write_json(output / "proof_review_summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exp-dir", type=Path, default=EXP)
    parser.add_argument("--output", type=Path, default=EXP / "review_v2")
    parser.add_argument("--aggregate-proofs", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.aggregate_proofs:
        summary = aggregate_proofs(args.output)
    else:
        summary = rescore(args.exp_dir, args.output)
        prepare_blind_review(args.exp_dir, args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
