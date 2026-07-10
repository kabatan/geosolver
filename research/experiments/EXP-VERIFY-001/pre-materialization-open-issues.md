# EXP-VERIFY-001 pre-materialization blockers and counterexamples

This file records definitions that are deliberately unresolved at the
source-scaffold checkpoint. None may be chosen after looking at a V1 outcome.

## Must be frozen before one-shot materialization

1. Exact analytic fixture formulas, independent Gold formulas, and VREF
   formulas. Candidate fixtures and the assessor must not call one another.
2. The canonical textual center, exact lower/upper endpoint, and paired
   binary64 point-endpoint recipe for every coordinate. The regular allocation
   and radius levels are fixed, but endpoint material has not been generated.
3. The exact canonical spelling for the subnormal-neighborhood control and the
   reduced large-rational numerator/denominator. Decimal tokens must satisfy
   the current canonical `ProtocolDecimal.text` grammar and 4096-byte bound.
4. Pinned IntervalArithmetic and IntervalRootFinding versions, Julia version,
   rounding configuration, guarantee/decorations API, and backend environment
   lock. No dependency is present in this checkpoint.
5. The research-only explicit validated-callback calling convention for scalar
   and plugin-owned opaque values, and the independently declared interval
   Jacobian path. The product `OperatorKernel` ABI remains unchanged.
6. Content-locked fixture source, operation/type/selector declarations, plugin
   IDs, and graph documents. Semantic descriptor IDs in this scaffold must not
   appear in candidate manifests.
7. The one-shot materializer, independent assessor materializer, external
   safety-instruction executor, atomic output layout, and canonical checksum
   format. They must bind this source lock and refuse pre-existing outputs.
8. Exact proof-input handling for reduced rationals and binary-pre-rounded
   negatives. Binary provenance must be rejected before interval construction,
   even if the backend can soundly enclose that different binary number.
9. Stable whole-box `Choice`/`Select` evidence: validity margin, selector
   margin, and one branch key must be represented without point midpoint
   selection.
10. Independent artifact schema and replay algorithm. Artifact encoding,
    Krawczyk data, and replay code are mechanism work and therefore forbidden
    until inputs freeze.

## Mandatory counterexamples already allocated

- An opaque plugin with no C3V callback.
- An opaque plugin that declares C3V only through the current
  `generic_numeric=true` fallback and has `validated=nothing`.
- Exact decimal intent reconstructed from a pre-rounded binary64 value.
- A point-valid midpoint whose full box touches or crosses a domain, strict
  guard, or branch boundary.
- Zero residual at double/cubic roots and along constant- or varying-target
  manifolds.
- Non-guaranteed, trivial, and ill-formed interval states.
- Tampering with the box, plugin lock, interval Jacobian, Krawczyk image, or
  configuration hash after an otherwise replayable artifact is produced.

## Stop conditions before materialization

Materialization must stop, without partial output, if any required hash is
different, an exact token is noncanonical, a content lock is missing, candidate
and assessor projections share a destination or checksum, any output already
exists, or any validated interpreter, Krawczyk candidate, artifact encoder, or
replay verifier source already exists.
