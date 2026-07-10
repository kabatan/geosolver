# EXP-SINGULAR-001 result index

- `baseline-audit-v0.json`: pre-experiment implementation and P1 audit.
- `development-s0-s1-v0/`: frozen 72-instance S0/S1 development execution.
- `development-s2-v0/`: frozen 24-instance S2 development execution and independent recomputation.
- `development-s3-v0/`: frozen 30-instance S3 development execution and independent recomputation.
- `development-s4-v0/`: frozen 36-instance S4 execution, checkpoint replay,
  exact independent closure and bounded-negative claim boundary.

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

The S4 development gate also failed before locked validation. The black-box
finite-difference candidate and independent analytic control made identical
decisions and each recovered 11/15 eligible endpoints with zero S4 false
promotions, but both failed the orthogonal representation in the same four
groups while promoting the other two equivalent representations. Exact
analysis also found that Float64 Gold/assessment could not support four S1
coverage claims; this does not change the S4 recall/metamorphic failure. The
authoritative closure is `development-s4-v0/independent-analysis.json` plus
its A11 archival binding. S4 remains product-disconnected and is recorded as
`EVID-20` / `NEG-014`.
