# OPERATOR_GRAPH_DIVIDE_CONCUR_V1

## Hypothesis and scope

A source-fixed closed projector graph may supply useful proposals to the frozen
canonical solver after 64 Difference-Map iterations (`beta=1`).  This arm only
implements the conservative source gate, anonymous recurrence gate, and
proposal-only 75/25 connector seam.  It does not claim a solver implementation
or performance evidence.

## Gate and safety

- Accepted projector vocabulary is deliberately small: scalar `EQ`/`PIN`,
  fixed-segment incidence, point/fixed-line and point/fixed-circle incidence,
  direct-parameter fixed line/circle graphs, explicit `sin(2*pi*t)` /
  `cos(2*pi*t)` graphs, and explicitly sheet-selected fixed line-circle
  intersections.
- Composite coordinates, moving or opaque geometry, ambiguous intersections,
  tangency, tied coordinates/bounds, zero radius, strict or opaque guards, and
  infinite/oversized sheet sets make the entire attempt `UNKNOWN` and return it
  to the baseline.
- Static admission requires 3..16 closed factors, incidence <=64, arity <=4,
  shared variable degree >=2, graph cycle rank >=1, at least two projector
  kinds, sheet product <=8, and typed inverse/collapse for every factor.
- Activation additionally requires at least four eligible source attempts and
  two anonymous structural hashes.  The gate sees no case ID, family, target,
  answer, truth, or prior result.
- Only every fourth start can enter the side route.  Any side result is a
  proposal without authority; canonical LM and exact source/guard/branch/raw
  target replay remain mandatory.

## Current disposition

Generated seam tests pass 9/9 on CPU14.  No development, formal, scorer, truth,
validation, sealed, or 98-case artifact was accessed.  The real recurrence
gate is therefore unevaluated in this lane, and no worker binding is installed.
Root may run `source_gate.py` and `aggregate_scans.py` under dataset custody.  If
the real gate fails, this candidate remains `HOLD`; if it passes, the separate
synthetic D0 owner may bind only the predeclared one-quarter proposal hook.

## Reopen condition

After a real gate failure, reopen only with evidence that a rejected source
construct has an exact source-fixed closed projector, typed inverse/collapse,
and finite unambiguous sheet accounting.  Threshold, radius, seed, or case
specific routing is not a reopen condition.
