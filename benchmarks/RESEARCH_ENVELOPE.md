# Benchmark Envelope and Generalization Levels

The machine-readable M0-M4 staging envelope is
[`manifests/m0-m4-tested-envelope.json`](manifests/m0-m4-tested-envelope.json).
It fixes the domain of the first three component experiments before results are
observed. It does **not** shrink the v1 product scope.

## M0-M4 primary envelope

- deterministic bounded real problems;
- 1-16 free variables, 1-64 residuals and 1-1024 construction nodes;
- one real scalar target;
- C0 Float64 required, C1 derivative optional;
- branch-free or selector-margin-separated execution;
- primary Gold roots at least 0.05 normalized units from artificial bounds.

The first experiments may report diagnostic results outside this envelope, but
those results cannot promote a component or support a product-completion claim.

## Generalization levels

Results are reported separately for:

- **U1 unseen instance:** new parameters from a known generator;
- **U2 unseen composition:** new graphs using known primitives;
- **U3 unseen family:** a held-out geometry/problem family;
- **U4 unseen plugin:** a plugin created after ABI/policy freeze; and
- **U5 out of envelope:** size, scale, cost or regularity beyond the frozen
  envelope.

Calling all five simply "unknown" would hide memorization and routing failures.

## Truth and partitions

Only analytic, validated-interval, restricted-exact or independently
cross-validated truth enters `P_full`. A long numerical union is
`reference_only` and can diagnose a miss but cannot label a solver correct.

Family grouping uses generator, construction template, constraint graph and
closely related primitive family. Opening a locked family to repair a failure
burns that set and moves it to development; a generator-disjoint replacement
is required.

The eight critical strata and the mandatory metamorphic transformations are
enumerated in the JSON envelope so experiment and benchmark tooling share one
definition.
