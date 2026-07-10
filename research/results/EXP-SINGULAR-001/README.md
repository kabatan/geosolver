# EXP-SINGULAR-001 result index

- `baseline-audit-v0.json`: pre-experiment implementation and P1 audit.
- `development-s0-s1-v0/`: frozen 72-instance S0/S1 development execution.
- `development-s2-v0/`: frozen 24-instance S2 development execution and independent recomputation.
- `development-s3-v0/`: frozen 30-instance S3 development execution and independent recomputation.

The S0/S1 development advancement gate passed, so the next research route is
`S2-AP-CPQR-SUBSET`. This is not locked validation and `product_connected` is
false. The point-replay-only control is recorded as reproduced negative result
`NEG-006`.

The S2 development advancement gate also passed, so the next research route is
`S3-AP-BROYDEN`. S2 remains product-disconnected and unlocked: the observed
gain applies only to target-constant rank-deficient manifolds, not isolated
multiple roots or general singular solving. This boundary is recorded as
`EVID-15` and `NEG-009`.

The S3 development gate failed without opening locked inputs. Both
`S3-AP-BROYDEN` and the independently coded analytic inverse-secant control
recovered 0/12 eligible isolated/coalesced singular endpoints because all
twelve reached the shared 64-iteration hard cap. They emitted typed unknown,
not evidence or answers, with zero false promotions. The frozen S1 baseline
also disagreed across the three equivalent `s3-fold-close` transforms (one
promotion, two unknowns). S3 remains product-disconnected and is rejected as
`EVID-18` / `NEG-012`; S4 requires a separate development gate.
