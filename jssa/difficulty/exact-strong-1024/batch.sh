#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PYTHON=${EXSTRONG_PYTHON:-/home/kabatan/work/solver/.venv/bin/python}
if (( $# < 1 )); then
  echo 'usage: batch.sh OUTDIR [--cases FILE ...] [--stage-b] < ids.txt' >&2
  exit 2
fi
OUT=$1
shift
mkdir -p -- "$OUT"
export PATH="/tmp/q6-tools/bin:$PATH"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
# Both xargs and the one-case supervisor have no retry path. Every worker has
# its own process group, 600s total wall budget and aggregate 8GiB RSS guard.
printf '%s\n' "4 workers; each 600 seconds, 8 GiB; no retries" >&2
xargs -r -P 4 --process-slot-var=EXSTRONG_SLOT -I '{}' "$PYTHON" "$HERE/run_strong.py" '{}' --out "$OUT/{}.json" "$@"
