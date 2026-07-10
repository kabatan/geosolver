# EXP-LOCAL-002 diagnostic LM/TR routing development replay

This is the single preregistered tuning round. It does not access locked inputs or authorize production changes.

| Prefix | Variant | P_local_gold | P_full_target | Residual-qualified non-Gold | Fully charged work | Warm wall (s) |
|---:|---|---:|---:|---:|---:|---:|
| 8 | ROUTE-LMTR-A1 | 0.927083 | 0.833333 | 21 | 85394 | 0.958170 |
| 8 | NLS-TR | 0.919271 | 0.812500 | 21 | 86128 | 0.251241 |
| 8 | NLS-LM | 0.885417 | 0.833333 | 35 | 121178 | 0.143400 |
| 8 | LXR-LMQR | 0.791667 | 0.708333 | 31 | 139293 | 1.738442 |
| 16 | ROUTE-LMTR-A1 | 0.927083 | 0.895833 | 43 | 170266 | 1.003899 |
| 16 | NLS-TR | 0.917969 | 0.875000 | 43 | 172691 | 0.273602 |
| 16 | NLS-LM | 0.889323 | 0.875000 | 65 | 247478 | 0.513430 |
| 16 | LXR-LMQR | 0.792969 | 0.791667 | 66 | 270318 | 2.373414 |
| 32 | ROUTE-LMTR-A1 | 0.927083 | 0.916667 | 82 | 341500 | 1.043159 |
| 32 | NLS-TR | 0.920573 | 0.895833 | 82 | 343469 | 0.344391 |
| 32 | NLS-LM | 0.885417 | 0.875000 | 131 | 493424 | 0.783915 |
| 32 | LXR-LMQR | 0.795573 | 0.812500 | 134 | 534029 | 3.407594 |

## Preregistered decision

- Development freeze gate passed: **False**.
- Prefix-32 P_local_gold delta vs NLS-TR: **0.006510**.
- Fully charged work ratio vs NLS-TR: **0.994267**.
- LM selection fraction: **0.007161**.
- Locked inputs remain inaccessible unless every declared criterion passes.
