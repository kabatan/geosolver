# EXP-DISC-001 amendments

The original experiment card remains the preregistered source for discovery
candidate selection. `current-policy-amendment.json` adds the production H0
coordinator and its Halton source as mandatory controls. This prevents an
experiment over new algorithms from silently forgetting the solver behavior it
would replace.

`qmc-prefix-amendment.json` records the preimplementation audit of that control
and of the randomized-QMC and soft-ordering candidates. It fixes the exact
single-128-column prefix construction, separates Owen and Matousek scrambling,
limits IID capture claims to their stated independence model, and makes
deferred-launch liveness auditable at action, launch and completion boundaries.
It also preserves the current refinement-exhaustion behavior as an exact H0
control while requiring a nonblocking research counterfactual and dedicated
counterexample family; that counterfactual cannot directly change production.
`local-champion-dependency-amendment.json` (A3) prospectively replaces only the
now-impossible instruction to freeze an EXP-LOCAL-001 champion. EXP-LOCAL-001
closed without a formal result or product selection. A3 therefore requires a
current-core chain: terminally decide EXP-LOCAL-003 and freeze its locked-pass
scaling policy or explicit `L0-SEMANTIC`; preregister and run the separate
native-globalization study EXP-LOCAL-004 with that frozen policy; then create an
outcome-bound local-champion freeze record. A rejected, inconclusive, protocol-
failed or infrastructure-failed study falls back explicitly to the current
production `L0-SEMANTIC` pipeline, never to a non-gating pilot or a
development-only winner.

The original card and all three amendments form one preregistration bundle.
No EXP-DISC-001 candidate input, assessor input or proposal matrix may be
materialized until the champion freeze record exists. Every downstream
artifact must record the original, A1, A2, A3 and champion-record hashes plus
the exact selected local-solver source and canonical-options hashes.

The amendment was written after a small non-gating six-instance diagnostic.
That diagnostic is deliberately excluded from development and locked inputs,
does not set a threshold, and cannot support promotion or rejection. Formal
inputs, proposal traces and local outcomes must be generated and frozen in a
later commit before the experiment is run.

The A2 audit inspected committed source and primary or official documentation
only. A3 inspected the terminal EXP-LOCAL-001 governance record and the
preregistered EXP-LOCAL-003 card as upstream dependency evidence. No
EXP-DISC-001 proposal matrix, formal input or outcome existed or was inspected
while either amendment's choices were written. A3 preserves every discovery
method, threshold, budget, control and gate from the original card, A1 and A2,
and has no product connection.
