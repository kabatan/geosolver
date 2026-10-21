"""Numerical variants prepared before any confirmation generation or FT.

Retains 24 structures and the same labels; replaces repeated numerical constants
with consistent, hand-specified values. Pure proof structures keep label variants.
"""
import hashlib,json,re
from fractions import Fraction as F
from pathlib import Path
D=Path(__file__).resolve().parent;R=Path('qwen/.runtime/foundation_pilot_20260923')
assert not (R/'confirmation-qwen3_4b/receipt.json').exists()
base=[r for r in json.loads((D/'foundation-train.json').read_text()) if r['label_shift']==0]
def f(x):return str(F(x))
def numeric(i,v,p,a):
 if i==1:
  k,l=[(3,5),(2,7),(4,9),(5,8)][v];q=f(F(k,l))
  p=f'Triangles ABC and DEF satisfy AB={2*k}, AC={3*k}, DE={2*l}, DF={3*l} and angle BAC=EDF. Find BC/EF, with justification.'
  a=f'AB/DE=AC/DF={q}, and the included angles at A,D are equal. SAS similarity therefore gives A-D, B-E, C-F. In particular BC/EF={q}.'
 elif i==2:
  ab,ef,ac=[(8,12,6),(6,15,4),(10,14,5),(9,12,6)][v];q=F(ab,ef);ed=F(ac)/q
  p=f'Triangles ABC and DEF satisfy angle BAC=DEF and angle ABC=EFD. Given AB={ab}, EF={ef} and AC={ac}, find ED.'
  a=f'AA similarity gives triangles ABC and EFD similar in that order. Thus AC/ED=AB/EF={f(q)}. Hence ED=AC/(AB/EF)={f(ed)}.'
 elif i==3:
  x,y,z=[(5,6,7),(4,5,6),(5,7,8),(7,8,9)][v];assert x+y>z
  p=f'Triangle ABC has AB={x}, BC={y}, CA={z}. Triangle DEF has DE={y}, EF={z}, FD={x}. Identify the correspondence in a congruence and the angle equal to BAC.'
  a=f'AB=FD, BC=DE and CA=EF. The common endpoint of the length-{x} and length-{z} sides is A in the first triangle and F in the second. Thus A-F, B-D, C-E. SSS gives ABC congruent to FDE, and angle BAC=DFE.'
 elif i==6:
  ang=[32,41,57,26][v]
  p=f'Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD={ang} degrees, find angle ACD.'
  a=f'B and C are on the same arc from A to D. Angles ABD and ACD subtend the same opposite arc AD and are equal by the inscribed-angle theorem. Therefore ACD={ang} degrees.'
 elif i==7:
  b,c=[(73,108),(65,112),(82,96),(70,105)][v]
  p=f'ABCD is a convex cyclic quadrilateral with angle ABC={b} degrees and angle BCD={c} degrees. Find angles CDA and DAB.'
  a=f'Opposite angles in a cyclic quadrilateral are supplementary. Thus CDA=180-ABC={180-b} degrees and DAB=180-BCD={180-c} degrees.'
 elif i==8:
  ang=[100,80,120,140][v]
  p=f'O is the center of a circle, and the smaller central angle AOB is {ang} degrees. C lies on the major arc AB. Find angle ACB.'
  a=f'Since C is on the major arc AB, angle ACB intercepts the minor arc AB, whose measure is {ang} degrees. The inscribed-angle theorem gives ACB={ang}/2={ang//2} degrees.'
 elif i==9:
  ang=[35,25,40,50][v]
  p=f'A,B,C lie on a circle. AT is tangent at A, and T and B lie on opposite sides of line AC. Given angle TAC={ang} degrees, find angle ABC.'
  a=f'By the tangent-chord theorem, the angle between tangent ray AT and chord AC equals the inscribed angle on the opposite side of AC. B is on that side by assumption. Thus ABC=TAC={ang} degrees.'
 elif i==10:
  radius,half,dist=[(10,8,6),(13,12,5),(17,15,8),(25,24,7)][v];assert radius**2==half**2+dist**2
  p=f'A circle with center O and radius {radius} has chord AB of length {2*half}. M is the foot of the perpendicular from O to AB. Find OM, justifying why M is the midpoint.'
  a=f'Right triangles OMA and OMB have equal hypotenuses OA=OB and common leg OM. They are congruent, so AM=BM={half}. Pythagoras gives OM^2={radius}^2-{half}^2={dist**2}. Therefore OM={dist}.'
 elif i==11:
  op,radius,leg=[(13,5,12),(17,8,15),(25,7,24),(10,6,8)][v];assert op**2==radius**2+leg**2
  p=f'P is outside a circle with center O and radius {radius}, with OP={op}. PT is tangent at T. Find PT.'
  a=f'OT is perpendicular to tangent PT, so triangle OTP is right at T. Thus PT^2=OP^2-OT^2={op**2}-{radius**2}={leg**2}, giving PT={leg}.'
 elif i==13:
  bd,dc=[(3,5),(4,7),(2,9),(5,8)][v]
  p=f'In triangle ABC, D is on segment BC with BD={bd} and DC={dc}. Find the ratio of the areas of triangles ABD and ACD.'
  a=f'Let h be the common perpendicular distance from A to line BC. The two areas are {bd}h/2 and {dc}h/2 because their bases are on the same line. Hence their ratio is {f(F(bd,dc))}.'
 elif i==14:
  ad,db,ae,bc=[(4,6,6,15),(3,6,4,12),(5,10,3,18),(6,4,9,15)][v];q=F(ad,ad+db);ac=F(ae)/q;ec=ac-ae;de=q*bc
  p=f'D and E are inside AB and AC respectively in triangle ABC, and DE is parallel to BC. Given AD={ad}, DB={db}, AE={ae}, BC={bc}, find EC and DE.'
  a=f'Parallelism gives angles ADE=ABC and AED=ACB, so triangles ADE and ABC are similar with A-A,D-B,E-C. Their scale is AD/AB={ad}/{ad+db}={f(q)}. Thus AC=AE/(AD/AB)={f(ac)}, EC=AC-AE={f(ec)}, and DE=(AD/AB)*BC={f(de)}.'
 elif i==15:
  m,n,side=[(7,9,14),(2,5,6),(3,4,9),(5,7,10)][v];big=F(side*n,m)
  p=f'Two similar triangles have areas in the ratio {m*m}:{n*n}. A side of the smaller triangle has length {side}. Find its corresponding side in the larger triangle.'
  a=f'Let k be the length scale from the larger triangle to the smaller. Both a base and its altitude scale by k, so the area ratio is k^2={m*m}/{n*n}. Thus k={f(F(m,n))}, and the larger corresponding side is {side}/k={f(big)}.'
 elif i==16:
  aa,bb=[(47,68),(36,79),(52,61),(43,82)][v];assert aa+bb<180
  p=f'In triangle ABC, angle BAC={aa} degrees and angle ABC={bb} degrees. Extend BC beyond C to D. Find angle ACD.'
  a=f'The triangle angle sum gives ACB=180-{aa}-{bb}={180-aa-bb} degrees. B,C,D are in that order, so CB and CD are opposite rays. Therefore ACD=180-ACB={aa+bb} degrees.'
 elif i==18:
  ang=[37,28,41,56][v]
  p=f'AB is a diameter of a circle and C is another point on it. Given angle BAC={ang} degrees, find angle ABC.'
  a=f'Angle ACB subtends diameter AB, hence is 90 degrees. The triangle angle sum gives ABC=180-90-{ang}={90-ang} degrees.'
 elif i==19:
  ab,bd,dc,h,ac=[(13,5,9,12,15),(10,6,15,8,17),(17,8,20,15,25),(25,7,10,24,26)][v];assert ab*ab==bd*bd+h*h and ac*ac==dc*dc+h*h
  p=f'In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB={ab}, BD={bd} and DC={dc}, find AC.'
  a=f'Triangle ADB is right at D, so AD^2=AB^2-BD^2={ab**2}-{bd**2}={h**2}. In right triangle ADC, AC^2=AD^2+DC^2={h**2}+{dc**2}={ac**2}. Therefore AC={ac}.'
 elif i==23:
  b,d,h=[(2,1,1),(3,1,2),(4,1,3),(5,2,2)][v];mx=F(b+d,2);my=F(h,2)
  a=f'No. Take A=(0,0), B=({b},0), C=({b+d},{h}), D=({d},{h}). This is a convex parallelogram, and both diagonals have midpoint ({f(mx)},{f(my)}). But AB=({b},0) and AD=({d},{h}) have dot product {b*d}, not zero. Hence angle BAD is not right, and this is not a rectangle.'
 elif i==24:
  ab,bc=[(5,3),(7,2),(8,3),(9,4)][v];assert ab>bc>0
  p=f'Three distinct collinear points satisfy AB={ab} and BC={bc}. Must AC={ab+bc}? Explain carefully.'
  a=f'No. On a number line take A=0, B={ab}, C={ab-bc}. Then AB={ab} and BC={bc}, but AC={ab-bc}. Taking C={ab+bc} instead gives the same given lengths with AC={ab+bc}. Without the order of the points, the lengths cannot simply be added.'
 return p,a

letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
def relabel(text,shift):
 mapping={c:letters[(i+shift)%26] for i,c in enumerate(letters)}
 return re.sub(r'\b[A-Z]{1,4}\b',lambda m:m[0] if m[0] in {'AA','SSS','SAS','RHS'} else ''.join(mapping[c] for c in m[0]),text)
rows=[]
for i,original in enumerate(base,1):
 for v,shift in enumerate([0,5,11,17]):
  p,a=numeric(i,v,original['problem'],original['answer'])
  rows.append(original|dict(id=f'T{i:02}-v{v}',label_shift=shift,problem=relabel(p,shift),answer=relabel(a,shift),plan=relabel(original['plan'],shift),source='Codex-authored foundation proof with checked numerical variant and bijective point relabeling'))
out=D/'foundation-train-v2.json';assert not out.exists();out.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
protocol=json.loads((D/'sft-protocol.json').read_text());protocol.update(train_file=out.name,train_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),data_version=2,data_change='Before any confirmation generation or FT: vary numerical conditions as well as labels in 17 of the 24 structures. Still 24 independent structures and 96 instances; pure proof structures keep relabeling only.')
(D/'sft-protocol-v2.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
(D/'training-manifest-v2.json').write_text(json.dumps(dict(n_structures=24,n_instances=96,n_numerical_structures=17,sha256=protocol['train_sha256'],previous_version='foundation-train.json remains for provenance but is not used for SFT',timing='Before first confirmation generation and before any weight update',excluded='Target configurations, core Humpty/Dumpty relations and evaluation solutions',not_claimed='96 independent configurations or a finished foundation curriculum'),indent=2)+'\n')
