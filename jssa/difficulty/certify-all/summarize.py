"""Summarize fixed-budget results; no reference-answer comparison or reruns."""
from pathlib import Path
import collections
import csv
import hashlib
import json
import statistics
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from result_paths import result_path


def quantiles(xs):
    if not xs: return {"n": 0}
    ys = sorted(xs)
    return {"n": len(xs), "sum": sum(xs), "mean": statistics.mean(xs), "median": statistics.median(xs),
            "p90_nearest_rank": ys[max(0, (9*len(ys)+9)//10-1)], "min": min(xs), "max": max(xs)}


def main():
    manifest = json.loads((HERE / "input-manifest.json").read_text())
    rows = []
    for case in manifest["cases"]:
        rp = result_path(case["id"])
        if not rp.exists(): continue
        r = json.loads(rp.read_text())
        if r["status"] == "running" or "process_wall_seconds" not in r: continue
        row = {"id": case["id"], "group": case["group"], "status": r["status"],
               "primary_main_output_available": r.get("primary_main_output_available", False),
               "source_kind": case["source_kind"], "source_path": case["source_path"],
               "source_sha256": case["source_sha256"], "input_sha256": case["input_sha256"],
               "saved_candidate_count": case["candidate_count"], "proposed_candidate_count": r.get("proposed_candidate_count", 0),
               "variables": r.get("variables"), "equations": r.get("equations"), "max_degree": r.get("max_degree"),
               "total_terms": r.get("total_terms"), "zero_dimensional": r.get("zero_dimensional"),
               "certificate_kind": r.get("certificate_kind"), "identity_count": len(r.get("identities", [])),
               "allowed_root_count": r.get("last_root_check", {}).get("allowed_root_count"),
               "candidate_union_P": r.get("candidate_union_P"),
               "stage": r.get("stage"), "detail": r.get("detail", ""), "stage_timeouts": ";".join(r.get("stage_timeouts", [])),
               "hard_timeout": r.get("hard_timeout", False), "process_wall_seconds": r["process_wall_seconds"],
               "charged_seconds": r.get("charged_seconds", min(r["process_wall_seconds"],60)),
               "encoding_seconds": r.get("stages", {}).get("encode", 0),
               "numeric_pslq_seconds": r.get("stages", {}).get("numeric_and_pslq", 0),
               "groebner_seconds": sum(v for k,v in r.get("stages", {}).items() if k.startswith("groebner")),
               "identity_and_check_seconds": sum(v for k,v in r.get("stages", {}).items() if k.startswith("identity")),
               "root_seconds": sum(v for k,v in r.get("stages", {}).items() if k.startswith("roots")),
               "bounds": json.dumps(r.get("last_root_check", {}).get("range", r.get("bound_derivation", {}).get("bounds")), ensure_ascii=False),
               "pslq_proposal_kinds": ";".join(sorted({c.get("proposal_kind", "") for c in r.get("candidates", []) if c.get("proposal_kind")})),
               "candidate_failure_details": ";".join(sorted({c.get("candidate_status", "") for c in r.get("candidates", []) if c.get("candidate_status") != "proposed"})),
               "identity_raw_saved": sum(i.get("raw_saved",False) for i in r.get("identities",[])),
               "identity_bytes": sum(i.get("bytes",0) for i in r.get("identities",[])),
               "identity_max_cofactor_terms": max([i.get("cofactor_terms",0) for i in r.get("identities",[])]+[0]),
               "result_path": str(rp.relative_to(HERE)),
               "result_sha256": hashlib.sha256(rp.read_bytes()).hexdigest()}
        rows.append(row)
    if rows:
        with (HERE / "per-case.csv").open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={"complete":len(rows)==343,"completed":len(rows),"total":343,"primary_main_output_available":False,
             "primary_main_certification_rate":None,"primary_reason":"Returned answer values from the main campaign are absent; the measured endpoint proxy is not the main solver output.","groups":{}}
    for group,total in [("development323",323),("holdout2026",20),("all",343)]:
        rr=[r for r in rows if group=="all" or r["group"]==group]
        ok=[r for r in rr if r["status"]=="certified_saved_endpoint_set"]
        failures=[r for r in rr if r["status"]!="certified_saved_endpoint_set"]
        to=[r for r in failures if r["status"]=="timeout"]
        capable=[r for r in rr if r["saved_candidate_count"]]
        summary["groups"][group]={
            "total":total,"completed":len(rr),"saved_endpoint_sets_available":len(capable),
            "certified_endpoint_sets":len(ok),"rate_all_cases":len(ok)/total,
            "rate_candidate_available_cases":len(ok)/len(capable) if capable else None,
            "failure_counts":dict(collections.Counter(r["status"] for r in failures)),
            "certificate_kinds":dict(collections.Counter(r["certificate_kind"] for r in ok)),
            "time_all_completed":quantiles([r["process_wall_seconds"] for r in rr]),
            "time_successes":quantiles([r["process_wall_seconds"] for r in ok]),
            "timeout_count":len(to),"timeout_fraction_of_failures":len(to)/len(failures) if failures else 0,
            "hard_timeout_count":sum(r["hard_timeout"] for r in to),
            "final_timeout_stages":dict(collections.Counter(r["stage"] for r in to)),
            "any_identity_cases":sum(r["identity_count"]>0 for r in rr),
            "raw_identity_count":sum(r["identity_raw_saved"] for r in rr),
            "multi_candidate_cases":sum(r["saved_candidate_count"]>1 for r in rr),
            "multi_candidate_success_ids":[r["id"] for r in ok if r["saved_candidate_count"]>1],
            "missing_saved_candidate_cases":sum(not r["saved_candidate_count"] for r in rr),
        }
    if summary["groups"]["development323"]["completed"]==323:
        dev=summary["groups"]["development323"]
        summary["preregistered_threshold"]=97
        summary["endpoint_proxy_below_30_percent"]=dev["certified_endpoint_sets"]<97
        summary["main_output_kill_rule_evaluable"]=False
    run=HERE/"runs/run-manifest.json"
    if run.exists():summary["campaign"]=json.loads(run.read_text())
    recovery=HERE/"recovery/run-manifest.json"
    if recovery.exists():summary["infrastructure_recovery_campaign"]=json.loads(recovery.read_text())
    recovery_plan=HERE/"recovery-plan.json"
    if recovery_plan.exists():summary["infrastructure_recovery"]=json.loads(recovery_plan.read_text())
    for name in ["recovery2-plan.json","recovery2/run-manifest.json"]:
        p=HERE/name
        if p.exists():summary[name]=json.loads(p.read_text())
    (HERE/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"completed":len(rows),"statuses":dict(collections.Counter(r["status"] for r in rows)),"success_by_group":{g:v["certified_endpoint_sets"] for g,v in summary["groups"].items()}},ensure_ascii=False))


if __name__=="__main__":main()
