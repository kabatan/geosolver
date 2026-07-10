# EXP-DEF-001

This experiment tests archive-coupled deflated Gauss-Newton as a small local
search lane layered on the existing multistart solver. It does not replace the
geometry DSL, canonical oracle, ordinary LM-QR lane, CandidateStore, evidence
log or final validator.

The card and ordinary-control source hashes are frozen in
`preregistration-lock.json` before formal input materialization. The already
inspected `EXP-LOCAL-002` close-root cases are excluded from every gate: they
may explain why this experiment exists, but they may not tune it or support a
decision.

The next research commits must occur in this order:

1. freeze a byte-for-byte snapshot of the card and current LM-QR control;
2. implement the research-only step rule and differential/adversarial tests;
3. generate and checksum development inputs without executing a variant;
4. run the mechanism and empty-archive sequential stages;
5. either record a bounded negative result or freeze one candidate before
   generating any family-disjoint locked input.

The corrected formal retry completed and the frozen independent analyzer
recorded `bounded-negative-stop-before-locked`. Neither candidate advanced or
qualified for the one allowed retune. `EVID-19` and `NEG-013` bind that result;
the detailed artifacts are indexed under `research/results/EXP-DEF-001/`.
Locked inputs were neither materialized nor opened, and no production dependency
or public policy changed.
