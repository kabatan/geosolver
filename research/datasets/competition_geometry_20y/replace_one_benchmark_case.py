#!/usr/bin/env python3
"""Re-run one case and replace its row in a fixed benchmark artifact."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--case", type=Path, required=True)
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--runtime-root", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--budget", type=float, default=180.0)
    args = ap.parse_args()

    runtime = args.runtime_root.resolve()
    case = args.case.resolve()
    py = runtime / "solver/python/.venv/bin/python"
    child = case.parent.parent / "benchmark_child.py"
    geo = runtime / "geosolver/src"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(geo)
    started = time.monotonic()
    proc = subprocess.run(
        [
            "taskset",
            "-c",
            "0",
            str(py),
            str(child),
            str(case),
            str(args.seed),
            str(args.budget),
        ],
        cwd=str(runtime / "geosolver"),
        env=env,
        text=True,
        capture_output=True,
        timeout=max(190.0, args.budget + 10.0),
    )
    payload = None
    for line in reversed(proc.stdout.splitlines()):
        try:
            payload = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    if payload is None:
        raise SystemExit(f"child emitted no JSON; stdout={proc.stdout[-2000:]!r}; stderr={proc.stderr[-2000:]!r}")

    data = json.loads(args.input.read_text(encoding="utf-8"))
    rows = data.get("results", [])
    matches = [row for row in rows if row.get("case_id") == args.case_id]
    if len(matches) != 1:
        raise SystemExit(f"expected one row for {args.case_id}, found {len(matches)}")
    row = matches[0]
    row.update(payload)
    row["case_id"] = args.case_id
    row["seed"] = args.seed
    row["wall_sec"] = time.monotonic() - started
    data["results"] = rows
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"case_id": args.case_id, "status": payload.get("status"), "elapsed_sec": payload.get("elapsed_sec")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
