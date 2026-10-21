"""Small, explicitly authored foundation-only SFT feasibility dataset.

24 proof structures, four labelings each. This is NOT 96 independent geometries.
The supplied plans are short mathematical strategies, not model-generated traces.
"""
import hashlib,json,re
from pathlib import Path
D=Path(__file__).resolve().parent
items=[
('sas_correspondence',
 'Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.',
 'Check the two side ratios about the equal included angle. Keep the vertex correspondence explicit.',
 'AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.'),
('aa_correspondence',
 'Triangles ABC and DEF satisfy angle BAC=DEF and angle ABC=EFD. Given AB=8, EF=12 and AC=6, find ED.',
 'Use the two angle equalities to map A to E, B to F, and C to D.',
 'AA similarity gives triangles ABC and EFD similar in that order. Hence AC/ED=AB/EF=2/3. With AC=6 we obtain ED=9.'),
('sss_correspondence',
 'Triangle ABC has AB=5, BC=6, CA=7. Triangle DEF has DE=6, EF=7, FD=5. Identify the correspondence in a congruence and the angle equal to BAC.',
 'Match vertices by the two incident side lengths, not by the order in which the triangles were named.',
 'AB=FD, BC=DE and CA=EF. The common endpoint of the length-5 and length-7 sides is A in the first triangle and F in the second. Thus A-F, B-D, C-E, and SSS gives ABC congruent to FDE. Therefore angle BAC=DFE.'),
('isosceles_median',
 'In triangle ABC, AB=AC, and D is the midpoint of BC. Prove AD is perpendicular to BC.',
 'Compare the two triangles separated by AD. Equal adjacent angles on a straight line must be right angles.',
 'AB=AC, BD=CD, and AD is common, so triangles ABD and ACD are congruent by SSS. Hence angle BDA=ADC. Since B,D,C are collinear, their sum is 180 degrees. Each is 90 degrees, proving AD perpendicular BC.'),
('perpendicular_bisector',
 'Points A and B are distinct and P lies off line AB with PA=PB. M is the midpoint of AB. Prove PM is perpendicular to AB.',
 'Use congruent triangles on the two halves of AB.',
 'In triangles PMA and PMB, PM is common, PA=PB, and MA=MB. SSS gives angle PMA=PMB. These adjacent angles sum to 180 degrees, so both are right angles. Thus PM is perpendicular to AB.'),
('same_arc_angles',
 'Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.',
 'Both angles subtend the arc AD not containing B or C.',
 'B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.'),
('opposite_cyclic_angles',
 'ABCD is a convex cyclic quadrilateral with angle ABC=73 degrees and angle BCD=108 degrees. Find angles CDA and DAB.',
 'Use opposite, not adjacent, angle pairs.',
 'Opposite angles in a cyclic quadrilateral are supplementary. Thus CDA=180-ABC=107 degrees, and DAB=180-BCD=72 degrees.'),
('central_inscribed',
 'O is the center of a circle, and the smaller central angle AOB is 100 degrees. C lies on the major arc AB. Find angle ACB.',
 'Locate the arc intercepted by the inscribed angle before halving the central angle.',
 'Since C lies on the major arc AB, angle ACB intercepts the minor arc AB, of measure 100 degrees. The inscribed-angle theorem gives ACB=50 degrees.'),
('tangent_chord_orientation',
 'A,B,C lie on a circle. AT is tangent at A, and T and B lie on opposite sides of line AC. Given angle TAC=35 degrees, find angle ABC.',
 'The side condition chooses the alternate-segment angle rather than its supplement.',
 'By the tangent-chord theorem, the angle between tangent ray AT and chord AC equals the inscribed angle on the opposite side of AC. The stipulated point B is on that side. Therefore ABC=TAC=35 degrees.'),
('chord_distance',
 'A circle with center O and radius 10 has chord AB of length 16. M is the foot of the perpendicular from O to AB. Find OM, justifying why M is the midpoint.',
 'Use right-triangle congruence to bisect the chord, then Pythagoras.',
 'Right triangles OMA and OMB have equal hypotenuses OA=OB and common leg OM. They are congruent, so AM=BM=8. Pythagoras in OMA gives OM^2=10^2-8^2=36, hence OM=6.'),
('radius_tangent',
 'P is outside a circle with center O and radius 5, with OP=13. PT is tangent at T. Find PT.',
 'A radius to a point of tangency is perpendicular to the tangent.',
 'OT is perpendicular to PT, so triangle OTP is right at T. Pythagoras gives PT^2=OP^2-OT^2=169-25=144. Thus PT=12.'),
('bisector_distances',
 'P lies strictly inside angle BAC on its internal bisector. D and E are the perpendicular projections of P onto the lines AB and AC. Prove PD=PE.',
 'The two right triangles have common hypotenuse AP and equal acute angles at A.',
 'Because P is on the internal bisector, angle DAP=PAE, each half of BAC and hence acute. The right triangles ADP and AEP have common hypotenuse AP and equal angle at A, so are congruent. The corresponding perpendicular sides PD and PE are equal.'),
('area_base_ratio',
 'In triangle ABC, D is on segment BC with BD=3 and DC=5. Find the ratio of the areas of triangles ABD and ACD.',
 'Use the common altitude from A to line BC.',
 'Let h be the perpendicular distance from A to BC. The areas are 3h/2 and 5h/2, since their bases BD and DC are on the same line. Their ratio is 3/5.'),
('parallel_scale',
 'D and E are inside AB and AC respectively in triangle ABC, and DE is parallel to BC. Given AD=4, DB=6, AE=6, BC=15, find EC and DE.',
 'Identify the similarity scale for the smaller triangle ADE.',
 'Parallelism gives angles ADE=ABC and AED=ACB, so ADE and ABC are similar with A-A,D-B,E-C. Their scale is AD/AB=4/10=2/5. Thus AC=AE*(5/2)=15, EC=15-6=9, and DE=(2/5)*BC=6.'),
('similarity_area_scale',
 'Two similar triangles have areas in the ratio 49:81. A side of the smaller triangle has length 14. Find its corresponding side in the larger triangle.',
 'Area scales as the square of the length scale.',
 'If the length scale from the larger triangle to the smaller is k, both a base and its altitude scale by k. Thus the area ratio is k^2=49/81, giving k=7/9. The corresponding larger side is 14/k=18.'),
('exterior_angle',
 'In triangle ABC, angle BAC=47 degrees and angle ABC=68 degrees. Extend BC beyond C to D. Find angle ACD.',
 'First get the interior angle at C; the extension chooses its supplement.',
 'Angle ACB=180-47-68=65 degrees. Since B,C,D are in that order, rays CB and CD are opposite, so ACD=180-65=115 degrees.'),
('common_chord_centers',
 'Two circles with different centers O and P meet at A and B. Prove OP is perpendicular to AB.',
 'Both centers are equidistant from the two common points.',
 'OA=OB and PA=PB, so both O and P lie on the perpendicular bisector of AB. Because O and P are distinct, their joining line is that perpendicular bisector. Hence OP is perpendicular to AB.'),
('diameter_angle_sum',
 'AB is a diameter of a circle and C is another point on it. Given angle BAC=37 degrees, find angle ABC.',
 'The diameter supplies a right angle at C.',
 'The angle ACB subtends diameter AB, hence equals 90 degrees. The triangle angle sum now gives ABC=180-90-37=53 degrees.'),
('two_right_triangles',
 'In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.',
 'Use the shared altitude in two different right triangles.',
 'Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.'),
('varignon_midpoints',
 'E,F,G,H are the midpoints of AB,BC,CD,DA in a convex quadrilateral ABCD. Prove EFGH is a parallelogram.',
 'Use midpoint segments in triangles cut out by the two diagonals.',
 'In triangle ABC the midpoint theorem gives EF parallel AC. In triangle ADC it gives HG parallel AC, so EF parallel HG. Likewise FG parallel BD in BCD and EH parallel BD in BAD, so FG parallel EH. Both pairs of opposite sides are parallel, proving EFGH is a parallelogram.'),
('circumscribed_quadrilateral',
 'A convex quadrilateral ABCD is circumscribed about a circle, touching its sides AB,BC,CD,DA at E,F,G,H respectively. Prove AB+CD=BC+DA.',
 'Break each side at its tangency point and pair the equal tangents from each vertex.',
 'Equal tangent segments give AE=AH, BE=BF, CF=CG, DG=DH. Thus AB+CD=AE+EB+CG+GD=AH+BF+CF+DH=AD+BC.'),
('parallel_chords',
 'A,B,C,D are distinct points in cyclic order on a circle and AB is parallel to CD. Prove AD=BC.',
 'Find equal inscribed angles by using AC as a transversal of the parallel lines.',
 'Parallelism gives angle BAC=ACD. These inscribed angles subtend chords BC and AD respectively. Equal inscribed angles subtend equal chords in the same circle, so BC=AD.'),
('invalid_bisected_diagonals',
 'A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.',
 'Bisected diagonals force a parallelogram, but not right angles. Construct a slanted parallelogram.',
 'No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.'),
('invalid_segment_order',
 'Three distinct collinear points satisfy AB=5 and BC=3. Must AC=8? Explain carefully.',
 'Lengths alone do not say whether B lies between A and C.',
 'No. On a number line take A=0, B=5, C=2. Then AB=5 and BC=3, but AC=2. If instead C=8, the same given lengths produce AC=8. The position order must be specified to add the lengths.'),
]
assert len(items)==24
letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
def relabel(text,shift):
 mapping={c:letters[(i+shift)%26] for i,c in enumerate(letters)}
 def word(m):
  w=m.group()
  return w if w in {'AA','SSS','SAS','RHS'} else ''.join(mapping[c] for c in w)
 return re.sub(r'\b[A-Z]{1,4}\b',word,text)
rows=[]
for i,(family,p,plan,a) in enumerate(items):
 for v,shift in enumerate([0,5,11,17]):
  rows.append(dict(id=f'T{i+1:02}-v{v}',family=family,problem=relabel(p,shift),plan=relabel(plan,shift),answer=relabel(a,shift),source='Codex authored and mathematically audited foundation example',label_shift=shift))
out=D/'foundation-train.json'
assert not out.exists()
out.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
(D/'training-manifest.json').write_text(json.dumps(dict(n_rows=len(rows),n_structures=len(items),variants='Four point-label permutations per structure; no increase in independent geometric diversity is claimed.',sha256=hashlib.sha256(out.read_bytes()).hexdigest(),excluded='Humpty, Dumpty, their core configurations and target proof solutions. No screen or confirmation answers are copied into training.',purpose='Bounded SFT feasibility and proof-execution pilot, not a finished foundation curriculum or evidence for target self-learning.'),indent=2)+'\n')
