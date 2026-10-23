"""Independent integer-count checks and source/registration integrity checks."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def rows(path):
    with (ROOT / path).open() as f:
        return list(csv.DictReader(f))


def main():
    summary = json.loads((HERE / "summary.json").read_text())
    lock = json.loads((HERE / "registration-lock.json").read_text())
    for name, digest in lock["files"].items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest
    sources = json.loads((HERE / "sources.json").read_text())
    for path, info in sources.items():
        assert "sealed-raw" not in path and "unseen-1983" not in path
        data = (ROOT / path).read_bytes()
        assert len(data) == info["bytes"]
        assert hashlib.sha256(data).hexdigest() == info["sha256"], path
    c = rows("jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv")
    cert = rows("jssa/difficulty/certify-all/per-case.csv")
    dev = {r["id"]: r for r in cert if r["group"] == "development323"}
    m = {r["id"]: r for r in c}
    non = [r for r in c if r["msolve_class"] != "answer_set_matches"]
    assert len(non) == 122
    assert sum(int(r["geo_matched"]) > 0 for r in non) == 121
    assert sum(r["geo_matched"] == "3" for r in non) == 115
    assert sum(dev[r["id"]]["status"] == "certified_saved_endpoint_set" for r in non) == 10
    assert sum(r["status"] == "certified_saved_endpoint_set" for r in dev.values()) == 68
    h = rows("jssa/strategy/astra-consult-17/H/classification.csv")
    genuine = [r for r in h if r["evidence_code"] == "G"]
    isolated = [r for r in h if r["evidence_code"] in {"L0", "R0"}]
    assert len(genuine) == 16 and len(isolated) == 38
    assert sum(dev[r["id"]]["status"] == "certified_saved_endpoint_set" for r in genuine) == 6
    assert sum(dev[r["id"]]["status"] == "certified_saved_endpoint_set" for r in isolated) == 1
    chosen, repeated, stable = [], [], []
    combined_starts = 0
    for p in (ROOT / "jssa/difficulty/minima/raw-323").glob("*.json"):
        a = json.loads(p.read_text())
        aa = a.get("records", [])
        if a["n_vars"] <= 0 or not aa or any(r.get("cls") == "hit" for r in aa):
            continue
        cid = a["case_id"]
        chosen.append(cid)
        b = json.loads((ROOT / "jssa/difficulty/minima/raw-323-seed1" / p.name).read_text())
        bb = b.get("records", [])
        if bb and not any(r.get("cls") == "hit" for r in bb):
            repeated.append(cid)
            if m[cid]["geo_matched"] == "3":
                stable.append(cid)
                combined_starts += len(aa) + len(bb)
    assert (len(chosen), len(repeated), len(stable), combined_starts) == (29, 25, 21, 6971)
    attribution = rows("jssa/results/mechanism-attribution/attribution.csv")
    origins = Counter(r["answer_source_uid_prefix"] for r in attribution if r["case_id"] in stable)
    assert origins == {"search/nomad": 49, "search/scipy": 7, "rescue/nomad": 7}
    assert not summary["comparison_attribution_discrepancies"]
    assert not summary["raw_stored_counts_disagreements"]
    provenance = json.loads((ROOT / "jssa/strategy/astra-consult-17/H/sources/provenance.json").read_text())
    data = (ROOT / "jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv").read_bytes()
    data = data[:-1]  # The copied file has one extra trailing newline; no data normalization.
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    assert blob == provenance["files"][0]["sha"]
    result = {
        "passed": True, "locked_files_unchanged": True,
        "source_files_unchanged": len(sources), "comparison_blob_verified": blob,
        "independent_counts": {"selected": 29, "repeated_zero": 25, "zero_both_full_all3": 21, "local_starts": 6971, "origins": dict(origins)},
        "optimizer_calls": 0,
    }
    (HERE / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
