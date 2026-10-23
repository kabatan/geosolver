"""Independent receipt checks for the E analysis and target intervention."""
import csv
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]


def main():
    rows=list(csv.DictReader((OUT/"features.csv").open()))
    cases={c["id"]:c for c in map(json.loads,(ROOT/"benchmarks/cases.jsonl").read_text().splitlines())}
    byid={r["id"]:r for r in rows}
    assert len(byid)==len(rows)==323
    assert set(byid)==set(cases)
    for cid,r in byid.items():
        assert int(r["n_vars"])==len(cases[cid]["dsl"]["variables"])
        assert int(r["n_cons"])==len(cases[cid]["dsl"]["constructions"])
    # Hand-audited named-construction graphs, not recomputation by the extractor.
    assert byid["AIME-2021-I-11"]["target_only_names"]=="C1;D1"
    assert int(byid["AIME-2021-I-11"]["target_depth"])==2
    assert int(byid["AIME-2014-II-14"]["target_only"])==0  # P also occurs in a guard.
    assert int(byid["AIME-2014-II-14"]["target_depth"])==4
    assert int(byid["HMMT-2019-FEB-GEO-10"]["target_depth"])==4
    human=[r for r in rows if r["human"]]
    assert len(human)==131
    common=[r for r in human if r["p"]]
    assert len(common)==109
    raw_mismatch=[]
    for r in common:
        raw=json.loads((ROOT/"jssa/difficulty/minima/raw-323"/(r["id"]+".json")).read_text())
        rec=raw["records"]
        p=sum(x.get("cls")=="hit" for x in rec)/len(rec)
        if abs(p-float(r["p"]))>1e-12 or len(rec)!=int(r["n_starts"]):
            raw_mismatch.append(r["id"])
    assert not raw_mismatch,raw_mismatch
    join=list(csv.DictReader((OUT/"source-join.csv").open()))
    missing=[r["id"] for r in join if r["n_matches"]!="1"]
    assert len(missing)==0
    assert max(abs(float(r["rating_difference"])) for r in join if r["rating_difference"])<1e-12
    assert all(r["truncated_cells"]=="[]" for r in join if r["n_matches"]=="1")
    source=json.loads((OUT/"source-fetch.json").read_text())
    assert len(source["requests"]) in (40,41)
    assert sum(r["n_rows"] for r in source["requests"])==3975
    intervention=json.loads((OUT/"target-swap-records.json").read_text())
    assert len(intervention)==128
    assert sum(len(r["variants"]) for r in intervention)==384
    pairs=[v for r in intervention for v in r["paired"].values()]
    assert len(pairs)==256
    assert all(all(p.values()) for p in pairs)
    assert all(v["candidate"] and v["error"] is None for r in intervention for v in r["variants"].values())
    manifest=json.loads((OUT/"target-swap-manifest.json").read_text())
    assert manifest["inputs_unchanged"]
    current_changes=[p for p,h in manifest["inputs_before"].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    report=dict(passed=True, feature_rows=len(rows), human_rows=len(human), local_rows=len(common),
                raw_p_checked=len(common),raw_p_mismatches=raw_mismatch,original_texts=len(join)-len(missing),
                missing_original_texts=missing,original_texts_truncated=0,
                source_total_rows=3975,intervention_runs=384,paired_comparisons=256,
                source_files_unchanged_during_intervention=True,source_changes_since_intervention=current_changes,
                intervention_sum_sec=sum(v["sec"] for r in intervention for v in r["variants"].values()),
                intervention_total_nfev=sum(v["nfev"] for r in intervention for v in r["variants"].values()),
                artifact_bytes=sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file()))
    (OUT/"audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
