# Fresh2 target grading checks: H08 and H15

These are grader-only checks for the two frozen fresh2 target prompts. The
fresh2 key has nine rows and confirms H08=`195/29` and H15=`27√13/13`.
The parent heldout key contains older variants (H08 has `AP=√34`; H15 has
`AB=8`), so do not copy those older givens or answers into this fresh2 grading
pass. Accept equivalent self-contained proofs; the coordinate calculations
are audit checks, not a required method.

## H08 — tangent circles and reflection

**Required relation.** The construction-specific lemma is
`∠CAP = ∠BAQ` on the ordinary acute branch. A bare assertion of this angle
equality, or a tangent-chord argument that does not connect the reflected
point C to both tangent circles, is not decisive proof.

One coordinate route is to set `P=(0,0)`, `Q=(d,0)`, `A=(x,y)`,
`B=(u,v)`, with `y>v>0`. Write the tangent-circle equations as
`X²+Y²−2sY=0` and `(X−d)²+Y²−2tY=0`. Applying both equations to A and B gives

```text
r = (2x−d)/y = (2u−d)/v,
d² = (r²+4)yv.
```

The second identity follows by equating `x²/y+y` and `u²/v+v` after the
substitution `x=(d+ry)/2`, `u=(d+rv)/2`. If `θ_L` denotes the direction of
the ray from A toward L, substitution of the four ray slopes gives

```text
tan(θ_AQ−θ_AB) =  2d / ((r²+4)y−rd),
tan(θ_AP−θ_AC) = −2d / ((r²+4)y−rd).
```

The second equality uses `d²=(r²+4)yv`. Thus the directed turns have equal
magnitude; the ordinary-angle branch still needs to be resolved.

For this frozen fresh2 instance, the construction-check parameters are
`P=(1,0)`, `Q=(7,0)`, `A=(2,5)`. The circles have centers `(1,13/5)` and
`(7,5)`; their second common point is `B=(98/29,45/29)`, so
`C=(98/29,−45/29)`. The relevant vectors from A are

```text
AB=(40,−100)/29,   AQ=(5,−5),
AC=(40,−190)/29,   AP=(−1,−5).
```

Both angle dot products are positive:
`AB·AQ=700/29` and `AC·AP=910/29`. Their absolute cross/dot ratios are
`300/700=390/910=3/7`. This confirms that both are acute and that the
construction lemma uses the ordinary acute branch here; a tangent-only
calculation leaving a supplementary-angle ambiguity is incomplete.

**Numerical checks.** `AP²=26`; `AC²=37700/841`, so `AC≠AP` (indeed,
`37700≠26·841=21866`). With
`sin∠CAP=3/√58`, the area is

```text
½·AP·AC·sin∠CAP
= ½·√26·(10√377/29)·(3/√58)
= 195/29.
```

Do not accept an isosceles substitution `AP=AC` or use of `AP²` in place of
`AP·AC`, even if the response states the angle lemma.

## H15 — three reflections

**Required relation.** The answer must derive that K is the midpoint of AD
from the three reflections and the tangent-defined line AX. Merely asserting
the midpoint, checking a numerical diagram, or applying the median formula
without first proving the midpoint relation is insufficient.

A compact coordinate proof uses an oblique unit basis along AB and AC, whose
angle is 60 degrees. Write `c=AB`, `b=AC`; a point with basis coordinates
`(x,y)` has squared norm `x²+xy+y²`. Then `A=(0,0)`, `B=(c,0)`, `C=(0,b)`,
and the circumcircle is
`x²+xy+y²−cx−by=0`. Its tangent lines at B and C are respectively

```text
c x + (c−b)y = c²,
(b−c)x + b y = b²,
```

so `X=(b,c)`. The second intersection of AX with the circumcircle is

```text
W = b²+bc+c²,
D = (2b²c/W, 2bc²/W).
```

For the reflection step, line BC has equation `b x+c y=bc`. With
`Δ=b²−bc+c²`, reflection of `(x,y)` across BC is

```text
(x,y) − ((b x+c y−bc)/Δ)·(2b−c, 2c−b).
```

Substituting D gives `E=(bc²/W,b²c/W)`. Reflection in AB maps
`(x,y)→(x+y,−y)`; reflection in AC maps `(x,y)→(−x,x+y)`. Hence

```text
C0 = (bc(b+c)/W, −b²c/W),
B0 = (−bc²/W, bc(b+c)/W),
M = D/2 = (b²c/W, bc²/W).
```

The collinearity checks reduce to

```text
det(M−B, B0−B) = (bc³/W²)·(bc+W−(b+c)²) = 0,
det(M−C, C0−C) = (b³c/W²)·((b+c)²−bc−W) = 0,
```

since `bc+W=(b+c)²`. Thus M lies on both `BB0` and `CC0`; the prompt's
distinct-line assumption makes their intersection K equal to M.

**Fresh2 numerical check.** With `AB=9`, `BD=9√91/13`, and
`AD=18√13/13`, Apollonius gives

```text
4 BK² = 2 AB² + 2 BD² − AD²
      = 37908/169,
BK = 27√13/13.
```

The construction audit's `b=3,c=9` is consistent with this instance, but the
final distance follows from AB, BD, AD once the midpoint lemma is proved.
