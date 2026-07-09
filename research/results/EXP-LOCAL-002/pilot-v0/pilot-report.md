# EXP-LOCAL-002 non-gating pilot

This pilot checks adapters and records observations only. It does not evaluate the preregistered promotion gate.

| Variant | Gold-valid / attempts | Full-target instances | False candidates | Callback calls | Median warm (s) | Cold first attempt (s) |
|---|---:|---:|---:|---:|---:|---:|
| NLS-LM | 53 / 64 | 7 / 8 | 11 | 11642 | 0.0001262 | 4.8336 |
| NLS-TR | 59 / 64 | 7 / 8 | 5 | 7142 | 3.75e-5 | 1.3195 |
| NLS-RMN | 59 / 64 | 7 / 8 | 5 | 7142 | 4.46e-5 | 2.4432 |
| NLS-TR-STRICT | 59 / 64 | 7 / 8 | 5 | 7251 | 1.97e-5 | 6.42e-5 |
| LXR-LMQR | 43 / 64 | 6 / 8 | 13 | 20569 | 0.0006343 | 0.053435 |

## Fixed protocol

- Eight checksum-pinned starts for each of eight representative families, including S4 and S6.
- Bounds-midpoint/half-range variable normalization and declared residual scales for every variant.
- `NonlinearLeastSquaresProblem` receives explicit normalized `lb` and `ub`.
- All external routes use `AutoFiniteDiff(fdtype=Val(:central))`; no analytic or silent fallback route is attached.
- Acceptance ignores package retcodes and independently checks scaled residual, bounds, the S4 strict guard, normalized Gold configuration distance, and target error.

## Fairness limits

- Package load/compile is measured once for the fresh process.
- Each variant's first attempt is marked cold, but variants run sequentially and may share compiled infrastructure; cold comparisons are exploratory.
- solver_nf has implementation-specific semantics; callback_residual_calls is the comparable primal callback count.
- All external candidates use the preregistered explicit central AutoFiniteDiff route; no analytic-Jacobian lower-bound control is included in this pilot.

Environment, exact package versions, card/environment checksums, replay checksums, and per-attempt records are in `summary.json`, `environment.json`, `attempts.json`, and `attempts.csv`.
