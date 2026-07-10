# EXP-SINGULAR-001 S4 implementation audit

Status: source review and family-disjoint synthetic verification are complete;
no development case has executed and no Gold outcome has been interpreted.
Development inputs and the separate Gold artifact are immutable at commit
`3fb7480`; locked inputs do not exist and product code is disconnected.

## Numerical map and independence

The candidate and analytic control each implement their own rank selection,
SVD split, principal-angle check, counter schedule, range solve, projected
operator, null solve, trajectory, transport, convergence and error routines.
They share only the frozen endpoint/oracle, work-ledger and canonical semantic
replay types, confirmation-start formula, artifact vocabulary and final gate.
Both mechanisms receive only metadata-free `S4CandidateInput`; only the control
separately receives `S4AnalyticControlOracle`. Candidate source and capability
objects contain no case/family/group/Gold or analytic-fixture routing field.

At every step, the split is computed at `x`. Its `U2`, `V2` and physical probe
remain fixed through the range correction, derivative evaluation at `x_range`,
projected `B`, and null correction. There is no SVD at `x_range`. Actual steps
use the local `ell=1:64` counter; start/final audits use the per-trajectory
`ell=65` physical reference transported into every accepted local basis.
The eligible primary endpoint is the sole smallest-gap selector of `k`.
Primary/confirmation starts inherit that frozen `k` while retaining all
finite, retained-value, projected-rank, condition and subspace checks; every
final probe repeats the smallest-gap selection and must agree with `k`.

## Fail-closed work accounting

All residual and target calls are charged. Candidate finite-difference
Jacobians and mixed stencils are composed only from charged residual calls.
The control charges one callback for each analytic Jacobian and one residual
callback for each analytic second-directional vector. Every SVD is charged as
a factorization. One ledger covers route probes, both primary trajectories,
two confirmations, every final audit, error propagation and semantic replay.

Deadline checks occur both before and after every black-box callback, after
each generic SVD and projected solve, and in the single timestamp used to
construct promotion work evidence. A call that starts before but returns after
ten seconds therefore produces typed unknown with `deadline_reached=true`; it
cannot be promoted. These are cooperative checks: an adversarial callback or
factorization that never returns cannot be preempted in-process. The
development fixtures are frozen, pure and trusted; no product hard-wall claim
is made until worker-process isolation supplies an OS-enforced timeout. Public
research entry points reject any option set differing from the frozen protocol.

The formal runner first executes three family-disjoint, unmeasured synthetic
warm-ups at nullity 1, 2 and 4, rotating which variant runs first. Within every
three-representation metamorphic group, official variant order follows a
frozen Latin schedule, with orientation reversed on alternating groups. Thus
each variant occupies every position once per group and JIT/warm-cache order is
not confounded with representation or variant.

## Protocol corrections A2 through A6

A2 is fully observable: each audit records `V2_ref`, `v_ref`, `c65`, every
local `V2`, raw `c_local`, its norm, transported direction, projection loss,
principal angle, bound and decision. The independent analyzer reconstructs
the transport identities and every order/null/residual decision.

Static implementation review found a common-mode hole in A1's error formula:
radius/precision differences between final corrections can be tiny while all
corrections agree on one large vector. A3, frozen before any execution, adds
`max ||q||_Inf` to `raw_x` for both variants. Every q, q norm, reserve operand,
configuration disagreement, gradient, uncertainty and target operand is
persisted and independently reconstructed. Cross-precision aggregation is
explicitly executed at 256-bit precision, independent of caller ambient
precision.

A4 narrows the numerical capability to metadata-free `S4CandidateInput`,
binds exact runtime/checkpoint replay, counterbalances official execution and
states the cooperative-deadline boundary. Synthetic verification then exposed
two wiring errors without loading a development case: the new oracle lacked
charged evaluator dispatch, and start-side A2 probes incorrectly redetected a
gap despite A1 freezing `k` for the whole endpoint run. A5 binds the corrected
source and distinguishes inherited start probes from strict final probes. It
also corrects the synthetic ledger expectation: the two perturbed
confirmations each need a root-reaching step and a second complete step to
satisfy the normalized-last-step gate.

The final runner-source preflight, still before any development mechanism
execution, found that Julia 1.12.6 cannot parse the shorthand terminal
`@__FILE__ && main()` expression. A6 binds the equivalent explicit `if`
entrypoint after source inclusion and immutable case-grid verification pass.
It changes no numerical map, runtime policy, checkpoint field or gate.

## Claim boundary

The resulting errors remain conservative empirical estimates, not interval
enclosures or a proof of multiplicity, isolation, existence or completeness.
Passing the development gate can authorize only family-disjoint locked
validation; it cannot connect S4 to the solver product. The analytic control is
an independently coded derivative lower bound for this map, not a different
algorithmic certificate.
