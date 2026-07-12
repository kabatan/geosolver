# EXP-LOCAL-014 — guard-aware local successor wave

Status: **G0/R1 passed and independently audited; E4 full T2 authorized**.

This experiment compares the two frozen successors to the rejected E1 endpoint
filter without changing the local base solver, start prefix, scorer, callback
budget, or canonical assessor:

- `E3-FD2-GUARD-CHART-CPQR3` and its same-work shadow;
- `E4-EXP-GUARD-SLACK-CPQR` and its same-work shadow.

The first stage is a frozen, broad failure stratum: the six NearRank and six
StrictGuard cases already present in the committed 48-case T2 corpus.  It uses
all 32 saved paired starts and the existing 4,800-callback case stop.  A later
authorization may advance only G0 survivors to the representative nine cases,
then only a committed representative-stage finalist to the full 48-case T2.

`run_wave.jl` reuses the existing truth-blind case adapter and attempt scorer.
It emits one case per process and enforces one Julia/BLAS/OMP/MKL thread.  Host
launch concurrency is at most 16; there is no within-case parallelism.  Every
executing child must be pinned with `taskset` to its assigned CPU in `0..15`,
pass that CPU through `--assigned-cpu`, and set
`GEOTARGET_CASE_PROCESS_LIMIT=16`; the runner verifies and records the actual
Linux affinity mask.  A nonblocking per-CPU `flock` is held for the whole case,
so the sixteen allowed CPU slots are an enforced bound rather than launcher
metadata.  Julia 1.12.6 is checked by the runner; aggregation must run through
uv with Python 3.12.11 and uv 0.11.24.

`aggregate_wave.py` independently recomputes accounting, target recall,
safe-full, unsafe reports, right-censored work, and candidate/shadow identity
from raw attempts.  This directory adds no service, queue, custody layer, or
production dependency.

The future representative-nine manifest is already frozen through replay,
target count, and saved-start checksums.  R1 and full T2 remain fail-closed
until a committed predecessor decision hash names exactly their survivors.
Targeted tests and the independent static audit are bound through
`preoutcome-evidence.json`; pending evidence makes every candidate gate fail.
