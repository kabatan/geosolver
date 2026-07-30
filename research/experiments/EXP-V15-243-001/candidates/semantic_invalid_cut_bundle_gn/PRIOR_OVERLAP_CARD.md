# Prior-overlap card: semantic-invalid cut-bundle Gauss--Newton

## Audit scope

The repository was searched before implementation for filter, barrier,
restoration, billiard/reflection, bundle/cutting-plane, derivative-free trust
region, and semantic-invalid trial mechanisms.  The closest lineages are:

- `guard_interior_filter`, `guard_filter_restoration`,
  `interior_filter_restoration`, and `wave11_guard_filter_sqp`;
- `semantic_stratum_facet_reflection_g0` and
  `wave20_guard_billiard_portal_g0`;
- `epoch_b_trajectory_whole_jacobian_bundle_g0`;
- `nonsmooth_dfo` and the OrthoMADS/extreme-barrier experiments.

## Mechanism distinction

This candidate does not add guard violations to an objective or filter and
does not take a guard-Jacobian restoration step.  It starts only from a
source-valid accepted point.  When the unchanged residual model repeatedly
proposes a finite semantic-invalid trial, it uses only the existing Boolean
semantic callback to bisect that accepted/trial segment.  The valid bracket
endpoint supplies a local halfspace normal proportional to the rejected chord.
Up to eight such halfspaces persist at that accepted anchor and constrain the
next residual Gauss--Newton model through a small dense QP.

That accumulated polyhedral state is absent from the terminal local
filter/barrier/restoration lineage.  It is also different from:

- single facet reflection, which emits one point on the other side rather than
  constraining later model steps by a bundle;
- billiard motion, which preserves a ballistic path through repeated specular
  reflections and does not solve the residual model in the cut polyhedron;
- trajectory whole-Jacobian bundles, which retain several complete residual
  Jacobians, not source-semantic boundary cuts;
- cutting-plane/bundle methods for a known nonsmooth objective, because the
  source Boolean is never treated as a value oracle or subgradient.

No repository implementation was found that accumulates multiple
Boolean-bracketed semantic boundary halfspaces at one accepted residual-model
anchor and solves the next GN/LM step inside their intersection.

## TRFD reference boundary

Davar and Grapiglia, *TRFD: A Derivative-Free Trust-Region Method Based on
Finite Differences for Composite Nonsmooth Optimization*, SIAM Journal on
Optimization 35(3), 2025, DOI
[`10.1137/24M1701587`](https://doi.org/10.1137/24M1701587), motivates keeping a
trust region around a finite-difference model when a known convex Lipschitz
outer function is nonsmooth.  This prototype borrows only the discipline of a
bounded local model and explicit evaluation accounting.  It is not TRFD: the
semantic Boolean is neither a Lipschitz value nor a convex outer function, no
complexity claim is made, and the residual Jacobian is supplied by the
generated ordinary GN model.

## Reopen/stop boundary

The lineage may advance only if equal-cap generated D0 gains safe roots in at
least two unrelated semantic geometries, loses none, emits no false descriptor,
and reduces semantic-invalid evaluations by at least 30%.  Failure of any gate
stops before a real/source/scorer connection.
