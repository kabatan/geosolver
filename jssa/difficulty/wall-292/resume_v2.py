"""Recover logging and continue the UNCHANGED preregistered local solves."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import run

HERE, ROOT, ARMS = run.HERE, run.ROOT, run.ARMS

_original_write_json = run.write_json
def ensured_write_json(path, obj):
    for attempt in range(100):
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            return _original_write_json(path, obj)
        except FileNotFoundError:
            if attempt == 99:
                raise
            time.sleep(0.1)
run.write_json = ensured_write_json


def load_rows(path):
    rows={}
    malformed=[]
    if path.exists():
        for i,line in enumerate(path.read_text().splitlines(keepends=True)):
            if not line.endswith("\n"):
                malformed.append(i)
                continue
            try:
                r=json.loads(line)
            except json.JSONDecodeError:
                malformed.append(i)
                continue
            assert r["k"] not in rows, (path, "duplicate k", r["k"])
            rows[r["k"]]=r
    return rows, malformed


def arm_order(meta, k):
    i=(meta["index"]+k)%3
    arms=ARMS[i:]+ARMS[:i]
    spec=next(s for s in meta["starts"] if s["k"]==k)
    if spec["diagnostic"] and meta["method"]=="LM":
        arms+=("S",)
    return arms


def atomic_rows(path, meta, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_suffix(path.suffix+".atomic-tmp")
    text="".join(json.dumps(run.clean(rows[s["k"]]),ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n"
                 for s in meta["starts"] if s["k"] in rows)
    for attempt in range(100):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp.write_text(text)
            temp.replace(path)
            return
        except FileNotFoundError:
            if attempt == 99:
                raise
            time.sleep(0.1)


def verify_frozen():
    fixed=json.loads((HERE/"execution-freeze.json").read_text())
    changed=[p for p,h in fixed["sha256"].items() if run.sha(ROOT/p)!=h]
    assert not changed, changed
    return fixed


def prepare():
    verify_frozen()
    assert not (HERE/"recovery-plan.json").exists()
    manifest=json.loads((HERE/"manifest.json").read_text())
    for name in ("initial-summaries", "initial-prefixes", "completed-records", "resume-state", "resume-errors"):
        (HERE/name).mkdir(exist_ok=True)
    for name in ("progress.json", "run.log"):
        shutil.copy2(HERE/name,HERE/("initial-"+name))
    plans=[]
    known_calls=0
    for meta in manifest["problems"]:
        cid=meta["id"]
        path=HERE/"records"/(cid+".jsonl")
        rows,malformed=load_rows(path)
        summary_path=HERE/"case-summary"/(cid+".json")
        summary=json.loads(summary_path.read_text()) if summary_path.exists() else None
        if summary is not None:
            shutil.copy2(summary_path,HERE/"initial-summaries"/summary_path.name)
        missing=[s["k"] for s in meta["starts"] if s["k"] not in rows]
        assert set(rows)<=set(s["k"] for s in meta["starts"])
        if missing and path.exists():
            shutil.copy2(path,HERE/"initial-prefixes"/path.name)
        if not missing:
            atomic_rows(HERE/"completed-records"/path.name,meta,rows)
        completed_initial=summary is not None and summary.get("n")==meta["n"]
        initial_known_k=[s["k"] for s in meta["starts"]] if completed_initial else list(rows)
        initial_calls=sum(len(arm_order(meta,k)) for k in initial_known_k)
        known_calls+=initial_calls
        plans.append({"id":cid,"initial_summary":summary,"retained_k":list(rows),"missing_k":missing,
                      "malformed_lines":malformed,"initial_calls_at_least":initial_calls,
                      "missing_from_completed_initial":completed_initial and bool(missing),
                      "new_calls_planned":sum(len(arm_order(meta,k)) for k in missing),
                      "prefix_sha256":run.sha(path) if path.exists() else None})
    run.write_json(HERE/"recovery-plan.json",{
        "fixed_utc":run.stamp(),"initial_exit_code":1,"initial_exit_reason":"unknown; preserved log lacks final error",
        "initial_calls_at_least":known_calls,"unrecorded_initial_attempts_unknown":True,
        "protocol_sha256":run.sha(HERE/"recovery-protocol.md"),"resume_code_sha256":run.sha(Path(__file__)),
        "cases":plans})
    print(json.dumps({"retained_starts":sum(len(r["retained_k"]) for r in plans),
                      "missing_starts":sum(len(r["missing_k"]) for r in plans),
                      "missing_from_completed_starts":sum(len(r["missing_k"]) for r in plans if r["missing_from_completed_initial"]),
                      "initial_calls_at_least":known_calls,"new_calls_planned":sum(r["new_calls_planned"] for r in plans)}),flush=True)


def summary(meta,rows,seconds,case_error=None):
    out={"id":meta["id"],"n":len(rows),"method":meta["method"],"seconds":seconds,
         "counts":{a:dict(Counter(r[a]["cls"] for r in rows.values())) for a in ARMS},
         "B_old_disagree":sum(r["B"]["cls"]!=r["old_cls"] for r in rows.values()),
         "completed_utc":run.stamp(),"storage":"atomic prefix plus complete backup"}
    if case_error:
        out["case_error"]=case_error
    return out


def worker(cid):
    run.init_worker()
    manifest=json.loads((HERE/"manifest.json").read_text())
    meta=next(r for r in manifest["problems"] if r["id"]==cid)
    plan=next(r for r in json.loads((HERE/"recovery-plan.json").read_text())["cases"] if r["id"]==cid)
    t0=time.monotonic()
    context=run.case_context(cid)
    case,bundle,ev,raw,bounds,lo,width=context
    assert run.sha(ROOT/"jssa/difficulty/minima/raw-323"/(cid+".json"))==meta["raw_sha256"]
    assert hashlib.sha256(json.dumps(case,sort_keys=True,ensure_ascii=False).encode()).hexdigest()==meta["case_sha256"]
    refs=run.reference_values(case["answer"])
    config=run.ExternalPipelineConfig.production_baseline_tier(seed=0,total_time_budget_sec=180).search
    path=HERE/"records"/(cid+".jsonl")
    rows,_=load_rows(path)
    saved={r["k"]:r for r in raw["records"]}
    state_path=HERE/"resume-state"/(cid+".json")
    state=(json.loads(state_path.read_text()) if state_path.exists() else
           {"new_calls":{},"partial":None,"active_arm":None,"interrupted_arms":[]})
    if state.get("active_arm") and state.get("partial"):
        a=state["active_arm"]
        state["partial"][a]={"cls":"error","exception":"worker exited after arm start before recording result","optimizer":{}}
        state["interrupted_arms"].append({"k":state["partial"]["k"],"arm":a})
        state["active_arm"]=None
        run.write_json(state_path,state)
    for spec in meta["starts"]:
        k=spec["k"]
        if k in rows:
            continue
        old=saved[k]
        rec=(state["partial"] if state.get("partial") and state["partial"]["k"]==k else
             {"k":k,"F":spec["F"],"diagnostic":spec["diagnostic"],"start":old["start"],"old_cls":old["cls"],
              "order":list(arm_order(meta,k)),"recovery_origin":"missing_initial_log" if plan["missing_from_completed_initial"] else "continuation_after_exit"})
        for a in arm_order(meta,k):
            if a in rec:
                continue
            state["partial"]=rec
            state["active_arm"]=a
            state["new_calls"][a]=state["new_calls"].get(a,0)+1
            run.write_json(state_path,state)
            try:
                rec[a]=run.solve(context,old["start"],k,a,spec["diagnostic"],refs,config)
            except Exception as ex:
                rec[a]={"cls":"error","exception":repr(ex),"optimizer":{}}
            state["partial"]=rec
            state["active_arm"]=None
            run.write_json(state_path,state)
        rows[k]=rec
        atomic_rows(path,meta,rows)
        state["partial"]=None
        run.write_json(state_path,state)
    atomic_rows(path,meta,rows)
    atomic_rows(HERE/"completed-records"/path.name,meta,rows)
    out=summary(meta,rows,time.monotonic()-t0)
    run.write_json(HERE/"case-summary"/(cid+".json"),out)


def run_child(meta):
    cid=meta["id"]
    for attempt in (1,2):
        ans=subprocess.run([sys.executable,str(Path(__file__)) ,"worker",cid],cwd=ROOT,capture_output=True,text=True)
        if ans.returncode==0:
            return json.loads((HERE/"case-summary"/(cid+".json")).read_text())
        run.write_json(HERE/"resume-errors"/f"{cid}-attempt-{attempt}.json",{
            "returncode":ans.returncode,"stdout":ans.stdout[-20000:],"stderr":ans.stderr[-20000:],"utc":run.stamp()})
    path=HERE/"records"/(cid+".jsonl")
    rows,_=load_rows(path)
    raw=json.loads((ROOT/"jssa/difficulty/minima/raw-323"/(cid+".json")).read_text())
    saved={r["k"]:r for r in raw["records"]}
    state_path=HERE/"resume-state"/(cid+".json")
    state=json.loads(state_path.read_text()) if state_path.exists() else {}
    for spec in meta["starts"]:
        k=spec["k"]
        if k in rows:
            continue
        old=saved[k]
        rec=(state["partial"] if state.get("partial") and state["partial"]["k"]==k else
             {"k":k,"F":spec["F"],"diagnostic":spec["diagnostic"],"start":old["start"],"old_cls":old["cls"],"order":list(arm_order(meta,k))})
        for a in arm_order(meta,k):
            if a not in rec:
                rec[a]={"cls":"error" if state.get("active_arm")==a and (state.get("partial") or {}).get("k")==k else "missing_run",
                        "exception":"case process failed twice; no further attempts","optimizer":{}}
        rows[k]=rec
    atomic_rows(path,meta,rows)
    atomic_rows(HERE/"completed-records"/path.name,meta,rows)
    out=summary(meta,rows,0,"worker failed twice; see resume-errors")
    run.write_json(HERE/"case-summary"/(cid+".json"),out)
    return out


def main_run():
    verify_frozen()
    plan=json.loads((HERE/"recovery-plan.json").read_text())
    extension=json.loads((HERE/"recovery-v2-freeze.json").read_text())
    assert extension["code_sha256"]==run.sha(Path(__file__))
    assert extension["plan_sha256"]==run.sha(HERE/"recovery-plan.json")
    for name in ("initial-summaries", "initial-prefixes", "completed-records", "resume-state", "resume-errors", "records", "case-summary"):
        (HERE/name).mkdir(parents=True, exist_ok=True)
    assert plan["protocol_sha256"]==run.sha(HERE/"recovery-protocol.md")
    manifest=json.loads((HERE/"manifest.json").read_text())
    pending_ids={r["id"] for r in plan["cases"] if r["missing_k"]}
    completed=[]
    for meta in manifest["problems"]:
        if meta["id"] in pending_ids:
            continue
        path=HERE/"case-summary"/(meta["id"]+".json")
        if path.exists():
            completed.append(json.loads(path.read_text()))
        else:
            rows,_=load_rows(HERE/"records"/(meta["id"]+".jsonl"))
            row=summary(meta,rows,0)
            run.write_json(path,row)
            completed.append(row)
    pending=sorted([r for r in manifest["problems"] if r["id"] in pending_ids],key=lambda r:(-r["old_seconds"],r["id"]))
    run.write_json(HERE/"resume-start.json",{"started_utc":run.stamp(),"pending_cases":len(pending),"max_child_processes":4})
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(run_child,meta):meta["id"] for meta in pending}
        for future in as_completed(jobs):
            row=future.result()
            completed.append(row)
            run.write_json(HERE/"progress.json",{"updated_utc":run.stamp(),"completed":len(completed),"total":292,"cases":completed,"phase":"resume"})
            print(json.dumps({"complete":len(completed),"id":row["id"],"n":row["n"],"case_error":row.get("case_error")},ensure_ascii=False),flush=True)
    run.write_json(HERE/"run-complete.json",{"completed_utc":run.stamp(),"cases":len(completed),
                                           "case_errors":sum("case_error" in r for r in completed),"phase":"resume"})
    print("ALL COMPLETE",flush=True)


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("stage",choices=("prepare","run","worker"))
    ap.add_argument("id",nargs="?")
    args=ap.parse_args()
    if args.stage=="prepare":prepare()
    elif args.stage=="run":main_run()
    else:worker(args.id)
