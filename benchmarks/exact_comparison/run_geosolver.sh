#!/bin/bash
# usage: run_geosolver.sh OUTDIR JOBS < ids   (seeds 0,1,2; canonical 180 s, 1 core)
out=$1; jobs=$2; mkdir -p $out
while read id; do for s in 0 1 2; do echo "$id $s"; done; done | \
xargs -P $jobs -L1 sh -c '[ -f '$out'/$0.$1.json ] || OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/claude/geosolver/.venv/bin/python -m geosolver.application.cli solve /home/claude/geosolver/benchmarks/dsl/$0.json --time-limit-seconds 180 --cores 1 --seed $1 --output '$out'/$0.$1.json > /dev/null 2>&1'
