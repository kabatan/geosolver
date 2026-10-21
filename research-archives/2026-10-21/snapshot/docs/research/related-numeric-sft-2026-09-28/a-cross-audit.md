# Agent A: PN06–PN10 generator independent read-only audit

2026-09-28. Reviewed `generate_b.py` against the source questions in `proof-related-numeric-pack-2026-09-28/numeric_problems.md` and the generated `b-cases.jsonl`. No blocking discrepancy found. I did not edit Agent B's files.

| Pack / source | Original construction and branch | Label oracle |
|---|---|---|
| PN06 / DA07 | Acute scalene ABC; circumcenter O, orthocenter H; M and N from the specified diameter-circle intersections; X and Y from the second line-circle intersections. The A–M–X order is checked by a positive directed dot product. | `abs(X-Y)` from constructed X,Y. Similarity identity only in `checks`. |
| PN07 / DA08 | Q is constructed antipodal to O on circle BOC; M uses CQ and the parallel through A; `N=A+C-M` enforces the ANCM parallelogram; T is the specified line intersection. | `abs(O-T)`. Pythagorean identity only in `checks`. |
| PN08 / DA11 | I,J,K are the stated midpoints; tangent circles use I and J as contact points; T is their second intersection. | Radius from the independently constructed circle ABT. `R*AB/BC` only in `checks`. |
| PN09 / DB02 | P and Q come from the specified angle rotations and are checked to lie inside BC; M,N are the doubled ray points; X is BM∩CN. | `abs(B-X)`. Circumcircle and chord-ratio identities only in `checks`. |
| PN10 / DB12 | The two exact 1:2 and 2:1 division points, specified parallel-line intersections, and two circles determine X; interior membership is checked. | `abs(A-X)`. The target relation to `BX+CX` and BC only in `checks`. |

Every English prompt retains the source query, geometric assumptions, and listed numeric givens. The printed givens and targets use `.17g`, and no coordinates, theorem names, hidden relations, or solution text enter `problem_en`. The target in every case is calculated from constructed geometry before the separate `solution_identity` check.

The 60 saved rows contain 12 distinct normalized side-ratio signatures per type. Re-running `generate(seed=20260928, per_type=12)` succeeded with maximum recorded relative audit residual `7.23e-14`; each saved target is positive and finite. The source's generic final sentence about nondegenerate circles is omitted from these English prompts, but the generator checks distinct named points, successful circle intersections, and the required branch for the sampled instances. This is a wording difference, not a numeric or construction defect.
