#!/usr/bin/env bash
# Run from repository root. Foreground only; same command resumes unstarted slots.
set -euo pipefail
S8=jssa/difficulty/mechanism-1024/stage/S8
exec /home/kabatan/work/solver/.venv/bin/python -B "$S8/rerun-driver/supervise_superpc.py" \
  --slots-file "$S8/run-plan-rerun.json" \
  --max-parallel 8 \
  --output "$S8/run-superpc-rerun" \
  --raw-root /tmp/mechanism-S8-rerun-raw \
  --base-src /tmp/mechanism-7b-lkdjle5l/final \
  --repo-root "$PWD" \
  --python /home/kabatan/work/solver/.venv/bin/python
