# EXP-LOCAL-009 — feasibility-restoring line-search Gauss–Newton

Status: **candidate, T0 corpus, and gate preregistered; no T0 outcome has been run**

This experiment owns one general local mechanism for the guard/branch/domain
failure class. It does not modify Core or a public API, and it does not switch
solvers after observing an outcome. The candidate receives only the public
numeric case view: dimensions, finite bounds, declared scales, callback
evaluations, and semantic validity.

## Frozen mechanism

For bounds `l < x < u`, the candidate works directly in normalized coordinates

`z = (x - (l+u)/2) / ((u-l)/2)`, with `z` clipped only to `[-1,1]^n`.

Residual row `i` is divided by its declared scale. No benchmark identity,
known solution, target, family, primitive, or plugin name is read.

At a valid iterate, each Jacobian column first uses a forward one-sided
difference in the direction with more box room. The symmetric opposite-sign
point is the fallback at the same radius. If that callback is also invalid or
unavailable, the radius is halved, at most 16 times. Invalid evaluations are
charged and are never converted into a finite penalty residual.

The local step is the truncated column-pivoted QR solution of

`min_p ||r + J p||_2`.

The leading rank threshold is
`max(m,n) * eps(Float64) * max(abs(diag(R)))`. A rank-zero or non-descent model
returns a typed stalled outcome; it does not add fixed damping or call another
solver.

For a proposed step `p`, the trial point is clipped to the normalized box and
the effective step `d = z_trial-z` is used in both the Armijo and linear-model
tests. Backtracking uses factor `1/2`, Armijo coefficient `1e-4`, and minimum
actual/predicted reduction ratio `1e-4`, with at most 24 trials. Invalid trials
are rejected and backtracked toward the last valid iterate. This is the
feasibility-restoration mechanism used during ordinary iterations.

An invalid saved start has one result-independent restoration rule. The
normalized box center must be valid; then the center-to-start segment is
bisected, retaining the feasible side, until the bracket width is at most the
finite-difference step. If the center is invalid, the attempt ends with typed
`RESTORING_GN_INITIAL_INFEASIBLE`. There is no search portfolio hidden in this
phase.

The candidate stops successfully only at declared-scaled residual L-infinity
at most `1e-12`. Candidate flags are diagnostics. The unchanged common assessor
owns endpoint qualification, guard/branch/domain validity, target matching,
and safety.

## Prospective T0

[`t0-preregistration.json`](t0-preregistration.json) freezes the experiment
before any outcome. The measured corpus is the unchanged local five-case T0
(Curved, NearRank, Tangent, and two Warped target maps) plus the existing
on-boundary strict-guard case. Each has 512 frozen paired starts; there are 11
Gold targets in total. Gold is visible only to the independent assessor.

The variants are:

- `prod-tol-120x600` (primary control)
- `prod-options-250x2000`
- `RESTORING-GN-CPQR` (120 iterations, hard cap 600 callbacks)

Each case/variant consumes one paired-start stream. Summaries are taken after
the first completed attempt crossing cumulative observed callback work
`600/1200/2400/4800`; prefixes are not rerun. Threshold overshoot is retained
as a diagnostic, not used as promotion work. Primary work is rebuilt from raw
attempts as the earliest suffix-stable common-assessor safe-full callback work
for each case. A miss or a value above 4,800 is right-censored to 4,800, then
case values are summed. The older reported-acceptance/lab suffix metric is
diagnostic only. Wall time is diagnostic.

At 4,800 callbacks the candidate passes only if all of the following hold:

- Path A: common-assessor qualified target count and safe-full case count are
  both noninferior, at least one is strictly higher, and right-censored
  common-assessor work is at most 1.20 times the primary control;
- Path B: both outcome counts are noninferior and right-censored
  common-assessor work is at most 0.80 times the primary control;
- target count is noninferior in Curved, NearRank, Tangent, combined Warped,
  and StrictGuard strata;
- StrictGuard is safe-full and at least one qualified endpoint follows a
  diagnostic-recorded restored start, FD sign reversal, invalid FD trial, or
  invalid line-search trial;
- accepted-endpoint safety, assessor consistency, callback accounting, hard
  caps, unhandled exceptions, and truth-leak violations are all zero.

There are zero tuning rounds. Passing T0 authorizes only a separately frozen
T1 study, not Core integration or production promotion.

## Targeted tests

The tests cover regular/scaled solving, invalid-start restoration, invalid
midpoint fail-closed behavior, throwing-domain FD sign reversal, invalid-step
line-search recovery, rank-one CPQR truncation, rank-zero safeguarding, hard
callback caps, the prospective gate, and the exact six-case replay contract.

```bash
env JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 julia +1.12.6 --startup-file=no --history-file=no \
  --project=julia research/experiments/EXP-LOCAL-009/test/runtests.jl
```

## Outcome command (not yet authorized)

After these files are committed, root explicitly authorizes the outcome, and
the repository is clean, one case shard has this command shape:

```bash
env JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 taskset -c 0 julia +1.12.6 \
  --startup-file=no --history-file=no --project=julia \
  research/experiments/EXP-LOCAL-009/run_t0.jl \
  --shard-index=0 --shard-count=6
```

Indices `0..5` must use distinct physical cores and separate output paths. No
command in this experiment has produced a T0 outcome yet.

The authorized execution uses the shared
`../EXP-LOCAL-008/run_t0_wave.py` driver and raw-attempt aggregator so both
candidates receive the same corpus, controls, callback accounting, and gate.
