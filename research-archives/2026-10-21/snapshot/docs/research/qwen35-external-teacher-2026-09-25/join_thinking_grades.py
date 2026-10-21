"""Join frozen blind grades to the hidden Thinking comparison condition map."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path("docs/research/qwen35-external-teacher-2026-09-25")
BLIND = ROOT / "thinking-comparison-blind"
PACKET = Path("qwen/.runtime/qwen35_external_teacher_20260925/blind-thinking-fresh4-ae/packet.json")
VAULT = Path("qwen/.runtime/qwen35_external_teacher_20260925/blind-thinking-fresh4-ae-vault/mapping.json")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows_for(source: str) -> list[dict]:
    grade = json.loads((BLIND / f"grades-{source}.json").read_text())
    return grade["entries" if source == "H03" else "items"]


def passing(value: object) -> bool:
    return value is True or value == "pass"


def main() -> None:
    freeze = json.loads((BLIND / "THINKING_BLIND_GRADE_FREEZE.json").read_text())
    assert freeze["condition_mapping_opened"] is False
    for name, expected in freeze["sha256"].items():
        assert digest(Path(name)) == expected, name
    packet = {r["blind_id"]: r for r in json.loads(PACKET.read_text())}
    mapping = {r["blind_id"]: r for r in json.loads(VAULT.read_text())}
    graded = {}
    for source in ("H03", "H04", "H14"):
        for row in rows_for(source):
            assert row["blind_id"] not in graded
            graded[row["blind_id"]] = row
    assert set(packet) == set(mapping) == set(graded) and len(packet) == 24

    joined = []
    for blind_id, meta in mapping.items():
        answer = packet[blind_id]
        grade = graded[blind_id]
        source = answer["source_id"]
        assert source in meta["job_id"]
        exact = (grade["exact_value"] if source == "H03" else
                 grade["exact_value_correct"])
        proof = grade["complete_proof"]
        relation_proof = (grade["downstream_proof"] if source != "H04" else
                          grade["downstream_relation_proof_valid"])
        mapping_proof = (grade["mapping_proof"] if source != "H04" else
                         "given_in_original_problem")
        joined.append({
            "blind_id": blind_id,
            "arm": meta["arm"],
            "source_id": source,
            "instance": int(meta["job_id"].rsplit("fresh4-", 1)[1]) + 1,
            "finish_reason": answer["finish_reason"],
            "answer_present": answer["answer_present"],
            "completion_tokens": meta["completion_tokens"],
            "exact_value_correct": passing(exact),
            "complete_proof": passing(proof),
            "relation_proof": passing(relation_proof),
            "mapping_proof": mapping_proof,
        })
    order = ["base_nonthinking", "adapter_nonthinking", "base_thinking",
             "adapter_thinking"]
    joined.sort(key=lambda r: (order.index(r["arm"]), r["source_id"], r["instance"]))
    groups = defaultdict(list)
    for row in joined:
        groups[row["arm"], row["source_id"]].append(row)
    summary = {}
    for arm in order:
        summary[arm] = {}
        for source in ("H03", "H04", "H14"):
            pair = groups[arm, source]
            assert len(pair) == 2
            summary[arm][source] = {
                "answers": sum(r["answer_present"] for r in pair),
                "exact": sum(r["exact_value_correct"] for r in pair),
                "complete_proofs": sum(r["complete_proof"] for r in pair),
                "tokens": [r["completion_tokens"] for r in pair],
                "finish": [r["finish_reason"] for r in pair],
            }
        summary[arm]["total"] = {
            metric: sum(summary[arm][source][metric] for source in
                        ("H03", "H04", "H14"))
            for metric in ("answers", "exact", "complete_proofs")
        }

    payload = {
        "blind_freeze_sha256": digest(BLIND / "THINKING_BLIND_GRADE_FREEZE.json"),
        "mapping_sha256": digest(VAULT),
        "summary": summary,
        "rows": joined,
    }
    out = BLIND / "THINKING_JOINED_SCORES.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
