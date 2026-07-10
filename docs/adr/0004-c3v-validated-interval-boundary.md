# ADR-0004: C3V is an explicit validated-box capability

Status: Accepted  
Date: 2026-07-10

## Context

`C3V` exists in the capability vocabulary, but the current evaluator still
interprets every result as a point `OracleObservation`. That path asks scalar
questions such as `isfinite(x)`, `x < lower`, and `margin > 0`; those questions
do not establish validity over an interval box. Re-evaluating a point in
`BigFloat`, inflating a floating-point value, or accepting a package success
flag is not a validated existence or uniqueness proof.

The interval path must retain the open-world plugin graph. Requiring polynomial
lowering would discard the main DSL advantage: arbitrary content-locked plugin
calls, custom intermediate types, guarded domains, and stable branch choices.

## Decision

1. C3V evaluates a **box**, never a point disguised as a box. Core will expose
   one capability-neutral raw graph execution path. Point observations and
   validated-box observations interpret that raw trace separately; neither
   calls the other or silently falls back.
2. A future core-ABI revision will require an explicit `validated` callback for
   every C3V kernel. `generic_numeric=true` alone will no longer manufacture a
   C3V claim. A plugin may deliberately reuse generic code by registering it as
   its validated callback, but that is then an explicit, content-locked promise
   that it supports the validated numeric and differentiation types.
3. The optional `GeoTargetValidated` package will own the interval backend and
   Krawczyk implementation. `GeoTargetBase` and the JSON graph remain free of a
   concrete interval package. The first backend candidate is
   [IntervalArithmetic.jl](https://juliaintervals.github.io/IntervalArithmetic.jl/stable/),
   whose current documentation describes outward enclosures and IEEE 1788-2015
   conformance; dependency selection remains subject to a frozen experiment.
4. Box endpoints enter from exact rational or decimal text and are rounded
   outward. Binary literals such as `interval(0.1)` cannot stand for the exact
   real decimal `0.1`; the backend's guarantee flag and decorations are part of
   the evidence and are checked, not discarded.
5. Every executed relation, target, guard, domain, branch, and selector path
   must have C3V. A bounded proof box must remain wholly within one valid,
   continuous domain and one stable branch chart. An interval touching a strict
   guard, crossing a domain boundary, selecting more than one branch, carrying
   a non-guaranteed enclosure, or degrading below the frozen safe decoration
   returns typed unknown.
6. The interval residual and interval Jacobian are independent evidence
   objects. The Jacobian may come from a separately declared validated
   derivative or from an explicitly supported interval/forward-mode path; C2
   finite differences never become a derivative enclosure.
7. Krawczyk is a **local configuration verifier**. It may prove that exactly one
   nonsingular root lies in a candidate box. Failure, a singular preconditioner,
   or an inconclusive inclusion is unknown; it neither rejects the numerical
   witness nor proves global completeness. The public configuration certificate
   is emitted only after independent canonical point replay also succeeds.
8. Configuration and target assurance remain separate. Evaluating the target
   over a certified root box may produce a validated target interval, but it is
   not an algebraic identity certificate and cannot create an exact answer.
9. A replay artifact binds the problem, graph, plugin locks, selected branch
   chart, exact input box, interval residual/Jacobian enclosures, preconditioner,
   Krawczyk image, inclusion decision, backend version/configuration, and output
   configuration hash. A separate verifier recomputes the inclusion; serialized
   floating-point fields alone are not trusted.

## Initial experiment boundary

The first experiment is local and candidate-seeded. It compares point replay
with a C3V Krawczyk verifier on regular square systems, while including domain,
guard, branch-crossing, singular-root, feasible-manifold, false-C3V, exact-input
construction, and malformed-artifact controls. It must demonstrate zero false
certificates and deterministic independent replay before any product route is
connected. Whole-domain interval branch-and-bound and interval-based all-root
completeness are later, separate mechanisms.

## Consequences

- Existing C0/C2 plugins remain expressive and usable; they simply report C3V
  unavailable.
- Custom geometric objects remain legal when their content-locked plugin
  callbacks support the validated scalar path.
- Branch and domain uncertainty stays visible instead of being hidden by a
  midpoint choice.
- The validated package is optional for discovery, so rigorous verification
  cost is paid only for candidates routed to it.
- The current point evaluator cannot issue a validated certificate. Any direct
  `C3V` point-kernel diagnostic remains provisional and must not be interpreted
  as validated success until this boundary is implemented and gated.
