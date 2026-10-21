# Independent audit: projection-bridge candidate

**The mathematics, prompt structure, leakage checks, hashes, and declared
exploratory token criterion pass.** I did not run a model/GPU or inspect LOO
outputs or condition scores. I independently checked the formulas and
branches, compared candidate rows against the frozen base, selected v0 source
rows and held-out answer key, and recounted tokens with the frozen tokenizer.

## Mathematics and proof branches

The review covered each distinct treatment proof, each full-task treatment
answer, and each integrated control answer. Repeated rotation copies use the
same text and mathematics.

- **H03:** With `M=(0,0)`, `B=(-m,0)`, `C=(m,0)`, `A=(x,y)`,
  `r^2=x^2+y^2`, and `b=CA,c=AB`, the bisector intercepts are
  `k=m(c-b)/(c+b)` and `l=m(c+b)/(c-b)`. The triangle being scalene makes the denominators
  nonzero, and `kl=m^2`. The circle through `A,(k,0),(l,0)` has constant
  term `m^2`; its median restriction has roots `s=1` and `s=m^2/r^2`.
  Since `r^2-m^2=(B-A)·(C-A)>0` for acute A, the second root is distinct
  and lies strictly between M and A. The altitude equations give
  `H=(x,(m^2-x^2)/y)`, so `A·H=A·P=m^2`; this proves `P` is the foot.
  Cyclically the three points are H's median projections, and
  `(P_i-H)·(P_i-G)=0` puts them on the diameter-`HG` circle. Its center is
  `Z=(H+G)/2`. The H03 full-task treatment answer and the control answer now
  derive the centroid step: with O as origin and `|a|=|b|=|c|`,
  `(b+c)·(b-c)=0` and `(a+c)·(c-a)=0`; thus `h=a+b+c` lies on two
  altitudes and is the orthocenter vector. Hence `g=h/3`, `z=2h/3`, and
  `OZ=4` when `OH=6`.
- **H04:** The altitude equations give
  `H=(x,(m^2-x^2)/y)` and projection `P=(m^2/r^2)A`. Acuteness gives
  `r^2-m^2=(B-A)·(C-A)>0`, so `lambda=m^2/r^2<1`; cancelling
  `1-lambda` in the expansion of `TA^2-TP^2` is valid. It yields
  `2sx=r^2+m^2`, then `AT^2=MT^2-m^2`. The `T-B-C` order places T left
  of B, so `MT=BT+BC/2=5`; consequently `AT^2=25-9=16` and `AT=4`.
- **H14:** For `A=(u,v)`, `B=(-m,0)`, `C=(m,0)`, set
  `S=u^2+v^2`, `delta=S-m^2>0`, and `U=|AB|^2>0`. The circumcircle and
  its reflection have equations `x^2+y^2-(delta/v)y-m^2=0` and
  `x^2+y^2+(delta/v)y-m^2=0`. On `AB`, `W=A+t(B-A)` gives
  `|W-C|^2-|A-C|^2=t(Ut-2delta)` and
  `Omega*(W)=(t-1)(Ut-2delta)`, hence the specified second point has
  `t=2delta/U>0` and lies on `Omega*`; symmetry gives E. Inversion
  `I(X)=m^2X/|X|^2` sends `Omega*` to `Omega`: substituting
  `(x,y)=m^2(X,Y)/(X^2+Y^2)` gives the displayed `Omega` equation.
  M has power `-m^2`, so each positive ray has a unique `Omega` point and
  `P=I(D), Q=I(E)`. Substituting inversion into
  `AB: vx-(u+m)y+mv=0` gives the circle
  `v(X^2+Y^2)+mvX-m(u+m)Y=0` through `M,B,I(A),P`; symmetrically the
  image of AC is `CQM` through `I(A)`. Thus `R=I(A)=(m^2/S)A`.
  The altitude formula gives `A·H=A·R=m^2`; `0<m^2/S<1`, so R is the
  projection on AM. The right triangle has `HR=sqrt(10^2-6^2)=8` and area
  `24`.

No incorrect relation, invalid cancellation, wrong inversion branch, or
incorrect numerical value was found. H03's orthocenter-vector identity is
now derived explicitly in both whole-solution forms. The H14 inversion
substitution and line-image equations are also shown in the integrated
answers.

## Rows, prompts, English, and leakage

Every rotation/arm has 38 rows and 34 distinct source IDs: the same 32-row
base followed by six additions, three for each permitted source. Treatment
rows 1 and 2 are focused relation/proof prompts; row 3 for each source uses
that source's exact standard full-task prompt and a standalone integrated
answer. Control row 1 uses the same standard prompt, and rows 2 and 3 use
distinct paraphrases of the full task with complete integrated answers. Each
source has three distinct control prompts. All prompts and answers are
English text with no Japanese script.

For each rotation, the omitted source ID is absent from the training rows.
The omitted source's full v0 problem and answer, and the corresponding held-out
problem and exact answer, are also absent. These checks read the frozen source
and answer-key files only; no model output was read. The shared projection
lemma is deliberately taught using the two permitted sources, so the design
remains a transfer positive control rather than a test of discovering an
unseen lemma. The selected v0 audit records for H03/H04/H14 all have accepted
status and true numeric, relation, proof, use, and branch fields.

The same 32 base rows appear identically, in order, at the start of each
arm. All source and candidate file hashes match their manifests. The frozen
tokenizer recount matches every manifest count; the common base has 19,936
target tokens.

| Rotation | Added treatment/control | Added mismatch | Merged treatment/control | Merged mismatch |
|---|---:|---:|---:|---:|
| rotation-1 | 1,424 / 1,623 | 199 (12.26%) | 21,360 / 21,559 | 199 (0.923%) |
| rotation-2 | 1,867 / 2,040 | 173 (8.48%) | 21,803 / 21,976 | 173 (0.787%) |
| rotation-3 | 1,467 / 1,389 | 78 (5.32%) | 21,403 / 21,325 | 78 (0.364%) |

## Methodological disposition

All rotations satisfy the explicitly declared exploratory tolerance of at most
2% relative mismatch in merged answer-token totals, using the larger arm as
the denominator. This is approximate full-dataset matching, not strict token
equality. The added rows alone differ by 5.32–12.26%; the longer arm varies by
rotation, so equal added supervision is not established. The candidate is
untrained and supports exploratory positive-control comparisons only.
