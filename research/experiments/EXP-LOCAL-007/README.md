# EXP-LOCAL-007 — square-system Powell hybrid comparator

Status: **48-case T2 rejected SCIPY-HYBR; native port and production promotion forbidden**

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

## Audited T0 decision

Five clean detached-HEAD shards at revision
`949386bf4b89fe500cb0790d299e4cfc89d9f1ae` ran on distinct physical cores
with one Julia/BLAS/OpenMP/MKL thread each. At the 4,800-callback threshold,
`SCIPY-HYBR` preserved assessor-qualified target recovery at `4/10`, improved
assessor-safe-full from `2/5` to `3/5`, and used 24,297 callbacks versus 25,286
for `prod-tol-120x600` (ratio `0.9608874475994622`). Candidate accepted-endpoint
safety, assessor inconsistency, count mismatch, runner-cap, and exception
counts were all zero. Curved, NearRank, Tangent, and combined Warped target
recovery were all noninferior.

The 653 attempts and 60 summaries were independently rebuilt from the raw
artifacts. Callback-role sums, exact paired starts, replay checksums, threshold
crossings, overshoot, and suffix-stable work all matched. The authoritative
hash-bound record is [`t0-decision.json`](t0-decision.json). This result
authorizes only the preregistered T1 screen below.

## Frozen representative-nine T1

[`t1-preregistration.json`](t1-preregistration.json) freezes the existing
`representative_problems` nine-case corpus, all 512 saved starts and replay
checksums, the same case-cumulative callback thresholds
`600/1200/2400/4800`, and the unchanged three variants. No T1 outcome was
observed while defining the runner or gate.

Eight cases satisfy HYBR's public `residual_dimension == dimension`
applicability predicate. The redundant overdetermined case remains in the
corpus and must produce `INAPPLICABLE_NONSQUARE` with zero callbacks on the
first paired start. `run_t1.jl` records this as an explicit terminal snapshot
at each threshold label with `threshold_reached=false`; it is not credited as
performance or silently discarded. Applicable-family metrics therefore cannot
support a production-default claim for nonsquare problems.

T1 can authorize a separately frozen T2 study only when all safety and
generality gates pass. Family-equal assessor-safe-full must either improve by
at least 5 percentage points with callback work at most 1.2x, or remain within
1 point while callback work or confirmed end-to-end wall falls by at least
20%. Callback work here is per-case suffix-stable common-assessor safe-full
work, with a miss right-censored at 4,800 callbacks; it is not the nearly fixed cost of forcing
both streams through the final reporting threshold. Every preregistered
critical-stratum delta must be at least -2 points,
the signal must repeat in at least three unrelated applicable families, and
all safety/truth/accounting violations must be zero. A wall-only efficiency
claim additionally requires two clean one-thread AB/BA process-order
replicates. T1 is not a production or native-port gate.

The zero-violation gate is candidate-only across every applicable case and
every recorded prefix; truth leak is checked from candidate/runner source.
Control violations remain part of the control safe-full and work baseline but
are not added to the candidate's zero count. This matches the audited T0 gate.

## Audited T1 decision

Nine clean one-case shards at revision
`b37f6bb60ed8682aed41db7153db376fc23236e6` produced 2,997 attempts and 108
summaries. Independent reconstruction found no safety, accounting, runner-cap
or typed-inapplicability violation. On the eight square-applicable cases,
family-equal common-assessor safe-full rose from `0.5714285714` to
`0.8571428571`; right-censored callback work fell from 19,675 to 9,834, a
ratio of `0.4998221093`. Callback-only Path B repeated in six unrelated
families with no critical-stratum regression.

The authoritative record is [`t1-decision.json`](t1-decision.json). It
authorizes only the frozen T2 generalization study. Both variants still found
zero of the six MultiRoot targets, and HYBR remained typed-inapplicable on the
public nonsquare case; neither limitation is hidden by the T1 decision.

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

## Formal T0 runner — completed and retained for audit

Each `(case, variant)` consumes the same paired saved-start order once and
snapshots after the first completed attempt crossing cumulative observed
callback thresholds 600, 1200, 2400, and 4800. Attempts are never split;
overshoot is recorded. Replay material is verified before sharding,
suffix-stable work is computed from the completed stream, and every shard
requires a clean worktree plus one Julia/BLAS/OpenMP/MKL thread.

The completed T0 used the following command shape:

```bash
env JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 julia +1.12.6 --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-007 \
  research/experiments/EXP-LOCAL-007/run_t0.jl \
  --shard-index=0 --shard-count=5
```

Launch each zero-based case shard exactly once; this implementation creates no
additional T0 outcome.

## T1 runner — completed and retained for audit

The completed T1 used this one-case shard command shape:

```bash
env JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 taskset -c 0 julia +1.12.6 \
  --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-007 \
  research/experiments/EXP-LOCAL-007/run_t1.jl \
  --shard-index=0 --shard-count=9
```

Indices `0..8` ran on distinct physical cores with the same thread settings and
separate output paths. An agent that did not implement the candidate rebuilt
the metrics and gate from the nine raw artifacts.

## Lightweight 48-case T2

[`t2-preregistration.json`](t2-preregistration.json) fixes eight existing
development families, six cases per family, 32 paired starts, saved-start
prefixes `8/16/32`, and the three unchanged variants. The canonical corpus
checksum is
`9b17d99a33b076833902b14d19c9b7a8f490f78d15e600c47fe068668d139e26`;
all 48 cases also match the pre-T1 EXP-LOCAL-004 manifest. The six redundant
overdetermined cases remain explicit typed-inapplicability checks outside the
square performance denominator. MultiRoot remains both a critical stratum and
an independently reported diagnostic.

`run_t2.jl` owns exactly one case and records 96 variant-start attempts plus
nine prefix summaries. `run_t2_campaign.py` is the only outer driver and
aggregator: it runs at most 16 independent processes pinned to physical cores
0–15, with Julia, BLAS, OpenMP and MKL fixed to one thread. It verifies the 48
disjoint shards, callback caps, paired starts, safe-full, target recall,
nonsquare behavior and the preregistered callback-only promotion gate. Wall
time remains diagnostic. It rebuilds safe-full, target recall and primary work
from raw attempts and rejects disagreement with the Julia summaries. Primary
work is per-case suffix-stable common-assessor safe-full callback work, with
misses right-censored at 4,800; it is not the total cost of forcing all 32
starts. A short independent source audit supplies only the truth-leak pass/fail
input; there is no source-authorization protocol, runtime tree seal,
artifact-custody service or publication launcher.

If an outcome-independent aggregation bug is repaired after shard execution,
the summary records both the immutable shard execution revision and the clean
descendant aggregation revision; raw shards and the preregistration hash remain
unchanged.

After these files are committed, run the campaign and aggregation as follows:

```bash
python3 research/experiments/EXP-LOCAL-007/run_t2_campaign.py run --jobs=16
python3 research/experiments/EXP-LOCAL-007/run_t2_campaign.py aggregate \
  --truth-leak-audit=pass
```

T2 may promote HYBR only as a square-capability local mechanism study. It does
not itself authorize a production dependency or claim to solve global
MultiRoot discovery. A passing T2 triggers a native implementation wave.

## Audited T2 decision

The clean 48-case execution produced 4,608 attempts and 432 summaries. An
independent raw reaggregation matched every prefix and aggregate metric. The
candidate tied the primary control at family-equal safe-full `0.738095`, used
`0.905336` times its right-censored suffix-stable callback work, regressed
StrictGuard from `6/6` to `3/6` and MultiRoot from `2/6` to `1/6`, and produced
five common-assessor Gold-inconsistent close-root endpoints. It therefore
failed both performance paths, the critical gate, generality gate and safety
gate.

[`t2-decision.json`](t2-decision.json) is authoritative. No native HYBR port is
authorized. The next local wave tests general feasibility restoration and a
distinct OrthoMADS extreme-barrier mechanism; MultiRoot remains a separate
all-target discovery problem.

If T2 rejects the candidate, delete the adapter, bridge, dependency locks, and
candidate-specific knobs. Retain only the compact audited decisions, artifact
hashes, bounded negative-result entry, and the mathematical counterexample
needed to prevent repetition.
