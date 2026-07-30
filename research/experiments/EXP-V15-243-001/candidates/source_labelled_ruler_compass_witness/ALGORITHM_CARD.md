# SOURCE_LABELLED_RULER_COMPASS_WITNESS — eligibility + D0

## Decision

**Generated D0: PASS. Real connector: HOLD.**

Mechanism hash: `890940e7b23df0d673f703ffbce5651487ea4b20379a274fedfa571019503485`.

This mechanism is the fail-safe continuation after the Gram Repair A emitter
gate stopped at 3/4 attempts. It constructs free points only as exact
intersections of two source-labelled lines/circles over exact anchors. It does
not infer missing distances from endpoint Float64 values and performs no PSLQ.

## Exact construction and containment

- Allowed steps are line-line, line-circle, and circle-circle intersections.
- Every locus must reference already constructed exact labels.
- Radical/QQBar intersection coordinates are solved exactly.
- Endpoint coordinates only sort branch trial order; changing the hints cannot
  change the exact branch set, accepted set, or target set.
- Every branch is replayed exactly through orientation guards, selector bits,
  and the raw invariant target.
- Total live branches are capped at 32; overflow fails closed with no partial
  certificate.
- Absolute-coordinate guards, bounds, raw scalar escapes, non-ruler-compass
  operations, near-zero orientation, empty intersection, or malformed selectors
  fail closed.

The independent verifier reconstructs the complete branch tree without using
the candidate ordering, compares the exact accepted realization set, and
replays the untouched source target set.

## Evidence

- truth-free real static subset: 3 attempts / 3 anonymous signatures, all
  circle-circle; this is insufficient for a real connector claim;
- generated circle-circle, line-circle, line-line: 3/3 authority and 3/3
  independent verification;
- reversed endpoint hints: 3/3 authority, invariant target sets;
- branch-cap overflow, near-zero orientation, operation escape: 0/3 false
  authorities;
- branch/target/coordinate certificate mutations are independently rejected;
- CPU15 unit tests: 5/5 pass.

The additive wrapper calls the baseline first. Baseline authority suppresses
the side route; otherwise baseline retains 80% and the side route at most 20%.
Failure or exception returns the exact baseline object.

No formal execute, scorer, full98, truth lookup, validation/sealed formulation,
or CPU other than CPU15 was used.
