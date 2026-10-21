## C01 sample 0

In triangle ABC, AB=6, AC=9, and BC=10. The internal bisector of angle BAC meets BC at D. Through D draw the line parallel to AB, meeting AC at E. Find AE.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 138; finish: stop.



The internal angle bisector theorem gives BD/DC=AB/AC=2/3. B,D,E,C are collinear in that order, and DE is parallel to AB. The parallelism gives angle BDE=BAD, which is equal to DAC by angle bisector. Hence triangles BDE and BAC are similar with BD/BA=2/6=1/3. Therefore DE/AB=1/3 and AE=AB-AD=9-6*(BD/BA)=9-6*(1/2)=6.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Incorrect collinearity assumptions and similarity correspondences; wrong numerical answer."}

## C01 sample 1

In triangle ABC, AB=6, AC=9, and BC=10. The internal bisector of angle BAC meets BC at D. Through D draw the line parallel to AB, meeting AC at E. Find AE.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 216; finish: stop.



B-A-D-C in that order on the straight line BC. The parallelism gives angle BDE=BAD, which is half of BAC. This common angle pairs D on BC with E on AC, and B with D. The two rays BD and BE are in the same direction, so D,E are on the same ray from B. The two rays BD and BA are in the same direction, so D and A are on the same ray from B. Thus B,D,E are collinear in that order, and BD/BA=BE/BA=BE/BD. The angle BDA=BAC/2=BED, and the included ray BD is common to the two halfplanes of the bisector. Thus triangles BDA and BED are similar in that order. Their scale is BD/BA=5/8. Therefore BE=BD/BA*BA=BD=5, and AE=AC-EC=AC-BE=3.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Incorrect collinearity assumptions and similarity correspondences; wrong numerical answer."}

## C02 sample 0

In triangle ABC, angle BAC=48 degrees. The internal bisectors of angles ABC and ACB meet at I. Find angle BIC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 84; finish: stop.



Let BA and CA meet the internal bisectors at B and C. The two halves of angle BAC add to 48 degrees. Their supplements at I add to 180 degrees. Hence BIC=180-24=156 degrees.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Incorrect incenter angle calculation or mislabeled angle sum."}

## C02 sample 1

In triangle ABC, angle BAC=48 degrees. The internal bisectors of angles ABC and ACB meet at I. Find angle BIC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 104; finish: stop.



In triangle IBC, the angle at I is 180-IBI-CBI. The internal bisectors give IB_A/2 and IC_C/2. Therefore BIC=180-A/2-C/2=90+A/2. With A=48 degrees, BIC=90+24=114 degrees.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": true, "note": "Intended correct formula 90+A/2, but wrong angle labels and explicit preceding angle-sum equation. Repairable, not a valid proof as written."}

## C03 sample 0

ABCD is a convex quadrilateral with AB=BC and AD=DC. Prove that its diagonals AC and BD are perpendicular.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 71; finish: stop.



In triangles ABC and ADC, AC is common, AB=BC and AD=DC. SSS gives AC perpendicular BD. The two halves are mirror images across AC, so BD has opposite slopes at A and C. Thus AC and BD are perpendicular.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Misapplies SSS to unrelated sides and does not establish the perpendicular bisector."}

## C03 sample 1

ABCD is a convex quadrilateral with AB=BC and AD=DC. Prove that its diagonals AC and BD are perpendicular.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 120; finish: stop.



In triangles ABC and ADC, the side AC is common, AB=BC and AD=DC. SSS gives angle BAC=ACD and BCA=ADC. Since AB and AD are adjacent sides of the convex quadrilateral, BAC+ADC=pi. Thus both BAC and ACD=pi/2, and AC is perpendicular to both BC and DC. Therefore AC is perpendicular to the entire line BD.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Misapplies SSS to unrelated sides and does not establish the perpendicular bisector."}

## C04 sample 0

ABCD is a nondegenerate parallelogram, E is the midpoint of AB, and lines DE and AC meet at F. Find AF/FC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 64; finish: stop.



Join DB and let E bisect AB. Then B,E,D are collinear with EB=ED, so F=E. Thus AF/FC=AE/AD=1/2.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Incorrect point incidence / mass-point relations and unsupported ratio."}

## C04 sample 1

ABCD is a nondegenerate parallelogram, E is the midpoint of AB, and lines DE and AC meet at F. Find AF/FC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 94; finish: stop.



Assign weights -1 and 1 at A and B to make E the midpoint. The entire weight on DB is zero, so F must divide AC in the same ratio DE:FB. Both vectors DB and DA have weight zero at E, giving DF=DB-FD=FB-FD. Hence AF/FC=DB/DA=1.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Incorrect point incidence / mass-point relations and unsupported ratio."}

## C05 sample 0

AB is a diameter of a circle with center O. C is another point on the circle. The tangent at C meets the tangents at A and B at X and Y, respectively. Prove that angle XOY=90 degrees.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 335; finish: stop.



Angle ACB=90 degrees because AB is a diameter. The tangent at C is perpendicular to the radius OC, so the tangent line CX has slope -OC_x/OC_y. The tangents at A and B are perpendicular to OA and OB, respectively. Their slopes are -OA_x/OA_y and -OB_x/OB_y. The dot product of CX and CA is -OC_x/OC_y*OA_x/OA_y - OC_y/OC_x*OB_x/OB_y. Since OA and OB are perpendicular and OC is their sum, this dot product is -OC_x OA_x/OC_y OA_y - OC_y OB_x/OC_x OB_y = -OA_x OB_x - OA_y OB_y= -AB^2/2. Because ACB=90 degrees, OC_x^2+OC_y^2=OA^2+OB^2. Thus OC_x OA_x+OC_y OA_y=OA^2, and OC_x OB_x+OC_y OB_y=OB^2. The two perpendicularity conditions give OA^2=OC_x OA_x+OC_y OA_y and OB^2=OC_x OB_x+OC_y OB_y. Hence the dot product is -(OA^2+OB^2)/2= -OC^2/2. This is not zero unless O,C,X,Y are coplanar. Therefore CX and CY are perpendicular, and angle XOY=90 degrees.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "False tangent parallelism or dot-product identities; does not prove XOY perpendicularity."}

## C05 sample 1

AB is a diameter of a circle with center O. C is another point on the circle. The tangent at C meets the tangents at A and B at X and Y, respectively. Prove that angle XOY=90 degrees.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 132; finish: stop.



Because AB is a diameter, ACB=90 degrees. The tangent at C is perpendicular to the radius OC, so XC is parallel to CB. Likewise YC is parallel to CA. Thus X,Y,C,B are vertices of a parallelogram, giving XY=CB-CA=XC-YC. The two adjacent sides of this parallelogram are tangents at C, and hence perpendicular. Therefore XY is perpendicular to both XC and YC, proving XOY=90 degrees.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "False tangent parallelism or dot-product identities; does not prove XOY perpendicularity."}

## C06 sample 0

ABC is an equilateral triangle of altitude h. P is strictly inside the triangle, and its perpendicular distances to lines AB, BC, CA are x,y,z. Prove that x+y+z=h.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 107; finish: stop.



Base AB has length h/z, so z>0. Similarly x>0 and y>0. The areas of PAB, PBC, PCA are 1/2*h*x, 1/2*(h/z)*y, 1/2*(h/x)*z. These sum to 1/2*h*(x+y+z). The total area is 1/2*h^2, hence x+y+z=h.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Incorrect area bases/heights or unsupported interpolation."}

## C06 sample 1

ABC is an equilateral triangle of altitude h. P is strictly inside the triangle, and its perpendicular distances to lines AB, BC, CA are x,y,z. Prove that x+y+z=h.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 50; finish: stop.



The three parallelism conditions give z=0, x=0, y=0 on the three sides, and hence x+y+z=h in between.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Incorrect area bases/heights or unsupported interpolation."}

## C07 sample 0

Triangle ABC has AB=13, AC=14, BC=15. Its incircle touches BC at D. Find BD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 78; finish: stop.



Let the incircle touch AB at F and AC at E. Then BD=BF and CD=CE. Their sum is BC=15, and their difference is AB-AC= -1. Solving these equations gives BD=7.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct equal-tangent equations x+y=15 and x-y=-1 give BD=7."}

## C07 sample 1

Triangle ABC has AB=13, AC=14, BC=15. Its incircle touches BC at D. Find BD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 89; finish: stop.



Let x=BD and y=CD. The incircle tangency condition gives BD=BF and CD=CF, where F is the touchpoint on AB. Thus x=AB-AC+y=13-14+y. Also BC=x+y=15. Solving these equations gives y=12 and x=3.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Incorrect tangency labels and algebra in second sample."}

## C08 sample 0

In an isosceles triangle ABC with AB=AC, D is strictly inside AB and E is strictly inside AC, with BD=CE. Let F be the intersection of BE and CD. Prove BF=CF.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 75; finish: stop.



In triangles BFD and CFE, AB=AC, BD=CE, and angles BDF and CED are vertical angles. SSS gives BFD congruent CFE, so corresponding segments BF and CF are equal.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Incorrect congruence data and angle incidences."}

## C08 sample 1

In an isosceles triangle ABC with AB=AC, D is strictly inside AB and E is strictly inside AC, with BD=CE. Let F be the intersection of BE and CD. Prove BF=CF.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 149; finish: stop.



Triangles BDF and CEF have equal side BD=CE, equal included angle BDC=CED, and shared transversal FD=FD. SSS gives BFD=CFE, so BF/CF=FD/ED and angle BFC=CFE. BD/CE=1 gives FD/ED=BF/CF=1, so BF=CF. The angle equality gives F,B,C,E in that order on the transversal FC. Thus B,C,F,E are not colinear, so FD=ED. SSS gives BFD congruent CEF, hence BF=CF.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Incorrect congruence data and angle incidences."}

## C09 sample 0

The diagonals of a convex quadrilateral ABCD are perpendicular. Prove AB^2+CD^2=BC^2+DA^2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 153; finish: stop.



Let O be the intersection of the perpendicular diagonals AC and BD. Then AO^2+BO^2=AB^2, CO^2+DO^2=CD^2, BO^2+CO^2=BC^2, and AO^2+DO^2=DA^2. Subtracting gives AB^2-CD^2=AO^2-CO^2 and BC^2-DA^2=BO^2-DO^2. Adding these equations gives AB^2+CD^2=BC^2+DA^2.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": true, "note": "Four correct Pythagorean equations already imply the goal, but the explicitly claimed subtractions are false. Repairable by replacing those lines with addition."}

## C09 sample 1

The diagonals of a convex quadrilateral ABCD are perpendicular. Prove AB^2+CD^2=BC^2+DA^2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 103; finish: stop.



Let p and q be the perpendicular distances from A and C to the diagonal BD. Then AB^2=p^2+BP^2, AD^2=q^2+DP^2, CB^2=p^2+BD^2, and CD^2=q^2+BC^2. Thus AB^2+CD^2=AD^2+BC^2.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Incorrect subtractions / Pythagorean assignments."}

## C10 sample 0

ABC is a triangle with incenter I. D is the midpoint of the arc BC of its circumcircle that does not contain A. Prove DB=DC=DI.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 85; finish: stop.



The midpoint of arc BC not containing A lies on the perpendicular bisector of BC and on the bisector of the angle BIC. Hence DB=DC and DI=DB.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Claims DI=DB without the needed angle argument and introduces false tangency/bisector relations."}

## C10 sample 1

ABC is a triangle with incenter I. D is the midpoint of the arc BC of its circumcircle that does not contain A. Prove DB=DC=DI.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 93; finish: stop.



Because D is on the perpendicular bisector of BC, DB=DC. It also bisects the angle BAC, so its tangents to the circumcircle are DB and DC. Equal tangents give DI=DB. Thus DB=DC=DI.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Claims DI=DB without the needed angle argument and introduces false tangency/bisector relations."}

## C11 sample 0

Triangle ABC is right-angled at A. D is the midpoint of BC. The perpendicular from D to AC meets AC at E. Prove AE=EC and DE=AB/2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 184; finish: stop.



Right triangle ADC has midpoint D of hypotenuse BC, so DA=DC. The perpendicular from D to AC gives DE perpendicular DC, hence triangles DEA and DEC are right-angled at E. These have common hypotenuse DA=DC and common altitude DE, so are congruent. Thus AE=EC and DA^2=DE^2+EA^2=DE^2+EC^2. Since DA=AB, this gives AB^2=2DE^2, so DE=AB/sqrt(2). In right triangle ABC, Pythagoras gives AC^2=BC^2-AB^2=4DC^2-AB^2=2DE^2, so AC=2DE. Therefore AE=AC/2=DE. Both parts are proved.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "False midpoint/hypotenuse incidences and wrong DE value."}

## C11 sample 1

Triangle ABC is right-angled at A. D is the midpoint of BC. The perpendicular from D to AC meets AC at E. Prove AE=EC and DE=AB/2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 111; finish: stop.



Right triangle ABD has AD its median to hypotenuse BD. Thus AD=AB. Similarly ADBE is a right parallelogram with DE perpendicular AE, giving AE=AD=AB/2. In right triangle ADC, D is midpoint of hypotenuse BC so DC=DA. The perpendicular from D to AC gives DE=DC. Thus AE=AD=AB/2 and DE=DC=DA=AB/2.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "False midpoint/hypotenuse incidences and wrong DE value."}

## C12 sample 0

Two distinct circles intersect at A and B. The point diametrically opposite A on the first circle is C, and the point diametrically opposite A on the second is D. Assume C,D are different from B. Prove B,C,D are collinear.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 93; finish: stop.



Angle ACB subtends diameter AA', so is 90 degrees. Similarly ADB is 90 degrees. Thus A,B,C,D are not on the same circle, contradicting the two-circle assumption. Therefore C,B,D are collinear.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Misidentifies the diameter angle vertex."}

## C12 sample 1

Two distinct circles intersect at A and B. The point diametrically opposite A on the first circle is C, and the point diametrically opposite A on the second is D. Assume C,D are different from B. Prove B,C,D are collinear.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 99; finish: stop.



Angle ACB subtends diameter AA', so is 90 degrees. B lies on the first circle, hence CB is perpendicular to AB. Similarly DB is perpendicular to AB because D is the diameter opposite A on the second circle. Both C and D lie on the line perpendicular to AB at B. Since C,D are distinct, they are on the same perpendicular line. Therefore B,C,D are collinear.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": true, "note": "Correct perpendicular-line idea and conclusion, but explicitly attributes the diameter right angle to C rather than B. Repairable by correcting that angle."}

## C13 sample 0

D and E are the midpoints of BC and CA in triangle ABC. The medians AD and BE meet at G. Prove AG=2GD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 118; finish: stop.



Midpoint B,E gives AE=EC, so E divides AC in ratio 1:1. Thus B,E,A are collinear with E between B and A. Parallelism AE/EC=BE/ED=1 gives BD parallel AE. Therefore BD/AG=ED/EA=1, so AG=BD/2. But D is the midpoint of BC, so BD=BC/2. Hence AG=BC/4. Therefore AG=2GD.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Misidentifies midpoints and collinearities; does not derive the median ratio."}

## C13 sample 1

D and E are the midpoints of BC and CA in triangle ABC. The medians AD and BE meet at G. Prove AG=2GD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 71; finish: stop.



In triangle ABE, D and E are midpoints of the sides AB and AC. The midpoint theorem gives ED parallel AB. Hence GD parallel AD, and G divides AD in the same ratio AE/AC=1/2. Therefore AG=2GD.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Misidentifies midpoints and collinearities; does not derive the median ratio."}

## C14 sample 0

A convex quadrilateral has equal diagonals. Must its four vertices lie on a circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 71; finish: stop.



No. Take a parallelogram with unequal adjacent sides. Its diagonals bisect each other, and their equal halves force opposite sides to be equal. Thus this convex quadrilateral has equal diagonals without being cyclic.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Counterexample is not a noncyclic quadrilateral with equal diagonals."}

## C14 sample 1

A convex quadrilateral has equal diagonals. Must its four vertices lie on a circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 109; finish: stop.



No. Take a parallelogram with equal diagonals. This forces it to be a rectangle, and hence cyclic. Thus the answer is no.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Counterexample is not a noncyclic quadrilateral with equal diagonals."}

## C15 sample 0

A,B are distinct points. C,D are distinct points off line AB, and triangles ABC and ABD have equal (unsigned) areas. Must CD be parallel to AB? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 69; finish: stop.



The two equal areas give the same height from C and D to line AB. Hence C and D are on the two parallel lines through A and B perpendicular to AB. Therefore CD is parallel to AB.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Confuses unsigned area with signed cross product or ignores opposite sides."}

## C15 sample 1

A,B are distinct points. C,D are distinct points off line AB, and triangles ABC and ABD have equal (unsigned) areas. Must CD be parallel to AB? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 75; finish: stop.



The area equality gives (B-A) cross (C-A)= (B-A) cross (D-A). Subtracting gives (B-A) cross (C-D)=0, so C-D is parallel to AB.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": false, "note": "Confuses unsigned area with signed cross product or ignores opposite sides."}

## C16 sample 0

In an acute triangle ABC, the perpendicular from B to AC has the same length as the perpendicular from C to AB. Prove AB=AC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 108; finish: stop.



Let h_b and h_c denote the perpendiculars from B and C respectively. Equal areas give (1/2)*AC*h_b=(1/2)*AB*h_c. The common length cancels, giving AC*h_b=AB*h_c. Because h_b=BC*sin A and h_c=BC*sin C, this becomes AC*sin A=AB*sin C. The sine rule gives AB/sin C=AC/sin A, so AB=AC.<|im_end|>

Grade: {"valid": false, "method": "synthetic", "repairable": true, "note": "Correct initial area equality would solve it immediately using given equal heights; subsequent unretracted false sine relationships spoil the proof. Repairable by removing/replacing those lines."}

## C16 sample 1

In an acute triangle ABC, the perpendicular from B to AC has the same length as the perpendicular from C to AB. Prove AB=AC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 75; finish: stop.



Let h_b and h_c denote the perpendiculars from B and C to AC and AB respectively. The area of ABC is 1/2*AC*h_b=1/2*AB*h_c. Dividing gives AC/AB=h_c/h_b=1. Therefore AB=AC.<|im_end|>

Grade: {"valid": true, "method": "area", "repairable": false, "note": "Correct area equality and cancellation of equal altitudes."}
