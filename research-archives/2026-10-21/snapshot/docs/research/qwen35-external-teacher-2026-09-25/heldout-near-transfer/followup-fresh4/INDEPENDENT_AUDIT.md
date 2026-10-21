# Fresh4 independent audit

**Status: passed; no blocking discrepancy found.** This note is audit-only and
was added after the fresh4 freeze. It is not part of either evaluation input.

I checked the six frozen problem/key pairs using direct coordinate derivations,
not the fresh4 freezer's branch-check functions. I also checked the frozen
input/source hashes, visible prompts, and collision exclusions. I did not open
LOO outputs or condition scores, run a model, or use a GPU.

## Mathematics and branch checks

**H03.** In the unscaled shape coordinates
`A=(2,7), B=(-7,0), C=(5,0)`, the squared side lengths are 130, 58, and 144;
the angle dot products at A, B, C are 22, 108, and 36. Thus the triangle is
acute and scalene. Directly constructing the three angle-bisector circles and
intersecting each with its median gives the orthocenter-projection parameters
`11/29`, `216/245`, and `72/137`, all strictly between 0 and 1. The three
projection points are noncollinear (their triangle's area is
`225828/139055`). The coordinates give `O=(-1,11/7)`, `H=(2,27/7)`, and the
center of the projection-point circle `Z=(1,65/21)`, so
`OZ^2/OH^2=4/9`. Scaling the shape to the displayed OH therefore gives
`OZ=2 OH/3`: the keys `26/3` for OH=13 and `28/3` for OH=14 are correct.

**H04.** Put `B=(-c,0), C=(c,0), M=(0,0), A=(u,v)`, where
`c=BC/2`, `u=1-BC/2`, and `v=sqrt(BC)`. Then
`AM^2=c^2+1`, the angle-A dot product is `AM^2-c^2=1`, and the other two
angle dot products are `BC` and `BC(BC-1)`. They are positive for both
instances; side lengths are distinct. The orthocenter is
`(u,(c^2-u^2)/v)`, whose projection onto AM is
`P=(c^2/AM^2)A`. Since `AM^2-c^2=1`, the perpendicular-bisector equation
for AP can be divided by a nonzero factor. For `T=(t,0)` it gives
`tu=(AM^2+c^2)/2`, hence `AT^2=t^2-c^2=BT·TC`.

For BC=13 this gives `t=-171/22`, so T is before B,
`BT=14/11`, `TC=157/11`, and `AT^2=2198/121`.
For BC=14 it gives `t=-33/4`, again before B,
`BT=5/4`, `TC=61/4`, and `AT^2=305/16`. Both keyed positive roots are
therefore correct. The nonzero value `AM^2-c^2=1` verifies the cancellation
condition on these acute branches.

**H14.** Use `A=(a,y), B=(-w,0), C=(w,0), M=(0,0)` and
`S=a^2+y^2`. The circumcircle has equation
`x^2+Y^2-2oY-w^2=0`, where `o=(S-w^2)/(2y)`, and the orthocenter is
`H=(a,(w^2-a^2)/y)`. Its projection onto AM is
`R=(w^2/S)A`, since `H·A=w^2`.

I checked the actual non-A intersections defining D and E by writing
`D=A+delta(B-A)` and `E=A+epsilon(C-A)` and solving their circle equations.
The second-root parameters `(delta, epsilon)` are respectively
`(78/1369, 26/51)` for `(w,a,y)=(19,16,12)` and
`(34/397, 34/37)` for `(20,18,12)`. The resulting ray parameters `(MD→P,
ME→Q)` are `(494209/443860, 6137/5812)` and
`(39700/33529, 3700/3649)`, all positive; substituting the resulting P and Q
into the circumcircle equation gives zero. The projection R lies on both
constructed circles: their equations are
`x^2+Y^2+wx-w(w+a)Y/y=0` and
`x^2+Y^2-wx-w(w-a)Y/y=0`. They are distinct, and P,Q are off BC, so this R is
the non-M common point. The angle dot products are `(39,1330,114)` and
`(68,1520,80)`, respectively, with distinct squared side lengths
`(1369,153,1444)` and `(1588,148,1600)`. The ray roots are unique on each
positive ray because M has power `-w^2` with respect to the circumcircle.

For the first instance, `AH=13/4`, `AR=39/20`, and the right-triangle leg
`HR=13/5`, giving area `507/200`. For the second,
`AH=17/3`, `AR=34 sqrt(13)/39`, and `HR=17/sqrt(13)`, giving area `289/39`.
Both answer-key values and the asserted orthocenter-projection branch check.

## Prompt, collision, and hash checks

Each evaluation job has one user message containing the English instruction
and its English problem. The prompts contain no Japanese script and no exact
answer, parameter object, branch-condition object, or answer-key field. The
answer keys remain separate from the jobs.

For each source ID, I compared full givens and canonical/English problem text
against fresh1, fresh2, fresh3, and v0-v3; none collide. The normalized
full-givens signatures and evaluation seeds also differ. The visible metrics
are outside the original finite generator projections: H03 OH uses
`{5,6,8,9,10}`, H04 BC uses `{5,6,7,8,9}`, and H14 AH is projected from
`abs((w^2-x^2-y^2)/y)` over
`w∈{8,10,12,14}`, `x∈{10,12,14,16}`, `y∈{8,10,12}`; neither `13/4` nor `17/3`
occurs in that H14 projection. For fresh1, fresh2, and fresh3, full givens and
canonical/English text differ; for v0-v3, full givens, normalized signatures,
and canonical problem text differ.

All 23 artifact/source SHA-256 entries in `hashes.json` match. The six nested
canonical-problem, English-problem, and generator-signature hashes in
`construction_checks.json` also match. `target_eval_jobs.json` has the same
records as `eval_jobs.json`. The frozen inputs were not modified.
