# ED-critical / moved-affine-slice sampling D0

## Mechanism and prior-overlap audit

At a numerically source-solved point with stable positive nullity, this side
lane spends only ordinal `3 mod 4`.  It reflects already-owned full-support
anchors through the source chart center, locally projects each generic query
onto `F=0` as a numerical Euclidean-distance critical proposal, then moves a
complementary affine slice in the local null coordinates and solves the square
augmented intersection.  Every proposal is only a warm endpoint; untouched
source/guard/branch replay is the sole emission authority.

This is not the terminal `wave15_affine_slice_residual_scout`, which scanned
residual values along one or two full-support lines and lost two generated
families.  Here the slice is an equation appended to `F`, and ED normal
projection plus isolated slice intersection changes the solved system.  The
old rational slice witness acted only on existing HP/PSLQ records and added no
search proposal.  Neither is an exact mechanism duplicate.

Primary derivation:

- Draisma et al., *The Euclidean distance degree of an algebraic variety*,
  arXiv:1309.0049: distance-critical points of a generic external query.
- Dufresne et al., *Sampling real algebraic varieties for topological data
  analysis*, arXiv:1802.07716: numerical-algebraic critical-point sampling.
- Sottile, *General witness sets for numerical algebraic geometry*,
  arXiv:2002.00180: complementary slices as finite witness intersections.

The prototype uses only numerical residuals/Jacobians, the caller's affine
source chart and bounds, start bytes, rank/nullity, callback ledger, and fresh
replay.  It never receives case ID/name/family, truth, target, target count, or
prior outcome.  It supports smooth nonpolynomial residuals; missing/opaque
Jacobian capability falls back byte-identically.

## Frozen D0

- Four generated positive-dimensional families: curved circle, disconnected
  ovals, a 1e4-scale space curve, and a nonpolynomial sine sheet.
- Each has positive, inconsistent-negative, and semantic-near-miss roles over
  12 prospective seeds.  Additional isolated/full-rank and opaque counters
  run over 12 seeds each.
- Both arms receive four starts and 44 callbacks per lane.  Ordinals 0--2 are
  byte-identical baseline, so baseline/candidate quotas are 75%/25%.
- Gate: gain in at least two structural families; loss/false/extra, callback
  mismatch, insurance mismatch, and variable/residual permutation,
  rotation/scale metamorphic failures all zero.

This is generated-only disposable code.  No compiler, solver framework, real
adapter, benchmark, scorer, HP/CAS, validation, or sealed data is used.

## Frozen result

The first prospective run passed without repair:

- 168 total cases, including 48 positives;
- positive gains by family: curved circle `12`, disconnected ovals `12`,
  scaled space curve `12`, nonpolynomial sheet `0`;
- aggregate gain/loss/false/extra: `36/0/0/0`;
- activation `96`, ED queries `218`, moved-slice intersections `144`;
- callback mismatch `0`, 75%-insurance mismatch `0`;
- variable/residual permutation, affine rotation and scale metamorphic:
  `16/16` passed;
- isolated and opaque counters failed closed; opaque lane was byte-identical
  to baseline apart from its status label.

This passes D0 because three unrelated positive-dimensional structures gain
with no safety/work regression.  Freeze these bytes for independent review
and a new prospective breadth panel.  The nonpolynomial family had no gain,
so no real/shared connection is authorized by this result alone.
