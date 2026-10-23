"""Direct statement-to-DSL authoring. No geometry evaluation or solver imports."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from source_plan import SELECTED, TRANSCRIPTIONS, identifier

HERE = Path(__file__).resolve().parent

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class Case:
    def __init__(self, cid, variables, gauge):
        self.dsl = dict(id=cid, variables=variables.split(), constructions=[], conditions=[], target='')
        self.mapping = []
        self.gauge = gauge
        self.notes = []

    def c(self, name, expr, clause):
        i=len(self.dsl['constructions'])
        self.dsl['constructions'].append(dict(name=name, expression=expr))
        self.mapping.append(dict(path=f'constructions[{i}]',source_clause=clause,expression=expr))

    def rel(self, lhs, op, rhs, clause):
        i=len(self.dsl['conditions'])
        self.dsl['conditions'].append(dict(left=lhs,operator=op,right=rhs))
        self.mapping.append(dict(path=f'conditions[{i}]',source_clause=clause,expression=f'{lhs} {op} {rhs}'))

    def eq(self,lhs,rhs,clause): self.rel(lhs,'=',rhs,clause)
    def gt(self,lhs,rhs,clause): self.rel(lhs,'>',rhs,clause)
    def interval(self,v,lo,hi,clause,closed=False):
        self.rel(v,'>=' if closed else '>',lo,clause)
        self.rel(v,'<=' if closed else '<',hi,clause)

    def pred(self,expr,clause):
        i=len(self.dsl['conditions'])
        self.dsl['conditions'].append(dict(predicate=expr))
        self.mapping.append(dict(path=f'conditions[{i}]',source_clause=clause,expression=expr))

    def target(self,expr,clause):
        self.dsl['target']=expr
        self.mapping.append(dict(path='target',source_clause=clause,expression=expr))
        return self

def point(c,n,x,y,why): c.c(n,f'Point({x}, {y})',why)
def regular(c,names):
    n=len(names)
    for i,name in enumerate(names):
        point(c,name,f'cos(2*pi*{i}/{n})',f'sin(2*pi*{i}/{n})',f'正{n}角形の中心角の定義。中心原点、半径1。')

def cross(a,b,p):
    return f'({b}.x-{a}.x)*({p}.y-{a}.y)-({b}.y-{a}.y)*({p}.x-{a}.x)'

def definitions():
    out=[]
    c=Case('HMMT-2010-FEB-GUTS-13','ax ay bx by cx cy','原文のxy座標を保持。頂点の任意ラベルA,B,Cを導入し、尺度・原点・回転を変えない。')
    for n in 'ABC': point(c,n,n.lower()+'x',n.lower()+'y','未知三角形の頂点')
    for axis,lo,hi in [('x',1,5),('y',8,13)]:
        c.eq(f'min(a{axis}, b{axis}, c{axis})',lo,'軸への射影線分の端点')
        c.eq(f'max(a{axis}, b{axis}, c{axis})',hi,'軸への射影線分の端点')
    c.eq('min((ax+ay)/2, (bx+by)/2, (cx+cy)/2)',5,'y=xへの直交射影の座標の定義と下端(5,5)')
    c.eq('max((ax+ay)/2, (bx+by)/2, (cx+cy)/2)','15/2','同上、上端(7.5,7.5)。15/2は原文7.5の正確な表記。')
    c.gt('Area(A,B,C)',0,'非退化な三角形')
    out.append(c.target('Area(A,B,C)','三角形の面積'))

    c=Case('HMMT-2011-FEB-GUTS-01','b x y u v','B=(0,0), C=(b,0), b>0, Aは上半平面。剛体変換と鏡映だけ。面積1なので尺度固定しない。')
    point(c,'B',0,0,'座標固定'); point(c,'C','b',0,'座標固定'); point(c,'A','x','y','未知頂点')
    c.c('D','PointOnSegment(A,B,u)','DはAB上'); c.c('E','PointOnSegment(A,C,v)','EはAC上')
    c.c('F','Reflect(A,Line(D,E))','Aの直線DEに関する鏡像')
    c.eq('Area(A,B,C)',1,'面積1'); c.eq('Parallel(Line(D,E),Line(B,C))',0,'DEとBCは平行')
    c.eq('Distance(D,E)/Distance(B,C)','1/3','DE/BC=1/3')
    c.gt('b',0,'BC>0'); c.gt('y',0,'非退化・鏡映固定')
    c.interval('u',0,1,'DはAB上',True); c.interval('v',0,1,'EはAC上',True)
    out.append(c.target('Area(F,B,C)','FBCの面積'))

    c=Case('HMMT-2012-FEB-GUTS-06','ex ey','ABをx軸、ADをy軸に置く。長さ20,12は原文どおり。')
    for n,x,y in [('A',0,0),('B',20,0),('C',20,12),('D',0,12),('Z',20,'12+18'),('E','ex','ey')]:
        point(c,n,x,y,'長方形ABCD、BCのC側への延長CZ=18、内部点Eの定義')
    c.c('X','IntersectLines(Line(E,Z),Line(A,B))','EZとABの交点')
    c.c('Y','IntersectLines(Line(E,Z),Line(C,D))','EZとCDの交点')
    c.eq('Distance(E,Line(A,B))',6,'EからABの垂直距離6'); c.eq('Distance(E,Line(A,D))',6,'EからADの垂直距離6')
    c.interval('ex',0,20,'Eは長方形内部'); c.interval('ey',0,12,'Eは長方形内部')
    out.append(c.target('Area(A,X,Y,D)','四角形AXYDの面積'))

    c=Case('HMMT-2013-FEB-GUTS-01','k','原文の座標を保持。差4の任意の2マーカーの差ベクトルは(4,4k)なのでn=1と1+4を代表として用いる。整数変数を導入しない。')
    for n,x in [('U','1'),('V','1+4'),('P','7'),('Q','19')]: point(c,n,x,f'({x})*k','マーカー(n,nk)の定義')
    c.gt('k',0,'kは正の実数'); c.eq('Distance(U,V)',31,'x座標差4のマーカー間距離31')
    out.append(c.target('Distance(P,Q)','(7,7k)と(19,19k)の距離'))

    c=Case('HMMT-2014-FEB-GUTS-03','','面積比なので中心を原点、外接半径を1に固定できる。')
    regular(c,list('ABCDEF')); c.c('P','Incircle(B,D,F)','BDFの内接円')
    out.append(c.target('pi*Radius(P)**2/Area(A,B,D,E)','円Pの面積/長方形ABDEの面積'))

    c=Case('HMMT-2015-FEB-GUTS-24','cx cy dx dy wx wy r','A=(0,0), B=(10,0)。Dを上半平面に置く鏡映固定。尺度は変更しない。円omegaが四角形に内包されるとは追加しない。')
    for n,x,y in [('A',0,0),('B',10,0),('C','cx','cy'),('D','dx','dy'),('W','wx','wy')]: point(c,n,x,y,'原文の点、接円の未知中心W')
    c.c('Gamma','Circumcircle(A,B,C)','ABCDの共円条件のための円ABC')
    for a,b,length in [('B','C',8),('C','D',25),('D','A',12)]: c.eq(f'Distance({a},{b})',length,f'{a}{b}={length}')
    c.eq('Distance(Center(Gamma),D)','Radius(Gamma)','Dも円ABC上')
    for i,(a,b) in enumerate([('D','A'),('A','B'),('B','C')]):
        t=f'T{i}'; c.c(t,f'FootOfPerpendicular(Line({a},{b}),W)',f'接点は中心Wから{a}{b}への垂足')
        c.eq(f'Distance(W,{t})','r',f'半径rの円が直線{a}{b}に接する')
        dot=f'({t}.x-{a}.x)*({b}.x-{a}.x)+({t}.y-{a}.y)*({b}.y-{a}.y)'
        c.interval(dot,0,f'Distance({a},{b})**2',f'接点が線分{a}{b}上（延長線ではない）',True)
    c.pred('ConvexPolygon([A,B,C,D])','通常の非自己交差な共円四角形の頂点順'); c.gt('dy',0,'鏡映固定'); c.gt('r',0,'円の半径は正')
    out.append(c.target('r','接円omegaの半径'))

    c=Case('HMMT-2016-FEB-GUTS-14','cx cy','A=(0,0), B=(13,0), Cは上半平面。剛体変換と鏡映のみ。')
    point(c,'A',0,0,'座標固定'); point(c,'B',13,0,'AB=13'); point(c,'C','cx','cy','未知頂点C')
    c.eq('Distance(B,C)',14,'BC=14'); c.eq('Distance(C,A)',15,'CA=15'); c.gt('cy',0,'非退化・鏡映固定')
    c.c('E','FootOfPerpendicular(Line(A,C),B)','BからACへの垂足'); c.c('F','FootOfPerpendicular(Line(A,B),C)','CからABへの垂足')
    c.c('omega','Circumcircle(A,E,F)','AEFの外接円')
    for p in ['A','E','F']: c.c('l'+p,f'PerpendicularLine(Line(Center(omega),{p}),{p})','接線は接点の半径に垂直な直線という定義')
    for p,l,m in [('U','lA','lE'),('V','lE','lF'),('W','lF','lA')]: c.c(p,f'IntersectLines({l},{m})','指定3接線の交点')
    out.append(c.target('Area(U,V,W)','3接線が囲む三角形の面積'))

    c=Case('HMMT-2017-FEB-GUTS-02','t zx zy','X=(0,0), Y=(t,0), t>0, Zは上半平面。指定線分順序と長さを単位方向ベクトルで直接構成する。')
    for n,x,y in [('X',0,0),('Y','t',0),('Z','zx','zy'),('A',-3,0),('D','t+10',0)]: point(c,n,x,y,'AX=3, DY=10, A-X-Y-Dの順序')
    point(c,'B','-2*zx/Distance(X,Z)','-2*zy/Distance(X,Z)','BX=2, B-X-Zの順序')
    point(c,'E','zx+16*zx/Distance(X,Z)','zy+16*zy/Distance(X,Z)','EZ=16, 円周上の順序よりB-X-Z-E')
    point(c,'C','t+4*(t-zx)/Distance(Y,Z)','-4*zy/Distance(Y,Z)','CY=4, C-Y-Zの順序')
    point(c,'F','zx+12*(zx-t)/Distance(Y,Z)','zy+12*zy/Distance(Y,Z)','FZ=12, 円周上の順序よりC-Y-Z-F')
    c.c('omega','Circumcircle(A,B,C)','原文の共通円')
    for p in 'DEF': c.eq(f'Distance(Center(omega),{p})','Radius(omega)','6頂点が同一円周上')
    c.gt('t',0,'X,Yの順序'); c.gt('zy',0,'非退化・鏡映固定'); c.pred('ConvexPolygon([A,B,C,D,E,F])','A,B,C,D,E,Fの円周順序')
    out.append(c.target('Distance(X,Y)+Distance(Y,Z)+Distance(Z,X)','三角形XYZの周長'))

    c=Case('HMMT-2018-FEB-GUTS-01','s','正方形を軸に沿わせる。辺長sは未知。原図の中線による四等分をそのまま構成。')
    for n,x,y in [('A',0,0),('B','s',0),('C','s','s'),('D',0,'s')]: point(c,n,x,y,'外側の正方形')
    for n,a,b in [('O','A','C'),('M','A','B'),('N','B','C'),('P','C','D'),('Q','D','A')]: c.c(n,f'Midpoint({a},{b})','原図の中点・中心')
    for points in ['A,M,O,Q','M,B,N,O','O,N,C,P','Q,O,P,D']: c.eq(f'Area({points})',1,'4つの合同な小正方形は各面積1')
    c.gt('s',0,'正方形の辺長は正')
    out.append(c.target('Area(A,B,C,D)','外側の正方形の面積'))

    c=Case('HMMT-2019-FEB-GUTS-17','ax ay t1 t2 u1 u2 v1 v2 px py s','B=(0,0), C=(4,0), Aは上半平面。Pを内心とする解法は入力に使用しない。')
    point(c,'B',0,0,'座標固定');point(c,'C',4,0,'BC=4');point(c,'A','ax','ay','未知頂点');point(c,'P','px','py','原文で存在する点P')
    c.eq('Distance(A,B)',3,'AB=3');c.eq('Distance(C,A)',5,'CA=5');c.gt('ay',0,'非退化・鏡映固定');c.gt('s',0,'3つの合同な正三角形の未知辺長')
    for prefix,a,b,var in [('A','B','C','t'),('B','C','A','u'),('C','A','B','v')]:
        for i in [1,2]:
            c.c(prefix+str(i),f'PointOnSegment({a},{b},{var}{i})',f'{prefix}{i}は辺{a}{b}上')
            c.interval(var+str(i),0,1,f'{prefix}{i}は線分上',True)
        for a1,b1 in [('P',prefix+'1'),('P',prefix+'2'),(prefix+'1',prefix+'2')]:
            c.eq(f'Distance({a1},{b1})','s','3つの合同な正三角形の9辺が共通長s')
    c.pred('ConvexPolygon([A1,A2,B1,B2,C1,C2])','原文の凸六角形とラベル順序')
    out.append(c.target('Area(A1,A2,B1,B2,C1,C2)','凸六角形の面積'))

    c=Case('HMMT-2020-FEB-GUTS-13','ax ay u v tx ty','C=(0,0), B=(1,0), Aは上半平面。原文は直線AC,BCなのでX,Yのパラメータの正負は制限せず、Cとの相違だけを課す。')
    point(c,'C',0,0,'座標固定'); point(c,'B',1,0,'BC=1'); point(c,'A','ax','ay','未知頂点')
    c.c('D','PointOnSegment(A,B,u)','角三等分線とABの交点'); c.c('E','PointOnSegment(A,B,v)','もう一方の三等分線とABの交点')
    c.c('omega','Circumcircle(C,D,E)','CDEの外接円')
    point(c,'X','tx*ax','tx*ay','直線CA上の未知の第2交点'); point(c,'Y','ty',0,'直線CB上の未知の第2交点')
    c.eq('Distance(A,B)',7,'AB=7');c.eq('Distance(C,A)','4*sqrt(3)','CA=4sqrt(3)')
    c.eq('Angle(A,C,D)','Angle(D,C,E)','三等分'); c.eq('Angle(D,C,E)','Angle(E,C,B)','三等分')
    for p in ['X','Y']: c.eq(f'Distance(Center(omega),{p})','Radius(omega)','第2交点が外接円上')
    c.gt('ay',0,'非退化・鏡映固定');c.interval('u',0,1,'内角三等分線の交点');c.interval('v','u',1,'D,EをAからBの順にラベル付け（原文のX,YはD,Eを交換しても同じ）')
    c.rel('tx','!=',0,'Xは既知交点C以外');c.rel('ty','!=',0,'Yは既知交点C以外')
    out.append(c.target('Distance(X,Y)','XYの長さ'))

    c=Case('HMMT-2021-FEB-GUTS-14','b cx cy','A=(0,0), B=(b,0), b>0, Cは上半平面。a,bの整数出力表現は導入せず、幾何量ABを求める。DSLのbは辺長の実数パラメータ。')
    point(c,'A',0,0,'座標固定');point(c,'B','b',0,'未知辺長AB');point(c,'C','cx','cy','未知頂点')
    c.eq('Distance(A,C)',6,'AC=6');c.eq('Distance(B,C)',8,'BC=8');c.eq('Angle(B,A,C)','2*Angle(B,C,A)','角A=2角C')
    c.gt('b',0,'辺長は正');c.gt('cy',0,'非退化・鏡映固定')
    out.append(c.target('Distance(A,B)','幾何量AB。sqrt(a)-bから100a+bへの変換は参照答側に分離。'))

    c=Case('HMMT-2022-FEB-GUTS-11','','原文の単位円を中心原点、P1=(1,0)に剛体固定。円弧領域の面積を、原文の放射線で分かれる扇形から三角形OXYを除いた定義式で表す。')
    point(c,'O',0,0,'単位円の中心');regular(c,[f'P{i}' for i in range(1,13)])
    c.c('X','IntersectLines(Line(P1,P5),Line(O,P2))','指定の交点X');c.c('Y','IntersectLines(Line(P1,P5),Line(O,P4))','指定の交点Y')
    out.append(c.target('Angle(P2,O,P4)/2-Area(O,X,Y)','半径1の小扇形の面積theta/2から三角形OXYを引いた領域面積A。床変換は入力に置かない。'))

    c=Case('HMMT-2023-FEB-GUTS-03','d a cx cy','B=(0,0), D=(d,0), d>0。ABDが直角なのでA=(0,a)、鏡映によりa>0。')
    for n,x,y in [('B',0,0),('D','d',0),('A',0,'a'),('C','cx','cy')]: point(c,n,x,y,'原文の頂点と直角ABDの座標表現')
    c.c('M','Midpoint(B,D)','BDの中点')
    c.eq('Angle(B,C,D)','pi/2','BCD=90度'); c.eq('Distance(C,M)',2,'CM=2');c.eq('Distance(A,M)',3,'AM=3')
    c.gt('d',0,'BDは正');c.gt('a',0,'鏡映固定');c.pred('ConvexPolygon([A,B,C,D])','原文の凸四角形')
    out.append(c.target('Distance(A,D)','ADの長さ'))

    c=Case('HMMT-2024-FEB-GUTS-04','','角度は相似不変。正五角形の中心原点・外接半径1。反時計回りのAB,BCの外側へ60度回して正三角形の第3頂点を定義する。')
    regular(c,list('ABCDE'));c.c('F','Rotate(B,-pi/3,A)','辺ABの外側の正三角形');c.c('G','Rotate(C,-pi/3,B)','辺BCの外側の正三角形')
    out.append(c.target('Angle(F,E,G)','角FEG（ラジアン）。公式は4pi/15も明記。'))

    c=Case('HMMT-2025-FEB-GUTS-06','ax ay t u','B=(0,0), D=(1,0), C=(1+4,0)。和1+4は原文の隣接線分BD,DCの配置。Aの座標は解かず未知にする。')
    for n,x,y in [('B',0,0),('D',1,0),('C','1+4',0),('A','ax','ay')]: point(c,n,x,y,'原文の線分BCと内部点D、未知頂点A')
    point(c,'E','ax+t*(1+4-ax)','ay*(1-t)','半直線ACのパラメータt>=0')
    point(c,'F','ax*(1-u)','ay*(1-u)','半直線ABのパラメータu>=0')
    c.eq('Distance(A,B)','Distance(B,C)','正三角形');c.eq('Distance(A,C)','Distance(B,C)','正三角形')
    c.eq('E.x+F.x','2*D.x','DがEFの中点');c.eq('E.y+F.y','2*D.y','DがEFの中点')
    c.gt('ay',0,'非退化・鏡映固定');c.rel('t','>=',0,'Eは半直線AC上');c.rel('u','>=',0,'Fは半直線AB上')
    out.append(c.target('Distance(E,F)','EFの長さ'))

    c=Case('HMMT-2010-FEB-TEAM1-07','fx fy dx dy cx cy','角度だけなのでA=(0,0),Q=(1,0)。Fを下半平面に置く鏡映固定。P=F+D-Qは平行四辺形FPDQの定義。')
    for n,x,y in [('A',0,0),('Q',1,0),('F','fx','fy'),('D','dx','dy'),('C','cx','cy'),('P','fx+dx-1','fy+dy')]: point(c,n,x,y,'原文の頂点、平行四辺形によるPの定義')
    for pts,val in [('F,A,Q',10),('P,A,C',10),('P,F,A',15),('P,D,C',15)]:c.eq(f'Angle({pts})',f'{val}*pi/180',f'指定角{val}度')
    c.pred('ConvexPolygon([A,F,Q,D,C])','原文の凸五角形');c.rel('fy','<',0,'鏡映固定')
    for a,b in [('A','F'),('F','Q'),('Q','D'),('D','C'),('C','A')]:c.gt(cross(a,b,'P'),0,'Pは凸五角形の内部。各有向辺の内側にあることを表す。')
    out.append(c.target('Angle(A,Q,C)','角AQC（ラジアン）。公式答pi/12。'))
    assert [c.dsl['id'] for c in out]==[identifier(y,s,n) for y,s,n,*_ in SELECTED]
    return out

def main():
    assert not (HERE/'prediction.lock.json').exists(), 'Prediction already locked'
    cases=[]; mapping=[]
    for c,(year,section,n,reference,official,conversion) in zip(definitions(),SELECTED,strict=True):
        cid=c.dsl['id'];p=HERE/'dsl'/f'{cid}.json';save(p,c.dsl)
        cases.append(dict(id=cid,dsl_path=f'dsl/{cid}.json',dsl=c.dsl,
                          problem_statement=TRANSCRIPTIONS[cid],
                          source=f'https://hmmt-archive.s3.amazonaws.com/tournaments/{year}/feb/{section}/problems.pdf',
                          answer=[reference],authoring_status='runnable',truth_status='verified',dedupe_key=cid))
        m=dict(id=cid,gauge=c.gauge,notes=c.notes,mapping=c.mapping,input_sha256=sha(p),
               geometric_reference=reference,official_output=official,output_conversion=conversion)
        mapping.append(m)
        lines=[f'# {cid}', '', '状態: 作成済み。採用は一次資料・代入監査の合格後。', '',
               f'座標固定・同値性: {c.gauge}', '', '## 原文（PDF照合用転記）', '',TRANSCRIPTIONS[cid], '',
               '## 条件対応', '', '| 原文の条件・定義 | DSL位置 | DSL |','|---|---|---|']
        lines += [f"| {x['source_clause']} | `{x['path']}` | `{x['expression']}` |" for x in c.mapping]
        lines += ['', '定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。',
                  '解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。','']
        (HERE/'cards'/f'{cid}.md').write_text('\n'.join(lines))
    (HERE/'cases.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in cases))
    save(HERE/'mapping.json',mapping)
    print(json.dumps({'authored':len(cases),'variables':[len(r['dsl']['variables']) for r in cases],'solver_executed':False}))

if __name__=='__main__':main()
