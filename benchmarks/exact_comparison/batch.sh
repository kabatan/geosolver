#!/bin/bash
# usage: batch.sh OUTDIR MODE SOLVER TIMEOUT JOBS < ids
out=$1; mode=$2; solver=$3; to=$4; jobs=$5
mkdir -p $out
xargs -P $jobs -I{} sh -c "[ -f $out/{}.json ] || timeout $(( ${to%.*} + 900 )) /home/claude/geosolver/.venv/bin/python run_exact.py {} $mode $solver $to $out/{}.json > $out/{}.log 2>&1"
