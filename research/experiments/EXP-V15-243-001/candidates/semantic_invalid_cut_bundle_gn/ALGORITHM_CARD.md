# Algorithm card: semantic-invalid cut-bundle Gauss--Newton D0

## Status and scope

`D0_GENERATED_GATE_PASS / HOLD_FOR_SOURCE_SEAM_AUDIT`

This is a candidate-private generated prototype.  It has no real solver
binding and changes no common guard compiler, QP framework, worker, scorer,
HP/restoration service, or canonical authority path.

## Mechanism

At a finite source-valid accepted point `x`, an ordinary damped GN model
proposes `y`.  Only after semantic-invalid rejection repeats does the side
lane act:

1. reject nonfinite, opaque, branch/rank/scaling-disagreeing observations;
2. probe beyond `y`; a valid result identifies an isolated invalid pocket and
   fails closed;
3. bisect `[x,y]` with the unchanged Boolean semantic callback;
4. retain the valid bracket endpoint `z` and normalized outward chord
   `n ∝ y-z` as the proposal-only halfspace
   `nᵀp <= nᵀ(z-x)`;
5. retain at most eight local cuts; and
6. solve

   `min 1/2 ||F+Jp||² + lambda/2 ||Dp||²`

   subject to `||Dp||_inf <= Delta` and every retained halfspace.

The small dense QP enumerates active sets and checks primal feasibility and
nonnegative inequality multipliers.  It is deliberately private and capped at
four variables.  No shared QP abstraction was introduced.

Cuts are cleared when branch, rank, or scaling changes, when the accepted
point moves materially relative to its trust radius, when their local
polyhedron blocks all model progress, or when model/cut disagreement indicates
strong nonconvexity.  A cut is never feasibility or answer authority.

## Portfolio and safety

- Routing is structural progress only: every fourth start is side, preserving
  75% byte-ordinary start slots.
- Invalid starts, isolated invalid pockets, nonfinite/opaque evaluations,
  branch/rank/scaling changes, and strong local disagreement fail closed.
- The side lane is capped at 25%; ordinary search/HP/replay authority is not
  replaced.
- Every claimed generated root uses an independent canonical replay.
- Strict-boundary closure roots are never promoted.
- No case identifier, family label, target truth, prior outcome, scorer, or
  validation/sealed input enters the candidate.

## Intended D0 geometries

Positive families are a thin curved corridor, a rotated wedge, and a valid
cell accompanied by a disconnected remote cell.  Negative/near-miss families
are an infeasible source, a strict-boundary-only root, an isolated invalid
near-root pocket, a strongly nonconvex cell, nonfinite trials, and opaque
semantic trials.  Permutation, diagonal scaling, reflection, and guard-order
changes are outcome metamorphics.

See `PRIOR_OVERLAP_CARD.md` for the repository audit and the deliberately
limited relationship to TRFD.

## D0 result

At 100 callbacks per arm/case and 20 seeds per family:

- control/candidate safe roots: `0/60 -> 60/60`;
- gains/losses: `+60/-0`, across all three positive families;
- semantic-invalid evaluations: `5880 -> 1878`, a `68.061%` reduction;
- callback mismatches: `0/60`;
- false descriptors: `0/120` negative/near-miss cases;
- permutation/scale/reflection/guard-order failures: `0/12`;
- maximum simultaneously retained cuts observed: `2` (hard cap `8`);
- tests: `11/11`.

This passes the requested generated gate.  It is not real-corpus evidence:
the control deliberately represents the diagnosed no-information semantic-
invalid churn mode, and fixed-cap accounting pads a discovered root with
source-valid observations so both arms consume the same callback cap.  A
future connection must first prove that the current worker exposes accepted
points and rejected semantic trials without changing ordinary ownership.
