"""Repeat only jobs whose first execution was disrupted by unavailable paths.

Never retries an ordinary timeout, unsupported DSL, or algebraic failure.
The 60s budget, source inputs, and generation code are unchanged.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent


def main():
    original=json.loads((HERE/"runs/run-manifest.json").read_text())
    for name,sha in original["hashes"].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==sha,(name,"changed since registration")
    rows=[]
    for cid in original["ids"]:
        rp=HERE/"runs"/cid/"result.json"
        r=json.loads(rp.read_text()) if rp.exists() else {}
        if r.get("status")=="process_failure" or r.get("status") in (None,"running") or "process_wall_seconds" not in r:
            log=HERE/"runs"/cid/"process.log"
            content=log.read_text() if log.exists() else ""
            assert "No such file or directory" in content or cid in ("HMMT-2024-FEB-GEO-07","HMMT-2024-FEB-GEO-09")
            rows.append({"id":cid,"prior_status":r.get("status"),"prior_stage":r.get("stage"),
                         "original_result_sha256":hashlib.sha256(rp.read_bytes()).hexdigest() if rp.exists() else None,
                         "original_log_sha256":hashlib.sha256(log.read_bytes()).hexdigest() if log.exists() else None,
                         "reason":"input code path or result directory temporarily unavailable; no ordinary algorithm failure selected"})
    plan={"created_utc":datetime.now(timezone.utc).isoformat(),"ids":[r["id"] for r in rows],"cases":rows,
          "unchanged_generation_hashes":original["hashes"],"workers":4,"per_case_seconds":60,
          "policy":"Use the recovery outcome for every listed job, regardless of whether it improves. Preserve all first-run artifacts. Do not retry ordinary algorithm timeouts or failures.",
          "first_runner_error":"FileNotFoundError while saving runs/HMMT-2024-FEB-GEO-07/result.json; the 58 failed launches reported missing worker.py. The current code exists and its hash equals the pre-experiment hash.",
          "first_run_end_observed_utc":datetime.now(timezone.utc).isoformat(),
          "first_run_wall_until_observed_seconds":(datetime.now(timezone.utc)-datetime.fromisoformat(original["started_utc"])).total_seconds()}
    assert not (HERE/"recovery-plan.json").exists()
    (HERE/"recovery-plan.json").write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n")
    print("Infrastructure-only recovery",len(rows),"unchanged worker hash",original["hashes"]["worker.py"],flush=True)
    subprocess.run([sys.executable,"-B",str(HERE/"run.py"),"--dest","recovery","--ids"]+plan["ids"],check=True)


if __name__=="__main__":main()
