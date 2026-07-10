# EXP-SINGULAR-001 S4 implementation audit

Status: source-only review before the first candidate, analytic-control, or
development execution. Development inputs and the separate Gold artifact are
already immutable at commit `3fb7480`; locked inputs do not exist and product
code is disconnected.

## Numerical map and independence

The candidate and analytic control each implement their own rank selection,
SVD split, principal-angle check, counter schedule, range solve, projected
operator, null solve, trajectory, transport, convergence and error routines.
They share only the frozen endpoint/oracle, work-ledger and canonical semantic
replay types, confirmation-start formula, artifact vocabulary and final gate.
The candidate receives only `CandidateInput`; only the control receives
`S4AnalyticControlOracle`. Candidate source contains no case/family/group/Gold
or analytic-fixture routing read.

At every step, the split is computed at `x`. Its `U2`, `V2` and physical probe
remain fixed through the range correction, derivative evaluation at `x_range`,
projected `B`, and null correction. There is no SVD at `x_range`. Actual steps
use the local `ell=1:64` counter; start/final audits use the per-trajectory
`ell=65` physical reference transported into every accepted local basis.

## Fail-closed work accounting

All residual and target calls are charged. Candidate finite-difference
Jacobians and mixed stencils are composed only from charged residual calls.
The control charges one callback for each analytic Jacobian and one residual
callback for each analytic second-directional vector. Every SVD is charged as
a factorization. One ledger covers route probes, both primary trajectories,
two confirmations, every final audit, error propagation and semantic replay.

Deadline checks occur both before and after every black-box callback, after
each generic SVD and projected solve, and immediately before promotion. A call
that starts before but returns after ten seconds therefore produces typed
unknown with `deadline_reached=true`; it cannot be promoted. Public research
entry points reject any option set differing from the frozen protocol.

## Static corrections A2 and A3

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

## Claim boundary

The resulting errors remain conservative empirical estimates, not interval
enclosures or a proof of multiplicity, isolation, existence or completeness.
Passing the development gate can authorize only family-disjoint locked
validation; it cannot connect S4 to the solver product. The analytic control is
an independently coded derivative lower bound for this map, not a different
algorithmic certificate.
