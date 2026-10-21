"""Bind a natural-case worker to one explicitly authorized, frozen campaign."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def authorize_request(request, problem):
    if request.get("synthetic_canary") is True:
        if not problem["id"].startswith("SYNTHETIC_"):
            raise RuntimeError("A natural problem cannot use synthetic authorization")
        return
    path = Path(request.get("campaign_manifest", ""))
    if not path.is_file():
        raise RuntimeError("Natural-case execution requires a sealed campaign manifest")
    if hashlib.sha256(path.read_bytes()).hexdigest() != request.get("campaign_manifest_sha256"):
        raise RuntimeError("Campaign manifest hash mismatch")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("authorization", {}).get("user_authorized") is not True:
        raise RuntimeError("This campaign has not been authorized")
    if manifest.get("protocol", {}).get("main_run_authorized") is not True:
        raise RuntimeError("The protocol does not authorize natural cases")
    matches = [item for item in manifest["entries"] if item["case_id"] == problem["id"]]
    if len(matches) != 1:
        raise RuntimeError("Problem must occur exactly once in the campaign")
    entry = matches[0]
    expected = {
        "case_id": entry["case_id"],
        "cpu": manifest["cpu"],
        "timeout_seconds": manifest["timeout_seconds"],
        "input_sha256": entry["geo_sha256"],
        "engine_identity": manifest["engine_identity"],
        "declarations": entry["declarations"],
        "bindings": entry["bindings"],
        "instrument": True,
        "venv": manifest["geo_environment"]["prefix"],
    }
    if any(request.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Worker request differs from the frozen campaign")
    if type(request.get("seed")) is not int or request["seed"] not in manifest["seeds"]:
        raise RuntimeError("Seed is not in the frozen campaign")
    if entry.get("original_assumptions_covered") is not True:
        raise RuntimeError("Original-condition coverage has not passed")
    root = path.parent.resolve()
    if Path(request["input"]).resolve() != (root / entry["geo_input"]).resolve():
        raise RuntimeError("Worker input path differs from the frozen copy")
    output = root / "geosolver/runs" / entry["case_id"] / str(request["seed"])
    if Path(request["output_directory"]).resolve() != output.resolve():
        raise RuntimeError("Worker output is outside the assigned case/seed directory")
