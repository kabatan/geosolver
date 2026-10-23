"""Freeze small, existing reports/tables only. Never import or run the solver."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCES = {
    "task.md": "jssa/strategy/codex-tasks-1023.md",
    "report-v10.md": "jssa/draft/report-draft-v10.md",
    "supplement-v10.md": "jssa/draft/supplement-v10.md",
    "G-answer.md": "jssa/strategy/astra-consult-17/G/answer.md",
    "G-intervention.csv": "jssa/strategy/astra-consult-17/G/intervention-summary.csv",
    "G-mechanism-summary.json": "jssa/strategy/astra-consult-17/G/mechanism-summary.json",
    "Q1-answer.md": "jssa/difficulty/wall-292/answer.md",
    "Q1-preregistration.md": "jssa/difficulty/wall-292/preregistration.md",
    "Q1-per-problem.csv": "jssa/difficulty/wall-292/per-problem.csv",
    "Q1-summary.json": "jssa/difficulty/wall-292/summary.json",
    "Q4-answer.md": "jssa/difficulty/multiplicity/answer.md",
    "Q4-per-case.csv": "jssa/difficulty/multiplicity/per-case.csv",
    "Q4-per-candidate.csv": "jssa/difficulty/multiplicity/per-candidate.csv",
    "Q4-aggregate.csv": "jssa/difficulty/multiplicity/aggregate.csv",
    "Q4-summary.json": "jssa/difficulty/multiplicity/summary.json",
    "Q6-answer.md": "jssa/strategy/astra-consult-17/Q6/answer.md",
    "Q6-per-problem.csv": "jssa/strategy/astra-consult-17/Q6/per-problem.csv",
    "Q6-mechanism-checks.json": "jssa/strategy/astra-consult-17/Q6/mechanism-checks.json",
    "Q7-answer.md": "jssa/strategy/astra-consult-17/Q7/answer.md",
    "Q7-sources.md": "jssa/strategy/astra-consult-17/Q7/sources.md",
    "Q7-search-log.md": "jssa/strategy/astra-consult-17/Q7/search-log.md",
    "Q2-authoring-rules.md": "jssa/difficulty/unseen-1983/authoring-rules.md",
    "scipy-multistart-source.txt": "src/geosolver/engine/standard/search/scipy_multistart_backend.py",
}

def main():
    dest = HERE / "snapshots"
    lock = HERE / "source-manifest.json"
    if lock.exists() or dest.exists():
        raise SystemExit("Snapshot already exists; do not overwrite.")
    prepared = []
    for name, rel in SOURCES.items():
        p = ROOT / rel
        data = p.read_bytes()
        if len(data) > 4_000_000:
            raise SystemExit(f"Too large: {rel}")
        if data != p.read_bytes():
            raise SystemExit(f"Source changed while reading: {rel}; retry later.")
        prepared.append((name, rel, data, p.stat().st_mtime_ns))
    if sum(len(x[2]) for x in prepared) > 15_000_000:
        raise SystemExit("Snapshot total too large.")
    dest.mkdir()
    entries = []
    for name, rel, data, mtime in prepared:
        (dest / name).write_bytes(data)
        entries.append({"source": rel, "snapshot": "snapshots/" + name,
                        "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                        "source_mtime_ns": mtime})
    result = {"captured_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Existing reports and tables; no solver or numerical evaluation.",
              "not_transactional_across_files": True, "files": entries}
    lock.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"files": len(entries), "bytes": sum(e["bytes"] for e in entries),
                      "captured_utc": result["captured_utc"]}))

if __name__ == "__main__":
    main()
