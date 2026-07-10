# EXP-LOCAL-002 development result

Development-only execution: 48 frozen instances × 32 paired starts × five variants. Locked validation and promotion were not performed.

## Prefix-32 overall

| Variant | P_local_gold | P_full_target | Residual-qualified non-Gold | Budget exhausted | Charged work | Warm wall (s) |
|---|---:|---:|---:|---:|---:|---:|
| NLS-LM | 0.8854 | 0.8750 | 131 | 36 | 493424 | 0.7839 |
| NLS-TR | 0.9206 | 0.8958 | 82 | 35 | 343469 | 0.3444 |
| NLS-RMN | 0.9206 | 0.8958 | 82 | 38 | 346387 | 1.8100 |
| NLS-TR-STRICT | 0.9219 | 0.8958 | 82 | 36 | 356176 | 0.3786 |
| LXR-LMQR | 0.7956 | 0.8125 | 134 | 173 | 534029 | 3.4076 |

## Mechanical development decisions

- RMN kill gate: **True**.
- Strict threshold has no measured advantage: **False**.
- Next locked-validation freeze candidate: **none**.
- Promotion/product dependency decision: **not evaluated**.

## Confidence semantics

Paired effects use the repository's equal-family-weighted clustered bootstrap. `lower_95` is the preregistered one-sided 95% percentile bound; `upper_95` is the mirrored one-sided bound using the same persisted resample plan. Starts and instances are paired before family averaging; there is no within-family resampling.

## Cold protocol

Each variant ran in a separate fresh Julia process. The process measured package/module load, then one identical ScaleLadder cold solve, then one unmeasured warm-up per family before all 1,536 measured attempts. The full harness is identical across variants; therefore the LXR cold number conservatively includes loading the research environment containing NonlinearSolve.

Raw attempts are stored as deterministic-header `attempts.csv.gz`; input, start, replay, worker, bootstrap-plan, and result checksums are persisted alongside this report.
