# Independent math caveats

This note describes what an auditor should check in the candidate QA rows. The
original English v0 records for the three permitted configurations were marked
accept; the selected audit rows report numeric, true_relation, proof, use, and
branches_checked as true. The candidate responses are rewritten from those
proofs and should still be checked independently.

## H03 angle-bisector circle and median

- In coordinates centered at the active base midpoint, the side lengths
  b=CA, c=AB satisfy b!=c because the triangle is scalene. This makes the
  external-bisector intercept finite; b+c is also nonzero.
- The bisector intercept product is kl=m^2. Substitution on the median must
  yield roots s=1 and s=m^2/(x^2+y^2).
- The acute angle at A gives (x^2+y^2)-m^2>0, so the second root is distinct
  from A and lies strictly between M and A.
- The orthocenter formula gives A dot H=m^2, matching A dot P; this proves
  HP is perpendicular to the median. Since the centroid is on every median,
  the three projections lie on the circle with diameter HG.
- The original numerical application uses OH=6; with O as origin,
  the full-task answer should derive `h=a+b+c` from the two altitude dot
  products `(b+c) dot (b-c)=0` and `(a+c) dot (c-a)=0`. Thus h is the
  orthocenter vector, `G=H/3`, `Z=(H+G)/2=2H/3`, and `OZ=4`.

## H04 perpendicular-bisector construction

- Acuteness gives r^2>m^2, so lambda=m^2/r^2 is strictly between zero and
  one. In particular P is not A and cancelling 1-lambda is valid.
- Expanding TA^2=TP^2 must retain the nonzero factor and give
  2sx=r^2+m^2, hence AT^2=MT^2-m^2.
- The ordering T,B,C selects the exterior point left of B. With
  BT=2, BC=6, this gives MT=5, m=3, and the positive length AT=4.

## H14 inversion and orthocenter projection

- In midpoint-centered coordinates, acuteness gives |u|<m and
  delta=u^2+v^2-m^2>0; v and U=(u+m)^2+v^2 are nonzero. The second-circle
  parameter t=2delta/U is positive.
- The reflected circumcircle factor on AB and the radius-CA circle factor
  must share the nontrivial root Ut=2delta; the same check applies to E.
- Inversion is I(X)=m^2 X/|X|^2, which is defined at D and E under the
  nondegeneracy assumptions. Substitution in the reflected-circle equation
  should give the circumcircle equation. It preserves positive rays. Because
  M is inside the circumcircle, the ray intersections are unique.
- Inversion fixes B and C and maps AB and AC to the two defining circles.
  Substituting inversion into the line equations verifies these circle
  images. The circles are distinct for the scalene source; the stated
  construction excludes degenerate intersections. Their non-M common point
  is R=I(A)=(m^2/(u^2+v^2))A.
- A dot H=m^2=A dot R proves HR is perpendicular to AM. Also
  0<m^2/(u^2+v^2)<1, so R lies between M and A. For the source numbers,
  AH=10, AR=6, HR=8, and area 24.

The held-out numeric instances are not used here. The source numbers used in
these candidate rows are precisely those of the selected v0 problems:
OH=6; BT=2, BC=6; and AH=10, AR=6.
