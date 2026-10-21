## F01 sample 0

A point S outside a circle has a tangent ST. A secant meets the circle at U,V in the order S,U,V, with SU=3 and UV=9. Find ST. Establish the product identity you use from similar triangles instead of citing the power-of-a-point theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without a complete final proof.", "repairable": false}

## F01 sample 1

A point S outside a circle has a tangent ST. A secant meets the circle at U,V in the order S,U,V, with SU=3 and UV=9. Find ST. Establish the product identity you use from similar triangles instead of citing the power-of-a-point theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without a complete final proof.", "repairable": false}

## F02 sample 0

Two chords AC and BD of a circle meet at an interior point P. PA=3, PC=8, PB=4. Find PD. Derive the needed product relation from angles and similar triangles instead of quoting the intersecting-chords theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without a complete final proof.", "repairable": false}

## F02 sample 1

Two chords AC and BD of a circle meet at an interior point P. PA=3, PC=8, PB=4. Find PD. Derive the needed product relation from angles and similar triangles instead of quoting the intersecting-chords theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without a complete final proof.", "repairable": false}

## F03 sample 0

Triangle ABC is right-angled at A. The perpendicular from A to BC meets BC at D. Given BD=4 and DC=9, find AD and AB. Justify the relations rather than citing a special theorem about the altitude to a hypotenuse.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 6702; finish: stop.


Triangle ABC is right-angled at A, with BC as the hypotenuse. Given BD = 4 and DC = 9, BC = BD + DC = 13.

To find AD, the altitude from A to BC, consider triangles ABD and ACD, both right-angled at D. Let AD = h, AB = c, and AC = b.

From triangle ABD:  
AB² = AD² + BD² ⇒ c² = h² + 4² ⇒ c² = h² + 16.

From triangle ACD:  
AC² = AD² + CD² ⇒ b² = h² + 9² ⇒ b² = h² + 81.

By the Pythagorean theorem in triangle ABC:  
AB² + AC² = BC² ⇒ c² + b² = 13² ⇒ c² + b² = 169.

Substitute the expressions for c² and b²:  
(h² + 16) + (h² + 81) = 169 ⇒ 2h² + 97 = 169 ⇒ 2h² = 72 ⇒ h² = 36 ⇒ h = 6 (since length is positive).

Thus, AD = 6.

Now, find AB:  
From c² = h² + 16 ⇒ c² = 36 + 16 = 52 ⇒ c = √52 = 2√13 (since length is positive).

Verification:  
AC² = h² + 81 = 36 + 81 = 117, and AB² + AC² = 52 + 117 = 169 = BC², confirming the Pythagorean theorem.

The relations are justified using the Pythagorean theorem in the smaller triangles and the original triangle, without citing special theorems.

\boxed{AD=6,\ AB=2\sqrt{13}}<｜end▁of▁sentence｜>

Grade: {"valid": true, "method": "analytic", "note": "Valid derivation from Pythagoras / general right-triangle coordinates; AD=6, AB=2sqrt(13).", "repairable": false}

## F03 sample 1

Triangle ABC is right-angled at A. The perpendicular from A to BC meets BC at D. Given BD=4 and DC=9, find AD and AB. Justify the relations rather than citing a special theorem about the altitude to a hypotenuse.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 7396; finish: stop.


Triangle ABC is right-angled at A, with BC as the hypotenuse. Given BD = 4 and DC = 9, BC = BD + DC = 13.

Place A at (0,0), B at (b,0), and C at (0,c) in the coordinate plane. Then b² + c² = 169.

The perpendicular from A to BC has equation y = (b/c)x. The intersection with BC gives D at ((b c²)/169, (b² c)/169).

The distance BD = 4 gives (delta x)² + (delta y)² = 16, where delta x = -b³/169 and delta y = b²c/169. This simplifies to b⁴/169 = 16, so b⁴ = 16 × 169 = 2704, and b² = 52 (since b > 0).

Then c² = 169 - b² = 117.

AB is the distance from A to B, so AB = b = √52 = 2√13.

AD is the distance from A to D, which is (b c)/13. Since b c = √(52 × 117) = √6084 = 78, AD = 78/13 = 6.

Verification using similarity: Triangle ABD ~ Triangle ABC gives AB² = BC × BD = 13 × 4 = 52, so AB = √52. Triangle ACD ~ Triangle ABC gives AC² = BC × CD = 13 × 9 = 117, and AD = (AB × AC)/BC = (√52 × √117)/13 = 78/13 = 6.

The area is consistent: (1/2) × AB × AC = (1/2) × √52 × √117 = 39, and (1/2) × BC × AD = (1/2) × 13 × 6 = 39. Pythagoras holds: AB² + AC² = 52 + 117 = 169 = 13².

The labeling is fixed by BD = 4 and DC = 9, so no other configuration is possible.

\boxed{AD=6,\ AB=2\sqrt{13}}<｜end▁of▁sentence｜>

Grade: {"valid": true, "method": "analytic", "note": "Valid derivation from Pythagoras / general right-triangle coordinates; AD=6, AB=2sqrt(13).", "repairable": false}

## F04 sample 0

ABC is an acute triangle. D is the foot of the perpendicular from B to AC, and E is the foot from C to AB. Prove that angle ADE equals angle ABC.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without a complete final proof.", "repairable": false}

## F04 sample 1

ABC is an acute triangle. D is the foot of the perpendicular from B to AC, and E is the foot from C to AB. Prove that angle ADE equals angle ABC.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without a complete final proof.", "repairable": false}

## F05 sample 0

ABCD is a convex trapezoid with AB parallel to CD, AB=6, CD=10. Diagonals AC and BD intersect at O. The line through O parallel to the bases meets AD at E and BC at F. Find EF.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without a complete final proof.", "repairable": false}

## F05 sample 1

ABCD is a convex trapezoid with AB parallel to CD, AB=6, CD=10. Diagonals AC and BD intersect at O. The line through O parallel to the bases meets AD at E and BC at F. Find EF.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without a complete final proof.", "repairable": false}

## F06 sample 0

In triangle ABC, D is inside AB and E is inside AC, with AD/DB=AE/EC=2/3. Lines BE and CD intersect at F. Find BF/FE.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 7553; finish: stop.


In triangle ABC, D divides AB in the ratio AD:DB = 2:3, and E divides AC in the ratio AE:EC = 2:3. The lines BE and CD intersect at point F.

Using coordinate geometry, assign coordinates to the vertices: A(0,0), B(b,0), and C(0,c) for arbitrary b and c (non-zero). Then D is at (2b/5, 0) and E is at (0, 2c/5).

The parametric equations for line BE are:
- x = b - b t
- y = (2c/5) t

The parametric equations for line CD are:
- x = (2b/5) s
- y = c - c s

Setting the equations equal to find the intersection F:
- b - b t = (2b/5) s
- (2c/5) t = c - c s

Solving these equations gives t = 5/7.

The parameter t ranges from 0 at B to 1 at E. The distance from B to F is proportional to t, and the distance from F to E is proportional to (1 - t). Thus, the ratio BF/FE is t / (1 - t) = (5/7) / (2/7) = 5/2.

This ratio is independent of the specific coordinates of A, B, and C, as long as the triangle is non-degenerate.

\boxed{\dfrac{5}{2}}<｜end▁of▁sentence｜>

Grade: {"valid": false, "method": "analytic", "note": "Sets A=(0,0), B=(b,0), C=(0,c) without explaining affine coordinates/invariance. Correct division calculation but generality is not justified.", "repairable": true}

## F06 sample 1

In triangle ABC, D is inside AB and E is inside AC, with AD/DB=AE/EC=2/3. Lines BE and CD intersect at F. Find BF/FE.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without final proof.", "repairable": false}

## F07 sample 0

The two tangents from T touch a circle at A and B, and TA=7. A third tangent touches the minor arc AB at P and meets the segments TA and TB at X and Y. Assume P lies between X and Y, with T,X,A and T,Y,B in those respective orders. Find the perimeter of triangle TXY.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without a complete final proof.", "repairable": false}

## F07 sample 1

The two tangents from T touch a circle at A and B, and TA=7. A third tangent touches the minor arc AB at P and meets the segments TA and TB at X and Y. Assume P lies between X and Y, with T,X,A and T,Y,B in those respective orders. Find the perimeter of triangle TXY.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without a complete final proof.", "repairable": false}

## F08 sample 0

A,B,C are distinct points on a circle. The line through C parallel to the tangent at A meets the ray AB at D, with A,B,D in that order. Prove AB*AD=AC^2.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without a complete final proof.", "repairable": false}

## F08 sample 1

A,B,C are distinct points on a circle. The line through C parallel to the tangent at A meets the ray AB at D, with A,B,D in that order. Prove AB*AD=AC^2.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.


Consider a circle with center \(O\) and radius \(r\), tangent to the line at \(A\). Place \(A\) at \((a, 0)\) and the center \(O\) at \((a, r)\), so the circle equation is \((x - a)^2 + (y - r)^2 = r^2\), which simplifies to \((x - a)^2 +

Grade: {"valid": false, "method": "none", "note": "Output limit reached without a complete final proof.", "repairable": false}

## F09 sample 0

ABC is an isosceles triangle with AB=AC. P is any point in the interior of BC. E and F are the perpendicular projections of P onto the lines AB and AC. Prove that PE+PF equals the perpendicular distance from B to line AC.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.


Consider isosceles triangle \(ABC\) with \(AB = AC\). Let \(M\) be the midpoint of \(BC\), so \(AM\) is the altitude from \(A\) to \(BC\). Let \(h_a = AM\) and let \(d = BM\), so \(BC = 2d\). Then, \(AB = AC = l = \sqrt{d^2 + h_a^2}\).

For any point \(P\) on \(BC\), parameterize \(P\) by \(BP = m\). The perpendicular distance from \(P\) to \(AB\) is given by \(\frac{h_a}{l} \cdot m\). The perpendicular distance from \(P\) to \(AC\) is given by \(\frac{h_a}{l} \cdot (2d - m)\). The sum is:
\[
PE + PF = \frac{h_a}{l} \cdot m + \frac{h_a}{l} \cdot (2d - m) = \frac{h_a}{l} \cdot 2d.
\]

The perpendicular distance from \(B\) to \(AC\) is \(l \sin \theta\), where \(\theta\) is the angle at \(A\). Since \(\theta = 180^\circ - 2\beta\) and \(\beta\) is the angle at \(B\), \(\sin \theta = \sin(

Grade: {"valid": false, "method": "none", "note": "Final proof begins but is cut off before completing the distance comparison.", "repairable": false}

## F09 sample 1

ABC is an isosceles triangle with AB=AC. P is any point in the interior of BC. E and F are the perpendicular projections of P onto the lines AB and AC. Prove that PE+PF equals the perpendicular distance from B to line AC.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 4664; finish: stop.


In isosceles triangle ABC with AB = AC, place B at (-c, 0) and C at (c, 0) in the coordinate plane, with A at (0, h) for some h > 0 and c > 0.

Let P be a point on BC with coordinates (p, 0) where -c < p < c.

The equation of line AB is -hx + cy - hc = 0.

The perpendicular distance from P to AB is | -h(p) + c(0) - hc | / √(h² + c²) = h(p + c) / √(h² + c²), since p + c ≥ 0.

The equation of line AC is hx + cy - hc = 0.

The perpendicular distance from P to AC is | h(p) + c(0) - hc | / √(h² + c²) = h(c - p) / √(h² + c²), since p - c ≤ 0.

The sum of these distances is [h(p + c) + h(c - p)] / √(h² + c²) = 2hc / √(h² + c²).

The perpendicular distance from B to line AC is | h(-c) + c(0) - hc | / √(h² + c²) = 2hc / √(h² + c²).

Thus, PE + PF = 2hc / √(h² + c²) equals the perpendicular distance from B to line AC.

\boxed{\text{The sum of the perpendicular distances from any point P on BC to the sides AB and AC equals the perpendicular distance from B to line AC.}}<｜end▁of▁sentence｜>

Grade: {"valid": true, "method": "analytic", "note": "General isosceles coordinates and correct perpendicular-distance formulas prove the identity.", "repairable": false}

## F10 sample 0

ABCD is a convex trapezoid with AB parallel to CD, AB>CD, and AD=BC. Prove that A,B,C,D lie on one circle.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 6714; finish: stop.


In trapezoid ABCD with AB parallel to CD and AB > CD, and AD = BC, the trapezoid is isosceles. This implies that angle A equals angle B and angle D equals angle C.

Since AB is parallel to CD, the consecutive interior angles sum to 180°. Specifically, angle A and angle D are consecutive interior angles with transversal AD, so angle A + angle D = 180°. Similarly, angle B and angle C are consecutive interior angles with transversal BC, so angle B + angle C = 180°.

Given that angle A = angle B and angle D = angle C, it follows that angle A + angle C = angle A + angle D = 180° and angle B + angle D = angle A + angle D = 180°.

The sum of opposite angles is 180°, which is a necessary and sufficient condition for a quadrilateral to be cyclic. Therefore, points A, B, C, D lie on a circle.

\boxed{\text{A, B, C, D are concyclic.}}<｜end▁of▁sentence｜>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct use of equal base angles in a non-parallelogram isosceles trapezoid and supplementary opposite angles."}

## F10 sample 1

ABCD is a convex trapezoid with AB parallel to CD, AB>CD, and AD=BC. Prove that A,B,C,D lie on one circle.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 6371; finish: stop.


Given that ABCD is a convex trapezoid with AB parallel to CD, AB > CD, and AD = BC, the goal is to prove that A, B, C, D are concyclic.

Since AB is parallel to CD, the consecutive interior angles sum to 180 degrees. Thus, ∠DAB + ∠ADC = 180° and ∠ABC + ∠BCD = 180°.

Given AD = BC, the trapezoid is isosceles. In an isosceles trapezoid, the base angles are equal. Therefore, ∠DAB = ∠ABC and ∠ADC = ∠BCD.

From ∠DAB + ∠ADC = 180° and ∠DAB = ∠ABC, ∠ABC + ∠ADC = 180°. Similarly, from ∠ABC + ∠BCD = 180° and ∠ADC = ∠BCD, ∠DAB + ∠BCD = 180°.

Thus, the opposite angles sum to 180 degrees: ∠DAB + ∠BCD = 180° and ∠ABC + ∠ADC = 180°.

A quadrilateral with opposite angles summing to 180 degrees is cyclic. Therefore, A, B, C, D lie on a circle.

\boxed{\text{A, B, C, D lie on a circle.}}<｜end▁of▁sentence｜>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct use of equal base angles in a non-parallelogram isosceles trapezoid and supplementary opposite angles."}

## F11 sample 0

Four distinct points A,B,C,D have no three collinear. Suppose angle BAC equals angle BDC, where both angles are ordinary angles in (0,180 degrees). Must the four points lie on one circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "repairable": false, "note": "Output limit reached; no complete final counterexample or proof."}

## F11 sample 1

Four distinct points A,B,C,D have no three collinear. Suppose angle BAC equals angle BDC, where both angles are ordinary angles in (0,180 degrees). Must the four points lie on one circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "repairable": false, "note": "Output limit reached; no complete final counterexample or proof."}

## F12 sample 0

Two nondegenerate triangles ABC and DEF satisfy AB/DE=AC/DF and angle ABC=angle DEF. Must the triangles be similar with correspondence A-D, B-E, C-F? Prove it or give an explicit counterexample.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "repairable": false, "note": "Output limit reached; no complete final counterexample or proof."}

## F12 sample 1

Two nondegenerate triangles ABC and DEF satisfy AB/DE=AC/DF and angle ABC=angle DEF. Must the triangles be similar with correspondence A-D, B-E, C-F? Prove it or give an explicit counterexample.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.


The given conditions are that triangles ABC and DEF are nondegenerate, AB/DE = AC/DF, and ∠ABC = ∠DEF.

A counterexample is provided by triangle ABC with angles ∠A = 80°, ∠B = 40°, ∠C = 60° and triangle DEF with angles ∠D = 20°, ∠E = 40°, ∠F = 120°. Set DE = 1. Then, by the law of sines in triangle DEF, DF = DE × sin(∠E) / sin(∠F) = 1 × sin(40°) / sin(120°) ≈ 0.7421. In triangle ABC, set AB = c and AC = b, so b / c = sin

Grade: {"valid": false, "method": "none", "repairable": false, "note": "Output limit reached; no complete final counterexample or proof."}
