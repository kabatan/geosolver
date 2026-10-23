"""Read-only audit of completed raw records; writes only the audit in HERE."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ARMS = ("B", "N", "G2")
PREREG = "f4a72cadf217c76c47b1466cdcaf1adf36696f3449feef7182e3f6b0e05586ac"


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert (HERE/"run-complete.json").exists(), "Audit requires a completed run"
    assert digest(HERE/"preregistration.md") == PREREG
    frozen = json.loads((HERE/"execution-freeze.json").read_text())
    changed = [p for p, h in frozen["sha256"].items() if digest(ROOT/p) != h]
    assert not changed, changed
    manifest = json.loads((HERE/"manifest.json").read_text())
    cases = {c["id"]: c for c in map(json.loads, (ROOT/"benchmarks/cases.jsonl").open())}
    table = {r["id"]: r for r in csv.DictReader((HERE/"per-problem.csv").open())}
    counts = Counter()
    counts_by_arm = {a: Counter() for a in (*ARMS, "S")}
    differences = []
    for meta in manifest["problems"]:
        cid = meta["id"]
        path = ROOT/"jssa/difficulty/minima/raw-323"/(cid+".json")
        assert digest(path) == meta["raw_sha256"], cid
        raw = json.loads(path.read_text())
        by_k = {r["k"]:r for r in raw["records"]}
        expected_case_hash = hashlib.sha256(json.dumps(cases[cid], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        assert expected_case_hash == meta["case_sha256"], cid
        p = HERE/"records"/(cid+".jsonl")
        lines = p.read_text().splitlines(keepends=True) if p.exists() else []
        assert all(l.endswith("\n") for l in lines), (cid,"partial line")
        rows = [json.loads(l) for l in lines]
        found = {r["k"]:r for r in rows}
        assert len(found) == len(rows), (cid, "duplicates")
        if len(rows) != meta["n"]:
            counts["missing_records"] += meta["n"]-len(rows)
        pc = {a: Counter() for a in ARMS}
        for spec in meta["starts"]:
            k = spec["k"]
            if k not in found:
                for a in ARMS:
                    pc[a]["missing_run"] += 1
                continue
            r = found[k]
            old = by_k[k]
            assert r["start"] == old["start"], (cid,k,"start changed")
            assert r["F"] == spec["F"] and r["diagnostic"] == spec["diagnostic"]
            order = (meta["index"]+k)%3
            arms = ARMS[order:]+ARMS[:order]
            if spec["diagnostic"] and meta["method"] == "LM":
                arms += ("S",)
            assert r["order"] == list(arms)
            assert all(a in r for a in arms)
            counts["paired_starts"] += 1
            for a in arms:
                o = r[a]
                counts_by_arm[a][o["cls"]] += 1
                if a in ARMS:
                    pc[a][o["cls"]] += 1
                native = o.get("native")
                if native and native.get("raw_info") is not None:
                    counts["native_completed"] += 1
                    raw_info = native["raw_info"]
                    assert raw_info in range(1,9)
                    opt=o.get("optimizer", {})
                    if "nfev" in opt:
                        assert opt["nfev"] == native["native_nfev"], (cid,k,a,"nfev")
                    counts["native_issue_runs"] += bool(native.get("issues"))
                if o["cls"] == "hit":
                    assert o["hard"] is True and o["res"] <= 1e-8 and o["ans"] is not None
                    assert all(lo <= x <= hi for x,(lo,hi) in zip(o["x"],raw["box"]))
                    assert any(abs(o["ans"]-ref) <= 1e-6*max(1,abs(ref)) for ref in raw["references"])
            b = r["B"]
            counts["B_old_class_equal"] += b["cls"] == old["cls"]
            if b.get("x") is not None and old.get("x") is not None:
                equal = b["x"] == old["x"]
                counts["B_old_x_comparable"] += 1
                counts["B_old_x_exact_equal"] += equal
                counts["B_old_x_exact_equal_diagnostic"] += equal and r["diagnostic"]
            if b["cls"] != old["cls"]:
                differences.append({"id":cid,"k":k,"old":old["cls"],"new":b["cls"],
                                    "diagnostic":r["diagnostic"],"seconds":b.get("seconds"),
                                    "old_seconds":old.get("sec")})
        for a in ARMS:
            assert sum(pc[a].values()) == meta["n"]
            assert int(table[cid][a+"_hits"]) == pc[a]["hit"]
            assert abs(float(table[cid]["p_"+a])-pc[a]["hit"]/meta["n"]) < 1e-12
    sizes=[(p.stat().st_size,str(p.relative_to(HERE))) for p in HERE.rglob("*") if p.is_file()]
    assert max(sizes)[0] < 20*1024**2
    out={"preregistration_sha256":PREREG,"unchanged_frozen_files":len(frozen["sha256"]),
         "changed_frozen_files":changed,"counts":dict(counts),
         "classes":{a:dict(c) for a,c in counts_by_arm.items()},"old_B_class_differences":differences,
         "largest_file_bytes_and_name":max(sizes),"total_artifact_bytes":sum(n for n,_ in sizes),
         "pycache_paths":[str(p.relative_to(HERE)) for p in HERE.rglob("__pycache__")]}
    (HERE/"audit.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"audit":"passed","pairs":counts["paired_starts"],"old_B_differences":len(differences),
                      "changed_files":changed,"largest_bytes":max(sizes)[0]}))


if __name__ == "__main__":
    main()
