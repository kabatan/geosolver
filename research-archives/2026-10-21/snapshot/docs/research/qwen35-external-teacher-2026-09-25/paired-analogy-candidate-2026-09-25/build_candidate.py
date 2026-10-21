#!/usr/bin/env python3
"""Build a CPU-only paired-analogy candidate from frozen audited teachers."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
OUT = ROOT / "paired-analogy-candidate-2026-09-25"
BASE_PATH = ROOT / "heldout-near-transfer" / "train.json"
TEACHER_PATH = ROOT.parent / "qwen35-external-teacher-2026-09-24" / "train.json"
AUDIT_PATH = ROOT.parent / "qwen35-external-teacher-2026-09-24" / "audits.json"
TOKENIZER_PATH = REPO / "qwen/.runtime/qwen35_external_teacher_20260925/train-near-32-original/tokenizer/tokenizer.json"
MODEL_REVISION = "c202236235762e1c871ad0ccb60c8ee5ba337b9a"
SEED = 2026092431

ROTATIONS = {
    "rotation-1": {"omitted": "H03", "pair": ("H04", "H14")},
    "rotation-2": {"omitted": "H04", "pair": ("H03", "H14")},
    "rotation-3": {"omitted": "H14", "pair": ("H03", "H04")},
}

METHOD = {
    "H03": "a second intersection of a median with the circle through the two angle-bisector traces",
    "H04": "the orthocenter's directly defined median foot, selected by a perpendicular bisector",
    "H14": "the non-midpoint common point of two circles, recovered by positive-ray inversion",
}
POINT = {"H03": "P_a (and cyclically P_b and P_c)", "H04": "P", "H14": "R"}

TREATMENT_TASKS = [
    "Compare the two constructions before finishing either solution. Then give two complete, separately headed solutions. Identify the named constructed point in each case as X_i on median M_iA_i. In the common coordinates M_i=(0,0), B_i=(-m_i,0), C_i=(m_i,0), A_i=(x_i,y_i), prove for each construction that X_i=(m_i^2/(x_i^2+y_i^2))A_i, so H_iX_i is perpendicular to M_iA_i and X_i lies strictly inside M_iA_i. Explain the distinct construction step that produces this same projection schema in each case. Include every decisive intersection/inversion calculation, nonzero condition, acute-angle branch, and numerical application. Do not rely on one solution to prove the other.",
    "Work both problems completely, keeping their proofs separate. Before the two solutions, state the shared normalized schema: with each midpoint at the origin and its base endpoints at (-m_i,0),(m_i,0), the case's constructed point X_i should be shown to equal (m_i^2/|A_i|^2)A_i. Compare how the nonisomorphic constructions produce this same orthocenter-to-median projection. In each solution prove that identification from that problem's own construction, justify the segment/branch and all cancellations, then finish its exact requested value. Include full standalone proofs; no step may refer to the companion solution.",
    "Give a construction-by-construction comparison followed by a full solution to each task. Use X_1 and X_2 only as generic names for the two problems' respective constructed points. For each, derive X_i=(m_i^2/|A_i|^2)A_i in midpoint-centered coordinates and verify that it is the perpendicular projection of H_i onto the median, including why 0<m_i^2/|A_i|^2<1. Explain which construction-specific calculation leads to the common schema. Then provide separate complete proofs and the stated exact numerical answers, preserving each problem's intersection choices and branch conditions.",
]

CONTROL_TASKS = [
    "Solve both problems, but write two independent, separately headed answers. For each problem state a useful relation, prove it from that problem's construction without omitting the decisive step, justify nonzero and branch conditions, and apply it to obtain the requested exact value. Keep each answer self-contained and do not refer from one solution to the other.",
    "Provide a complete solution for Problem 1 and a complete solution for Problem 2. Treat them as separate tasks: give the construction-specific relation, its proof with all intersection and branch details, and its numerical application in each answer. Use separate headings and make neither proof depend on the other.",
    "Write two stand-alone worked solutions in the order given. Each should identify and prove its own useful construction relation, explain all decisive algebra and branch choices, and finish the exact computation. Keep the reasoning for the two problems in separate sections.",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def problem(row: dict[str, str]) -> str:
    parts = row["prompt"].split("\n\n", 1)
    if len(parts) != 2:
        raise ValueError(f"unexpected source prompt layout: {row['id']}")
    return parts[1].strip()


def make_prompt(task: str, rows: list[dict[str, str]]) -> str:
    return (
        "Write the entire response in English. The two tasks use separate acute scalene triangles; "
        "do not identify their points across tasks unless explicitly asked.\n\n"
        + task.strip()
        + "\n\nProblem 1\n"
        + problem(rows[0])
        + "\n\nProblem 2\n"
        + problem(rows[1])
    )


def treatment_answer(ids: tuple[str, str], rows: list[dict[str, str]]) -> str:
    a, b = ids
    pa, pb = POINT[a], POINT[b]
    mapping = (
        "The two constructions reach one normalized geometric object by different routes. In Problem 1, "
        f"the named point {pa} is produced by {METHOD[a]}; in Problem 2, the named point {pb} is produced by "
        f"{METHOD[b]}. In each case call that point X, put M=(0,0), B=(-m,0), C=(m,0), A=(x,y), and r^2=x^2+y^2. "
        "The common schema to prove from each construction is X=(m^2/r^2)A. The altitude equations then give "
        "H=(x,(m^2-x^2)/y), so A dot H=m^2=A dot X; hence HX is perpendicular to AM. Acuteness gives "
        "r^2-m^2=(B-A) dot (C-A)>0, so 0<m^2/r^2<1 and X lies strictly between M and A. "
        "The complete solutions below independently derive the claimed X from each construction before using it.\n\n"
    )
    return (
        mapping
        + "Problem 1 — complete solution\n"
        + rows[0]["answer"].strip()
        + "\n\nProblem 2 — complete solution\n"
        + rows[1]["answer"].strip()
    )


def count_tokens(tokenizer: Any, text: str) -> int:
    return len(tokenizer.encode(text, add_special_tokens=False).ids)


def main() -> None:
    from tokenizers import Tokenizer

    if not TOKENIZER_PATH.exists():
        raise FileNotFoundError(TOKENIZER_PATH)
    base = read_json(BASE_PATH)
    source_rows = {r["source"]: r for r in read_json(TEACHER_PATH)}
    audits = {r["id"]: r for r in read_json(AUDIT_PATH)}
    tokenizer = Tokenizer.from_file(str(TOKENIZER_PATH))
    assert len(base) == 32 and len({r["source"] for r in base}) == 32
    assert [r["source"] for r in base] == [r["source"] for r in read_json(BASE_PATH)]
    for sid in ("H03", "H04", "H14"):
        assert sid in source_rows
        audit = audits[sid]
        assert audit.get("status") == "accept" or audit.get("verdict") == "accept", (sid, audit)

    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "status": "candidate_untrained_unreviewed",
        "purpose": "result-independent paired-analogy SFT data candidate; CPU construction only",
        "common_base_sha256": sha256(BASE_PATH),
        "source_teacher_sha256": sha256(TEACHER_PATH),
        "source_audit_sha256": sha256(AUDIT_PATH),
        "tokenizer_sha256": sha256(TOKENIZER_PATH),
        "rows_per_arm": 35,
        "common_base_rows": 32,
        "paired_addition_rows": 3,
        "paired_rows_each_present_both_permitted_source_three_times": True,
        "row_source_metadata_for_additions": "paired-permitted-siblings (one synthetic provenance label; not included in prompt or answer)",
        "rotations": {},
        "caveats": [
            "Not independently audited; no GPU, training, evaluation generation, or model output inspection was performed.",
            "Each added row contains two complete tasks and answers. Updates are matched across arms, while tokens per update and added-token dose are reported explicitly.",
            "The three candidate rows repeat the same two numeric source instances with distinct instruction paraphrases; this does not vary geometry parameters.",
        ],
    }
    for rot, spec in ROTATIONS.items():
        omitted = spec["omitted"]
        ids = tuple(spec["pair"])
        source_pair = [source_rows[sid] for sid in ids]
        assert omitted not in ids
        additions: dict[str, list[dict[str, str]]] = {"treatment": [], "control": []}
        for idx in range(3):
            additions["treatment"].append({
                "id": f"paired-example-{idx + 1}",
                "source": "paired-permitted-siblings",
                "prompt": make_prompt(TREATMENT_TASKS[idx], source_pair),
                "answer": treatment_answer(ids, source_pair),
            })
            additions["control"].append({
                "id": f"paired-example-{idx + 1}",
                "source": "paired-permitted-siblings",
                "prompt": make_prompt(CONTROL_TASKS[idx], source_pair),
                "answer": (
                    "Problem 1 — independent complete solution\n"
                    + source_pair[0]["answer"].strip()
                    + "\n\nProblem 2 — independent complete solution\n"
                    + source_pair[1]["answer"].strip()
                ),
            })

        added_audit: dict[str, Any] = {}
        train_files: dict[str, str] = {}
        for arm in ("treatment", "control"):
            rows = base + additions[arm]
            assert len(rows) == 35
            # The omitted source and its exact full task are absent from each candidate row.
            omitted_problem = problem(source_rows[omitted])
            for row in additions[arm]:
                material = " ".join(str(row.get(k, "")) for k in ("id", "source", "prompt", "answer"))
                assert omitted not in material
                assert omitted_problem not in material
                assert not any("\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff"
                               for ch in row["prompt"] + row["answer"])
            full_path = OUT / rot / f"train-{arm}.json"
            add_path = OUT / rot / f"additions-{arm}.json"
            dump(full_path, rows)
            dump(add_path, additions[arm])
            train_files[arm] = str(full_path.relative_to(ROOT))
            base_answer = sum(count_tokens(tokenizer, r["answer"]) + 1 for r in base)
            add_answer = sum(count_tokens(tokenizer, r["answer"]) + 1 for r in additions[arm])
            full_answer = base_answer + add_answer
            prompt_toks = [count_tokens(tokenizer, r["prompt"]) for r in additions[arm]]
            answer_toks = [count_tokens(tokenizer, r["answer"]) + 1 for r in additions[arm]]
            combined_toks = [count_tokens(tokenizer, r["prompt"] + "\n" + r["answer"]) + 1 for r in additions[arm]]
            added_audit[arm] = {
                "dataset_sha256": sha256(full_path),
                "additions_sha256": sha256(add_path),
                "n_examples": len(rows),
                "n_configurations_for_trainer": len({r["source"] for r in rows}),
                "source_row_counts": {"base_rows": len(base), "paired_rows": len(additions[arm])},
                "answer_tokens_including_eos": {
                    "common_base": base_answer,
                    "added_rows": add_answer,
                    "merged_total": full_answer,
                    "added_per_row": answer_toks,
                },
                "prompt_tokens_no_chat_wrapper": prompt_toks,
                "prompt_plus_answer_tokens_no_chat_wrapper_approx": combined_toks,
                "max_prompt_plus_answer": max(combined_toks),
            }
            protocol = {
                "seed": SEED,
                "lr": 1e-5,
                "grad_clip": 1.0,
                "lora_rank": 8,
                "lora_alpha": 16,
                "modules": ["q_proj", "k_proj", "v_proj", "o_proj", "in_proj_qkv", "in_proj_z", "out_proj", "gate_proj", "up_proj", "down_proj"],
                "max_sequence_tokens": 8192,
                "micro_batch": 1,
                "optimizer": "AdamW, weight decay zero, constant learning rate",
                "loss": "English visible assistant answer including EOS only; non-thinking chat template",
                "checkpoint": "Candidate only; independent base-start protocol pending selection and audit",
                "dataset": str(full_path.resolve()),
                "dataset_sha256": sha256(full_path),
                "model_revision": MODEL_REVISION,
                "n_examples": 35,
                "n_configurations": len({r["source"] for r in rows}),
                "epochs": 1,
                "planned_updates": 35,
                "study_arm": f"external_teacher_paired_analogy_{rot}_{arm}",
                "shuffle_rule": "For epoch e, random.Random(seed + e).shuffle(list(range(n_examples))); paired treatment/control row positions and seed are identical.",
                "added_slots": "Three paired rows after the unchanged common 32; each row contains both permitted v0 sibling tasks and no omitted task.",
                "permitted_source_ids": list(ids),
                "omitted_source_id": omitted,
            }
            dump(OUT / rot / f"train-protocol-{arm}.json", protocol)

        t = added_audit["treatment"]["answer_tokens_including_eos"]["merged_total"]
        c = added_audit["control"]["answer_tokens_including_eos"]["merged_total"]
        ta = added_audit["treatment"]["answer_tokens_including_eos"]["added_rows"]
        ca = added_audit["control"]["answer_tokens_including_eos"]["added_rows"]
        added_audit["token_mismatch"] = {
            "merged_absolute": abs(t - c),
            "merged_relative_larger_denominator": abs(t - c) / max(t, c),
            "added_absolute": abs(ta - ca),
            "added_relative_larger_denominator": abs(ta - ca) / max(ta, ca),
            "strict_match": t == c and ta == ca,
        }
        added_audit["prompt_material_and_task_order_identical"] = all(
            problem(source_rows[sid]) in " ".join(r["prompt"] for arm in additions.values() for r in arm)
            for sid in ids
        )
        manifest["rotations"][rot] = {
            "omitted_source_id": omitted,
            "permitted_source_ids": list(ids),
            "rows": added_audit,
            "train_files": train_files,
        }

    dump(OUT / "candidate-manifest.json", manifest)
    dump(OUT / "candidate-hashes.json", {
        str(p.relative_to(OUT)): sha256(p)
        for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "candidate-hashes.json"
    })


if __name__ == "__main__":
    main()
