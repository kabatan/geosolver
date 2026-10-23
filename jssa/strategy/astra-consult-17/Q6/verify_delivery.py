"""Check evidence joins, frozen inputs, preregistration, and delivery bounds."""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy
import scipy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREREG_SHA256 = "8decbcf01ade9e59ccf632814c18796b2212302f8de98d119e6ff8ba87a997ba"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    manifest=json.loads((HERE/"input-manifest.json").read_text())
    assert sha(HERE/"preregistration.md")==PREREG_SHA256
    for name,expected in manifest["sha256"].items():
        assert sha(ROOT/name)==expected, name
    summary=json.loads((HERE/"per-problem.json").read_text())
    starts={r["id"]:r for r in csv.DictReader((ROOT/"jssa/difficulty/start-feasibility-1023/per-problem.csv").open())}
    census={r["id"]:r for r in csv.DictReader((ROOT/"jssa/strategy/astra-consult-17/G/census.csv").open())}
    records=list(csv.DictReader((HERE/"per-start.csv").open()))
    assert len(records)==2350 and len(summary)==12
    assert len({(r["id"],r["k"]) for r in records})==2350
    assert all(r["replay_cls"]==r["cls"] for r in records)
    expected_selection=sorted(
        [r for r in census.values() if int(r["n_F"])>=10 and int(r["n_I"])>=10
         and float(r["p_I"])>float(r["p_F"])
         and int(r["F_left_box"])+int(r["F_wrong_answer"])>0],
        key=lambda r:(-int(r["F_left_box"])-int(r["F_wrong_answer"]),r["id"]))
    assert manifest["selected_ids"]==[r["id"] for r in expected_selection]
    fbox=Counter()
    for r in summary:
        cid=r["id"]; independent=starts[cid]; old=census[cid]
        assert r["F_n"]==int(independent["n_feas"])==int(old["n_F"])
        assert r["I_n"]==int(independent["n_infeas"])==int(old["n_I"])
        assert r["F_original"].get("hit",0)==int(independent["hit_feas"])
        assert r["I_original"].get("hit",0)==int(independent["hit_infeas"])
        for cls in ["hit","left_box","stuck","wrong_answer","wrong_branch","error"]:
            assert r["F_original"].get(cls,0)==int(old["F_"+cls])
        fbox.update(r["F_left_box_without_box"])
    assert dict(fbox)=={"stuck":385,"hit":29,"wrong_answer":1}
    mechanism=json.loads((HERE/"mechanism-checks.json").read_text())
    assert mechanism["preregistration_sha256"]==PREREG_SHA256
    assert mechanism["preregistered_predictions"]=={
        "P1":{"n":48,"pass":48,"threshold":.8},
        "P2":{"n":120,"pass":120,"threshold":.8},
        "P3":{"n":24,"pass":24,"threshold":.5}}
    g_trace=ROOT/"jssa/strategy/astra-consult-17/G/mechanism-data/JMO-2017-PRE-01.json"
    assert sha(g_trace)==mechanism["jmo_2017_1"]["G_trace_sha256"]
    # Independent joins to the older endpoint perturbation data.
    g_diag=[json.loads(line) for line in (ROOT/"jssa/strategy/astra-consult-17/G/endpoint-diagnostics.jsonl").open()
            if '"JMO-2017-PRE-01"' in line]
    assert sum(r["cls"]=="left_box" and r["b6"]==1 for r in g_diag)==120
    assert sum(r["cls"]=="stuck" and r["b6"]==1 for r in g_diag)==15
    frozen=subprocess.run(["git","diff","--quiet","60db4b6","--","src"],cwd=ROOT,check=False).returncode==0
    assert frozen
    sizes={p.name:p.stat().st_size for p in HERE.iterdir() if p.is_file()}
    assert all(n<10*1024*1024 for n in sizes.values())
    assert not (HERE/"__pycache__").exists()
    deep=json.loads((HERE/"deep-audit.json").read_text())
    for cid in ["HMMT-2007-FEB-GEO-04","JMO-2017-PRE-01","AIME-2021-II-14"]:
        assert deep[cid]["seed1"]["records_with_start"]==0
        assert deep[cid]["seed1"]["records_with_x"]==0
    # Report exactly which source/code hashes underlie this delivery.
    selected_paths=[p for p in HERE.iterdir() if p.is_file() and p.name!="delivery-check.json"]
    result={"checked_at_utc":datetime.now(timezone.utc).isoformat(),"status":"pass",
        "python":platform.python_version(),"numpy":numpy.__version__,"scipy":scipy.__version__,
        "preregistration_sha256":PREREG_SHA256,"source_inputs_checked":len(manifest["sha256"]),
        "selection_matches_preregistered_rule":True,"problems":12,"endpoints":2350,
        "classification_mismatches":0,"independent_start_and_G_census_joins":"all match",
        "G_JMO_boundary_rejoin":{"left_box":120,"stuck":15},
        "F_box_secondary_classes":dict(fbox),"new_local_search_runs":0,
        "src_matches_60db4b6":frozen,"all_files_below_10_MiB":True,
        "artifact_sizes_bytes":sizes,"artifact_sha256":{p.name:sha(p) for p in selected_paths}}
    (HERE/"delivery-check.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ["artifact_sizes_bytes","artifact_sha256"]},ensure_ascii=False))


if __name__=="__main__":
    main()
