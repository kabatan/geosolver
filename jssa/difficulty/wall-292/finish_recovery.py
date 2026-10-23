"""Use complete backups, reconcile initial aggregates, and count recovery work."""
import json
from collections import Counter
from pathlib import Path

import run
import resume

HERE=run.HERE


def main():
    assert (HERE/"run-complete.json").exists()
    manifest=json.loads((HERE/"manifest.json").read_text())
    plan=json.loads((HERE/"recovery-plan.json").read_text())
    by_plan={r["id"]:r for r in plan["cases"]}
    restored=[]
    comparisons=[]
    counts=Counter()
    extra_calls=Counter()
    interrupted=[]
    for meta in manifest["problems"]:
        cid=meta["id"]
        backup=HERE/"completed-records"/(cid+".jsonl")
        rows,bad=resume.load_rows(backup)
        assert not bad and len(rows)==meta["n"], (cid,len(rows),bad)
        target=HERE/"records"/backup.name
        if not target.exists() or run.sha(target)!=run.sha(backup):
            old,_=resume.load_rows(target)
            restored.append({"id":cid,"old_records":len(old),"restored":len(rows)})
            resume.atomic_rows(target,meta,rows)
        row=by_plan[cid]
        if row["initial_summary"] and row["initial_summary"].get("n")==meta["n"]:
            initial=row["initial_summary"]["counts"]
            now={a:dict(Counter(r[a]["cls"] for r in rows.values())) for a in run.ARMS}
            comparisons.append({"id":cid,"initial":initial,"reconstructed":now,
                                "counts_match":all(Counter(initial[a])==Counter(now[a]) for a in run.ARMS),
                                "hit_counts_match":all(initial[a].get("hit",0)==now[a].get("hit",0) for a in run.ARMS)})
        state_path=HERE/"resume-state"/(cid+".json")
        if state_path.exists():
            state=json.loads(state_path.read_text())
            extra_calls.update(state["new_calls"])
            interrupted.extend({"id":cid,**r} for r in state.get("interrupted_arms",[]))
        counts["retained_initial_rows"]+=len(row["retained_k"])
        counts["continuation_rows"]+=len(row["missing_k"])
        if row["missing_from_completed_initial"]:
            counts["missing_from_completed_initial_rows"]+=len(row["missing_k"])
            counts["missing_from_completed_initial_cases"]+=1
        for r in rows.values():
            counts["primary_rows"]+=1
            for a in run.ARMS:
                counts["primary_missing_run"]+=r[a]["cls"]=="missing_run"
    failures=[json.loads(p.read_text()) for p in (HERE/"resume-errors").glob("*.json")]
    out={"completed_utc":run.stamp(),"counts":dict(counts),"restored_from_complete_backup":restored,
         "initial_process_exit_code":1,"initial_exit_reason":"unknown",
         "initial_calls_at_least":plan["initial_calls_at_least"],"new_call_start_records":dict(extra_calls),
         "total_calls_at_least":plan["initial_calls_at_least"]+sum(extra_calls.values()),
         "unrecorded_initial_attempts_unknown":True,"initial_summaries_compared":len(comparisons),
         "initial_counts_all_match":all(r["counts_match"] for r in comparisons),
         "initial_hit_counts_all_match":all(r["hit_counts_match"] for r in comparisons),
         "comparisons":comparisons,"resume_process_failures":failures,"interrupted_arms":interrupted}
    run.write_json(HERE/"recovery-summary.json",out)
    print(json.dumps({"recovered_rows":counts["continuation_rows"],"old_missing_rows":counts["missing_from_completed_initial_rows"],
                      "initial_comparisons":len(comparisons),"all_initial_counts_match":out["initial_counts_all_match"],
                      "restored_backups":len(restored),"resume_process_failures":len(failures)}))


if __name__=="__main__":main()
