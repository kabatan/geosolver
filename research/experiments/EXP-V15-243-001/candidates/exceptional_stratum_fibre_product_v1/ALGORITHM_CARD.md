# Exceptional-stratum projection + replicated-fibre products D0

## Hypothesis and mechanism

An unstable endpoint cluster can be the numerical shadow of a nearby parameter
stratum where fibre cardinality, rank, or dimension changes.  Instead of
blindly perturbing coefficients, this 25% side lane:

1. requires a source-parameter/scale callback and an unstable source endpoint
   signal (small scaled Jacobian singular value, a close endpoint cluster, or a
   source-near nonsolution);
2. samples a small normalized one- or two-dimensional parameter ball;
3. treats multiple endpoints over the **same** parameter as a replicated fibre
   and searches for endpoint coincidence, rank drop, or fibre-count jump;
4. chooses the nearest sampled exceptional signature, ranks nearby fibres by
   distance to that stratum, and continues their real endpoints back to the
   original parameter;
5. emits only finite points passing the untouched original residual, guard, and
   branch replay.

The perturbed system and its roots have proposal authority only.  They cannot
prove a source root, multiplicity, local dimension, completeness, or a target.
Twelve of sixteen portfolio slots remain byte-preserved baseline slots.

This is a disposable generated-only prototype.  It creates no compiler,
generic continuation backend, worker, scorer, shared telemetry, or real-case
adapter.

## Primary derivation

Cobian, Hauenstein, and Wampler, *Robust Numerical Algebraic Geometry*,
[arXiv:2403.18749](https://arxiv.org/abs/2403.18749), describes parameter-space
exceptional sets where integer solution-set structure changes and uses fibre
products `F(x_1,p)=...=F(x_j,p)=0` to express simultaneous endpoint/emergence
conditions.  It searches for nearby parameter points satisfying the structured
exceptional conditions.  The present prototype keeps only the solver-relevant
proposal idea: replicated fibres select a nearby special stratum, then all
candidate points are returned to the exact source instance and replayed.

The paper's full witness-set, projection, multiplicity, and local-optimization
machinery is not claimed or implemented here.

## Runtime state and targeted failure

Allowed state is source parameter/coefficient data, declared scales, numerical
residual/Jacobian/guard callbacks, an unstable endpoint cluster, local fibre
endpoints, rank, continuation progress, and work cap.  No case ID, name,
family, truth, target, descriptor, expected count, or previous case outcome is
available to the candidate.

The targeted failure is an incomplete/unstable endpoint cluster close to a
fold, crossing, cusp, emergent-solution locus, or fibre-dimension jump.  It is
not a generic root finder and cannot help opaque callbacks or a stable endpoint
without an exposed low-dimensional parameter family.

## D0 evidence

The prospective toy corpus has ten distinct families:

- positive: fold, transcritical, pitchfork, cusp;
- negative: strict guard, stable nonexceptional roots, opaque transcendental;
- near-miss: positive-dimensional fibre jump, overdetermined emergent root,
  real-to-complex fold.

Aggregate result: `4 wins / 0 losses / 0 false / 0 extra`; all four positive
families gain, eight cases activate, and baseline/side routing remains 75/25.
The three near-miss families activate without adding a false source point.

Eight tests pass.  They cover all ten families, source replay, positive-
dimensional collapse, parameter reflection, parameter-axis swap, source
coordinate reflection/scale, residual scale, stable/opaque fail-closed, and
baseline digest/quota invariance.

## Limits and disposition

`D0_PASS / REAL_AND_COMPILER_HOLD`.

The toy fibre callback returns all endpoints cheaply; that is the largest
unresolved causal gap.  A real seam is authorized only if an already-existing
source representation exposes a low-dimensional parameter/coefficient map and
can obtain replicated fibres inside the 25% share without a new generic
homotopy platform.  Promotion then requires new replay-safe configurations in
at least two unrelated structural clusters and no recurring loss.

Stop/fail closed on absent parameter capability, dimension above two, stable
endpoint state, inconsistent fibre degree/transcript, ambiguous/nonfinite
continuation, guard failure, or source replay failure.  Do not tune the sample
grid against real case outcomes.
