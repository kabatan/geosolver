#!/bin/bash
# usage: batch.sh OUTDIR MODE SOLVER TIMEOUT JOBS < ids
# PY: python of the GeoSolver environment (default: the repository .venv)
out=$1; mode=$2; solver=$3; to=$4; jobs=$5
here=$(cd "$(dirname "$0")" && pwd)
PY=${PY:-$here/../../.venv/bin/python}
mkdir -p "$out"
cd "$here"
xargs -P "$jobs" -I{} sh -c "[ -f '$out'/{}.json ] || timeout $(( ${to%.*} + 900 )) '$PY' run_exact.py {} $mode $solver $to '$out'/{}.json > '$out'/{}.log 2>&1"
