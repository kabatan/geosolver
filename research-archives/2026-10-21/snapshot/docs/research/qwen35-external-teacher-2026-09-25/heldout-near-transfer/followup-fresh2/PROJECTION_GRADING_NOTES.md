# Fresh2 projection-family grader checks

These are grader-only mathematical checks for fresh2 H03, H04, and H14. The expected values are H03 `22/3`, H04 `2*sqrt(37)/3`, and H14 `343/2960`. Require a construction-derived relation and its needed branch conditions; a correct value alone earns only the exact-value component.

## H03 — angle-bisector circle and median

Let `M_a` be the origin, `B=(-m,0)`, `C=(m,0)`, `A=(x,y)`, and `r^2=x^2+y^2`. Write `b=CA`, `c=AB`. The angle-bisector theorem gives the two directed x-intercepts

`k=m(c-b)/(c+b)`, `l=m(c+b)/(c-b)`, hence `kl=m^2` (scalene gives `b!=c`). A circle through `(k,0)` and `(l,0)` has equation `X^2+Y^2+uX+vY+m^2=0`. On the median, `(X,Y)=sA`, this is a quadratic with leading coefficient `r^2`, constant `m^2`, and root `s=1` because `A` lies on the circle. Thus the other root is `s=m^2/r^2`, so `P_a=(m^2/r^2)A`.

Acuteness at `A` supplies the branch: `(B-A)·(C-A)=r^2-m^2>0`, so `0<m^2/r^2<1`; the second root is distinct from `A` and lies on segment `M_aA`. The altitude equations give `H=(x,(m^2-x^2)/y)`, so `A·H=m^2=A·P_a`. Hence `HP_a` is perpendicular to the median. Cyclically each `P_i` is the foot from `H` to its median. Since the centroid `G` lies on each median, `(P_i-H)·(P_i-G)=0`; the three points lie on the diameter-`HG` circle, whose center is `Z=(H+G)/2`.

To use `OH=11`, take `O` as vector origin and let the vertex vectors be `a,b,c`. Equal circumradii give `(b+c)·(c-b)=0` and its cyclic versions, so `h=a+b+c` is the orthocenter vector; the centroid vector is `g=h/3`. Therefore `z=(h+g)/2=2h/3`, and `OZ=(2/3)OH=22/3`.

**Proof gate:** do not credit the projection/circle relation for merely asserting the second intersection formula, or for omitting `r^2>m^2`. Credit the value only if the center relation is correctly applied to the given `OH`.

## H04 — perpendicular-bisector metric relation (distinct construction)

Put `a=BC/2=11/2`, `M=(0,0)`, `B=(-a,0)`, `C=(a,0)`, `A=(x,y)`, and `r^2=x^2+y^2`. The altitude equations give `H=(x,(a^2-x^2)/y)`, hence `A·H=a^2`. The foot from `H` to `AM` is therefore `P=λA`, with `λ=a^2/r^2`. Acuteness at `A` gives `r^2-a^2=(B-A)·(C-A)>0`, so `0<λ<1` and `1-λ` is nonzero.

Write `T=(s,0)`. The defining perpendicular-bisector condition is `TA^2=TP^2`; expansion must give

`TA^2-TP^2=(1-λ)((1+λ)r^2-2sx)=(1-a^2/r^2)(r^2+a^2-2sx)=0`.

After the valid cancellation, `2sx=r^2+a^2` and thus `AT^2=r^2-2sx+s^2=s^2-a^2=MT^2-a^2`. The order `T-B-C` selects `s<-a`: `MT=BT+BM=4/3+11/2=41/6`. Consequently `AT^2=(41/6)^2-(11/2)^2=148/9`, and the positive length is `AT=2*sqrt(37)/3`.

**H04 distinction:** this is not H03's circle/median construction. Require the `TA=TP` expansion, a justified cancellation (`r^2>a^2`), and the stated external-point order. Merely stating `AT^2=MT^2-(BC/2)^2` does not establish the relation.

## H14 — inversion identifies the constructed common point as a projection

Let `M=(0,0)`, `B=(-m,0)`, `C=(m,0)`, `A=(u,v)` with `v>0`, `S=u^2+v^2`, and `δ=S-m^2`. Acuteness at `A` gives `δ=(B-A)·(C-A)>0`. The circumcircle and its reflection across `BC` have equations

`Ω: x^2+y^2-(δ/v)y-m^2=0`, `Ω*: x^2+y^2+(δ/v)y-m^2=0`.

For `W=A+t(B-A)` and `U=|AB|^2>0`, the circle centered at `C` with radius `CA` gives

`|W-C|^2-|A-C|^2=t(Ut-2δ)`.

Meanwhile substitution into `Ω*` gives `(t-1)(Ut-2δ)=0`. Thus the non-`A` point `D` is on `Ω*` at `t=2δ/U>0`; the analogous calculation puts `E` on `Ω*` at the corresponding positive parameter on `AC`. The positive sign is required for the specified rays.

Inversion `I(X)=m^2X/|X|^2` sends `Ω*` to `Ω`, fixes `B,C`, and preserves each positive ray from `M`. Since `M` is inside `Ω` (the circle equation at `M` is `-m^2`), each such ray has a unique intersection with `Ω`; therefore `P=I(D)` and `Q=I(E)`. Inversion sends line `AB` to the circle through `M,B,I(A),P`; under the stated nondegeneracy this is circle `BPM`. Likewise line `AC` maps to circle `CQM`. Their common point other than `M` is `R=I(A)=(m^2/S)A`.

The altitude equations give `H=(u,(m^2-u^2)/v)`, so `A·H=m^2=A·R`. Also `0<m^2/S<1` by `δ>0`, placing `R` inside segment `MA`. Thus `HR` is perpendicular to `AM`, and `R` is the projection of `H` onto `AM`; `AHR` is right at `R`. With the givens, `AR/AH=5/sqrt(74)` and `HR/AH=7/sqrt(74)`. Hence

`[AHR]=(1/2)AH^2(AR/AH)(HR/AH)=(1/2)(7/10)^2(5/sqrt(74))(7/sqrt(74))=343/2960`.

**Proof gate:** an answer must connect the constructed `D,E,P,Q` and the common circles to `R=I(A)`. An unsupported claim that `R` is the altitude foot, or an inversion argument that omits `δ>0`, the positive-ray choice, or the non-`M` common point, does not prove the construction-specific relation.
