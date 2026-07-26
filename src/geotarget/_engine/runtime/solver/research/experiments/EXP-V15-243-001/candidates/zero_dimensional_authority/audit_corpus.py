#!/usr/bin/env python3
"""Inventory all zero-variable cases without reading offline truth."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
DATASET = Path("/home/kabatan/ダウンロード/omc_v15_merged_5files.jsonl")
EXPECTED_DATASET_SHA256 = (
    "e587c6ea3f315f270e13cae859bba947f52e59afb651b7485061fdc49be06b8f"
)
EXCLUDED_PI = {"OMC041(A)", "OMCB014(H)", "OMCB047(E)", "OMC117(A)"}
BASELINE_ROOT = (
    ROOT
    / "research/experiments/EXP-V15-243-001/results/"
    "baseline-corrected-247-180s-seed0-v1"
)
CHAMPION_ROOT = (
    ROOT
    / "research/experiments/EXP-V15-243-001/results/"
    "champion-v1-development145-180s-seed0-v1"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _manifest_index(root: Path) -> dict[str, str]:
    document = json.loads((root / "INPUT_MANIFEST.json").read_text())
    rows = document.get("rows")
    if not isinstance(rows, list):
        rows = document.get("inputs")
    index: dict[str, str] = {}
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, Mapping):
                problem_id = row.get("problem_id")
                slug = row.get("slug")
                if isinstance(problem_id, str) and isinstance(slug, str):
                    index[problem_id] = slug
    return index


def _artifact_summary(root: Path, slug: str | None) -> object:
    if slug is None:
        return None
    result_path = root / "artifacts" / slug / "RESULT.json"
    search_path = root / "artifacts" / slug / "search.json"
    if not result_path.is_file():
        return None
    result = json.loads(result_path.read_text())
    search = json.loads(search_path.read_text()) if search_path.is_file() else {}
    return {
        "slug": slug,
        "status": result.get("status"),
        "safe_endpoint_count": search.get("safe_endpoint_count"),
        "hp_attempts": [
            {
                "status": attempt.get("status"),
                "authority_pass": attempt.get("authority_pass"),
                "endpoint_float64_sha256": attempt.get(
                    "endpoint_float64_sha256"
                ),
            }
            for attempt in result.get("hp_attempts", [])
            if isinstance(attempt, Mapping)
        ],
        "exact_descriptor_count": len(
            result.get("distinct_exact_target_descriptors", [])
        ),
    }


def main() -> None:
    payload = DATASET.read_bytes()
    if _sha256(payload) != EXPECTED_DATASET_SHA256:
        raise SystemExit("dataset digest mismatch")
    baseline = _manifest_index(BASELINE_ROOT)
    champion = _manifest_index(CHAMPION_ROOT)
    rows = []
    algebraic_count = 0
    for line_number, line in enumerate(payload.splitlines(), 1):
        outer = json.loads(line)
        problem_id = outer.get("problem_id")
        if problem_id in EXCLUDED_PI:
            continue
        algebraic_count += 1
        formulation = outer.get("formulation")
        variables = (
            formulation.get("variables")
            if isinstance(formulation, Mapping)
            else None
        )
        names = variables.get("names") if isinstance(variables, Mapping) else None
        if isinstance(names, list) and not names:
            rows.append(
                {
                    "line_number": line_number,
                    "problem_id": problem_id,
                    "continuous_variable_count": 0,
                    "constraint_count": len(formulation.get("constraints", [])),
                    "guard_count": len(formulation.get("guards", [])),
                    "baseline_stored_artifact": _artifact_summary(
                        BASELINE_ROOT, baseline.get(str(problem_id))
                    ),
                    "champion_v1_development_stored_artifact": _artifact_summary(
                        CHAMPION_ROOT, champion.get(str(problem_id))
                    ),
                }
            )
    output = {
        "schema_version": "geotarget.exp-v15-243-zero-dimensional-audit/v1",
        "dataset_sha256": EXPECTED_DATASET_SHA256,
        "pi_excluded_case_count": len(EXCLUDED_PI),
        "algebraic_case_count": algebraic_count,
        "zero_variable_case_count": len(rows),
        "cases": rows,
        "truth_read": False,
        "candidate_routing_uses_case_identity": False,
        "finding": (
            "the unchanged lower HP authority accepts []; champion_v1 loses "
            "OMC009(C) only because its adaptive wrapper rejects empty endpoints"
        ),
    }
    (HERE / "CORPUS_AUDIT.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
