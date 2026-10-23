"""Prepare public E2H downloads and retain the rows needed for E.

All writes are confined to this directory. Network transfers use the generated
curl config, with responses capped at 4 MiB and 20 seconds each. Python does
not perform network operations. Saved data permits offline reanalysis.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlencode

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def main():
    if "--merge-retry-pages" in sys.argv:
        # Recover the one API page that returned HTML. Two 50-row requests
        # cover the same [100,200) slice. Preserve the original failed receipt.
        human = [r for r in csv.DictReader((ROOT / "jssa/difficulty/ghost-1023/human_feat.csv").open()) if r["human"]]
        keys = {(r["contest"], int(r["case_id"].split("-")[1]), int(r["case_id"].split("-")[-1])) for r in human}
        records = {(r["split"], r["row_idx"]):r for r in map(json.loads,(OUT/"e2h-rows.jsonl").read_text().splitlines())}
        manifest = json.loads((OUT/"source-fetch.json").read_text())
        if not any("error" in r for r in manifest["requests"]):
            print("No failed pages to merge; no change")
            return
        retry_receipts=[]
        indices=[]
        for offset in (100,150):
            path=OUT/"source-pages"/f"eval-{offset}-retry50.json"
            obj=json.loads(path.read_text())
            assert len(obj["rows"])==50 and obj["num_rows_total"]==2975
            for rr in obj["rows"]:
                indices.append(rr["row_idx"])
                r=rr["row"]
                if (r["contest"],r["year"],r["index"]) in keys:
                    records[("eval",rr["row_idx"])]=dict(split="eval",row_idx=rr["row_idx"],
                        truncated_cells=rr.get("truncated_cells",[]),**{k:v for k,v in r.items() if k!="solution"})
            params=dict(dataset="furonghuang-lab/Easy2Hard-Bench",config="E2H-AMC",split="eval",offset=offset,length=50)
            receipt=dict(url="https://datasets-server.huggingface.co/rows?"+urlencode(params),
                         path=str(path.relative_to(OUT)),split="eval",n_rows=50,total=2975,
                         raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            retry_receipts.append(receipt)
        assert sorted(indices)==list(range(100,200))
        manifest["failed_requests"]=[r for r in manifest["requests"] if "error" in r]
        manifest["requests"]=[r for r in manifest["requests"] if "error" not in r]+retry_receipts
        assert sum(r["n_rows"] for r in manifest["requests"])==3975
        data="".join(json.dumps(records[k],ensure_ascii=False)+"\n" for k in sorted(records))
        (OUT/"e2h-rows.jsonl").write_text(data)
        manifest.update(rows=len(records),sha256=hashlib.sha256(data.encode()).hexdigest(),
                        repair="Original eval offset=100 length=100 returned HTML; recovered with 2 x 50 rows.")
        (OUT/"source-fetch.json").write_text(json.dumps(manifest,indent=2))
        for r in retry_receipts:
            (OUT/r["path"]).write_text(json.dumps(r,indent=2))
        print("Merged complete source; candidate rows",len(records))
        return
    if "--plan-rows" in sys.argv:
        # /filter did not return within 30 s in this environment. /rows works.
        # At most 40 small pages, each <4 MiB; use curl directly so its existing
        # execution permission is used rather than a network-enabled Python.
        (OUT / "source-pages").mkdir(exist_ok=True)
        lines = ['max-time = 20', 'max-filesize = 4194304', 'fail', 'show-error']
        requests = []
        for split, total in (("train", 1000), ("eval", 2975)):
            for offset in range(0, total, 100):
                params = dict(dataset="furonghuang-lab/Easy2Hard-Bench", config="E2H-AMC",
                              split=split, offset=offset, length=100)
                url = "https://datasets-server.huggingface.co/rows?" + urlencode(params)
                dest = OUT / "source-pages" / f"{split}-{offset}.json"
                lines += [f'url = "{url}"', f'output = "{dest}"']
                requests.append({"url": url, "path": str(dest.relative_to(OUT)), "split": split})
        (OUT / "fetch.curl").write_text("\n".join(lines) + "\n")
        (OUT / "fetch-requests.json").write_text(json.dumps(requests, indent=2))
        print("Prepared", len(requests), "small pages")
        return
    if "--ingest-rows" in sys.argv:
        reqs = json.loads((OUT / "fetch-requests.json").read_text())
        loaded = []
        for req in reqs:
            path = OUT / req["path"]
            try:
                obj = json.loads(path.read_text())
            except Exception as exc:
                raise RuntimeError(f"Missing/invalid page {path}; fetch the pages before ingestion") from exc
            loaded.append(obj)
        if all("rows" not in obj for obj in loaded) and (OUT / "e2h-rows.jsonl").exists():
            print("Already ingested; retained data left unchanged. Fetch again to refresh.")
            return
        if any("rows" not in obj for obj in loaded):
            raise RuntimeError("Incomplete page set; no output changed. Fetch all pages again.")
        human = [r for r in csv.DictReader((ROOT / "jssa/difficulty/ghost-1023/human_feat.csv").open()) if r["human"]]
        keys = {(r["contest"], int(r["case_id"].split("-")[1]), int(r["case_id"].split("-")[-1])) for r in human}
        records, log = [], []
        for req in reqs:
            path = OUT / req["path"]
            try:
                obj = json.loads(path.read_text())
                for rr in obj["rows"]:
                    r = rr["row"]
                    if (r["contest"], r["year"], r["index"]) in keys:
                        records.append({"split": req["split"], "row_idx": rr["row_idx"],
                                        "truncated_cells": rr.get("truncated_cells", []),
                                        **{k:v for k,v in r.items() if k != "solution"}})
                # Keep provenance and counts, replace raw unrelated problems and
                # solutions to limit storage. The script owns these new files.
                log.append({**req, "n_rows": len(obj["rows"]), "total": obj["num_rows_total"],
                            "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
                path.write_text(json.dumps(log[-1], indent=2))
            except Exception as exc:
                log.append({**req, "error": str(exc)})
        data = "".join(json.dumps(r, ensure_ascii=False)+"\n" for r in records)
        (OUT / "e2h-rows.jsonl").write_text(data)
        (OUT / "source-fetch.json").write_text(json.dumps({
            "date": "2026-10-23", "dataset": "https://huggingface.co/datasets/furonghuang-lab/Easy2Hard-Bench",
            "license": "CC-BY-SA-4.0 (dataset card)", "requests": log,
            "rows": len(records), "sha256": hashlib.sha256(data.encode()).hexdigest(),
            "note": "Solutions and unrelated rows not retained. /filter unavailable; /rows used. Raw page files now contain provenance only."
        }, indent=2))
        print("Saved", len(records), "candidate rows")
        return
    print("Use --plan-rows, then curl -sS --config <E>/fetch.curl, then --ingest-rows.")
    print("The historical 100-row API failure can be recovered with --merge-retry-pages after fetching two 50-row pages.")


if __name__ == "__main__":
    main()
