"""Freeze Q14 selection using only identifiers and variable counts."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = ROOT / "jssa/difficulty/minima/basins-323.csv"
    with source.open() as stream:
        population = [
            {"id": row["id"], "n_vars": int(row["n_vars"])}
            for row in csv.DictReader(stream)
            if int(row["n_vars"]) >= 1
        ]
    assert len(population) == len({r["id"] for r in population}) == 292
    for row in population:
        row["selection_hash"] = hashlib.sha256(
            ("Q14-nomad-wall-20261023|" + row["id"]).encode()
        ).hexdigest()
    selected = sorted(population, key=lambda r: (r["selection_hash"], r["id"]))[:24]
    with (HERE / "selected-cases.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["id", "n_vars", "selection_hash"])
        writer.writeheader()
        writer.writerows(selected)
    evidence = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "src_diff_from_60db4b6": subprocess.check_output(
            ["git", "diff", "60db4b6", "--", "src"], cwd=ROOT, text=True
        ),
        "population_count": len(population),
        "selection_count": len(selected),
        "selection_inputs_used": ["id", "n_vars"],
        "source_csv_sha256": sha(source),
        "preregistration_sha256": sha(HERE / "preregistration.md"),
        "selected_cases_sha256": sha(HERE / "selected-cases.csv"),
        "src_file_sha256": {
            str(p.relative_to(ROOT)): sha(p)
            for p in sorted((ROOT / "src").rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        },
    }
    assert evidence["src_diff_from_60db4b6"] == ""
    with (HERE / "selection-manifest.json").open("x") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"population": 292, "selected": selected}, ensure_ascii=False))


if __name__ == "__main__":
    main()
