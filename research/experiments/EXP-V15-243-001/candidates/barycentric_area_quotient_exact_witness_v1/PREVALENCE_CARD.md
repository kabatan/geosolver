# BARYCENTRIC_AREA_QUOTIENT_EXACT_WITNESS_V1 prevalence gate

This mechanism is not implemented unless a truth-blind aggregate scan finds:

- at least six development sources with an `Area(...)` site in the raw answer
  that can be exactified through barycentric area quotients;
- at least two distinct structural source signatures; and
- at least four sources where a saved endpoint activates a finite,
  nondegenerate area quotient that is numerically consistent with a bounded
  rational.

The signatures distinguish direct/composite and triangle/polygon Area targets.
The quotient is the proposed barycentric witness mechanism; the source need
not spell an explicit division.  The scanner reads no scorer,
truth, known target, prior outcome, or case/family routing feature.  It emits
aggregate counts only; paths, identifiers, expressions, endpoints, targets,
and individual records remain hidden.

Endpoint activation is not authority.  It is a conservative cheap prevalence
signal over Point, Midpoint, PointOnSegment, Centroid, Distance, Area, and
scalar arithmetic.  Unsupported construction primitives simply do not
activate.  Any implemented witness would still need exact coordinate/source
reconstruction and the untouched existing canonical source/raw-target replay.
The fixed later gate is pure gain on at least two independent signatures with
zero false/extra/invalid results; otherwise STOP.

## Frozen aggregate result

The first spelling-only scanner required an explicit `Area(...)/Area(...)` in
the source answer and returned zero, while an aggregate sanity check found 43
Area answers and zero explicit divisions.  That hypothesis was too narrow:
the quotient is the proposed barycentric witness, not necessarily source
syntax.  The corrected, fixed scanner counts Area target sites and uses saved
endpoints only for rational-area activation.

The corrected development145 scan passed every prevalence gate:

- 43 static sources versus the required 6;
- 4 structural signatures versus the required 2: composite polygon 6,
  composite triangle 11, direct polygon 11, and direct triangle 16;
- 7 endpoint rational-area activations versus the required 4, spanning all
  four signatures with counts 2, 1, 2, and 3 respectively.

The aggregate emitted no individual paths, IDs, expressions, endpoints, or
targets and did not read truth, score, or outcomes.  Authority and target
release remained false.  Scanner SHA-256 is
`0956eaefaa2bd0418f65bc862f11bbb98b709bb8e3ddb4f9158b7d47372e229c`;
the repository-external raw aggregate SHA-256 is
`911168181ee2891b7373c07d6e0a83e90c0a6fcd4b65d106ed0ae079a1269033`.

Decision: `GO_IMPLEMENTATION`.  This authorizes only a generated exact-witness
prototype.  It does not authorize formal execution or descriptor release.
