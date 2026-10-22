#!/usr/bin/env bash
# Experiment 2: refine the same search candidates with and without the signed/smooth residual rewrite.
set -uo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd "$HOME/work/geosolver-searchmode" || exit 1
OUT="$HOME/work/jssa-searchmode/tangency-out"
mkdir -p "$OUT"
CASES="AIME-2015-II-15 AIME-2018-II-14 HMMT-2008-FEB-GEO-09 HMMT-2009-FEB-GEO-10 HMMT-2010-FEB-GEO-09 HMMT-2020-FEB-GEO-09 HMMT-2022-FEB-GEO-10 HMMT-2023-FEB-GEO-07 JMO-2013-PRE-05 JMO-2024-PRE-06 aime-2001-2-7 aime-2002-2-14"
run() {
  c=$1; ord=$2; cpu=$3
  [ -f "$OUT/$c.$ord.json" ] && return
  TANGENCY_PROBE_ORDER=$ord TANGENCY_PROBE_OUT="$OUT/$c.$ord.json" PYTHONPATH="$HOME/work/jssa-searchmode/probe" \
    taskset -c "$cpu" timeout 400 .venv/bin/python -m geosolver.application.cli solve "benchmarks/dsl/$c.json" \
    --time-limit-seconds 180 --cores 1 --seed 0 --output "$OUT/$c.$ord.solver.json" > "$OUT/$c.$ord.log" 2>&1
}
echo "== start $(date -Is)"
i=0
for ord in off_first on_first; do
  for c in $CASES; do
    cpu=$(( (i % 3) * 2 ))
    i=$((i+1))
    run "$c" "$ord" "$cpu" &
    if (( i % 3 == 0 )); then wait; fi
  done
  wait
done
echo "== done $(date -Is)"
