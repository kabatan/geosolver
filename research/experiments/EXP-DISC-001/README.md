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
The original card and both amendments form one preregistration bundle; later
artifacts must record all three hashes.

The amendment was written after a small non-gating six-instance diagnostic.
That diagnostic is deliberately excluded from development and locked inputs,
does not set a threshold, and cannot support promotion or rejection. Formal
inputs, proposal traces and local outcomes must be generated and frozen in a
later commit before the experiment is run.

The A2 audit inspected committed source and primary or official documentation
only. No EXP-DISC-001 proposal matrix, formal input or outcome existed or was
inspected while its choices were written.
