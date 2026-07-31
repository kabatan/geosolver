from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

import real_gate_scanner as gate


def _document(first: str, second: str = "y", *, variables=("x", "y")):
    return {
        "task": "solve",
        "variables": {"names": list(variables)},
        "construction": [],
        "constraints": [
            {"def": first, "value": 0},
            {"def": second, "value": 0},
        ],
        "guards": [],
        "answer": variables[0],
        "post_process": "",
    }


def _source(root: Path, name: str, document: dict):
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    path = root / f"{name}.json"
    path.write_bytes(payload)
    return path, hashlib.sha256(payload).hexdigest()


def _record(path: Path, digest: str, *, ready=False):
    return {
        "source_path": str(path),
        "source_sha256": digest,
        "endpoint": [0.0, 0.0],
        "refinement_contract": {
            "variant": "frozen-control",
            "status": "TARGET_STABILITY_READY" if ready else "TARGET_STABILITY_FAILED",
            "numeric_v3_ready": ready,
            "target_stability_ready": ready,
        },
    }


def test_gate_passes_four_eligible_from_two_structural_signatures():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        quadratic = _source(root, "quadratic", _document("x*x + y"))
        trigonometric = _source(root, "trigonometric", _document("sin(x)*sin(x) + y"))
        records = [
            _record(*quadratic),
            _record(*quadratic),
            _record(*trigonometric),
            _record(*trigonometric),
        ]
        result = gate.scan_manifest(
            {"schema_version": gate.INPUT_SCHEMA, "records": records}
        )
        assert result["gate_pass"] is True
        assert result["counts"]["eligible_count"] == 4
        assert result["signature_count"] == 2
        serialized = json.dumps(result, sort_keys=True)
        for forbidden in (str(root), "source_path", "source_sha256", "endpoint\""):
            assert forbidden not in serialized


def test_regular_cubic_nonsmooth_nonsquare_and_ready_fail_closed():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        sources = [
            _source(root, "regular", _document("x + y")),
            _source(root, "cubic", _document("x*x*x + y")),
            _source(root, "nonsmooth", _document("Abs(x) + y")),
            _source(root, "nonsquare", _document("x*x", variables=("x",))),
        ]
        records = [_record(*item) for item in sources]
        eligible = _source(root, "eligible", _document("x*x + y"))
        records.append(_record(*eligible, ready=True))
        result = gate.scan_manifest(
            {"schema_version": gate.INPUT_SCHEMA, "records": records}
        )
        assert result["gate_pass"] is False
        assert result["counts"].get("eligible_count", 0) == 0
        assert result["signature_count"] == 0


def test_outcome_or_identity_fields_are_rejected_without_access():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = _source(root, "eligible", _document("x*x + y"))
        record = _record(*source)
        for forbidden in ("outcome", "truth", "case_id", "family", "score"):
            mutated = dict(record)
            mutated[forbidden] = "do-not-read"
            result = gate.scan_manifest(
                {"schema_version": gate.INPUT_SCHEMA, "records": [mutated]}
            )
            assert result["counts"]["rejected_input_contract_count"] == 1
            assert result["counts"].get("eligible_count", 0) == 0


def test_cpu14_only():
    assert os.sched_getaffinity(0) == {14}
