# Fresh2 retention grader checks

These notes cover only retention IDs H01, H02, H07, and H13. Grade each answer
using the four independent fields in ../GRADE_RUBRIC.md. A correct number
alone may pass exact value, but not relation, proof, or use. Accept equivalent
coordinate/vector proofs; do not require the parametrization below verbatim.
An asserted construction-specific relation without its decisive derivation
does not pass proof.

## H01 — orthocenter projection onto a median

Expected exact value: 27/14.

Let M=(0,0), B=(-m,0), C=(m,0), A=(x,y), with m=13 and r=AM=14.
The altitude equations give H=(x,(m^2-x^2)/y), hence A dot H=m^2.
Projection onto AM is therefore P=(m^2/r^2)A. Since A is acute,
r^2-m^2=(B-A) dot (C-A)>0, so the projection parameter is in (0,1).
Thus
AP=r(1-m^2/r^2)=14-169/14=27/14.

**Proof gate:** credit the useful relation only if the answer gives a true
construction-specific projection relation, such as A dot H=(BC/2)^2 or
P=((BC/2)^2/AM^2)A. For proof, derive it from the altitude condition (or
an equivalent valid argument) and justify the segment branch. A guessed
27/14 passes exact only.

## H02 — affine circumcenter for the two auxiliary circles

Expected exact value: 4*sqrt(205)/13.

Use B=(0,0), C=(28,0), M=(14,0). From
AM^2-AK^2=205-169=36, KM=6; BK>KC selects K=(20,0), so
A=(20,13) up to reflection in BC. Let d=BD (3 or 7), and parametrize
U=A+t(C-A), V=A+s(B-A). The two defining circles are

AB D: x^2+y^2-dx+((20d-569)/13)y=0,

AC D: x^2+y^2-(28+d)x-((9+8d)/13)y+28d=0.

Substitution gives the non-A roots
t=(28d-551)/233 and s=(569-28d)/569. Both are nonzero for d=3,7.
If Z_d=(z_x,z_y) is the center of AUV, its perpendicular-bisector
equations reduce to

16z_x-26z_y=233t-18,
-40z_x-26z_y=569s-1138.

Subtracting and substituting the roots gives
56z_x=233t-569s+1120=56d, so
Z_d=(d,(569-12d)/26). Hence
Z_7-Z_3=(4,-24/13) and
Z_3Z_7=sqrt(16+576/169)=4*sqrt(205)/13.

**Proof gate:** the useful relation is the affine dependence of the center on
the coordinate d; accept an equivalent correct formula. To pass proof, an
answer must derive the two non-A intersections and then the center relation
from the circle/perpendicular-bisector equations (or an equivalent decisive
calculation). BK>KC must select K=20, and the two specified values of BD
must be used. Merely asserting that the center is affine in d fails proof.

## H07 — tangent-circle radical axis and reflected point

Expected exact value: 42/5.

Set A=(0,0), B=(10,0), O=(5,0). Since the circles are tangent to AB
at A and B, their powers at O are OA^2 and OB^2, which are equal.
Therefore O lies on their radical axis MN. Secant power gives
OM*ON=OA^2=25. M and N are on the same side of AB; the condition that M
is nearer AB selects the same ray with OM<ON. Thus
OM=25/ON=3*sqrt(2) and ON/OM=25/18. With MF=3, the heights above AB
are y_M=3 and y_N=25/6.

The horizontal chord through M=(x,3) has endpoints M,C=(-x,3) on the
circle tangent at A; on the circle tangent at B its other endpoint is
D=(20-x,3). Consequently AC and BD meet at E=(x,-3), the reflection
of M over AB. Write N=(u,v), with v=25/6. The line CD is horizontal:
P=AN intersect CD=(3u/v,3) and
Q=BN intersect CD=(10+(u-10)3/v,3). Therefore
PQ=10(1-3/v) and the altitude from E to PQ is 6, giving

area EPQ=10*3*(1-18/25)=42/5.

**Proof gate:** require the radical-axis/power relation (or an equivalent
construction-derived relation), the same-ray branch from “M is nearer,” and
the reflected-point fact or an equivalent derivation of E. For use, the
height ratio and area must follow from the stated MF and ON; an unresolved
sign choice does not pass proof/use.

## H13 — center of BJK lies on AC

Expected exact value: 1700/129.

Take C=(0,0), B=(10,0), and A above BC. From cos C=8/17, write
A=(8t,15t) and M=(4t,15t/2). The circle BMC has equation
x^2+y^2-10x+qy=0, where substituting M gives
q=(160-289t)/30. Its tangent at C is -10x+qy=0; K is on x=10.
Because K is opposite A across BC, its ordinate is negative. The given
BK=1000/43 thus gives q=-43/10, so t=1, A=(8,15), and
K=(10,-1000/43).

Line BM is 4y=50-5x; parametrizing AK shows its internal intersection is
J=(1070/123,200/123) (the AK parameter is 43/123, between 0 and 1).
Write circle BJK as
x^2+y^2+u x+v y+w=0. The two points B,K with x-coordinate 10 give
v=1000/43, w=-100-10u; substituting J gives
u=(100-J_x^2-J_y^2-(1000/43)J_y)/(J_x-10)=1600/129.
Therefore its center is
Z=(-u/2,-v/2)=(-800/129,-500/43)=-(100/129)(8,15).
This derives the useful relation that Z lies on AC. Consequently
CZ=(100/129)|CA|=(100/129)*17=1700/129.

**Proof gate:** the side condition on K must select the negative ordinate and
therefore the correct tangent/sign branch. The useful relation is Z on AC;
proof must derive it from the tangent-circle construction and the center of
BJK, not merely state it. The intersection J must be the specified internal
one. Accept an equivalent exact construction, center calculation, and value.

For any answer with unresolved contradictory derivations, mark uncertain
and give the specific issue rather than silently resolving it.
