# Guard-boundary conormal sampling D0

## Hypothesis and mechanism

For a positive-dimensional source stratum `F(x)=0` clipped by a supported
strict source guard `g(x)>0`, ordinary local starts can repeatedly land on one
feasible connected component.  This side lane replaces only ordinal `3 mod 4`.
It chooses the nearest supported strict guard using normalized source-only
margins, shifts to the interior parallel surface `g/||Dg||=0.02`, and solves

`F(x)=0`, `g(x)=epsilon`, and
`Proj_T(x-q)=0`,

where `T` is the tangent space orthogonal to the row space of `[DF; Dg]` and
`q` is a reflected full-support insurance anchor.  These are the numerical
conormal/KKT equations for a distance-critical point on the interior guard
slice.  The exact forbidden boundary `g=0` is never proposed.  Every returned
endpoint remains only a warm candidate and must pass the caller's untouched
source/strict-guard replay.

The candidate receives residuals/Jacobians, supported strict-guard signed
margins/gradients, anonymous chart/bounds, start bytes, and callback state.  It
does not receive case/family identity, target, truth, target count, or prior
outcome.  Unsupported guards, missing guard rows, nonfinite observations,
full-rank/isolated source points, and failure to reach a source anchor all fall
back without emitting a conormal endpoint.  Three of four lanes are exact
baseline insurance.

## Prior overlap and research basis

The nearest archived mechanism, `guard_boundary_deflation`, classifies
uncertain boundary endpoints and repels later starts from HP-rejected equality
basins.  It does not solve an active-guard conormal/KKT critical system.  The
explicit guard-wall candidates alter scheduling around guard proposals; they
also do not sample distance-critical points of `F=0, g=epsilon`.  This is
therefore a distinct mathematical mechanism, not a radius/chart repair.

The construction follows the critical-point method for sampling real
semi-algebraic components (Harris, Hauenstein, and Szanto, *Smooth Points on
Semi-algebraic Sets*, arXiv:2002.04707) and the ED/conormal formulation of
distance-critical points (Draisma et al., *The Euclidean distance degree of an
algebraic variety*, arXiv:1309.0049).  This disposable D0 uses finite-difference
Gauss--Newton on the projected conormal equations; it builds no polynomial
compiler, symbolic backend, or common framework.

## Frozen generated D0

The prospective panel contains three disconnected semi-algebraic structures:
twin circles clipped by a strict ball, Cassini ovals clipped by a strict ball,
and the two branches of a hyperbola clipped by a strict ball.  Each has eight
positive seeds, eight inconsistent negatives, and eight strict-guard near
misses that exclude the reflected component.  Both arms receive four starts
and 44 callbacks per lane; ordinals 0--2 must be byte-identical.

The first run produced 72 cases, 24 positives, aggregate `+24/-0`, and
false/extra `0`.  Each positive family gained eight.  Candidate activation was
48 with 48 conormal queries; callback and 75% insurance mismatches were zero.
Five tests additionally cover signed variable permutation plus affine scale,
residual-row permutation, unsupported-guard fallback, inconsistent systems,
and strict-boundary near misses; all passed.

This authorizes prospective breadth and a thin source-only adapter audit only.
It does not authorize truth/scorer access, validation/sealed evaluation,
symbolic infrastructure, or production integration.
