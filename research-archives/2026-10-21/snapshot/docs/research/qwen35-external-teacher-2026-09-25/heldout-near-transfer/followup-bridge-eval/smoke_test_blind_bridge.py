#!/usr/bin/env python3
"""CPU-only protocol smoke test using temporary synthetic records."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("blind_bridge_tools", HERE / "blind_bridge_tools.py")
assert SPEC and SPEC.loader
TOOLS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOLS)


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def check_raises(fn, contains: str) -> None:
    try:
        fn()
    except TOOLS.BridgeError as exc:
        assert contains in str(exc), str(exc)
    else:
        raise AssertionError(f"expected BridgeError containing {contains!r}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="blind-bridge-smoke-") as temp:
        root = Path(temp)
        eval_jobs = []
        for source_id, count, role in (
            ("H03", 2, "heldout_transfer"),
            ("H04", 2, "heldout_transfer"),
            ("H14", 2, "heldout_transfer"),
            ("H01", 1, "source_retention_control"),
            ("H02", 1, "source_retention_control"),
            ("H07", 1, "source_retention_control"),
            ("H13", 1, "source_retention_control"),
        ):
            for variant in range(count):
                job_id = f"synthetic-{source_id}-{variant}"
                prompt = f"Synthetic geometry prompt for {source_id}, instance {variant}."
                eval_jobs.append({
                    "id": job_id,
                    "source_id": source_id,
                    "seed": 100 + len(eval_jobs),
                    "evaluation_role": role,
                    "messages": [{"role": "user", "content": prompt}],
                })
        eval_path = root / "eval_jobs.json"
        dump(eval_path, eval_jobs)
        hashes_path = root / "hashes.json"
        dump(hashes_path, {
            "n_jobs": 10,
            "sources": [job["source_id"] for job in eval_jobs],
            "output_sha256": hashlib.sha256(eval_path.read_bytes()).hexdigest(),
        })
        inputs: dict[str, Path] = {}
        for condition in TOOLS.CONDITIONS:
            output_dir = root / "outputs" / condition
            output_dir.mkdir(parents=True)
            receipt = {
                "status": "complete",
                "jobs_sha256": hashlib.sha256(eval_path.read_bytes()).hexdigest(),
                "driver_sha256": "d" * 64,
                "model_metadata_sha256": "e" * 64,
                "samples": 1,
                "cap": 32,
                "context": 128,
                "temperature": 1.0,
                "top_p": 0.95,
                "top_k": 20,
                "presence_penalty": 1.5,
                "thinking": False,
                "adapter": None if condition == "base" else f"synthetic-{condition}",
            }
            dump(output_dir / "receipt.json", receipt)
            for job in eval_jobs:
                record = {
                    "id": job["id"],
                    "source_id": job["source_id"],
                    "seed": job["seed"],
                    "messages": job["messages"],
                    "sample": 0,
                    "prompt_ids": [101, 102, 103],
                    "final_text": f"Synthetic complete proof for {job['id']} in {condition}.",
                    "finish_reason": "stop",
                    "completion_ids": [201, 202, 203],
                }
                dump(output_dir / f"{job['id']}-0.json", record)
            inputs[condition] = output_dir
        parsed_inputs = TOOLS.parse_condition_inputs([f"{condition}={inputs[condition]}" for condition in TOOLS.CONDITIONS])
        assert parsed_inputs == inputs
        check_raises(lambda: TOOLS.parse_condition_inputs([f"base={inputs['base']}"]), "missing=")
        check_raises(
            lambda: TOOLS.parse_condition_inputs([f"{condition}={inputs[condition]}" for condition in TOOLS.CONDITIONS] + [f"base={inputs['base']}"]),
            "duplicate --input",
        )
        packet_path = root / "grader" / "blind-packet.json"
        vault_path = root / "private" / "vault.json"
        result = TOOLS.build_packet(eval_path, hashes_path, inputs, packet_path, vault_path, 7)
        assert result["n_records"] == 70
        packet = TOOLS.read_json(packet_path)
        vault = TOOLS.read_json(vault_path)
        assert all("condition" not in row and "job_id" not in row for row in packet["records"])
        assert len({entry["blind_id"] for entry in vault["entries"]}) == 70
        assert set(entry["condition"] for entry in vault["entries"]) == set(TOOLS.CONDITIONS)

        grade_rows = []
        uncertain_id = next(
            entry["blind_id"] for entry in vault["entries"]
            if entry["condition"] == "base" and entry["source_id"] == "H01"
        )
        for row in packet["records"]:
            grade_rows.append({
                "blind_id": row["blind_id"],
                "exact": True,
                "relation": True,
                "proof": True,
                "use": True,
                "uncertain": row["blind_id"] == uncertain_id,
                "note": "Synthetic uncertain retention case." if row["blind_id"] == uncertain_id else "Synthetic smoke-test grade.",
            })
        grade_path = root / "grader" / "blind-grades.json"
        dump(grade_path, grade_rows)
        frozen_path = root / "private" / "frozen-grades.json"
        freeze_result = TOOLS.freeze_grades(packet_path, grade_path, frozen_path)
        assert freeze_result["n_grades"] == 70
        report_path = root / "private" / "score-report.json"
        join_result = TOOLS.join_scores(packet_path, vault_path, frozen_path, eval_path, hashes_path, report_path)
        assert join_result["n_conditions"] == 7
        report = TOOLS.read_json(report_path)
        for rotation, omitted in TOOLS.ROTATION_OMITTED_ID.items():
            report_rotation = report["rotations"][rotation]
            assert report_rotation["omitted_source_id"] == omitted
            for condition in report_rotation["active_conditions"]:
                buckets = report_rotation["by_condition"][condition]
                assert buckets["heldout"]["summary"]["n_total"] == 2
                assert {row["source_id"] for row in buckets["heldout"]["rows"]} == {omitted}
                assert buckets["seen_source"]["summary"]["n_total"] == 4
                assert buckets["retention"]["summary"]["n_total"] == 4
                if condition == "base":
                    assert buckets["retention"]["summary"]["n_uncertain"] == 1
                    assert buckets["retention"]["summary"]["n_scored"] == 3
        assert all(report["lower_bar_H04"][cond]["summary"]["n_total"] == 2 for cond in TOOLS.CONDITIONS)
        assert report["rotations"]["rotation-2"]["by_condition"]["rotation-2-treatment"]["heldout"]["summary"]["n_complete"] == 2
        assert "condition_summaries" not in report  # no unpartitioned ten-item score is reported

        tampered_vault = json.loads(vault_path.read_text(encoding="utf-8"))
        tampered_vault["entries"][0]["answer_sha256"] = "0" * 64
        tampered_vault_path = root / "private" / "tampered-vault.json"
        dump(tampered_vault_path, tampered_vault)
        check_raises(
            lambda: TOOLS.join_scores(packet_path, tampered_vault_path, frozen_path, eval_path, hashes_path, root / "private" / "bad-report.json"),
            "answer hash does not match packet",
        )

        # Generator-style input corruption is rejected before a packet is emitted.
        base_dir = inputs["base"]
        bad_output_path = base_dir / f"{eval_jobs[0]['id']}-0.json"
        good_record = json.loads(bad_output_path.read_text(encoding="utf-8"))
        bad_record = dict(good_record, finish_reason="length")
        dump(bad_output_path, bad_record)
        check_raises(lambda: TOOLS.build_packet(eval_path, hashes_path, inputs, root / "bad-packet.json", root / "bad-vault.json", 7), "natural stop")
        dump(bad_output_path, dict(good_record, finish_reason="stop", id="wrong-id"))
        check_raises(lambda: TOOLS.build_packet(eval_path, hashes_path, inputs, root / "bad-packet.json", root / "bad-vault.json", 7), "id differs")
        dump(bad_output_path, dict(good_record, finish_reason="stop", seed=-1))
        check_raises(lambda: TOOLS.build_packet(eval_path, hashes_path, inputs, root / "bad-packet.json", root / "bad-vault.json", 7), "seed differs")
        dump(bad_output_path, dict(good_record, messages=[{"role": "user", "content": "changed prompt"}]))
        check_raises(lambda: TOOLS.build_packet(eval_path, hashes_path, inputs, root / "bad-packet.json", root / "bad-vault.json", 7), "messages differ")
        dump(bad_output_path, dict(good_record, completion_ids=[1] * 32))
        check_raises(lambda: TOOLS.build_packet(eval_path, hashes_path, inputs, root / "bad-packet.json", root / "bad-vault.json", 7), "below receipt cap")
        dump(bad_output_path, good_record)

        # Receipts must reference the frozen jobs and share generation settings.
        base_receipt_path = base_dir / "receipt.json"
        good_receipt = json.loads(base_receipt_path.read_text(encoding="utf-8"))
        dump(base_receipt_path, dict(good_receipt, jobs_sha256="0" * 64))
        check_raises(lambda: TOOLS.build_packet(eval_path, hashes_path, inputs, root / "bad-packet.json", root / "bad-vault.json", 7), "jobs_sha256")
        dump(base_receipt_path, good_receipt)
        control_receipt_path = inputs["rotation-1-control"] / "receipt.json"
        control_receipt = json.loads(control_receipt_path.read_text(encoding="utf-8"))
        dump(control_receipt_path, dict(control_receipt, cap=31))
        check_raises(lambda: TOOLS.build_packet(eval_path, hashes_path, inputs, root / "bad-packet.json", root / "bad-vault.json", 7), "settings differ")
        dump(control_receipt_path, control_receipt)

        # Strict booleans and exact grade coverage are part of the freeze gate.
        invalid_grades = [dict(row) for row in grade_rows]
        invalid_grades[0]["proof"] = 1
        invalid_path = root / "grader" / "invalid-grades.json"
        dump(invalid_path, invalid_grades)
        check_raises(lambda: TOOLS.freeze_grades(packet_path, invalid_path, root / "private" / "invalid-frozen.json"), "strict JSON boolean")
        print("blind bridge smoke test passed (temporary synthetic data only)")


if __name__ == "__main__":
    main()
