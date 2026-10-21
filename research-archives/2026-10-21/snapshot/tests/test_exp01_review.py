import json

import pytest

from qwen.review_exp01 import aggregate_proofs, load_jsonl, rescore, write_jsonl


def test_rescore_uses_historical_labels_and_preserves_raw_files(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    source.mkdir()
    output.mkdir()
    rows = [
        dict(
            id="H02",
            sample=0,
            raw_text=r"\boxed{\frac{5\sqrt{7}}{2}}",
            answer_exact="5*sqrt(7)/2",
            verdict=False,
            finish_reason="eos",
        ),
        dict(
            id="H07",
            sample=0,
            raw_text=r"\boxed{32/15}",
            answer_exact="16/3",
            verdict=False,
            finish_reason="eos",
        ),
    ]
    originals = {}
    for model in ["baseline", "trained"]:
        path = source / f"{model}_dev.jsonl"
        write_jsonl(path, rows)
        originals[path] = path.read_bytes()
    summary = rescore(source, output)
    assert summary["models"]["baseline"]["all"] == {"correct": 1, "n": 2}
    results = load_jsonl(output / "baseline_dev_rescored.jsonl")
    assert results[1]["as_written_verdict"] is True
    assert results[1]["verdict"] is False
    assert results[1]["eligible_for_clean_subset"] is False
    assert all(path.read_bytes() == data for path, data in originals.items())


def test_proof_aggregation_refuses_partial_grades_before_reading_identity_key(tmp_path):
    write_jsonl(tmp_path / "proof_blinded.jsonl", [{"review_id": "P001"}])
    write_jsonl(tmp_path / "proof_grades_blinded.jsonl", [])
    # There is deliberately no identity key: validation must run first.
    with pytest.raises(ValueError, match="Complete unique grades"):
        aggregate_proofs(tmp_path)


def test_proof_aggregation_refuses_modified_grades(tmp_path):
    write_jsonl(tmp_path / "proof_blinded.jsonl", [{"review_id": "P001"}])
    write_jsonl(tmp_path / "proof_grades_blinded.jsonl", [{"review_id": "P001"}])
    (tmp_path / "proof_review_protocol.json").write_text(json.dumps({}))
    (tmp_path / "proof_grades_freeze.json").write_text(json.dumps({"grades_sha256": "old"}))
    with pytest.raises(ValueError, match="frozen review"):
        aggregate_proofs(tmp_path)
