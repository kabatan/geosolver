# EXP-LOCAL-015 pre-outcome experiment card

Status: **implementation/conformance only; T0 outcome execution is not yet
authorized**.  This card was frozen before any corpus-wide candidate outcome.

## Question and single changed axis

Can a semantics-valid endpoint that E4 cannot certify be converted into a
better `RefinementSeed` by condition-triggered precision escalation or a
stable one-dimensional weak-line bracket, at no more than 600 weighted oracle
work?  Local globalization, proposal streams, novelty scheduling, public answer
acceptance and the 512/768-bit authority are unchanged.

T0 is a mechanism/activation screen on standalone black-box fixtures.  Its
zero-rescue arm represents the unchanged E4 endpoint boundary but does not
claim to rerun E4.  A survivor must next be attached after the real frozen E4
pipeline on the representative nine and 48-case compiled corpora; only those
T1/T2 runs can promote a production change.

## Frozen roles

- `E4-ENDPOINT-NO-RESCUE`: retain the input endpoint and spend no rescue work.
- `FLOAT64-H-H2-DIAGNOSTIC-ONLY`: reserve and execute the complete rank
  diagnostic, but emit no seed.
- `REFERENCE-512-CPQR-H-H2`: source-faithful fixed-precision diagnostic.  It is
  nonpromotional because a complete dimension-eight pre-step costs 650 work.
- `GEOTARGET-ADAPTED-128-256-512-CPQR`: condition/rank-triggered precision
  escalation, one residual-decreasing Newton correction and adjacent-tier
  confirmation.
- `WEAK-BRACKET`: complete Float64 rank evidence plus symmetric multiscale
  probes in the invariant weak direction.
- `ISOTROPIC-BRACKET`: the same stencil and probe count in a preregistered
  isotropic direction.
- `WEAK-NO-EMIT`: identical weak work with bracket emission disabled.
- `WEAK-THEN-ADAPTIVE`: a strict weak bracket midpoint is passed as a new
  prefilter endpoint to the adaptive candidate; all preceding calls reduce the
  same 600-work cap.

`REFERENCE` and `ADAPTED` differ in both precision schedule and derivative
stencil.  Their direct contrast cannot be attributed to precision scheduling
alone.  Isotropic/no-emit comparisons isolate weak-direction and emission
effects; the zero-rescue arm measures added recovery, not mechanism identity.

For `WEAK-BRACKET`, `ISOTROPIC-BRACKET`, and `WEAK-NO-EMIT`, the exact raw
activation object has two booleans: `rank_evidence_activated` and
`strict_bracket_detected`.  Activation rate is the latter only.  Merely
completing an applicable rank diagnostic is not weak-mechanism activation;
`WEAK-NO-EMIT` records an internally detected strict bracket even though it
emits nothing.  `WEAK-BRACKET`, `ISOTROPIC-BRACKET`, and `WEAK-NO-EMIT` must
always report an empty assessor matched-root list, and the aggregator excludes
them from root-recall metrics even if a malformed row attempts a claim.
Every other arm likewise has the exact runner-defined activation key set;
missing keys and additional booleans are rejected, so an injected unrelated
`true` value cannot forge mechanism activation.

Every row also retains a `mechanism_diagnostics` object.  ADAPTED and COMBINED
must identify `same_source_model` as the confirmation site and must set
`refined_endpoint_high_precision_confirmed=false`; a seed-ready row must record
same-source confirmation.  Each successful adaptive attempt retains selected
and confirmation precision/rank, true rank and correction stability, and
string-valued residual/Jacobian/correction disagreement and tolerance pairs.
COMBINED retains every adaptive-attempt object, including failed attempts whose
metric fields may be null.  This evidence explains why a `RefinementSeed` was
emitted; it is not high-precision verification of the emitted endpoint.

The shared Float64 condition trigger has an explicit representation guard:
SVD/Weyl lower and upper condition bounds are classified as `above_trigger`,
`below_trigger`, `uncertain`, or `rank_deficient`.  The grey relative width is
`sqrt(cbrt(eps(Float64)))`, derived from the frozen FD step.  `uncertain` never
enters a condition-only rescue lane; raw CPQR or a threshold-near quotient is
not routing authority.

## Frozen open-development corpus

The base corpus has 21 parameterized records:

- nine rotated full-rank linear systems: dimensions 2/4/8 and condition tiers
  `1e4/1e8/1e12`, with an exact `2^-160` coordinate barrier;
- six curved/warped weak-lane systems: dimensions 2/4/8 and 4/8 clustered
  simple roots separated by `2^-20`;
- six safety controls: stationary nonroot, even multiple root, constant-target
  manifold, varying-target manifold, branch crossing and guard crossing.

Each record has 16 deterministic endpoints.  Base, exact signed-permutation
and exact rational-orthogonal replicas are scored as one representation class,
giving 63 case shards and 1,008 endpoint trials per arm.  The sole exception is
the isotropic control: its fixed coordinate draw represents an orthogonally
invariant law but is not a covariant per-start draw, so representation-level
activation, valid-seed and work spreads are diagnostic only.  Candidate code
sees only finite bounds, numerical callbacks and endpoints.  Descriptor,
checksum, root/target truth, manifold witnesses and classification stay
assessor-side.

## Work and execution contract

- One Float64 callback costs one work unit; a `b`-bit callback costs
  `ceil(b/53)` units.  Failed or malformed calls are charged before invocation.
- T0 first materializes one shared truth-blind anchor plus complete Float64
  `h/h2` prefilter per endpoint.  The runner physically evaluates this
  `1 + 4n` callback stencil exactly once.  Its immutable precision/count/work
  ledger is joined into every arm row so the scorer can reconstruct case-total
  work and verify that all eight arms reference the same shared evaluation; the
  callbacks are never physically rerun per arm.
- Each rescue arm then has a 600 weighted-work mechanism cap.  `total_work` is
  always reported as `shared_prefilter_work + rescue_work`; both components and
  their requested precision counts are independently reconstructed.  The
  runner separately observes every physical rescue and shared callback by
  precision; observed callback/work fields are reconstructed from that ledger
  and must equal requested, charged and reported ledgers.  The 600 cap applies
  to rescue work, not to case-total work.  Per-work metrics and contrasts use
  case-total work.  This separation lets T0 test mechanism activation, but
  confers no production economics authority: T1/T2 must count the real E4 work
  and rescue work together under the frozen case-total callback thresholds.
- An arm must pre-reserve every complete symmetric stencil; partial stencils
  never emit evidence.
- Callback work is primary.  single-thread wall time is diagnostic only.
- One case per process, at most 16 physical-core processes.  Julia, BLAS, OMP
  and MKL use one thread; solver `worker_count=1`; there is no within-case
  parallelism.  Julia is fixed exactly at 1.12.6.  Every shard records these
  exact thread fields, including
  `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, and `MKL_NUM_THREADS` all equal to
  one.  Julia runs only under the hash-recorded formal
  `research/experiments/EXP-LOCAL-002` Project/Manifest; the aggregate records
  its own Python version separately.
- The top-level shard object has an exact field set.  All 63 shards must share
  one corpus checksum, clean revision, preregistration path/hash and Julia
  runtime contract; missing, additional or inconsistent custody fields reject
  the campaign before metrics are computed.
- Every raw row records observed/reported rescue work, shared precision/count/
  work, physically observed precision ledgers, case-total count/work,
  status/reason, activation observables,
  seed/bracket coordinates and a truth-free replay digest.  Every emitted
  bracket includes ordered parameters, opposite-sign projected residuals,
  midpoint coordinates and a unit direction; the scorer recomputes its shape,
  midpoint and emitted-seed consistency.  Before hashing candidate input, null,
  bool, integer, string, Float64, list and dict are recursively converted into
  disjoint type-tagged AST nodes; Float64 payloads use 16 lowercase IEEE-754 hex
  digits and dict entries are key-sorted.  Python/Julia exponent spelling cannot
  change the digest, `-0.0` and subnormals remain distinct, and a user string or
  reserved-looking dict cannot collide with a Float64 node.  The assessor joins
  truth only after each arm returns.  Point-seed arms may report matched
  isolated-root classes; weak/isotropic bracket arms report valid-seed support
  only and never enter root-recall authority.

## Pre-outcome conformance and activation gates

T0 remains unauthorized until independent audit reports zero blockers for:

1. source/formula trace and REFERENCE/ADAPTED separation;
2. analytic minimum-success and typed known-break fixtures;
3. charge-before-call, exact cap closure and finite termination;
4. mechanism activation differing from its control;
5. global residual scale, signed permutation, residual-row transform and
   orthogonal variable replica invariance for every arm except the isotropic
   law control, whose representation aggregates are nonpromotional diagnostics;
6. branch/guard/domain fail-closed behavior and forged-evidence rejection;
7. candidate-seam truth separation and deterministic replay.

## T0 measurements and decisions

Primary measurements are activation rate, valid refinement-seed rate,
assessor-matched isolated-root classes per case-total work, unsupported-seed
rate, and representation disagreement.  T0 seeds are proposals, not answers;
an unsupported seed on a positive stratum is a performance/precision signal
and does not make the run invalid.  Weak-only brackets are activation evidence,
not roots; recovery authority requires the combined follow-up or the later
canonical pipeline.  Manifold witnesses are never counted as isolated roots.

Candidate-arm emissions on safety controls, accounting failures, truth leaks,
cap violations and authoritative representation disagreements must all be
zero.  Safety emissions from noncandidate controls are reported separately as
nonpromotional diagnostics and do not causally invalidate another candidate.
A candidate advances to compiled T1 only if it activates on its minimum-success
stratum, beats its equal-work mechanism-off control on the same frozen
endpoints, and improves at least three parameterized strata (or the entire
preregistered rank/precision stratum) without losing an isolated root class
recovered by the zero-rescue arm.

Performance nonpromotion does not imply method rejection.  Every nonadvancing
arm is classified through the Algorithm Causal Closure Protocol as
`INVALID_RUN`, `IMPLEMENTATION_DEFECT`, `MECHANISM_UNEXERCISED`,
`APPLICABILITY_LIMITED`, `BUDGET_OR_PARAMETER_LIMITED`,
`BOUNDED_MECHANISM_NEGATIVE`, or `INCONCLUSIVE`.  Only an independently audited
bounded mechanism negative may be deleted as a frozen configuration.

Exact per-start representation agreement applies to deterministic candidate
and control mechanisms.  The isotropic random control has an orthogonally
invariant law but not a covariant sample-by-sample vector; its representation
split is reported distributionally and is diagnostic, not an exact-replica
gate.

## Promotion boundary

T0 cannot change Core, public APIs, E4, solve/policy versions or answer
semantics.  A T0 survivor must pass real E4-attached T1, the frozen 48-case T2
Path A/B gates, compiled 512/768-bit validation, metamorphic replicas and
U2/U3/U4 before any production integration.
