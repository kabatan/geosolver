from __future__ import annotations

import json

from research.homotopy_baseline.cli import main
from research.homotopy_baseline.runner import DATASET_SHA256


def test_analyze_cli_emits_machine_readable_manifest(tmp_path):
    problem = {
        "task": "solve",
        "id": "constant",
        "variables": {"names": []},
        "construction": [],
        "constraints": [],
        "guards": [],
        "answer": "3/2",
        "post_process": "",
    }
    source = tmp_path / "problem.json"
    output = tmp_path / "admission.json"
    source.write_text(json.dumps(problem), encoding="utf-8")
    assert main(["analyze", str(source), "--output", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["schema_version"] == "geotarget.homotopy-admission/v1"
    assert result["supported"] is True
    assert result["dataset_sha256"] == DATASET_SHA256
