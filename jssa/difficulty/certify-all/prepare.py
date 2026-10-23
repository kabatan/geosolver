"""Freeze answer-blind inputs from already saved numerical endpoints.

No solver execution and no use of references, cls, ref, or official answer fields.
The original main-campaign output is not present in the inspected checkout.
"""
from pathlib import Path
import collections
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
L = ROOT / "jssa/strategy/astra-consult-17/L"


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    assert len(data.encode()) < 8 * 1024**2
    p.write_text(data)


def main():
    dest = HERE / "inputs"
    dest.mkdir(exist_ok=True)
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "primary_main_output_available": False,
        "source_rule": "raw-323 seed0 or new2026-predict/raw seed5; all finite ans with res<=1e-8, ordered k; first representative of each 1e-7 relative cluster; never consult cls/ref/references/official answer",
        "primary_missing_reason": "Main-campaign CSVs contain no returned values. Recorded original path /home/kabatan/work/geosolver/benchmarks/local-evaluation/jssa-main-j6-20261022 is absent; local HEAD and fetched origin branches have no main-campaign run JSONs.",
        "zero_variable_rule": "No saved numerical endpoint; record missing candidate, still attempt DSL encoding; do not substitute official answer or newly solve.",
        "preregistration_sha256": digest(HERE / "preregistration.md"),
        "cases": [],
        "reused_sources": {str(p.relative_to(ROOT)): digest(p) for p in [
            L / "certificate.py", L / "experiment.py", L / "verify_certificate.py",
            L / "vendor/algebraize.py", L / "vendor/run_exact.py",
            L / "audit_source/certify.py", L / "audit_source/README.md", L / "answer.md",
        ]},
    }
    for group, src, raw in [
        ("development323", ROOT / "benchmarks/cases.jsonl", ROOT / "jssa/difficulty/minima/raw-323"),
        ("holdout2026", ROOT / "jssa/difficulty/new2026/cases.jsonl", ROOT / "jssa/difficulty/new2026-predict/raw"),
    ]:
        cases = [json.loads(line) for line in src.read_text().splitlines()]
        assert len(cases) == (323 if group == "development323" else 20)
        for c in sorted(cases, key=lambda c: c["id"]):
            cid = c["id"]
            rp = raw / f"{cid}.json"
            d = json.loads(rp.read_text()) if rp.exists() else {}
            candidates = []
            eligible = 0
            for r in sorted(d.get("records", []), key=lambda r: r["k"]):
                a, res = r.get("ans"), r.get("res", math.inf)
                if a is None or not math.isfinite(a) or not math.isfinite(res) or res > 1e-8:
                    continue
                eligible += 1
                if any(abs(a - v["value_float"]) <= 1e-7 * max(1.0, abs(a), abs(v["value_float"])) for v in candidates):
                    continue
                candidates.append({"k": r["k"], "value_float": a, "x": r["x"], "saved_residual": res})
            payload = {
                "id": cid, "group": group, "dsl": c["dsl"],
                "source_kind": "saved_local_search_endpoints" if candidates else "missing_saved_candidate",
                "source_path": str(rp.relative_to(ROOT)), "source_sha256": digest(rp) if rp.exists() else None,
                "saved_seed": d.get("seed"), "eligible_records": eligible,
                "candidates": candidates, "primary_main_output_available": False,
                "source_status": d.get("status", "absent"),
            }
            ip = dest / f"{cid}.json"
            write(ip, payload)
            manifest["cases"].append({k: payload[k] for k in ["id", "group", "source_kind", "source_path", "source_sha256", "source_status"]} | {
                "input_sha256": digest(ip), "candidate_count": len(candidates),
                "dsl_sha256": hashlib.sha256(json.dumps(c["dsl"], sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            })
    manifest["counts"] = dict(collections.Counter((r["group"] + ":" + r["source_kind"]) for r in manifest["cases"]))
    manifest["git_head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest["src_tree"] = subprocess.check_output(["git", "rev-parse", "HEAD:src"], cwd=ROOT, text=True).strip()
    write(HERE / "input-manifest.json", manifest)
    print(json.dumps(manifest["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
