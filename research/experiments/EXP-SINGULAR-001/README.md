# EXP-SINGULAR-001 executable harness

This directory implements the preregistered fixed-endpoint experiment without
connecting a candidate to the product solver. Its implemented development
routes are:

- `S0-POINT-REPLAY`, a diagnostic-only C2 point replay;
- `S1-AP-LMQR`, dense BigFloat refinement with an analytic-Jacobian lower-bound
  control;
- `S2-AP-CPQR-SUBSET`, target-aware rank-deficient subset refinement;
- `S3-AP-BROYDEN`, restarted multiprecision good-Broyden with a separately
  coded analytic inverse-secant control;
- the fixed P1 near-null counterexample, regular/full-rank controls,
  nonroot/manifold controls and identity-free metamorphic transforms; and
- callback, precision-equivalent and wall/deadline accounting.

Gold truth is held by `GeneratedEndpoint`; candidate methods receive only a
`CandidateInput`, which contains an opaque oracle and a fixed endpoint.
`SemanticReplayEvidence` cannot create a promoted outcome. S1 promotion needs a
`NumericalRootEvidence`; S2 uses typed manifold evidence; S3 can only construct
`NumericalSingularRootEvidence` after stable rank/nullity routing, two
independent confirmations, canonical replay, a linear trace gate and covered
configuration/target errors. Every route shares endpoint-wide callback,
iteration, precision and wall budgets.

Run the harness tests with:

```powershell
julia --project=research/experiments/EXP-SINGULAR-001 `
  research/experiments/EXP-SINGULAR-001/test/runtests.jl
```

Each phase freezes and checksums its inputs before candidate outcomes. S3 failed
its development gate at the global 64-iteration cap and remains rejected and
product-disconnected. Locked S3 inputs were never materialized or opened.

`s4-preregistration.json` freezes a separate S4 gate before any S4 input or
candidate outcome exists. It replaces the generic bordered-nullspace label
with an explicit C2 range/nullspace two-step map and an independently
differentiated analytic control. Higher-depth singularities, manifolds,
nonroots and regular close roots are mandatory non-promotion controls. S4 is
still product-disconnected and has no locked inputs.
