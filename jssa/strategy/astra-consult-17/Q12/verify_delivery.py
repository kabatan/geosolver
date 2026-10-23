"""Validate this document package only. No solver calls or outside writes."""
from pathlib import Path
import hashlib
import json
import re
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
DOCUMENTS = ("answer.md", "stop-criteria.md", "role-policy.md", "preregistration.md", "literature.md", "README.md")
CODE = ("freeze_sources.py", "reaggregate.py", "verify_delivery.py")

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest = json.loads((HERE / "source-manifest.json").read_text())
    for entry in manifest["files"]:
        assert digest(HERE / entry["snapshot"]) == entry["sha256"], entry["source"]
    report = json.loads((HERE / "reaggregate.json").read_text())
    assert report["G"]["wall_F_N_hits"] - report["G"]["wall_F_B_hits"] == 77
    assert report["Q1"]["complete_problems"] == 35
    assert report["Q1"]["complete_starts"] == 4282
    assert report["Q1"]["all_observed_starts"] == 5269
    assert all(a["all_counts_match_stored_summary"] for a in report["Q1"]["arms"].values())
    assert report["Q4"]["runs"] == 505
    assert report["Q4"]["qactive"] == {"n": 9, "O_stall": 6, "S_rescued_stall": 6}
    assert sum(report["Q6"]["F_left_box_without_box"].values()) == 415
    first = (HERE / "answer.md").read_text().splitlines()[0]
    assert first.startswith("**Aの中心を担えるか：縮小。**")
    links = []
    generated = {"document-lock.json", "delivery-check.json"}
    for name in DOCUMENTS:
        body = (HERE / name).read_text()
        for target in re.findall(r"\]\(([^\s)]+)\)", body):
            if target.startswith(("https://", "http://", "#")):
                continue
            path = (HERE / target.split("#")[0]).resolve()
            assert path == HERE or HERE in path.parents, (name, target)
            assert path.exists() or target in generated, (name, target)
            links.append([name, target])
    checked_files = list(DOCUMENTS + CODE) + ["source-manifest.json", "reaggregate.json"]
    hashes = {name: digest(HERE / name) for name in checked_files}
    lock_path = HERE / "document-lock.json"
    if lock_path.exists():
        old = json.loads(lock_path.read_text())
        assert old["files"] == hashes, "Frozen Q12 document changed; preserve old version before revising."
    else:
        lock = {"created_utc": datetime.now(timezone.utc).isoformat(),
                "status": "document_only; experiment_unexecuted; executable_preregistration_incomplete",
                "files": hashes}
        lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n")
    package = [p for p in HERE.rglob("*") if p.is_file() and p.name != "delivery-check.json"]
    assert all(p.stat().st_size < 8_000_000 for p in package)
    result = {"checked_utc": datetime.now(timezone.utc).isoformat(), "status": "pass",
              "source_hashes_checked": len(manifest["files"]), "local_document_links_checked": len(links),
              "document_hashes_checked": len(hashes), "package_files_excluding_this_report": len(package),
              "total_bytes_excluding_this_report": sum(p.stat().st_size for p in package),
              "largest_file_bytes": max(p.stat().st_size for p in package),
              "new_local_searches": 0,
              "limitations": ["Arithmetic verification of existing tables; no optimizer replay.",
                              "Q1 is partial and non-random.",
                              "Q2 numerical work and executable preregistration are not performed."]}
    (HERE / "delivery-check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
