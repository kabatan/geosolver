# EXP-SINGULAR-001 result index

- `baseline-audit-v0.json`: pre-experiment implementation and P1 audit.
- `development-s0-s1-v0/`: frozen 72-instance S0/S1 development execution.
- `development-s2-v0/`: frozen 24-instance S2 development execution and independent recomputation.

The S0/S1 development advancement gate passed, so the next research route is
`S2-AP-CPQR-SUBSET`. This is not locked validation and `product_connected` is
false. The point-replay-only control is recorded as reproduced negative result
`NEG-006`.

The S2 development advancement gate also passed, so the next research route is
`S3-AP-BROYDEN`. S2 remains product-disconnected and unlocked: the observed
gain applies only to target-constant rank-deficient manifolds, not isolated
multiple roots or general singular solving. This boundary is recorded as
`EVID-15` and `NEG-009`.
