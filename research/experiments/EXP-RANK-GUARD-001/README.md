# EXP-RANK-GUARD-001 — conformance recovery and weak/guard proposals

This is a non-promotional, development-only successor adapter for
`EXP-LOCAL-015`.  It changes no answer authority and never bypasses the
existing canonical verifier.

The experiment has four independently selectable mechanisms:

1. the unchanged `GEOTARGET-ADAPTED-128-256-512-CPQR` arm;
2. the unchanged `WEAK-THEN-ADAPTIVE` arm;
3. symmetric `+/- r*v` starts along a stable weakest right-singular line;
4. the same symmetric starts in a finite-bound logit chart.

The first two arms exist to recover evidence that the old aggregate marked
`INVALID_RUN` globally.  `conformance_adapter.py` fixes only two result-contract
problems: zero-count precision buckets compare equal to absent buckets, and
representation gating is candidate-local.  It separately reports proposal
disagreement and route/work disagreement; the latter is never silently erased.
In particular, disagreement in a weak arm cannot invalidate an unrelated
adapted-CPQR arm, and a route-cost difference with identical no-emission
behavior remains diagnostic rather than becoming a false proposal mismatch.

The new weak proposals are only starts.  They require a complete, callback-bound
`h/h2` prefilter, stable coarse/fine weak projectors, symmetric evaluation,
unchanged branch/guard/domain identities, and positive public semantic margins.
The radius is capped by trust radius, finite-bound slack and a conservative
fraction of the public guard/domain margin.  The chart arm maps every finite
strict interval through logit, so generated points remain strictly interior.
The baseline lane remains present in every S0 comparison.

No problem ID, family ID, target, primitive or Gold value enters a candidate
interface.  Generated truth is joined only after candidate return.  Do not run
this experiment against validation or sealed inputs.

## Full-v15 S1 arms

- `arms/charted-weak-proposal/arm.json` is the active proposal-only arm.
- `arms/adapted-cpqr-proposal/arm.json` is deliberately fail-closed and runs the
  unchanged frozen champion while recording the missing arbitrary-precision
  proposal callback as a plan blocker.

Each `entrypoint` is relative to its manifest, each manifest's
`mechanism_hash` is the SHA-256 of the entrypoint bytes.  The overlay files and
frozen champion entrypoint are hash-bound by their loaders; the frozen
entrypoint retains its existing closure checks.  The root benchmark owner, not
this experiment lane, owns formal S1 scoring.

## S0

From the repository root:

```bash
JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  julia --startup-file=no \
  --project=research/experiments/EXP-LOCAL-002 \
  research/experiments/EXP-RANK-GUARD-001/test/runtests.jl

JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  julia --startup-file=no \
  --project=research/experiments/EXP-LOCAL-002 \
  research/experiments/EXP-RANK-GUARD-001/run_s0.jl \
  --output /tmp/exp-rank-guard-s0.json
```

Re-audit the already frozen open-development `EXP-LOCAL-015` shards without
reading any per-case truth:

```bash
python3 research/experiments/EXP-RANK-GUARD-001/conformance_adapter.py \
  --raw-dir /home/kabatan/work/solver-experiment-runtime/solver/artifacts/raw/EXP-LOCAL-015 \
  --output /tmp/exp-rank-guard-conformance.json
```

The Python S1 seam checks are development/source-only and can be run with the
frozen Python environment:

```bash
GEOTARGET_FROZEN_SOLVER_ROOT=/home/kabatan/work/solver-experiment-runtime/solver \
  /home/kabatan/work/solver/.venv/bin/python -m unittest discover \
  -s research/experiments/EXP-RANK-GUARD-001/test \
  -p 'test_s1_overlay.py' -v
```
