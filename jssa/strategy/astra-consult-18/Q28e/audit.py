"""Read-only descriptive audit of Q15 metadata; no solver import or execution.

Writes only Q28e/audit.json. This is not a prediction test.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[4]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    csv_path = ROOT / "jssa/difficulty/false-attractors/per-problem.csv"
    cases_path = ROOT / "benchmarks/cases.jsonl"
    with csv_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    cases = {}
    with cases_path.open() as handle:
        for line in handle:
            case = json.loads(line)
            cases[case["id"]] = case
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate Q15 problem ID")
    if any(row["id"] not in cases for row in rows):
        raise ValueError("Q15 ID missing from cases.jsonl")

    escaped = [row for row in rows if int(row["b"]) > 0]
    main_escape = [row for row in rows if row["main_cause"] == "b"]
    selected = sorted(main_escape, key=lambda row: (int(row["n_vars"]), row["id"]))[:3]
    keys = ("id", "n_vars", "records", "finite_failed", "b", "main_cause", "p_saved")
    monitored = [
        csv_path,
        cases_path,
        ROOT / "jssa/difficulty/false-attractors/classify_endpoints.py",
        ROOT / "jssa/strategy/astra-consult-17/H/sources/algebraize.py",
        ROOT / "src/geosolver/engine/standard/evaluation/float_expressions.py",
        ROOT / "src/geosolver/engine/standard/search/scipy_multistart_backend.py",
        OUT / "preregistration.md",
        Path(__file__).resolve(),
    ]
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "descriptive_audit_not_prediction_test",
        "population": {
            "benchmark_cases": len(cases),
            "q15_variable_problems": len(rows),
            "saved_starts": sum(int(row["records"]) for row in rows),
            "finite_failed": sum(int(row["finite_failed"]) for row in rows),
            "any_escape_problems": len(escaped),
            "escape_endpoints": sum(int(row["b"]) for row in rows),
            "main_escape_problems": len(main_escape),
        },
        "any_escape_rows": [{key: row[key] for key in keys} for row in escaped],
        "representative_selection": "main_cause b, ascending n_vars then id, first 3; exploratory",
        "representative_inputs": [
            {"id": row["id"], "dsl": cases[row["id"]]["dsl"]} for row in selected
        ],
        "new_solver_runs": 0,
        "new_residual_evaluations": 0,
        "measured_escape_exponents": 0,
        "new_seed_tests": 0,
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in monitored},
    }
    output = OUT / "audit.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload["population"], ensure_ascii=False))
    print(f"Saved {output.relative_to(ROOT)} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
