# BARYCENTRIC_AREA_QUOTIENT_EXACT_WITNESS_V1

## Mechanism

For a two-coordinate source whose raw target contains `Area(...)`, the
candidate finds exactly one direct free construction `Q = Point(x,y)` (the
coordinate names may be swapped) and three source-constant exact Point
anchors forming a nondegenerate simplex.  At a saved endpoint it computes the
three signed-area quotients

`[QBC]/[ABC]`, `[AQC]/[ABC]`, and `1-alpha-beta`.

Bounded continued-fraction convergents propose exact rational barycentric
weights.  Every combination reconstructs Q by the exact affine identity
`Q = alpha*A + beta*B + gamma*C`; no absolute-coordinate PSLQ is used.  The
complete raw coordinate assignment then replays the untouched construction,
constraints, bounds, guards, and raw Area target in the independent exact
prototype.  A failed replay emits nothing.

This prototype reads the raw target only for its Area operation/dependency
structure (to identify the participating free Point) and for final replay; it
does not read a numeric target value for routing or pruning.  It receives no
ID, family, truth, score, expected target, or previous outcome.  Translation
and uniform scale change the raw coordinates but leave the barycentric
proposal signature invariant.

## Safety and fallback

The exact prototype replay is a mechanism test, not canonical authority.
Every result retains `authority_pass=false`, `target_release=false`, and no
target-set completeness claim.  Any later descriptor must pass the existing
untouched canonical source/raw-target authority boundary.  The prejoin returns
the exact untouched baseline object by identity for every non-applicable or
exceptional path.

Current caps are two direct coordinate variables, one direct free Area point,
12 exact anchors, 32 nondegenerate 2D simplexes, denominator 10,000, four CF
candidates per independent quotient, 64 proposals, 65,536 source bytes, and
2,048 source AST nodes.  All nondegenerate simplexes within the caps are
retained; unsupported DSL or symbolic uncertainty fails closed.

## Gates

The frozen prevalence gate passed: 43 sources across four signatures and 7
endpoint activations across all four signatures, versus fixed gates 6/2/4.
The CPU14 D0 gate passed on 2026-07-31: pytest was 7/7, and the generated
panel had 3/3 activation plus 3/3 full exact-prototype replay, invariant
translation/scale signatures, wrong-endpoint fallback, and zero authority or
release.  This is only a generated mechanism result.  No endpoint census or
formal/full replay run has been performed.

The later fixed real gate remains full-replay pure gain on at least two
independent signatures with zero false/extra/invalid results; otherwise STOP.
