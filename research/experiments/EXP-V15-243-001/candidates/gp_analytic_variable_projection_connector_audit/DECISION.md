# Analytic Golub--Pereyra connector: source activation gate

## Decision

**STOP at the mandatory source-only activation gate.** No solver connector,
worker hook, portfolio allocation, search, HP, replay, scorer, or formal run
was created.

The exact source-DAG audit found one activated development formulation and one
anonymous graph cluster.  The reopen gate required at least two graph
clusters.  The observed aggregate was:

- typed source-DAG programs: 22/145;
- exact joint-affine plus structural-matching activation: 1/145;
- anonymous graph clusters: 1 (required: 2);
- selected inner dimension: 2, affecting 3 residual rows;
- source numeric evaluator calls: 0.

The audit lexically extracted only each `formulation` value and projected only
variables, bounds, construction, constraints, and guards.  It did not retain
problem IDs, decode answer/target/post-process, deserialize outcome-bearing
sibling fields, read a scorer or previous outcome, or access validation/sealed
data.

## Why the analytic D0 does not reopen this gate by itself

Commit `5dcbf645cb0945f8ef45b4a669d4af0f6de478bf` correctly removes the old
finite-difference projected Jacobian overhead on generated separable systems:
the same generated roots required 147 rather than 289 inner solves.  That
resolves the old 918-extra-inner-solve failure mechanism, but it does not
provide a sufficiently broad current-source applicability seam.

The existing semantic algebraic lift has much broader syntax coverage, but it
introduces auxiliary variables and phase/selector replay ledgers.  Those
variables are not the current solver coordinates and therefore do not provide
a minimal `A(x)y-b(x)` connector without a new lifted-coordinate solver and
authority path.  Treating that cover as a current-coordinate affine block
would violate the fail-closed and canonical-replay requirements.

## Fixed safety boundary for a future reopen

A future attempt must first demonstrate a second independent anonymous graph
cluster through a branch-audited current-source DAG.  Only then may it connect
analytic `A,dA,b,db` and `dy/dx`.  Runtime numeric rank/condition, strict
guards, branch stability, analytic-derivative agreement, and final canonical
source replay must all fail closed.  Ordinary baseline search, HP, replay and
authority retain at least 75% of the budget; the side lane is capped at 25%.

The old opaque epoch-e detector remains evidence and a worker-seam reference,
not an authority for linearity.  Its 50/50 worker split must not be reused.
