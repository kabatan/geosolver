"""At most four single-threaded, bounded workers; never install dependencies."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
PYTHON = "/home/kabatan/work/solver/.venv/bin/python"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="pilot-v1")
    ap.add_argument("--verify", help="directory of existing complete certificates")
    ap.add_argument("--inputs", default="inputs")
    args = ap.parse_args()
    out = HERE / args.output
    out.mkdir(exist_ok=False)
    inputs = sorted((HERE / args.inputs).glob("*.json"))
    cert_dir = HERE / args.verify if args.verify else None
    if cert_dir:
        inputs = [p for p in inputs if (cert_dir / p.name).exists()
                  and json.loads((cert_dir / p.name).read_text()).get("status") == "complete"]
    sources = ["exact_onevar.py", "verify_certificate.py", "worker.py", "run_pilot.py", "preregistration.md"]
    meta = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "jobs": 4, "worker_processing_timeout_s": 120, "mode": "verify" if cert_dir else "generate",
            "inputs": [p.name for p in inputs],
            "source_sha256": {p: hashlib.sha256((HERE / p).read_bytes()).hexdigest() for p in sources}}
    (out / "run-manifest.json").write_text(json.dumps(meta, indent=2) + "\n")
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH="src", OPENBLAS_NUM_THREADS="1",
               OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    started = time.monotonic()

    def run(p):
        cmd = [PYTHON, str(HERE / "worker.py"), str(p), str(out / p.name)]
        if cert_dir:
            cmd.extend(["--verify", str(cert_dir / p.name)])
        t = time.monotonic()
        try:
            completed = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=140)
            if completed.returncode or not (out / p.name).exists():
                row = {"id": p.stem, "status": "worker_error", "returncode": completed.returncode,
                       "stderr": completed.stderr[-10000:], "stdout": completed.stdout[-3000:]}
                (out / p.name).write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n")
            else:
                row = json.loads((out / p.name).read_text())
            row["wall_seconds_including_startup"] = time.monotonic() - t
            (out / p.name).write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n")
            return {k: row.get(k) for k in ("id", "status", "processing_seconds", "reason")}
        except subprocess.TimeoutExpired:
            row = {"id": p.stem, "status": "parent_timeout", "wall_seconds_including_startup": time.monotonic() - t}
            (out / p.name).write_text(json.dumps(row) + "\n")
            return row

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(run, p) for p in inputs]
        for i, f in enumerate(as_completed(futures), 1):
            row = f.result()
            print(json.dumps({"done": i, "n": len(inputs), **row}, ensure_ascii=False), flush=True)
    (out / "run-timing.json").write_text(json.dumps({"total_wall_seconds": time.monotonic() - started,
                                                   "completed": len(inputs)}, indent=2) + "\n")


if __name__ == "__main__":
    main()
