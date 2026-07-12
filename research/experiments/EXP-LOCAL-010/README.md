# EXP-LOCAL-010 — two-resolution CPQR endpoint correction

Status: **preregistered; no outcome run authorized**.

`E1-FD2-CPQR3` reuses the endpoint observation from the frozen
`prod-tol-120x600` LM-QR trajectory, builds `h` and `h/2` finite-difference
Jacobians in normalized box coordinates, and accepts up to three Armijo
corrections only after the preregistered full-rank and two-resolution
backward-error proof. Any unknown proof drops a residual-qualified endpoint;
endpoints outside the correction eligibility set pass through unchanged.

The paired shadow performs exactly the same callbacks and returns the original
LM-QR endpoint. `run_t0.jl` is the shared five-variant runner for this CPQR
candidate and EXP-LOCAL-011's SVD candidate. It defaults to preflight and
refuses `--execute` while `preregistration.json` keeps outcome authorization
false. Outcome execution is one-case-per-process via `--case-index=1..9`; the
root campaign launcher owns CPU0-8 parallelism and shard aggregation.

`aggregate_t0.py` is that single lightweight aggregator. It independently
recomputes callback accounting, suffix-stable work, common-assessor safety,
candidate/shadow callback identity, reported-acceptance safety, active-family
support, and the preregistered gates from the nine raw shards.

Targeted tests:

```bash
JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  julia +1.12.6 --project=julia \
  research/experiments/EXP-LOCAL-010/test/runtests.jl
```

Runner preflight:

```bash
JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  julia +1.12.6 --project=julia \
  research/experiments/EXP-LOCAL-010/run_t0.jl
```
