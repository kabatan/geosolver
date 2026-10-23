"""Fixed-budget campaign: at most four one-thread child processes, 60s each."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PYTHON = "/home/kabatan/work/solver/.venv/bin/python"


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024**2,) * 2)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def one(cid, dest):
    out = HERE / dest / cid
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0",
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
               TMPDIR=str(HERE / "tmp"), MPLCONFIGDIR=str(HERE / "tmp"))
    start = time.monotonic()
    env["Q11_START"] = str(start)
    with (out / "process.log").open("w") as log:
        p = subprocess.Popen([PYTHON, "-B", str(HERE / "worker.py"), cid, dest], cwd=ROOT, env=env,
                             stdout=log, stderr=log, preexec_fn=limits)
        timed_out = False
        try:
            p.wait(timeout=max(0.001, 60 - (time.monotonic() - start)))
        except subprocess.TimeoutExpired:
            timed_out = True
            p.kill()
            p.wait()
    elapsed = time.monotonic() - start
    rp = out / "result.json"
    result = json.loads(rp.read_text()) if rp.exists() else {"id": cid, "stage": "import_or_setup"}
    if timed_out or result.get("seconds", 0) > 60:
        result["status"] = "timeout"
        result["detail"] = "parent enforced the total 60s wall limit"
        result["primary_main_output_available"] = False
    elif p.returncode or result.get("status") in (None, "running"):
        result["status"] = "process_failure"
        result["detail"] = f"return code {p.returncode}"
    result["process_wall_seconds"] = elapsed
    result["process_returncode"] = p.returncode
    result["hard_timeout"] = timed_out
    result["charged_seconds"] = min(elapsed, 60)
    save(rp, result)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--dest", default="runs")
    args = ap.parse_args()
    manifest = json.loads((HERE / "input-manifest.json").read_text())
    ids = args.ids or [r["id"] for r in manifest["cases"]]
    (HERE / "tmp").mkdir(exist_ok=True)
    dest = HERE / args.dest
    dest.mkdir(exist_ok=True)
    if any((dest / cid / "result.json").exists() for cid in ids):
        raise SystemExit("Refusing to overwrite measured results; use a new destination for a labeled rerun.")
    frozen = {
        "started_utc": datetime.now(timezone.utc).isoformat(), "ids": ids, "workers": 4,
        "per_case_wall_seconds": 60, "address_space_gib": 3, "threads_per_worker": 1,
        "phase_caps_seconds": {"encode": 20, "bounds": 4, "numeric_and_pslq": 12, "groebner_grevlex": 15, "groebner_lex": 22},
        "hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [
            HERE / "preregistration.md", HERE / "input-manifest.json", HERE / "prepare.py",
            HERE / "worker.py", HERE / "bounds.py", HERE / "run.py",
        ]},
    }
    save(dest / "run-manifest.json", frozen)
    start = time.monotonic()
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(one, cid, args.dest): cid for cid in ids}
        for f in as_completed(futures):
            row = f.result()
            rows.append(row)
            print(json.dumps({"done": len(rows), "total": len(ids), "id": row["id"], "status": row["status"], "seconds": round(row["process_wall_seconds"], 3)}, ensure_ascii=False), flush=True)
            save(dest / "progress.json", {"done": len(rows), "total": len(ids), "wall_seconds": time.monotonic() - start})
    frozen["finished_utc"] = datetime.now(timezone.utc).isoformat()
    frozen["campaign_wall_seconds"] = time.monotonic() - start
    save(dest / "run-manifest.json", frozen)


if __name__ == "__main__":
    main()
