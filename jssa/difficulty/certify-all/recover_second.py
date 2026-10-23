"""Three remaining path failures; generation code and per-case budget unchanged."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
original=json.loads((HERE/"runs/run-manifest.json").read_text())
for name,sha in original["hashes"].items():
    assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==sha
ids=["JMO-2023-PRE-10","JMO-2024-PRE-03","JMO-2024-PRE-06"]
for cid in ids:
    r=json.loads((HERE/"recovery"/cid/"result.json").read_text())
    assert r["status"] in ("process_failure","running")
plan={"created_utc":datetime.now(timezone.utc).isoformat(),"ids":ids,"reason":"A second temporary path disappearance interrupted one receipt and two Python launches. No ordinary algorithm failure is retried.","unchanged_generation_hashes":original["hashes"],"per_case_seconds":60,"workers":3,"first_recovery_end_observed_utc":datetime.now(timezone.utc).isoformat()}
assert not (HERE/"recovery2-plan.json").exists()
(HERE/"recovery2-plan.json").write_text(json.dumps(plan,indent=2)+"\n")
subprocess.run([sys.executable,"-B",str(HERE/"run.py"),"--dest","recovery2","--ids"]+ids,check=True)
