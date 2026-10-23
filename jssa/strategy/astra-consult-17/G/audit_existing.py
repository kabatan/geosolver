"""Recompute inherited summaries and verify source counts, without local search."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
from concurrent.futures import ProcessPoolExecutor

from common import HERE, ROOT, RAW, case_context, feasible, write_json


def diff(a, b, prefix=""):
    if isinstance(a, dict) and isinstance(b, dict):
        return [item for key in sorted(a.keys() | b.keys())
                for item in diff(a.get(key), b.get(key), f"{prefix}/{key}")]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [prefix+": length"]
        return [item for i, (u, v) in enumerate(zip(a, b)) for item in diff(u, v, f"{prefix}/{i}")]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return [] if math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12) else [prefix]
    return [] if a == b else [prefix]


def counts(cid):
    case, bundle, ev, raw, *_ = case_context(cid)
    out = {"id": cid, "n_F": 0, "n_I": 0, "hit_F": 0, "hit_I": 0}
    for r in raw["records"]:
        if "start" not in r:
            continue
        tag = "F" if feasible(ev, r["start"]) else "I"
        out["n_"+tag] += 1
        out["hit_"+tag] += r["cls"] == "hit"
    return out


def main():
    provenance = json.loads((HERE / "provenance.json").read_text())
    report = {"input_hash_mismatches": [name for name, digest in provenance["sha256"].items()
                if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest]}
    assert not report["input_hash_mismatches"]
    outputs = ["summary.json", "input-models.json", "intervention-summary.json", "provenance.json"]
    previous = {name: json.loads((HERE/name).read_text()) for name in outputs}
    report["inherited_sha256_before_reanalysis"] = {name: hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in outputs}
    import analyze
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        analyze.main()
    (HERE / "analysis.log").write_text(log.getvalue())
    report["reanalysis_differences"] = {name: diff(previous[name], json.loads((HERE/name).read_text())) for name in outputs}
    census = json.loads((HERE / "census.json").read_text())
    byid = {r["id"]: r for r in census}
    with ProcessPoolExecutor(max_workers=4) as pool:
        got = list(pool.map(counts, sorted(byid)))
    report["source_count_differences"] = [f"{r['id']}/{k}" for r in got for k in ("n_F", "n_I", "hit_F", "hit_I") if r[k] != byid[r["id"]][k]]
    report["source_problems"] = len(got)
    report["source_starts"] = sum(r["n_F"]+r["n_I"] for r in got)
    # Re-evaluate the three examples specified by the task, including their perturbations.
    from census import one_case
    ids = sorted(byid)
    report["endpoint_example_recheck"] = {}
    details = [json.loads(s) for s in (HERE/"endpoint-diagnostics.jsonl").read_text().splitlines()]
    for cid in ("AIME-2010-II-14", "HMMT-2007-FEB-GEO-04", "JMO-2017-PRE-01"):
        row, detail = one_case((ids.index(cid), cid))
        report["endpoint_example_recheck"][cid] = {
            "census": diff({k:v for k,v in byid[cid].items() if k != "seconds"},
                           {k:v for k,v in row.items() if k != "seconds"}),
            "details": diff([r for r in details if r["id"] == cid], detail)}
    # Instrumentation fix changed logging of zero-displacement calls only.
    old_digest = json.loads((HERE/"instrumentation-before-fix.json").read_text())
    keys = ["cls", "x", "res", "hard", "ans"]
    arms = ["B", "S", "J", "N", "C", "CS"]
    changed = []
    for cid, digest in old_digest.items():
        data = json.loads((HERE/"mechanism-data"/f"{cid}.json").read_text())
        values = [{"k": r["k"], **{a: {**{k:r[a].get(k) for k in keys},
                   "status": r[a]["optimizer"].get("status"), "raw_info": r[a]["native"]["raw_info"]} for a in arms}} for r in data["records"]]
        if hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest() != digest:
            changed.append(cid)
    report["instrumentation_fix_outcome_changes"] = changed
    write_json(HERE / "inheritance-audit.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
