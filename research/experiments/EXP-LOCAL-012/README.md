# EXP-LOCAL-012 — guard-chart CPQR endpoint heuristic

Status: **frozen; EXP-LOCAL-014 G0 passed and R1 outcome execution authorized**.

`E3-FD2-GUARD-CHART-CPQR3` is the narrow successor to the rejected E1
endpoint filter. It changes only a typed central-stencil failure caused by a
public guard or a box bound: one unique semantics-valid, branch-fixed side may
provide second-order `h`/`h/2` residual and normalized-guard Jacobians. During
FD/proof/chart construction, rank, two-resolution, backward-error, budget,
branch, non-guard, and nonunique-chart failures still return `UNKNOWN` and
drop a residual-qualified endpoint.

After a proof exists, Armijo retains E1's general invalid-trial backtracking.
An invalid public guard, changed branch token, or other invalid semantics at a
trial is charged and rejected; the next value in the fixed
`(1, 1/2, 1/4, 1/8)` list is tried. No new alpha, pseudo-residual, or alternate
proof is introduced.

The final direct predicted-center check uses an empirical guard-interior lower
model. Its status is `LOCAL_HEURISTIC_GUARD_INTERIOR`; finite samples provide
no derivative/remainder proof and never create a validated or certified
answer. The paired shadow executes identical work and returns the original LM
endpoint.

Only synthetic and metamorphic targeted tests are present. There is no runner,
aggregator, campaign result, Core integration, or production knob.
