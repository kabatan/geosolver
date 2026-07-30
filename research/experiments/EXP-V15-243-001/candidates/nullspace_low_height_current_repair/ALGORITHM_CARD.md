# NULLSPACE_LOW_HEIGHT_WITNESS_TRANSPORT current exact Repair

## Mechanism

This candidate incorporates the exact adversary handoff at
`329bd941636a54f731be02f023fdb7b984940b36`.  The old Float64 Jacobian boundary
that produced 337 false pre-authority claims is disabled and unreachable from
the connector.  Activation supports only untouched two-variable source
documents whose constraints and strict guards compile to bounded QQ
polynomials without construction calls.

The side route proves generic corank one from the polynomial Jacobian exactly.
For deterministic low-height rational free slices, it substitutes in QQ,
computes the dependent univariate source-fiber GCD, orders its real algebraic
roots only by the incoming numerical branch, and requires exact substitution
of every source polynomial, strict guard and bound.  Every coordinate minpoly
must be square-free and at least two distinct exact slices must survive.
Full-rank, zero-rank, nonpolynomial, constructed, non-strict-guard, wrong
dimension, malformed-bound, and single-slice inputs fail closed.

Each surviving transported endpoint is still sent through the copied current
refiner's three independent HP lanes.  The copied current exact candidate then
runs the existing untouched QQBar source/guard/branch/raw-answer/minpoly/root-
ordinal/isolator replay.  The candidate-private authority boundary differs
only in pinning the copied modified refiner hash; all canonical checks remain.

## Baseline and routing

The fixed current exact outer SHA
`05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7`
is loaded first and retained by identity.  It receives 75% of the endpoint
budget.  The side route receives at most 25% and is considered only when the
current exact artifact reports an independent refinement failure.  Target,
answer, provisional descriptor, case ID, family, truth and outcome are not
used to generate or route proposals.  Side failure, unsupported source,
containment failure and zero dimension return the baseline object by identity.

## D0

CPU15 generated evidence:

- exact polynomial positives 6/6 (affine row permutations/scales, curved,
  cusp);
- full-rank minimal counterexample, nonpolynomial and zero-rank fallback 3/3;
- row metamorphic invariance pass;
- copied refiner -> three HP lanes -> existing QQBar -> modified canonical
  boundary authority pass;
- nonactivation, side failure and zero dimension baseline identity 3/3;
- baseline/side allocation 15/5 seconds for a 20-second synthetic attempt;
- same PGID, PDEATHSIG 9, CPU affinity `[15]`, no containment breach/leak.

Disposition: `D0_GO_EXACT_SOURCE_SUBSET`.  Root owns activation and formal
measurement.  No corpus, runtime manifest/result, scorer, truth or formal
benchmark was accessed.

## Provenance

- current fallback source: `44d6fa802dc51e7f58e5a72e48b434a62be84275c328bd605f0e9e2f6eb11900`
- current refiner source: `14a107893f6db1b9ec113c28653a40b3817f274865b0fabc64e2a13702bdc7b3`
- current exact candidate: `e0f24e605e7e7211d134ddea66e66adbb89307148a8f03c1afebd4a2c969c66f`
- current authority boundary: `a36520a416d0b8c900bca6b79192c7014812c9b1270be09248347f0f19e167e9`
- exact adversary source commit: `329bd941636a54f731be02f023fdb7b984940b36`
