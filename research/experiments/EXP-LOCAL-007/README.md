# EXP-LOCAL-007 — square-system Powell hybrid comparator

Status: **preregistered; implementation-only; no T0 outcome exists**

This experiment-local candidate evaluates SciPy 1.18.0
`scipy.optimize.root(method="hybr")`, the MINPACK HYBRD modified Powell hybrid
method, as a truth-blind square-system root comparator. It is an established
root-finding mechanism distinct from the rejected least-squares TRF and LM
configurations: HYBRD combines a Powell hybrid step model with MINPACK's
finite-difference/QR path rather than delegating to SciPy's bound-aware TRF or
least-squares LM implementations. It remains a related local-model method, not
an independent correctness oracle, and package success is diagnostic only.

Official references:

- SciPy 1.18 `root(method='hybr')` API:
  https://docs.scipy.org/doc/scipy-1.18.0/reference/optimize.root-hybr.html
- MINPACK HYBRD documentation:
  https://www.math.utah.edu/software/minpack/minpack/hybrd.html

## Frozen candidate contract

- Applicability is exactly the public numerical condition
  `residual_dimension == dimension`. Nonsquare systems return typed
  `INAPPLICABLE_NONSQUARE` with zero callbacks. No case, family, primitive,
  plugin, target, or outcome identity participates in this decision.
- Every variable must have a finite declared box `l < u`. Physical coordinates
  are normalized by midpoint `o=(l+u)/2` and half-range `s=(u-l)/2`.
- MINPACK sees an unconstrained coordinate `w`; the mathematical forward map is
  `u=tanh(w)` and `x=o+s*u`. To keep binary64 normalized coordinates strictly
  inside `(-1,1)` after `tanh` saturation, the implementation clamps only a
  rounded `-1`/`+1` result to `nextfloat(-1)`/`prevfloat(1)`.
- A saved start is first normalized to the closed box. The inverse-start rule is
  exactly
  `w=atanh(clamp(u,-1+sqrt(eps(Float64)),1-sqrt(eps(Float64))))`.
  Thus exact and near-boundary starts are deterministically interiorized; this
  is a coordinate policy, not a claim that boundary roots are solved.
- Residuals are divided by their declared residual scales before reaching
  MINPACK. HYBRD forms an initial (and, when needed, restarted) forward-
  difference Jacobian and otherwise uses its Broyden rank-one updates; no
  separate candidate Jacobian or rank-routing solve is performed.
- `xtol=1e-12`, initial step `factor=100`, linear root residual, and SciPy's
  pinned HYBRD defaults are frozen. There are no tuning rounds.
- Each attempt has a 600-callback external hard cap. At most 599 callbacks are
  available to HYBRD and exactly one is reserved for the common endpoint
  screen. Every Python residual callback is charged before evaluation,
  including semantic-invalid, nonfinite, or throwing trials. Such a trial
  aborts the attempt; it is never converted into a finite penalty residual.
- The endpoint screen alone determines `reported_accepted`: finite endpoint,
  declared bounds, public semantic validity, and declared-scaled residual
  L-infinity at most `1e-12`. SciPy success/status/message/nfev are diagnostics.
- Candidate and Python bridge receive no benchmark identity, saved-start
  matrix, Gold configuration, Gold target, or scorer tolerance.

## Known break conditions and interpretation limits

The tanh chart cannot represent a mathematical root on a finite box boundary at
finite `w`, and `dx/dw = s*sech(w)^2` becomes ill-conditioned as a trajectory
approaches a boundary. The binary64 open-end clamp preserves safety but does
not repair this asymptotic loss. Boundary-root or strict-boundary success is
therefore not an applicability claim of this comparator.

HYBRD requires a square residual system. It can stagnate, stop for lack of
progress, or return a package success/status near a nonroot or a stationary
point of the local residual norm, especially with singular/rank-deficient
Jacobians, poor scaling, branch changes, or unusable finite-difference trials.
No MINPACK status is root evidence. Guards, domains, branch validity, residual
truth, Gold consistency, and target identity remain with the common endpoint
assessor and later production validation.

## Frozen T0 survive/kill gate

This README, implementation, tests, and dependency locks must be committed
before any T0 process is launched. Dirty T0 execution is rejected by the
runner. No dirty smoke or partial outcome is authorized for this experiment.

At the final 4,800-callback case threshold, `SCIPY-HYBR` advances to a newly
registered representative-nine-case T1 study if and only if all conditions
below hold against `prod-tol-120x600` under the common assessor:

- accepted-endpoint canonical-invalid, Gold-inconsistent, numeric-target-only,
  and ambiguous counts are zero; assessor-qualified Gold-inconsistent,
  evaluation-count mismatch, runner-cap violation, and unhandled-exception
  counts are also zero;
- aggregate assessor-qualified target count and safe-full case count are both
  noninferior, and at least one is strictly higher;
- observed callback work, including attempt-boundary overshoot, is at most
  1.2 times the primary control;
- qualified target count does not decrease in Curved, NearRank, Tangent, or the
  combined two-case Warped stratum.

Failure of any condition kills this exact frozen configuration at T0. Passing
only authorizes a separately preregistered T1 comparison; it cannot authorize a
native implementation, production route, T2, or champion claim. There are no
tuning rounds in EXP-LOCAL-007.

## Locked environment and targeted tests

Python 3.12.11 and SciPy 1.18.0 are locked by `python/uv.lock`; Julia 1.12.6 and
PythonCall are locked by `Manifest.toml`. PythonCall is forced to the
experiment-local virtual environment.

```bash
uv sync --project research/experiments/EXP-LOCAL-007/python \
  --python 3.12.11 --frozen
julia +1.12.6 --project=research/experiments/EXP-LOCAL-007 -e \
  'using Pkg; Pkg.instantiate()'
env JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 julia +1.12.6 --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-007 \
  research/experiments/EXP-LOCAL-007/test/runtests.jl
```

## Formal T0 runner — do not launch before review and commit

Each `(case, variant)` consumes the same paired saved-start order once and
snapshots after the first completed attempt crossing cumulative observed
callback thresholds 600, 1200, 2400, and 4800. Attempts are never split;
overshoot is recorded. Replay material is verified before sharding,
suffix-stable work is computed from the completed stream, and every shard
requires a clean worktree plus one Julia/BLAS/OpenMP/MKL thread.

After root review and a clean commit, the formal command is:

```bash
env JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 julia +1.12.6 --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-007 \
  research/experiments/EXP-LOCAL-007/run_t0.jl \
  --shard-index=0 --shard-count=5
```

Launch each zero-based case shard exactly once; this implementation creates no
T1 runner or outcome.

If T0 rejects the candidate, delete the adapter, bridge, dependency locks, and
candidate-specific knobs. Retain only the compact audited decision, artifact
hashes, bounded negative-result entry, and the mathematical counterexample
needed to prevent repetition.
