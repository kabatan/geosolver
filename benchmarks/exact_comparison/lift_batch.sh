#!/bin/bash
# usage: lift_batch.sh CAMPAIGN_DIR OUTDIR JOBS < ids
# Substitutes GeoSolver's configuration (first seed that has one) into the polynomial system.
camp=$1; out=$2; jobs=$3
here=$(cd "$(dirname "$0")" && pwd)
PY=${PY:-$here/../../.venv/bin/python}
mkdir -p "$out"; cd "$here"
xargs -P "$jobs" -I{} sh -c "[ -f '$out'/{}.json ] || for s in 0 1 2; do f='$camp'/runs/{}/\$s.json; [ -f \$f ] || continue; timeout 300 '$PY' lift_run.py {} \$f '$out'/{}.json > '$out'/{}.log 2>&1 && grep -qv no_geosolver_configuration '$out'/{}.json && break; done; [ -f '$out'/{}.json ] || echo '{\"id\":\"{}\",\"status\":\"lift_timeout_or_error\"}' > '$out'/{}.json"
