"""Freeze additional foundation questions before any adapter training."""
import hashlib
import json
from pathlib import Path

D = Path(__file__).resolve().parent
suffix = '\nGive a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.'
items = [
 ('C01','angle_bisector_parallel',
  'In triangle ABC, AB=6, AC=9, and BC=10. The internal bisector of angle BAC meets BC at D. Through D draw the line parallel to AB, meeting AC at E. Find AE.',
  'BD/DC=2/3, so CD/CB=3/5. CDE is similar to CBA, hence CE=27/5 and AE=18/5.'),
 ('C02','incenter_angle',
  'In triangle ABC, angle BAC=48 degrees. The internal bisectors of angles ABC and ACB meet at I. Find angle BIC.',
  'Angle IBC+ICB=(180-48)/2=66 degrees, so BIC=114 degrees.'),
 ('C03','kite_bisector',
  'ABCD is a convex quadrilateral with AB=BC and AD=DC. Prove that its diagonals AC and BD are perpendicular.',
  'B and D both lie on the perpendicular bisector of AC because each is equidistant from A,C. Thus BD is that perpendicular bisector.'),
 ('C04','parallelogram_midpoint',
  'ABCD is a nondegenerate parallelogram, E is the midpoint of AB, and lines DE and AC meet at F. Find AF/FC.',
  'A,E,B and D,F,E have the stated interior intersection; AFE and CFD are similar since AE parallel CD and vertical angles at F. AF/FC=AE/CD=1/2.'),
 ('C05','diameter_three_tangents',
  'AB is a diameter of a circle with center O. C is another point on the circle. The tangent at C meets the tangents at A and B at X and Y, respectively. Prove that angle XOY=90 degrees.',
  'RHS congruence of OAX,OCX shows OX bisects AXC; similarly OY bisects BYC. C lies between X,Y and XA,YB are parallel. Thus X+Y=180 degrees in the tangent strip; in triangle XOY the X,Y angles sum to 90. Alternatively normalize A=(-1,0),B=(1,0),C=(c,s), c²+s²=1,s nonzero; X=(-1,(1+c)/s),Y=(1,(1-c)/s), whose dot product is zero.'),
 ('C06','equilateral_area_partition',
  'ABC is an equilateral triangle of altitude h. P is strictly inside the triangle, and its perpendicular distances to lines AB, BC, CA are x,y,z. Prove that x+y+z=h.',
  'Join P to all vertices. Add areas PAB,PBC,PCA: s(x+y+z)/2=sh/2.'),
 ('C07','incircle_tangent_system',
  'Triangle ABC has AB=13, AC=14, BC=15. Its incircle touches BC at D. Find BD.',
  'Let the equal tangent lengths from A,B,C be x,y,z. x+y=13,x+z=14,y+z=15, giving y=7. Thus BD=7.'),
 ('C08','isosceles_two_cevians',
  'In an isosceles triangle ABC with AB=AC, D is strictly inside AB and E is strictly inside AC, with BD=CE. Let F be the intersection of BE and CD. Prove BF=CF.',
  'AD=AE. SAS triangles ABE,ACD give BE=CD. Then SSS triangles CBE,BCD (CB common,CE=BD,BE=CD) give angle CBE=BCD. These are the base angles of BFC, so BF=CF.'),
 ('C09','orthodiagonal_pythagoras',
  'The diagonals of a convex quadrilateral ABCD are perpendicular. Prove AB^2+CD^2=BC^2+DA^2.',
  'At intersection P, expand each side square in right triangles. Both sums equal PA²+PB²+PC²+PD².'),
 ('C10','arc_midpoint_incenter',
  'ABC is a triangle with incenter I. D is the midpoint of the arc BC of its circumcircle that does not contain A. Prove DB=DC=DI.',
  'Equal arcs give DB=DC and A,I,D collinear. Write angles A=alpha,B=beta,C=gamma. DBC=alpha/2, DBI=(alpha+beta)/2. AIB=90+gamma/2; A,I,D in order gives BID=90-gamma/2=(alpha+beta)/2. Thus DB=DI.'),
 ('C11','right_midpoint_projection',
  'Triangle ABC is right-angled at A. D is the midpoint of BC. The perpendicular from D to AC meets AC at E. Prove AE=EC and DE=AB/2.',
  'DE parallel AB. Thus CDE similar CBA, CD/CB=1/2 gives CE=CA/2,DE=AB/2.'),
 ('C12','two_diameters',
  'Two distinct circles intersect at A and B. The point diametrically opposite A on the first circle is C, and the point diametrically opposite A on the second is D. Assume C,D are different from B. Prove B,C,D are collinear.',
  'ABC and ABD are right at B by their respective diameters. Both BC and BD are the unique line through B perpendicular to BA.'),
 ('C13','median_ratio',
  'D and E are the midpoints of BC and CA in triangle ABC. The medians AD and BE meet at G. Prove AG=2GD.',
  'Let F be the midpoint of AB. EF parallel BC,EF=BC/2=BD and EF parallel BD. A quadrilateral E F B D need not be used. Simpler: DE parallel BA and DE=BA/2; triangles GDE and GAB are similar with GD/GA=DE/AB=1/2.'),
 ('C14','invalid_equal_diagonals',
  'A convex quadrilateral has equal diagonals. Must its four vertices lie on a circle? Prove the assertion or give an explicit counterexample.',
  'No. A=(0,0),B=(2,1),C=(4,0),D=(2,-3) is convex and AC=BD=4. At their intersection P=(2,0), PA*PC=4 but PB*PD=3, contradicting intersecting-chord power if cyclic. Or circle ABC has center(2,-3/2),radius5/2 and does not contain D.'),
 ('C15','invalid_equal_area_sides',
  'A,B are distinct points. C,D are distinct points off line AB, and triangles ABC and ABD have equal (unsigned) areas. Must CD be parallel to AB? Prove the assertion or give an explicit counterexample.',
  'No: A=(0,0),B=(2,0),C=(0,1),D=(1,-1). Both areas equal1 but CD has slope-2, not horizontal. The same-side assumption is missing.'),
 ('C16','altitude_area_converse',
  'In an acute triangle ABC, the perpendicular from B to AC has the same length as the perpendicular from C to AB. Prove AB=AC.',
  'Compute twice the area as AC*h_B=AB*h_C. The equal nonzero altitudes cancel.'),
]
out = D / 'confirmation-jobs.json'
assert not out.exists(), 'Confirmation is frozen; do not overwrite.'
rows = [dict(id=i,skill=s,problem=p+suffix,reference=r,stratum='foundation_confirmation',training_eligible=False) for i,s,p,r in items]
out.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
(D/'confirmation-freeze.json').write_text(json.dumps(dict(jobs_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),n=len(rows),timing='Before any foundation SFT in this pilot',scope='Additional held-out problems, not a representative random sample. Basic concepts necessarily overlap; no claims of disjointness from pretraining.'),indent=2)+'\n')
