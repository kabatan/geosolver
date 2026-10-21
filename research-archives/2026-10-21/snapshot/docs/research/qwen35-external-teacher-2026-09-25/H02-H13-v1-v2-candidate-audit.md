# H02/H13 v1/v2 candidate audit

These four English teacher examples are drafts for H02/H13 v1/v2 rows that benchmark authoring metadata tags as shape augmentations. At the model-visible level, each keeps the same geometry template and changes only numerical givens; the generator parameters are not present in the prompts. Treat them as numeric counterfactual examples rather than model-visible shape conditioning. Their English prompt instructions come from the external-teacher template. Each answer preserves the audited general proof from `external-H02-v0` or `external-H13-v0`; only the numerical branch verification and final substitution are rebuilt for its own givens. Both source proofs were accepted in `audits.json` with numeric, relation, proof, use, and branch checks all true. This memo uses only the H02/H13 v1/v2 training rows and the audited v0 teachers; no evaluation records or outputs were consulted.

## H02

The general center formula is `Z(d)=(d,(t²+m²−2dx)/(2h))`, so `Z₁Z₂=|d₂−d₁|t/h`. For the benchmark coordinates, `m=BC/2`, `h=AK`, `t=AM`, `x=√(t²−h²)>0` because `BK>KC`, and `dᵢ=BDᵢ−m`.

| Variant | `m,h,t²,x` | Acute and scalene checks | `d₁,d₂` | `AC², AB²` | `s_U(d₁),s_U(d₂)` | `s_V(d₁),s_V(d₂)` | Independent center-distance arithmetic |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | `9,10,136,6` | `t²−m²=55`; `−m<x<m`; side squares `109,325,324` are distinct | `−4,−2` | `109,325` | `−125/109,−89/109` | `47/65,199/325` | `2·(2√34)/10=2√34/5` |
| v2 | `8,10,109,3` | `t²−m²=45`; `−m<x<m`; side squares `125,221,256` are distinct | `−2,2` | `125,221` | `−7/25,29/125` | `125/221,61/221` | `4·√109/10=2√109/5` |

For both variants the base vertex dot products are positive because `−m<x<m`, and the angle-A dot product is `t²−m²>0`. Each `dᵢ` is strictly between `−m` and `m`, so both D points are interior to BC and the defining circles are nondegenerate. The listed `s_U` and `s_V` values are all nonzero. Therefore neither second intersection is A; U and V lie on different sidelines, making A,U,V noncollinear and validating each circle center used in the general relation.

## H13

The audited relation is `CZ=BK/(2 sin C)`. Since `cos C=3/5` and C is acute, `sin C=4/5`. To verify the numerical branch independently, let `a=BC`, `Q=BK`, and `t=AC`. The angle gives `A=(a−3t/5,4t/5)`. The tangent formula and opposite-side condition `k=−Q` imply

`S−a² = 8a²t/(5Q) = t²−6at/5`,

so the unique positive solution is `t=6a/5+8a²/(5Q)`.

| Variant | `a,Q,t` | Coordinates and acute/scalene checks | Interior intersection J | Independent distance |
| --- | --- | --- | --- | --- |
| v1 | `7,49,10` | `A=(1,8)`, `K=(0,−49)`; side squares `65,49,100` are distinct; angle-A dot product `S−au=58>0`, with `0<u<a` | `M=(4,4)`; `J=(7/8,7/8)=(7/32)M=A+(1/8)(K−A)` | `49/(2·4/5)=245/8` |
| v2 | `8,256,10` | `A=(2,8)`, `K=(0,−256)`; side squares `68,64,100` are distinct; angle-A dot product `S−au=52>0`, with `0<u<a` | `M=(5,4)`; `J=(80/41,64/41)=(16/41)M=A+(1/41)(K−A)` | `256/(2·4/5)=160` |

In both rows `0<u<a` verifies the acute angles at B and C, and the listed positive `S−au` verifies angle A is acute. Both line-segment parameters for J are strictly between 0 and 1. Also `J_x>0` while B and K lie on `x=0`, so B,J,K are noncollinear and the circle center is well-defined. The tangent formula reproduces the stated negative k in each case, satisfying the required opposite-side branch.

The candidates are untrained drafts. These arithmetic and construction checks validate the examples, not transfer or model performance.
