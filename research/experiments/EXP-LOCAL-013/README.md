# EXP-LOCAL-013 — exponential strict-guard slack CPQR heuristic

Status: **frozen; EXP-LOCAL-014 G0 outcome execution authorized**.

`E4-EXP-GUARD-SLACK-CPQR` is an experiment-local endpoint-correction
candidate for residual-qualified endpoints with public strict guards.  It is
not a validated solver and cannot create a numerical answer.  Its output must
still pass the unchanged canonical 512-bit refinement and independent 768-bit
replay before it can become an answer.

## Mechanism

For midpoint/half-range coordinates `x = o + R*u`, scaled equality residual
`F(u)`, and normalized public strict guards `g_i(u)`, let
`s_i = g_i(u_0) > 0` at the qualified base endpoint.  The candidate initializes
`z_i = 0` and applies at most three accepted corrections to

```text
H(u,z) = [ F(u) ; g_i(u)/s_i - exp(z_i) ].
```

The strict-guard tokens are sorted only to make the representation canonical.
Every sampled point must have the same token set and opaque branch token as the
base point.  A central `h`/`h/2` finite-difference column is used when both
sides are valid.  Otherwise, a single branch-stable direction must supply
`h/2`, `h`, and `2h`; the direction maximizing the minimum normalized public
guard slack is selected without using a case or family label.  The two
Jacobians share the same stencil.  The `z` columns are analytic.

The residual block must satisfy the heuristic rank/error gate
`sigma_min > 2*eta`.  The two augmented systems use column-scaled,
full-column-rank CPQR.  A trust-radius safeguard and the fixed trial sequence
`(1, 1/2, 1/4, 1/8)` accept only steps with Armijo decrease and positive
actual/predicted reduction ratio strictly greater than `1e-4`.  The total
base-plus-correction callback cap is 600.  Radius expansion uses the norm of
the accepted effective `alpha * clipped_step`; a pre-backtracking step at the
radius boundary cannot expand the radius after a shorter alpha is accepted.

## Final guard-separation heuristic

Acceptance never uses a cutoff on `z`.  From the final `h`/`h/2` models, the
candidate forms

```text
stability = 1 - 2*eta/sigma_min
rho_lift  = max(||p_h,u||, ||p_h/2,u||, ||p_h,u-p_h/2,u||) / stability
rho_F     = ||F||_2 / (sigma_min - eta)
rho       = max(rho_lift, rho_F).
```

For each guard it subtracts from `g_i/s_i` the gradient-envelope change over
`rho`, the `h`/`h/2` disagreement envelope, and an outward-rounded Float64
allowance.  It also requires the normalized box distance minus `rho` to be
positive.  The original and lifted infinity-norm residuals must both be at
most `1e-12`.  Any nonpositive lower value yields
`E4_HEURISTIC_UNKNOWN` and drops the candidate endpoint.

This model is deliberately labelled `HEURISTIC-NOT-ANSWER-AUTHORITY`.
Finite differences do not bound derivatives or remainders between samples;
therefore the lower model is neither an interval proof nor a Krawczyk
certificate.  In particular, oscillatory or nonsmooth guards remain a break
condition.

## Capability routing and accounting

- `public_guard_count == 0` delegates immediately and exactly to the injected
  frozen E1 CPQR candidate (or its matching shadow), before inspecting an
  outcome and without extra callbacks.  The factory rejects the injection
  unless both its name and its complete frozen configuration match:
  `base`, callback cap, proof step, proof radius, maximum corrections, and
  shadow role; extra fields are also rejected.
- A guarded case requires a residual-qualified base endpoint, exactly the
  declared number of distinct public strict guards, positive finite guard
  scales and slacks, and the declared branch-token capability.  A missing
  contract becomes `UNKNOWN`; it does not trigger another solver.
- If the guarded base endpoint is not residual-qualified, E4 never starts.
  The base endpoint, base status, convergence/acceptance flags, evaluation
  count, and iteration count pass through unchanged; the diagnostic records
  `reason=base-pass-through`.
- `fd_calls` and `trial_calls` count newly charged callbacks in those contexts.
  `invalid_fd` counts a charged FD callback rejected for finiteness,
  semantics, strict feasibility, token-set, or branch mismatch.  An
  out-of-box FD offset has no callback and increments neither counter.
- `invalid_trials` counts an out-of-box alpha (no callback), a newly charged
  trial callback rejected by the same contract, or a nonfinite/underflowed
  exponential after a valid callback.  A valid callback rejected only by
  Armijo or model ratio is in `trial_calls` but not `invalid_trials`.  A cache
  hit itself changes no counter; however, if a cached valid `u` is combined
  with a new `z` whose exponential is invalid, that failed exponential still
  increments `invalid_trials`.
- The same-work shadow executes the identical guarded trajectory and returns
  the original base endpoint.  Only the returned endpoint/acceptance role and
  the diagnostic `shadow` flag differ.

## Frozen pre-outcome scope

The targeted T0 fixtures cover true margins `1e-6`, `1e-8`, and `1e-12`, a
strict-boundary ghost, flat and curved guards, two guards, positive guard-scale
replicas from `1e-12` through `1e12`, guard tuple reorder, exponential
underflow, branch-token instability, guard-token relabel, residual raw-value
and declared-scale co-scaling, signed coordinate permutation, and a
NearRank-like large-step case.  They also freeze exact guardless E1 delegation,
candidate/shadow callback work, and disjoint FD/trial invalid accounting.
General orthogonal replicas are not claimed to preserve an axis-FD trajectory;
their answer class is evaluated only in a later campaign.

The qualified NearRank guard-crossing fixture fixes bounds `[-1,1]^2`, start
`(0.25,0.9)`, `F=(x-0.25, 5e-13*(y+0.25))`, and strict guard `g=y`.  Its base
residual is `5.75e-13`, while the weak-direction correction is `1.15` and the
unique root has `y=-0.25`.  E4 must therefore return `UNKNOWN` with no endpoint;
the shadow must perform identical work and return only the original base
endpoint.  The separate `epsilon=1e-10` fixture tests nonqualified-base
pass-through and is not evidence about E4's correction mechanism.

The direct feasible-chart candidate A is a later comparator, not part of this
implementation.  If E4 survives targeted T0, an exponential-versus-linear
slack ablation must use the same base endpoints, callback cap, starts, FD
stencils, and assessor.  Neither later comparison is authorized by this
directory.

Relevant prior work includes constrained Gauss--Newton and trust-region
globalization [Izmailov and Solodov (2026)](https://link.springer.com/article/10.1007/s10589-026-00801-4),
bound-aware trust regions [Bellavia et al.](https://www.sciencedirect.com/science/article/pii/S0168927402001708),
finite-difference error analysis [Shi et al.](https://epubs.siam.org/doi/10.1137/21M1452470),
and rigorous Krawczyk certification as the deliberately stronger standard
[Duff and Lee](https://arxiv.org/abs/2011.05000).

Only source, preregistration, and targeted tests are present.  There is no
runner, aggregator, outcome artifact, Core integration, or production knob.
