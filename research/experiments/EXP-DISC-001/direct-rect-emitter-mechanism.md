# DIRECT rectangle emitter — mechanism note

Status: experiment-local implementation, pre-corpus and non-production
Source: `src/direct_rect_emitter.jl`
Test: `test/direct_rect_emitter.jl`

## Frozen interface and evidence boundary

`emit_points(screen!, lower, upper; arm)` returns only requested proposal points and
truth-free accounting. `screen!` receives a physical point and returns a typed
`ScreeningObservation(scaled_residual, canonical_valid)`. The implementation never
sees a case/family/plugin name, target identity, Gold data, known root, external
success flag, or local-solver answer.

The stable row-permutation-invariant residual norm is mapped to the frozen bounded
score

```text
rho <= 1 : phi = rho / (1 + rho)
rho >  1 : phi = 1 - 1 / (1 + rho)
invalid  : phi = 1
```

The large-`rho` branch is evaluated through `1/rho`, so a finite valid residual is
kept below one even when its mathematical norm would overflow Float64. `phi` is
proposal evidence only.

## Shared ternary-center geometry

Both arms use the same normalized cube `[-1,1]^d`, ternary center coordinates, and
original DIRECT center stencil. Guided rectangle splitting evaluates both centers at
`c +/- 2*3^(-(depth+1))*e_i` for every longest dimension. Earlier dimensions in the
division order produce the larger side rectangles of the standard sequential DIRECT
partition.

- `DIRECT_RECT_EMIT` selects potentially optimal rectangles by the original global
  lower-envelope test over center score and half-diagonal, with fixed
  `epsilon=1e-4`. Pair minima determine the within-rectangle division order.
- `RECT_ORBIT_BREADTH` is the score-blind geometry control. After center and the
  level-1/support-1 axis orbit, it visits complete hyperoctahedral ternary orbits in
  `(level, support-size)` breadth order: level 1 uses `k=2..d`; every later level uses
  `k=1..d`. An orbit has coordinates `+/-2*3^(-level)` on exactly `k` axes and zero on
  the others, hence cardinality `2^k*C(d,k)`. An orbit too large for the remaining
  geometry cap is skipped; service continues at the next level's smaller `k=1` orbit.
  The final remainder is center-filled. It never reads `phi`.

The control name and construction are a pre-outcome amendment to the earlier
`RECT_BREADTH_FIRST` note. Independent audit found that selecting one member of an
exact largest-rectangle FIFO tie is not signed-permutation covariant. Renaming the wire
arm makes clear that the corrected control is symmetric orbit breadth, not a standard
single-partition FIFO implementation.

### Exact symmetry-tie fallback

A standard sequential DIRECT partition has no representation-invariant way to choose
one coordinate when its state-changing score/geometry key is exactly tied. Coordinate
FIFO makes a flat cube change its proposal set after a signed permutation. The guided
adapter therefore differs from standard DIRECT at that precise break condition:

- a tied pair-minimum division order or tied potentially-optimal geometry/score key
  changes no rectangle state;
- it switches to the same complete `(level, support-size)` orbit-breadth schedule as
  the control; the already serviced initial axis orbit is not repeated;
- any remainder is filled by charged center re-observations.

Every orbit point and center duplicate is retained. Numerically unique guided choices
continue through the original global DIRECT mechanism. Orbit breadth remains
score-blind.
Diagnostics expose whether this fallback occurred, the number of complete orbits, and
the number of center fills. The fallback is capability/numerics based and sees no
case identity or outcome.

The screen cap is exactly 48. A split starts only when its whole `2m` longest-axis
stencil fits callbacks 1–47; a coordinate-prefix stencil is never requested. Any
remaining callbacks are center re-observations. With a tie, the same even-cap closure
may require several center observations after the last whole orbit. This wrapper never
cuts a signed-permutation stencil/orbit and never uses a fill observation to change
rectangle selection.

## Applicability and accounting

The emitter is applicable only when all bounds are finite and nondegenerate, the
existing `8eps(Float64)` normalization-resolution gate passes, and
`1 + 2d <= 48`. Otherwise it returns a typed inapplicable result and performs zero
callbacks.

For an applicable call:

- exactly 48 screening callbacks and 48 proposal records are produced;
- invalid, nonfinite, throwing, malformed, and duplicate evaluations remain records;
- every record is returned for later frozen-local-solver service;
- hard discard, deduplication, configuration merge, answer acceptance, and
  completeness inference are absent;
- external-result use and external workers are absent (this is a native pure-Julia
  comparator, not a SciPy wrapper).

The unit fixtures cover cap/inapplicability, row permutations, signed coordinate
permutations crossed with flat/invalid ties in dimensions 2–12, a late exact tie,
deterministic score ties, a positive-residual plateau, an invalid moat, a thin rotated
basin, orbit coverage in dimensions 2/4/8, callback failures, duplicates, and
all-request service. These fixtures establish implementation contracts only; they are
not efficacy outcomes.

## Transfer boundary

The 1993 DIRECT potentially-optimal-rectangle mechanism is implemented, but its
Lipschitz/global-optimization conclusions are not transferred to guarded,
branch-discontinuous, invalid, or multi-root GeoTarget problems. Orthogonal axis
dependence, target recovery, callback-work benefit against orbit breadth and D0, and
unrelated-family generalization remain empirical kill gates for a later authorized
experiment.

Frequent exact ties are an explicit mechanism break condition: the invariant fallback
can spend much of a 48-callback screen on center fills, especially in higher dimension.
If equal-work experiments show that this loses useful breadth or makes DIRECT unable
to beat its geometry control and D0, Candidate A is rejected rather than adding a
case-specific tie rule.
