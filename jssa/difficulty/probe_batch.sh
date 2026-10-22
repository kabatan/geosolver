#!/usr/bin/env bash
# Usage: probe_batch.sh OUT_DIR JOBS [DSL_DIR] < ids.txt
# Runs probe_basins.py for each case id (200 starts, seed 0, 120 s budget per case).
# With DSL_DIR, the id is a variant id "<case>.k<k>" and the DSL is DSL_DIR/<id>.json.
# With INIT=1 (and DSL_DIR), extra point variables start at their constructed position (--init-from <case>.k0).
set -u
OUT=$1; JOBS=$2; DSL_DIR=${3:-}
HERE=$(cd "$(dirname "$0")" && pwd)
PY="$HERE/../../.venv/bin/python"
mkdir -p "$OUT"
INIT=${INIT:-}
export OUT DSL_DIR HERE PY INIT
xargs -P "$JOBS" -I{} bash -c '
  id="{}"; [ -s "$OUT/$id.json" ] && exit 0
  ulimit -v $((4*1024*1024))
  if [ -n "$DSL_DIR" ]; then
    timeout 300 "$PY" "$HERE/probe_basins.py" "${id%.k*}" "$OUT/$id.json" --dsl "$DSL_DIR/$id.json" ${INIT:+--init-from "$DSL_DIR/${id%.k*}.k0.json"} --starts 200 --budget 120 > "$OUT/$id.log" 2>&1
  else
    timeout 300 "$PY" "$HERE/probe_basins.py" "$id" "$OUT/$id.json" --starts 200 --budget 120 > "$OUT/$id.log" 2>&1
  fi
  echo "$id rc=$?"'
