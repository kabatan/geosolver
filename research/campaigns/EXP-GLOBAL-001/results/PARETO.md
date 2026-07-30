# S1/S2 provisional Pareto table

All wall ratios are candidate/control.  `—` means the arm was stopped before
that stage.  Invalid wrong-baseline measurements are excluded rather than
silently treated as losses.

| Arm | Valid formal evidence | Exact-set result | Wall GM | p95 ratio | Safety | Status |
|---|---:|---:|---:|---:|---:|---|
| frozen common control | S1 seed 0; S2 seed 0 | 16/24; 113/145 | 1.000 | 1.000 | 0 | Pareto anchor |
| adaptive progressive hybrid | S1 seeds 0–2; S2 seed 0 | 18/24, 18/24, 16/24; 116/145 | 0.958, 0.940, 0.930; **0.963** | 1.000, 0.994, 1.003 | 0 | **S2 survivor** |
| multi-target v4 union | S1 seed 0 | 16/24 | 1.007 | 0.995 | 0 | Dominated; zero side activation |
| rank chart v1 | S1 seeds 0–1 | 16/24, 14/24 | 1.003, 1.001 | 1.008, 1.001 | 0 | Rejected; recurring recall loss |
| incremental evaluator deadline v2 | S1 seed 0 | 14/24 | 1.138 | 1.100 | 0 | Dominated |
| BTF-polynomial v1 | S1 seed 0 | 15/24 | 1.004 | 1.011 | 0 | Dominated |
| clean `0967ff1c` transplant | Wave 0 seed 0 | 15/24 | 1.049 | 1.044 | 1 | Rejected; unsafe |

On the S2 seed-0 development145 evidence alone, the adaptive hybrid strictly
dominates the common control: +3 exact sets and 3.7% lower paired geometric
mean wall time.  The control nevertheless remains on the campaign front until
S3 because the candidate had one negative S1 seed (`-1`) and the S1/S2 runs did
not emit usable CPU measurements.  The long-run front will be recomputed from
five-seed ABBA wall/CPU, p95, completed-start, and exact-set evidence.

Unqualified but still open mechanisms are not placed on the formal front:

- rank trust-radius v2 passed generated S0 (`48/156` to `57/156`) but has not
  yet received a clean formal S1 measurement;
- structure-polynomial v2 has no valid formal measurement because its worker
  hash changed during the previous run;
- fixed progressive profiles and multi-target v1-v3 used the wrong baseline
  stack and are mechanism-invalid evidence.
