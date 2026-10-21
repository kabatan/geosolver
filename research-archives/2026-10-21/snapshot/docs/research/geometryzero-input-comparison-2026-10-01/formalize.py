"""Source-given-only Geometry3K-style input; no answers read by formalizer."""
import hashlib, json, re
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OLD=ROOT/'qwen/.runtime/geometryzero_stage1_20260930'
RUN=ROOT/'qwen/.runtime/geometryzero_input_20261001'

def write(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def build():
    out={};facts=[]
    def start(pid):
        nonlocal facts
        facts=[];out[pid]=facts
    def add(source,*fs):
        for f in fs: facts.append({'source_given':source,'statement':f})
    def tri(): add('triangle ABC','Triangle(A,B,C)')
    def ortho(): add('H is the orthocenter; generic definition',
                     'Perpendicular(Line(A,H),Line(B,C))','Perpendicular(Line(B,H),Line(A,C))','Perpendicular(Line(C,H),Line(A,B))')
    def circ(center,points,source):
        add(source,f'Circle({center})',*[f'PointLiesOnCircle({p},Circle({center}))' for p in points])
    def on(p,a,b,source): add(source,f'PointLiesOnLine({p},Line({a},{b}))')
    def cross(p,a,b,c,d,source): on(p,a,b,source);on(p,c,d,source)
    def length(a,b,n): add(f'given length {a}{b}={n}',f'Equals(LengthOf(Line({a},{b})),{n})')
    def angle(a,b,c,n):add(f'given angle {a}{b}{c}={n} degrees',f'Equals(MeasureOf(Angle({a},{b},{c})),{n})')
    def midpoint(m,a,b):add(f'{m} is midpoint of {a}{b}',f'IsMidpointOf({m},Line({a},{b}))')
    def foot(p,h,a,b):on(p,a,b,f'{p} is foot from {h} to {a}{b}');add(f'{p} is foot from {h} to {a}{b}',f'Perpendicular(Line({h},{p}),Line({a},{b}))')
    def find(x):add('quantity asked in original question',f'Find({x})')

    start('H01');tri();ortho();midpoint('M','B','C');foot('P','H','A','M');length('B','C','12');length('A','M','10');find('LengthOf(Line(A,P))')
    start('H02');tri();midpoint('M','B','C');foot('K','A','B','C');length('B','C','16');length('A','M','10');length('A','K','8')
    for i,n in ((1,'6'),(2,'9')):
        d,u,v,z=f'D{i}',f'U{i}',f'V{i}',f'Z{i}';on(d,'B','C','Di is on BC');length('B',d,n)
        circ(f'c_ABD{i}',('A','B',d,u),'circle ABDi meets AC again at Ui');on(u,'A','C','Ui is on AC')
        circ(f'c_ACD{i}',('A','C',d,v),'circle ACDi meets AB again at Vi');on(v,'A','B','Vi is on AB')
        circ(z,('A',u,v),'Zi is center of circle AUiVi')
    find('LengthOf(Line(Z1,Z2))')
    start('H03');tri();ortho();circ('O',('A','B','C'),'O is circumcenter');length('O','H','6')
    for a,b,c in (('A','B','C'),('B','C','A'),('C','A','B')):
        k,l,m,p='K'+a.lower(),'L'+a.lower(),'M'+a.lower(),'P'+a.lower()
        on(k,b,c,'internal angle bisector meets opposite line at K');on(l,b,c,'external angle bisector meets opposite line at L')
        add('internal angle bisector',f'BisectsAngle(Line({a},{k}),Angle({b},{a},{c}))')
        midpoint(m,b,c);circ(f'c_{a}KL',(a,k,l,p),'circle AKL meets AM again at P');on(p,a,m,'P on AM')
    circ('Z',('Pa','Pb','Pc'),'Z center of circle PaPbPc');find('LengthOf(Line(O,Z))')
    start('H04');tri();ortho();midpoint('M','B','C');foot('P','H','A','M');on('T','B','C','T intersection with BC')
    add('T on perpendicular bisector of AP','IsPerpendicularBisectorOf(Line(bisector_AP),Line(A,P))','PointLiesOnLine(T,Line(bisector_AP))')
    length('B','T','2');length('B','C','6');find('LengthOf(Line(A,T))')
    start('H07');add('triangle NAB','Triangle(N,A,B)')
    circ('c1',('A','M','N','C'),'first circle through its tangency and intersection points');circ('c2',('B','M','N','D'),'second circle through its tangency and intersection points')
    add('circles tangent to AB at A,B','Tangent(Line(A,B),Circle(c1))','Tangent(Line(A,B),Circle(c2))')
    on('M','C','D','line CD through M');add('CD parallel AB','Parallel(Line(C,D),Line(A,B))')
    cross('E','A','C','B','D','E=AC intersection BD');cross('P','A','N','C','D','P=AN intersection CD');cross('Q','B','N','C','D','Q=BN intersection CD');midpoint('O','A','B');foot('F','M','A','B')
    length('A','B','8');length('O','N','8*sqrt(10)/5');length('M','F','3');find('AreaOf(Triangle(E,P,Q))')
    start('H08');add('triangle APQ','Triangle(A,P,Q)');circ('c1',('P','A','B'),'first circle tangent at P and intersections A,B');circ('c2',('Q','A','B'),'second circle tangent at Q and intersections A,B')
    add('circles tangent to PQ','Tangent(Line(P,Q),Circle(c1))','Tangent(Line(P,Q),Circle(c2))')
    add('C reflection of B in PQ; generic definition','IsPerpendicularBisectorOf(Line(P,Q),Line(B,C))')
    length('A','P','6');length('A','C','3*sqrt(34)/2');add('tan angle BAQ=3/5','Equals(TanOf(Angle(B,A,Q)),3/5)');find('AreaOf(Triangle(A,P,C))')
    start('H12');add('quadrilateral ABCD','Quadrilateral(A,B,C,D)','Equals(MeasureOf(Angle(A,B,C)),MeasureOf(Angle(A,D,C)))')
    on('E','A','C','E on AC');on('F','A','C','F on AC');add('internal angle bisectors BE,DF','BisectsAngle(Line(B,E),Angle(A,B,C))','BisectsAngle(Line(D,F),Angle(A,D,C))')
    cross('P','B','E','D','F','P=BE intersection DF');midpoint('M','A','C');circ('c_BPD',('B','P','D','X','Y'),'circle BPD meets BM and DM again at X,Y');on('X','B','M','X on BM');on('Y','D','M','Y on DM');cross('Q','X','E','Y','F','Q=XE intersection YF');foot('V','P','A','C')
    length('P','M','sqrt(29)/2');length('P','V','5/2');length('Q','M','sqrt(101)');find('LengthOf(Line(P,Q))')
    start('H13');tri();length('B','C','6');add('cos angle ACB=3/5','Equals(CosOf(Angle(A,C,B)),3/5)');midpoint('M','A','C');circ('c_BMC',('B','M','C'),'circle BMC')
    add('CK tangent at C; BK perpendicular BC','Tangent(Line(C,K),Circle(c_BMC))','Perpendicular(Line(B,K),Line(B,C))');length('B','K','24');cross('J','A','K','B','M','J=AK intersection BM');circ('Z',('B','J','K'),'Z center of circle BJK');find('LengthOf(Line(C,Z))')
    start('DA01');tri();length('A','B','7');length('B','C','8');length('C','A','9');circ('c1',('A','B','T'),'first circle through A,B,T');circ('c2',('A','C','T'),'second circle through A,C,T');add('tangencies at A','Tangent(Line(A,C),Circle(c1))','Tangent(Line(A,B),Circle(c2))');find('LengthOf(Line(A,T))')
    start('DA02');tri();angle('B','A','C','60');length('A','B','10');length('A','C','8');angle('A','T','B','120');angle('B','T','C','120');angle('C','T','A','120');add('G centroid','IsCentroidOf(G,Triangle(A,B,C))');circ('c_BTC',('B','T','C','K'),'K intersection with circle BTC');on('K','T','G','K on TG');find('LengthOf(Line(T,K))')
    start('DA03');tri();circ('O',('A','B','C'),'O circumcenter');circ('c1',('A','C','T'),'circle through A,C tangent at A meets BOC at T');add('tangent at A to AB','Tangent(Line(A,B),Circle(c1))');circ('c_BOC',('B','O','C','T'),'circle BOC contains T');cross('K','T','O','B','C','K=TO intersection BC');length('B','C','32');length('B','K','49');find('LengthOf(Line(A,K))')
    start('DA04');circ('c_Omega',('A','B','X','Y'),'circle Omega contains chord AB and intersections X,Y');on('P','A','B','P interior AB');length('A','P','3');length('P','B','8');circ('c1',('A','P','Q'),'first inner circle');circ('c2',('B','P','Q'),'second inner circle');on('X','P','Q','X on PQ');on('Y','P','Q','Y on PQ');length('X','Y','14');find('LengthOf(Line(P,Q))')
    start('DA05');tri();length('B','C','12');circ('c1',('A','B','D'),'circle omega1 contains A,B,D');circ('c2',('C','B','D'),'circle omega2 contains C,B,D');add('given tangencies','Tangent(Line(B,C),Circle(c1))','Tangent(Line(B,A),Circle(c2))');midpoint('M','B','C');cross('E','M','D','A','C','E=MD intersection AC');length('M','D','4');find('LengthOf(Line(D,E))')
    start('DA06');tri();circ('O',('A','B','C'),'O circumcenter');midpoint('M','B','C');circ('c1',('A','B','D'),'omega1 through A,B,D');circ('c2',('A','C','D','E'),'omega2 through A,C,D,E');add('given tangencies at A','Tangent(Line(A,C),Circle(c1))','Tangent(Line(A,B),Circle(c2))');on('E','A','M','E on AM');length('A','O','5');length('A','D','4');find('LengthOf(Line(O,E))')
    start('DA07');tri();ortho();circ('O',('A','B','C'),'O circumcenter');circ('c_BOC',('B','O','C','M','X'),'circle BOC contains M,X');circ('c_BHC',('B','H','C','N','Y'),'circle BHC contains N,Y');circ('c_AO',('A','O','M'),'circle with diameter AO');circ('c_AH',('A','H','N'),'circle with diameter AH');add('given diameters','IsDiameterOf(Line(A,O),Circle(c_AO))','IsDiameterOf(Line(A,H),Circle(c_AH))');on('X','A','M','X on AM');on('Y','A','N','Y on AN');length('A','M','4');length('M','X','23');length('M','N','8/3');find('LengthOf(Line(X,Y))')
    start('DA08');tri();circ('O',('A','B','C'),'O circumcenter');circ('c_BOC',('B','O','C','Q'),'Q on circle BOC');add('Q antipodal to O','IsDiameterOf(Line(O,Q),Circle(c_BOC))');on('M','C','Q','M on CQ');add('line AM parallel BC','Parallel(Line(A,M),Line(B,C))','Parallelogram(A,N,C,M)');cross('T','A','Q','M','N','T=AQ intersection MN');length('O','Q','25');length('Q','T','24');find('LengthOf(Line(O,T))')
    start('DB01');tri();circ('O',('A','B','C'),'O circumcenter');circ('J',('A','P','Q','Y'),'omega centered J contains A,P,Q and tangency Y');add('J on altitude from A to BC','Perpendicular(Line(A,J),Line(B,C))');on('P','A','B','P on AB');on('Q','A','C','Q on AC');add('given BP*CQ=AP*AQ','Equals(Mul(LengthOf(Line(B,P)),LengthOf(Line(C,Q))),Mul(LengthOf(Line(A,P)),LengthOf(Line(A,Q))))');circ('U',('B','O','C','Z'),'U center of circle BOC; Z tangency point');length('J','A','1');length('U','B','4');add('common tangent at Y,Z','Tangent(Line(Y,Z),Circle(J))','Tangent(Line(Y,Z),Circle(U))');find('LengthOf(Line(Y,Z))')
    start('DB02');tri();length('A','B','7');length('A','C','11');length('B','C','12');on('P','B','C','P interior BC');on('Q','B','C','Q interior BC');add('given equal angles','Equals(MeasureOf(Angle(P,A,B)),MeasureOf(Angle(B,C,A)))','Equals(MeasureOf(Angle(C,A,Q)),MeasureOf(Angle(A,B,C)))');midpoint('P','A','M');midpoint('Q','A','N');cross('X','B','M','C','N','X=BM intersection CN');find('LengthOf(Line(B,X))')
    start('DB03');tri();angle('B','A','C','60');length('B','C','7');circ('c_Gamma',('A','B','C','M','T'),'circumcircle Gamma contains arc midpoint M,T');on('T','M','I_b','T on M I_b');add('given TB+TC=13','Equals(SumOf(LengthOf(Line(T,B)),LengthOf(Line(T,C))),13)');find('LengthOf(Line(T,I_b))')
    start('DB04');circ('c1',('A','B','D','E','X'),'omega1 contains these points');circ('c2',('A','B','C','F','Y'),'omega2 contains these points');add('given tangent lines at A','Tangent(Line(A,C),Circle(c1))','Tangent(Line(A,D),Circle(c2))');on('F','A','E','E,F on internal bisector line');add('internal bisector of CAD','BisectsAngle(Line(A,E),Angle(C,A,D))');on('Y','A','X','X,Y on external bisector line');midpoint('K','X','Y');length('E','F','6');length('A','K','4');circ('c_BEF',('B','E','F'),'circumcircle of requested triangle BEF');find('RadiusOf(Circle(c_BEF))')
    start('DB06');add('cyclic quadrilateral ABCD','Quadrilateral(A,B,C,D)');circ('c0',('A','B','C','D'),'ABCD inscribed in circle')
    for a,b,n in [('A','B','4'),('B','C','5'),('C','D','10'),('D','A','8'),('A','C','12'),('B','D','40/3')]:add(f'given {a}{b} squared={n}',f'Equals(SquareOf(LengthOf(Line({a},{b}))),{n})')
    on('X','B','D','X interior BD');on('Y','A','C','Y interior AC');add('given angle equalities','Equals(MeasureOf(Angle(B,A,C)),MeasureOf(Angle(X,A,D)))','Equals(MeasureOf(Angle(B,C,A)),MeasureOf(Angle(X,C,D)))','Equals(MeasureOf(Angle(C,B,D)),MeasureOf(Angle(Y,B,A)))','Equals(MeasureOf(Angle(C,D,B)),MeasureOf(Angle(Y,D,A)))');find('SquareOf(LengthOf(Line(X,Y)))')
    start('DB08');tri();circ('O',('A','B','C','K','L'),'Gamma circumcircle contains K,L');add('AP tangent at A','Tangent(Line(A,P),Circle(O))');on('P','B','C','P on BC');foot('X','A','O','P');on('E','A','B','E on AB');on('F','A','C','F on AC');add('given angle equalities','Equals(MeasureOf(Angle(E,X,P)),MeasureOf(Angle(A,C,X)))','Equals(MeasureOf(Angle(F,X,O)),MeasureOf(Angle(A,B,X)))');on('K','E','F','K on EF');on('L','E','F','L on EF');circ('U',('K','L','X','Y','Z'),'sigma center U through K,L,X and intersections Y,Z');on('Y','P','U','Y on PU');on('Z','P','U','Z on PU');length('P','Y','3');length('Y','Z','9');find('LengthOf(Line(P,X))')
    start('DB10');tri();angle('B','A','C','60');add('area ABC=31','Equals(AreaOf(Triangle(A,B,C)),31)');add('equilateral ABK,ACL','Equilateral(Triangle(A,B,K))','Equilateral(Triangle(A,C,L))');cross('S','C','K','A','B','S=CK intersection AB');cross('R','B','L','A','C','R=BL intersection AC');cross('T','B','L','C','K','T=BL intersection CK');circ('c_BSK',('B','S','K'),'circle BSK');circ('c_CLR',('C','L','R'),'circle CLR');circ('c_BTC',('B','T','C'),'circle BTC');midpoint('M','B','C');add('given AZ:ZM=12:19','Equals(RatioOf(LengthOf(Line(A,Z)),LengthOf(Line(Z,M))),12/19)');find('AreaOf(Triangle(A,Z,B))')
    start('DB12');tri();angle('B','A','C','45');length('B','C','13')
    for i,ratio in ((1,'1/2'),(2,'2')):
        d,e,f=f'D{i}',f'E{i}',f'F{i}';on(d,'B','C','Di divides BC internally');add('given division ratio',f'Equals(RatioOf(LengthOf(Line(B,{d})),LengthOf(Line({d},C))),{ratio})');on(e,'A','C','Ei on AC');on(f,'A','B','Fi on AB');add('given parallel lines',f'Parallel(Line({d},{e}),Line(A,B))',f'Parallel(Line({d},{f}),Line(A,C))');circ(f'c_AEF{i}',('A',e,f,'X'),'X second common point of circles AEiFi')
    add('given BX+CX=17','Equals(SumOf(LengthOf(Line(B,X)),LengthOf(Line(C,X))),17)');find('LengthOf(Line(A,X))')
    return out

def main():
    old_jobs=json.loads((OLD/'jobs.json').read_text())
    # Obtain original actor prompt, never labels or a proof reference.
    english={j['problem_id']:j['messages'][0]['content'].split('Geometry specification and question:\n',1)[1].split('\nOutput the thinking process',1)[0] for j in old_jobs}
    formal=build();assert list(formal)==list(english)
    defs=(HERE/'upstream/InterGPS__predicates.md').read_text()
    allowed=set(re.findall(r'`([A-Za-z]+)`',defs))
    audit=[];jobs=[];fmt='Output the thinking process in <think> </think> and final answer (number) in <answer> </answer> tags.'
    extra={'without':'','with':' You must edit the line instances to construct auxiliary lines in the thinking process, which should be marked with <auxiliary> </auxiliary> tags.','main':' You have a coin flip decision to make, whether to edit the line instances to construct auxiliary lines in the thinking process, which should be marked with <auxiliary> </auxiliary> tags.'}
    for j in old_jobs:
        pid=j['problem_id'];group=j['group'];fs=formal[pid]
        statements=[f['statement'] for f in fs]
        unknown=set(re.findall(r'([A-Za-z]+)\(', '\n'.join(statements)))-allowed-{'sqrt'};assert not unknown,(pid,unknown)
        lines=list(dict.fromkeys(re.findall(r'Line\(([A-Za-z0-9_]+),([A-Za-z0-9_]+)\)','\n'.join(statements))))
        code='\n'.join(statements)+'\nThe line instances are: '+', '.join(a+b for a,b in lines)
        prompt=english[pid]+'  '+fmt+extra[group]+'\n\n\nHere is the logic form for the geometry problem:```\n'+code+'\n```'
        for seed in (1,2):
            jobs.append(dict(id=f'{pid}-logic-s{seed}-{group}',problem_id=pid,group=group,arm='logic',replicate=seed,messages=[dict(role='user',content=prompt)],seed=j['seed']+(1000000 if seed==2 else 0)))
            if seed==2:jobs.append(dict(j,id=f'{pid}-text-s2-{group}',arm='text',replicate=2,seed=j['seed']+1000000))
        if group=='main':audit.append(dict(id=pid,problem_en=english[pid],facts=fs,line_instances=[a+b for a,b in lines],unencoded_given_policy='All original English givens remain verbatim. No inferred target relation is supplied.'))
    # Stable order by replicate/arm/problem/group for reproducible actors.
    ids=list(english);groups=['without','with','main']
    jobs.sort(key=lambda j:(j['replicate'],j['arm'],ids.index(j['problem_id']),groups.index(j['group'])))
    write(RUN/'jobs.json',jobs);write(HERE/'formalization-audit.json',audit)
    write(HERE/'freeze.json',dict(jobs=sha(RUN/'jobs.json'),formalizer=sha(__file__),protocol=sha(HERE/'PROTOCOL.md'),old_jobs=sha(OLD/'jobs.json'),old_selection=sha(ROOT/'docs/research/geometryzero-stage1-2026-09-30/selection.json'),questions=ids,new_groups=len(jobs),new_answers=len(jobs)*8))
    print(json.dumps(dict(questions=len(ids),new_groups=len(jobs),new_answers=len(jobs)*8)))

if __name__=='__main__':main()
