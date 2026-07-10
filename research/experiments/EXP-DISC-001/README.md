# EXP-DISC-001 amendments

The original experiment card remains the preregistered source for discovery
candidate selection. `current-policy-amendment.json` adds the production H0
coordinator and its Halton source as mandatory controls. This prevents an
experiment over new algorithms from silently forgetting the solver behavior it
would replace.

The amendment was written after a small non-gating six-instance diagnostic.
That diagnostic is deliberately excluded from development and locked inputs,
does not set a threshold, and cannot support promotion or rejection. Formal
inputs, proposal traces and local outcomes must be generated and frozen in a
later commit before the experiment is run.
