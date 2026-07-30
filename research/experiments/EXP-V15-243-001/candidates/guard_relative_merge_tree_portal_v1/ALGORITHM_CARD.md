# GUARD_RELATIVE_MERGE_TREE_PORTAL_V1

## Hypothesis

Low-residual invalid endpoints can reveal a boundary-attracting basin without
making them answer candidates.  A residual lower-star merge tree on charged
finite observations can locate the first topological merge from such an
invalid component into a source-interior component.  Restarting from the
existing interior vertex at that merge may cross the attraction barrier while
retaining exact guard safety.

## Mechanism

- Use dimensionless source scales and the mutual-kNN graph with the fixed
  `k=min(2*n+1,N-1)`; duplicate vertices or a kNN cutoff tie fail closed.
- Define a low-residual invalid endpoint without a numeric threshold: it is a
  strict residual local minimum among its mutual-kNN neighbors.
- Insert vertices in strictly increasing residual lower-star order and use
  union-find to find the first merge of the invalid-minimum component with a
  component containing typed source-interior observations.
- Promote only the existing interior observation selected at that merge.  The
  midpoint from invalid minimum to portal is one charged side probe and is
  never itself an answer or authority candidate.
- No persistence cutoff, residual threshold, radius, or sweep exists.

## Dynamic gate and safety

Every pool must have complete typed guard coverage, only charged finite
observations, and at least eight source-interior observations.  Activation
requires at least three low-residual invalid endpoints across at least two
anonymous source hashes.  Unknown guards, uncharged/nonfinite data, topology
ties, or insufficient recurrence return the entire route to baseline.

Every fourth start is the maximum side allocation; all others remain baseline.
Midpoint evaluation is charged inside the same side budget, so baseline is at
least 75% and side is at most 25% for both starts and callbacks.  A portal is a
proposal only.  The unchanged local solver and canonical source/guard/branch/
raw-target replay remain mandatory.

No problem/family ID, target, answer, truth, or prior outcome is a routing
feature.  The anonymous gate emits aggregate counts only.

## Generated D0

Three generated dimensions/families supply three anonymous invalid minima and
eight interior observations per pool.  All 3/3 produce an existing interior
portal.  Eight focused tests cover guard/recurrence/interior gates, charged and
finite observations, kNN ambiguity, proposal authority, 75/25 accounting, and
observation-order/residual-scale/coordinate-scale invariance.  With 1,200
callbacks, the frozen accounting is baseline 900 and side 300, including three
midpoint probes.

This is generated mechanism evidence only.  The real dynamic gate is not run
in this lane; Root owns aggregate observation custody.  No corpus, formal
runner, scorer, truth, 98-case, validation, sealed input, or individual result
was accessed.

## Nearest mechanisms and reopen

Barrier/guard penalties are not reused: invalid endpoints never become
answers, and exact typed guard state is separate from residual.  This is also
not residual-only start ranking: the proposal requires a mutual-kNN component
merge into an already source-interior component and retains a 75% baseline.
If the real dynamic gate is zero, reopen only with recurrence satisfying the
same fixed gate; do not tune k, persistence, thresholds, or midpoint policy.
