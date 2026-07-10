# EXP-SINGULAR-001 S4 static implementation audit

Status: input-generator checkpoint only; no S4 input or outcome has been
materialized, and no candidate/control implementation exists.

This audit was prepared while `EXP-COMP-001` held the host-exclusive formal
performance slot. No Julia or Python process, test, compilation, package
operation, input generator or benchmark was run. JSON syntax was checked only
with PowerShell's in-process parser; executable validation is deferred until
the exclusive run ends.

## Formula audit

The map in `s4-preregistration.json` agrees with Algorithm 1 of Lee, Li and
Zhi, arXiv:2305.10803v2. In particular, the SVD is taken at the current point
`x`, the retained-range correction produces `x_range`, and the projected
operator is formed from the *same* `U2`, `V2` and `v=V2*c` while derivatives
are evaluated at `x_range`. Recomputing or replacing the nullspace at
`x_range` would be a different algorithm and is forbidden.

The paper establishes a local quadratic-convergence result under a correct
deflation-one classification and a sufficiently close approximation. Its
experiments select the numerical-rank tolerance by example, and the paper
leaves quantitative certification as open work. S4 therefore remains an
empirical, development-only refiner with fixed multi-precision gap/angle
checks; it is not a singular-root certificate.

## Ambiguities closed before input generation

The original card did not uniquely define the rank cutoff, smallest-gap rule,
principal-angle reference, absolute mixed-stencil scale, projected-rank cutoff,
coefficient counter, strict route residual goal, or analytic Hessian callback
charge. A gap-only initial route can also admit a regular but ill-conditioned
close root. Amendment A1 therefore adds a final, scale-normalized null-decay
applicability gate. A persistent discarded singular value must fail as the last
step vanishes; this is a fail-closed empirical discriminator, not a proof of
multiplicity or isolation. These definitions do not change a stratum, budget,
advancement gate or allowed claim.

A second counterexample requires a separate residual-decay gate. If a regular
fold `F=(y,x^2-a^2)` is deliberately admitted by the small-gap route, the
two-step map can move the exact root `x=a` to the stationary midpoint `x=0`.
There the discarded singular value and next step vanish even though the
residual is `a^2`; both the stop tolerance and null-decay gate can pass when
`a` is small. S4 therefore normalizes the final residual by the frozen route
residual/Jacobian scale and requires quadratic decay relative to the final
step, with the same reserve, at both precisions for every primary and
confirmation endpoint. This remains an applicability check, not a root proof.

The candidate route makes four finite-difference probes (128/256 bits crossed
with radius 1/0.5) and compares the other three left/right nullspaces to the
fixed `(256, 0.5)` reference. The analytic control instead makes two analytic
Jacobian probes, one at each precision, with no fictitious radius. At every
trajectory iteration the endpoint-selected `k` remains fixed, but finite
retained singular values, the retained cutoff, and a full-rank/well-conditioned
projected operator are rechecked.

Every accepted iteration is one undamped, unclipped range-plus-null step. No
line search, trust adjustment, projection or fallback is allowed. At least one
complete step is mandatory, after which both the frozen residual and normalized
step goals must pass. Residual/target callback domain or guard failure is typed
unknown. `CandidateInput` has no declared-bound field and this S4 split freezes
no finite configuration bounds, so the experiment does not claim a bound gate.

The initial projected-operator audit uses coefficient counter `ell=1`. Actual
trajectories use their local iteration in `1:64`; all final unapplied-correction
audits use the reserved `ell=65`, regardless of trajectory length. Thus
cross-precision/radius reserves never compare corrections built from different
counter vectors. Audits charge oracle/factorization work but not a trajectory
iteration, and their `ell`, `c` and `v` remain trace fields.

The final artifact also freezes the S3-style conservative error construction:
configuration error is 16 times the maximum of both final steps, cross-precision
and confirmation disagreement, and a charged radius/precision finite-difference
reserve. Target error is 16 times the maximum of target disagreement, the
256-bit radius-1 target-gradient propagation, a charged gradient reserve and
target roundoff. Promotion requires the original `1e-10`/`1e-12` limits and all
route, null-decay, residual-decay, semantic and budget gates.

The phrase that the analytic control may share "only" ledger and semantic
types is impossible literally because a paired control must consume the same
frozen endpoint and counter schedule. A1 narrows the intended independence:
experimental inputs and final predicates are common, while all numerical
derivative, decomposition, solve, convergence and error-estimation helpers are
separately coded.

## Freeze and implementation boundary

The allowed order is:

1. preregistration and A1;
2. input-only generator source;
3. generated manifest plus input-freeze record in a separate commit;
4. candidate and independently coded analytic control;
5. implementation freeze;
6. first development run.

`src/s4_inputs.jl` is intentionally limited to opaque cases, exact transform
labels, analytic-control fixtures and manifest construction. `run_s4`, its
two-step map, route predicate and evidence constructor must not exist before
step 3. The candidate will receive only `CandidateInput`; the separate
analytic-control fixture is held by the development case wrapper.

The S4 route will reuse one existing `_WorkLedger` per variant/endpoint. That
single instance must cover route diagnosis, the 128- and 256-bit primary
trajectories, all confirmations, final audits, error work and semantic replay,
so the hard 64-iteration, 4,096-callback and 10-second limits cannot reset at a
trajectory or precision boundary. The research-only analytic
`analytic_second_directional(x,v,w)` call costs one residual-vector callback
and must fail closed on a shape or finite-value violation.

## Product isolation

All S4 files live under `research/experiments/EXP-SINGULAR-001`. This checkpoint
does not import, export from, or modify the product solver, plugin ABI, DSL,
checkpoint identity or default execution path. Passing development can only
authorize a separately generated locked study; it cannot authorize a product
connection.
