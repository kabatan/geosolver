"""Prepare answer-only OPD training rows and proof/numeric evaluation jobs.

This CPU-only preparation reads the canonical Humpty v2 problem/label files and
their checked English templates. It deliberately does not load prior teacher
answer text into the training pool.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STUDY = Path(__file__).resolve().parent
DATA = ROOT / "benchmarks/humpty_configurations_v2"
TEMPLATE_PATH = ROOT / "docs/research/qwen35-diverse-sft-2026-09-24/english_templates.py"
TRAIN_PATH = DATA / "training_variants.jsonl"
PROOF_SOURCE = ROOT / "docs/research/qwen35-external-teacher-2026-09-25/eval-proof-mechanism-jobs.json"

TRAIN_CONFIGS = ["H01", "H04", "H07", "H13", "H14", "H15", "DA01", "DA05"]

NUMERIC_TASK = (
    "Solve the following geometry problem. Derive the requested value from the "
    "given conditions and justify the decisive steps. You may use coordinates, "
    "vectors, or standard geometric theorems. Write the solution in English and "
    "end with the exact value.\n\n"
)
TEACHER_HINT_PREFIX = "\n\nVerified exact numeric-answer hint: "
PROOF_TASK = (
    "Prove the following statement for every nondegenerate configuration satisfying "
    "the assumptions. Give a self-contained proof and justify the ordering, branch, "
    "and sign conditions that the argument uses. Do not substitute a numerical "
    "example for a proof. Write the proof in English.\n\n"
)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_numeric_templates() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("pilot_english_templates", TEMPLATE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load English templates from {TEMPLATE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.NUMERIC_EN


def assert_english(text: str, label: str) -> None:
    if re.search(r"[ぁ-んァ-ン一-龥]", text):
        raise ValueError(f"Japanese text found in {label}")
    if "{" in text or "}" in text:
        raise ValueError(f"Unfilled template field in {label}")


def seeded(job_id: str) -> int:
    digest = hashlib.sha256(f"answer-opd-pilot-2026-09-26/{job_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % (2**31)


PROOF_TARGETS = [
    {
        "source_id": "H01",
        "target": "AM·MP = MB²",
        "statement": (
            "Let ABC be an acute scalene triangle with orthocenter H. Let M be the "
            "midpoint of BC, and let P be the perpendicular foot from H to line AM. "
            "Prove that AM·MP = MB²."
        ),
        "evidence": "audits.json: H01 accepted; catalogue.md H01; candidate H01 relation audit",
    },
    {
        "source_id": "H04",
        "target": "AT² = TB·TC",
        "statement": (
            "Let ABC be an acute scalene triangle with orthocenter H. Let M be the "
            "midpoint of BC, let P be the perpendicular foot from H to line AM, and "
            "let T be the intersection of line BC with the perpendicular bisector "
            "of AP. Assume T,B,C occur in that order. Prove that AT² = TB·TC."
        ),
        "evidence": "audits.json: H04 accepted; catalogue.md H04; candidate H04 exterior-power identity",
    },
    {
        "source_id": "H07",
        "target": "[EPQ] = AB·MF·(1 − AB²/(4·ON²))",
        "statement": (
            "Two circles tangent to line AB at distinct points A and B meet at distinct "
            "points M and N on the same side of AB, with M closer to AB than N. Assume "
            "triangle NAB is acute and scalene. Let O be the midpoint of AB. Through M "
            "draw the line parallel to AB; let it meet the first circle again at C and "
            "the second circle again at D. Set E=AC∩BD, P=AN∩CD, and Q=BN∩CD. Let F "
            "be the perpendicular foot from M to AB. Prove that the area of triangle "
            "EPQ is AB·MF·(1 − AB²/(4·ON²))."
        ),
        "evidence": "audits.json: H07 accepted; catalogue.md H07; candidate H07 proves OM·ON=OA² and E is reflection of M",
    },
    {
        "source_id": "H13",
        "target": "Z lies on AC",
        "statement": (
            "In an acute scalene triangle ABC, let M be the midpoint of AC. The tangent "
            "at C to circle BMC meets the line through B perpendicular to BC at K, where "
            "K lies on the side of BC opposite A. Let J be the interior intersection "
            "of segments AK and BM, and let Z be the circumcenter of triangle BJK. "
            "Prove that Z lies on line AC."
        ),
        "evidence": "audits.json: H13 accepted; catalogue.md H13; candidate H13 center-on-AC derivation",
    },
    {
        "source_id": "H14",
        "target": "AR is perpendicular to HR",
        "statement": (
            "Let ABC be an acute scalene triangle with orthocenter H and circumcircle Ω. "
            "Let M be the midpoint of BC. Let D be the second intersection of line AB "
            "with the circle centered at C of radius CA, and let E be the second "
            "intersection of line AC with the circle centered at B of radius BA. The "
            "rays MD and ME meet Ω at P and Q. Let R be the common point other "
            "than M of circles BPM and CQM. Assume all intersections are nondegenerate. "
            "Prove AR is perpendicular to HR."
        ),
        "evidence": "audits.json: H14 accepted; catalogue.md H14; candidate H14 identifies R as projection of H onto AM",
    },
    {
        "source_id": "H15",
        "target": "K is the midpoint of AD",
        "statement": (
            "Let ABC be a scalene triangle with angle BAC=60 degrees and circumcircle Ω. "
            "The tangents to Ω at B and C meet at X; line AX meets Ω again at D. Reflect "
            "D across BC to E, reflect E across AB to C₀, and reflect E across AC to "
            "B₀. Let K=BB₀∩CC₀. Assume all intersections are finite and BB₀ and CC₀ "
            "are distinct. Prove K is the midpoint of AD."
        ),
        "evidence": "audits.json: H15 accepted; catalogue.md H15; candidate H15 symbolic midpoint identities",
    },
    {
        "source_id": "DA01",
        "target": "AT·AM = AB·AC/2",
        "statement": (
            "In a nondegenerate triangle ABC, let M be the midpoint of BC. One circle "
            "passes through A and B and is tangent at A to line AC; another passes "
            "through A and C and is tangent at A to line AB. Let T be their intersection "
            "other than A. Prove AT·AM = AB·AC/2."
        ),
        "evidence": "audits.json: DA01 accepted; catalogue.md DA01; candidate DA01 direct tangent-circle derivation",
    },
    {
        "source_id": "DA05",
        "target": "MD·ME = MB²",
        "statement": (
            "Let ABC be an acute scalene triangle. A circle through A is tangent to line "
            "BC at B, and a circle through C is tangent to line BA at B. Let D be their "
            "intersection other than B, let M be the midpoint of BC, and let E be the "
            "intersection of line MD with line AC. Assume M,D,E occur in that order. "
            "Prove MD·ME = MB²."
        ),
        "evidence": "audits.json: DA05 accepted; catalogue.md DA05; candidate DA05 derives the tangent/secant product",
    },
]


def train_rows(templates: dict[str, str]) -> list[dict]:
    rows = load_jsonl(TRAIN_PATH)
    selected = [row for row in rows if row["id"] in TRAIN_CONFIGS]
    expected = {(cid, f"v{i}") for cid in TRAIN_CONFIGS for i in range(4)}
    found = {(row["id"], row["variant"]) for row in selected}
    if found != expected or len(selected) != 32:
        raise ValueError(f"Expected exactly four v0-v3 rows for each selected config; got {len(selected)}")

    output = []
    for cid in TRAIN_CONFIGS:
        for row in sorted((r for r in selected if r["id"] == cid), key=lambda r: r["variant"]):
            problem = templates[cid].format(**row["givens"])
            assert_english(problem, f"{cid}/{row['variant']} prompt")
            user_content = NUMERIC_TASK + problem
            reference = row["answer_exact"]
            # The teacher receives the exact numeric answer as its sole privilege.
            # No proof, general relation, or completed solution is included.
            output.append({
                "id": f"{cid}-{row['variant']}",
                "source_id": cid,
                "variant": row["variant"],
                "reference": reference,
                "student_messages": [{"role": "user", "content": user_content}],
                "teacher_messages": [{"role": "user", "content": user_content + TEACHER_HINT_PREFIX + reference}],
                "augmentation": row["augmentation"],
                "givens": row["givens"],
                "provenance": {
                    "problem_source": "benchmarks/humpty_configurations_v2/training_variants.jsonl",
                    "problem_line_sha256": sha_bytes(row["problem"].encode()),
                    "label_field": "answer_exact",
                    "label_source": "benchmarks/humpty_configurations_v2/training_variants.jsonl",
                    "english_template_source": "docs/research/qwen35-diverse-sft-2026-09-24/english_templates.py:NUMERIC_EN",
                    "augmentation_status": row["augmentation"],
                },
            })
    return output


def proof_jobs() -> tuple[list[dict], dict[str, dict]]:
    jobs: list[dict] = []
    answer_key: dict[str, dict] = {}
    for target in PROOF_TARGETS:
        base = f"proof-{target['source_id'].lower()}"
        prompt = PROOF_TASK + target["statement"]
        for replicate in (1, 2):
            job_id = f"{base}-r{replicate}"
            jobs.append({
                "id": job_id,
                "source_id": target["source_id"],
                "variant": "general-claim",
                "seed": seeded(job_id),
                "evaluation_role": "same_configuration_general_proof",
                "replicate": replicate,
                "messages": [{"role": "user", "content": prompt}],
                "provenance": {
                    "claim_audit": target["evidence"],
                    "claim_source": "docs/research/qwen35-external-teacher-2026-09-24/audits.json",
                },
            })
            answer_key[job_id] = {"target_claim": target["target"], "expected_value": None}

    source_jobs = json.loads(PROOF_SOURCE.read_text())
    for source_id in ("EV02", "OB01"):
        original = next(row for row in source_jobs if row["source_id"] == source_id)
        content = original["messages"][0]["content"]
        for replicate in (1, 2):
            job_id = f"secondary-{source_id.lower()}-r{replicate}"
            jobs.append({
                "id": job_id,
                "source_id": source_id,
                "variant": "existing-proof-mechanism",
                "seed": seeded(job_id),
                "evaluation_role": "cross_configuration_general_proof_secondary",
                "replicate": replicate,
                "messages": [{"role": "user", "content": content}],
                "provenance": {
                    "job_source": "docs/research/qwen35-external-teacher-2026-09-25/eval-proof-mechanism-jobs.json",
                    "source_job_id": original["id"],
                },
            })
            answer_key[job_id] = {"target_claim": None, "expected_value": None}
    return jobs, answer_key


def numeric_eval_jobs() -> tuple[list[dict], dict[str, dict]]:
    elementary = [
        {
            "source_id": "easy-triangle-median",
            "problem": "In triangle ABC, AB=5, AC=7, and BC=6. Let M be the midpoint of BC. Find AM and justify the exact value briefly.",
            "answer": "2*sqrt(7)",
            "grading_note": "Apollonius' median formula.",
        },
        {
            "source_id": "easy-right-circumradius",
            "problem": "A right triangle has perpendicular leg lengths 9 and 12. Find its circumradius and justify the exact value briefly.",
            "answer": "15/2",
            "grading_note": "The circumradius of a right triangle is half its hypotenuse.",
        },
        {
            "source_id": "easy-angle-bisector",
            "problem": "In triangle ABC, AD is the internal angle bisector of angle A and D lies on BC. If AB=10, AC=14, and BC=12, find BD and justify the exact value briefly.",
            "answer": "5",
            "grading_note": "The internal angle-bisector theorem gives BD/DC=AB/AC, with BD+DC=BC.",
        },
        {
            "source_id": "easy-intersecting-chords",
            "problem": "Chords AB and CD of a circle intersect at an interior point P. If AP=3, PB=8, and CP=4, find PD and justify the exact value briefly.",
            "answer": "6",
            "grading_note": "The intersecting-chords theorem gives AP·PB=CP·PD.",
        },
    ]
    output, answer_key = [], {}
    for row in elementary:
        cid = row["source_id"]
        job_id = f"numeric-elementary-{cid}"
        output.append({
            "id": job_id,
            "source_id": cid,
            "variant": "elementary",
            "seed": seeded(job_id),
            "evaluation_role": "elementary_numeric_retention",
            "messages": [{"role": "user", "content": row["problem"]}],
            "provenance": {
                "problem_source": "pilot-authored prompt from root instruction dated 2026-09-26",
                "label_basis": row["grading_note"],
            },
        })
        answer_key[job_id] = {
            "expected_value": row["answer"],
            "target_claim": None,
            "grading_note": row["grading_note"],
        }
    return output, answer_key


def main() -> None:
    templates = load_numeric_templates()
    pool = train_rows(templates)
    proof, answer_key = proof_jobs()
    numeric, numeric_key = numeric_eval_jobs()
    answer_key.update(numeric_key)
    jobs = proof + numeric
    if len(pool) != 32 or len(proof) != 20 or len(numeric) != 4 or len(jobs) != 24:
        raise AssertionError(f"Unexpected frozen data counts: pool={len(pool)}, proof={len(proof)}, numeric={len(numeric)}")
    if len({row["id"] for row in pool}) != len(pool):
        raise AssertionError("Training pool IDs must be unique")
    for row in pool:
        if row["student_messages"][0]["content"] == row["teacher_messages"][0]["content"]:
            raise AssertionError(f"{row['id']}: teacher must differ by the answer hint")
        if row["teacher_messages"][0]["content"].count(TEACHER_HINT_PREFIX) != 1:
            raise AssertionError(f"{row['id']}: expected exactly one numeric-only teacher hint")

    (STUDY / "train-pool.json").write_text(json.dumps(pool, ensure_ascii=False, indent=2) + "\n")
    (STUDY / "eval-jobs.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n")
    (STUDY / "eval-answer-key.json").write_text(json.dumps(answer_key, ensure_ascii=False, indent=2) + "\n")
    summary = {
        "status": "complete",
        "training_rows": len(pool),
        "training_configurations": TRAIN_CONFIGS,
        "training_augmentation_counts": {
            key: sum(row["augmentation"] == key for row in pool)
            for key in sorted({row["augmentation"] for row in pool})
        },
        "evaluation_jobs": len(jobs),
        "same_configuration_proof_jobs": 16,
        "secondary_proof_jobs": 4,
        "numeric_heldout_jobs": 4,
        "numeric_jobs_are_elementary_pilot_sentinels": True,
        "source_sha256": {
            "training_variants": sha_file(TRAIN_PATH),
            "english_templates": sha_file(TEMPLATE_PATH),
            "secondary_proof_jobs": sha_file(PROOF_SOURCE),
        },
        "output_sha256": {
            name: sha_file(STUDY / name)
            for name in ("train-pool.json", "eval-jobs.json", "eval-answer-key.json")
        },
    }
    (STUDY / "data-freeze.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
