"""Statement-only DSL authoring. No answers, witnesses, engine, or search imports.

Only writes unsealed DSLs and the clause-by-clause statement mapping.
Every expression is paired with its source/definition rationale.
"""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent


class Case:
    def __init__(self, identifier, variables, rationale):
        self.id = identifier
        self.dsl = dict(id=identifier, variables=variables.split(), constructions=[], conditions=[], target='')
        self.mapping = dict(id=identifier, coordinate_choice=rationale, constructions=[], conditions=[])

    def con(self, name, expression, source):
        self.dsl['constructions'].append(dict(name=name, expression=expression))
        self.mapping['constructions'].append(source)

    def rel(self, left, operator, right, source):
        self.dsl['conditions'].append(dict(left=left, operator=operator, right=right))
        self.mapping['conditions'].append(source)

    def pred(self, expression, source):
        self.dsl['conditions'].append(dict(predicate=expression))
        self.mapping['conditions'].append(source)

    def target(self, expression, source):
        self.dsl['target'] = expression
        self.mapping['target'] = source


def definitions():
    out = []
    c = Case('AIME-2001-I-05', 'x y', '楕円の指定座標を保持。y軸上の高度に対して左右頂点を交換し、右側をBと呼ぶ。')
    c.con('A', 'Point(0, 1)', '指定された頂点(0,1)。')
    c.con('B', 'Point(x, y)', '残りの頂点。')
    c.con('C', 'Point(-x, y)', 'y軸を含む高度は正三角形の対称軸。左右交換以外の枝を消さない。')
    c.rel('x**2 + 4*y**2', '=', 4, 'Bが指定楕円上。Cの楕円条件は同じ式になる。')
    c.rel('Distance(A, B)', '=', 'Distance(B, C)', '正三角形。AB=ACは構成で保証。')
    c.rel('x', '>', 0, '左右の名付けと非退化。')
    c.rel('y', '<', 1, 'A以外の頂点は楕円の最上点より下。')
    c.target('Distance(B, C)', '辺長そのもの。平方して分子分母を足すのは採点側。')
    out.append(c)

    c = Case('AIME-2001-I-07', 'x y t u', 'B=(0,0), C=(20,0)、Aを上半平面に置く等長変換のみ。')
    for n,e,s in [('B','Point(0, 0)','原点固定。'),('C','Point(20, 0)','原文BC=20。'),('A','Point(x, y)','第三頂点。'),('I','Incenter(A, B, C)','原文の内接円中心。'),('D','PointOnSegment(A, B, t)','DはAB上。'),('E','PointOnSegment(A, C, u)','EはAC上。')]: c.con(n,e,s)
    c.rel('Distance(A, B)', '=',21,'原文AB=21。')
    c.rel('Distance(A, C)', '=',22,'原文AC=22。')
    c.rel('y','>',0,'非退化と鏡映固定。')
    c.rel('D.y','=', 'E.y','DEは水平なBCに平行。')
    c.rel('D.y','=', 'I.y','DEは内心を通る。')
    for v in ['t','u']:
        c.rel(v,'>',0,'内心を通る線が辺の内部と交わる。')
        c.rel(v,'<',1,'内心を通る線が辺の内部と交わる。')
    c.target('Distance(D, E)','指定された長さDE。m+nは採点側。')
    out.append(c)

    c = Case('AIME-2002-I-02', 's u v w', '比だけなので共通半径1。Asymptoteは接続・3行の7/6/7個の位相だけに使用し、sqrt(3)等の完成座標は入力しない。')
    c.con('W','2 + 6*s','横7個、左右端の円が左右辺に接する。半径の2は定義、6は7個の6間隔。')
    c.con('H','w + 1','上段中心の高さwに半径1を足した長方形高。')
    for row,count,x,y in [('L',7,'1','1'),('M',6,'u','v'),('T',7,'1','w')]:
        for i in range(count): c.con(f'{row}{i}',f'Point({x} + {i}*s, {y})',f'図の{row}段の{i+1}番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。')
    c.rel('s','>',0,'各行を左から右へ列挙。')
    c.rel('u','>',1,'中段は下段の隙間に入る。')
    c.rel('u','<','1+s','中段先頭は下段先頭と次の中心の間。')
    c.rel('v','>',1,'中段は下段より上。')
    c.rel('w','>','v','上段は中段より上。')
    for row,count in [('L',7),('M',6),('T',7)]:
        for i in range(count-1): c.rel(f'Distance({row}{i}, {row}{i+1})','=',2,'図の同一行の隣接する単位円の外接。')
    for i in range(6):
        for row in ['L','T']:
            for j in [i,i+1]: c.rel(f'Distance(M{i}, {row}{j})','=',2,'図の上下段と中段の隣接円の外接。')
    for row,count in [('L',7),('M',6),('T',7)]:
        for i in range(count):
            n=f'{row}{i}'
            c.rel(n+'.x','>=',1,'円が長方形の左辺より内側。')
            c.rel(n+'.x','<=','W-1','円が長方形の右辺より内側。')
            c.rel(n+'.y','>=',1,'円が下辺より内側。')
            c.rel(n+'.y','<=','H-1','円が上辺より内側。')
    c.rel('W','>','H','長い辺/短い辺。図の横長の枝を表す。')
    c.target('W/H','長辺/短辺の比。sqrt(p), qの抽出は採点側。')
    out.append(c)

    c = Case('AIME-2003-I-02', '', '全同心円の中心を原点へ移すだけ。自由な未知量のない有限配置も除外しない。')
    c.con('O','Point(0, 0)','同心円の共通中心。')
    for i in range(1,101): c.con(f'C{i}',f'Circle(O, {i})',f'原文の半径列1,2,...,100の第{i}円。')
    c.target('('+' + '.join(f'(Area(C{i}) - Area(C{i-1}))' for i in range(2,101,2))+')/Area(C100)','内側が赤で交互なので、偶数の外半径の50環が緑。各環の面積の定義による有限和/全体。和の計算結果は入力しない。')
    out.append(c)

    c = Case('AIME-2004-II-07','h','Aを原点、ABをx軸とする。図の完成高さ70/3は使わない。')
    for n,e,s in [('A','Point(0, 0)','原点。'),('B','Point(8+17, 0)','AB=AE+EB、原文の8と17の和。'),('C','Point(8+17, h)','長方形の未知高さ。'),('D','Point(0, h)','長方形。'),('E','Point(8, 0)','AE=8。'),('F','Point(8+17-3, h)','CF=3。'),('Bp','Reflect(B, Line(E, F))','折り目EFに関する鏡映が折ったB。')]: c.con(n,e,s)
    c.rel('h','>',0,'長方形の非退化。')
    c.rel('Bp.x','=',0,"B'はAD上。")
    c.rel('Bp.y','>=',0,"B'は線分ADから外れない。")
    c.rel('Bp.y','<=','h',"B'は線分ADから外れない。")
    c.target('2*(Distance(A, B)+Distance(A, D))','長方形の周長。')
    out.append(c)

    c = Case('AIME-2005-I-01','r x1 y1 x2 y2 x3 y3 x4 y4 x5 y5','外円中心Oを原点、最初の内円中心P0を正のx軸に置く。正六角形の解法由来の角度や半径は入れない。')
    c.con('O','Point(0, 0)','外円中心。')
    c.con('Outer','Circle(O, 30)','原文の外円半径30。')
    c.con('P0','Point(30-r, 0)','半径rの内円が外円に内接する距離30-rと回転固定。')
    for i in range(1,6): c.con(f'P{i}',f'Point(x{i}, y{i})',f'第{i+1}内円の中心。')
    for i in range(6): c.con(f'C{i}',f'Circle(P{i}, r)','6円は共通半径r。')
    c.rel('r','>',0,'円の非退化。')
    c.rel('r','<',30,'内円が外円より小さい。')
    for i in range(1,6): c.rel(f'Distance(O, P{i})','=', '30-r','外円への内接。')
    for i in range(6): c.rel(f'Distance(P{i}, P{(i+1)%6})','=', '2*r','輪の隣接する2円への外接。')
    c.pred('ConvexPolygon([P0, P1, P2, P3, P4, P5])','交差せず円周順の輪。')
    c.rel('y1','>',0,'鏡映固定。')
    for i in range(6):
        for j in range(i+1,6):
            if j-i not in (1,5): c.rel(f'Distance(P{i}, P{j})','>', '2*r','隣接2円以外とは接触・重なりのない輪。')
    c.target('Area(Outer) - '+' - '.join(f'Area(C{i})' for i in range(6)),'外円の内側で6円の外側の面積K。floorは採点側。')
    out.append(c)

    c = Case('AIME-2005-I-07','b','Aを原点、B=(b,0)、四角形を上半平面に置く。角A,B=60度の辺方向を原文の数値で構成。')
    for n,e,s in [('A','Point(0, 0)','原点。'),('B','Point(b, 0)','未知の辺AB。'),('D','Point(10*cos(pi/3), 10*sin(pi/3))','AD=10、角A=60度。'),('C','Point(b-8*cos(pi/3), 8*sin(pi/3))','BC=8、角B=60度。')]: c.con(n,e,s)
    c.rel('b','>',0,'辺ABの正値。')
    c.rel('Distance(C, D)','=',12,'原文CD=12。')
    c.pred('ConvexPolygon([A, B, C, D])','A,Bが60度の通常の単純四角形の内角配置。凹角の別解を追加しない。')
    c.target('Distance(A, B)','辺長AB。p+qは採点側。')
    out.append(c)

    c = Case('AIME-2005-II-08','R z a b','内円中心をO1=(0,0), O2=(4+10,0)に置く。外円中心は同じ軸上のO3=(z,0)。接線は上側を選ぶ鏡映固定。')
    for n,e,s in [('O1','Point(0, 0)','第1円の中心。'),('O2','Point(4+10, 0)','2内円の外接による中心間距離、原文半径の和。'),('O3','Point(z, 0)','3中心が共線。'),('L','Line(Point(0, b), Point(1, a+b))','共通外接線y=ax+b。非鉛直なのは2中心が水平で半径が異なるため。')]: c.con(n,e,s)
    c.rel('R','>',10,'2内円を含む外円の半径。')
    c.rel('Distance(O3, O1)','=', 'R-4','第1円と第3円の内接。')
    c.rel('Distance(O3, O2)','=', 'R-10','第2円と第3円の内接。')
    c.rel('Distance(O1, L)','=',4,'第1円に接する。')
    c.rel('Distance(O2, L)','=',10,'第2円に接する。')
    c.rel('b','>',0,'上側外接線を選ぶ。')
    c.rel('a*(4+10)+b','>',0,'両中心が接線の同じ側。内接線を排除。')
    c.rel('Distance(O3, L)','<','R','外円を横切る弦。')
    c.target('2*sqrt(R**2-Distance(O3, L)**2)','円中心から弦への垂線で二分した弦長の定義式。外円半径の解は入力しない。')
    out.append(c)

    c = Case('AIME-2005-II-12','e f','正方形A=(0,0),B=(900,0),C=(900,900),D=(0,900)。尺度変更なし。')
    for n,ex,s in [('A','Point(0, 0)','正方形の原点。'),('B','Point(900, 0)','原文AB=900。'),('C','Point(900, 900)','正方形。'),('D','Point(0, 900)','正方形。'),('O','Midpoint(A, C)','正方形の中心。'),('E','Point(e, 0)','EはAB上。'),('F','Point(f, 0)','FはAB上。')]: c.con(n,ex,s)
    c.rel('e','>=',0,'Eは線分AB上。')
    c.rel('f','<=',900,'Fは線分AB上。')
    c.rel('e','<','f','EはAとFの間。')
    c.rel('Distance(A, E)','<','Distance(B, F)','原文AE<BF。')
    c.rel('Distance(E, F)','=',400,'原文EF=400。')
    c.rel('Angle(E, O, F)','=', 'pi/4','原文角EOF=45度。')
    c.target('Distance(B, F)','長さBF。p+q+rは採点側。')
    out.append(c)

    c = Case('AIME-2005-II-14','x y t','B=(0,0), C=(15,0)、Aを上半平面へ。原文の尺度を保持。')
    for n,e,s in [('B','Point(0, 0)','原点。'),('C','Point(15, 0)','原文BC=15。'),('A','Point(x, y)','頂点A。'),('D','Point(15-6, 0)','CD=6。'),('E','PointOnSegment(B, C, t)','EはBC上。')]: c.con(n,e,s)
    c.rel('Distance(A, B)','=',13,'原文AB=13。')
    c.rel('Distance(A, C)','=',14,'原文CA=14。')
    c.rel('y','>',0,'非退化と鏡映固定。')
    c.rel('t','>',0,'角の一致からEはBと異なる。')
    c.rel('t','<',1,'角の一致からEはCと異なる。')
    c.rel('Angle(B, A, E)','=', 'Angle(C, A, D)','原文の角BAE=角CAD。')
    c.target('Distance(B, E)','長さBE。既約分母qは採点側。')
    out.append(c)

    c = Case('AIME-2012-I-14','x y u v','根a,b,cを直角がaになるよう名前交換。回転でabを水平、acを垂直にする。原点は動かさない。複素係数q,rに他の制限はない。')
    for n,e,s in [('A','Point(x, y)','複素根a。'),('B','Point(u, y)','直角の1辺を水平にする回転固定。'),('C','Point(x, v)','Aが直角のため他辺は垂直。')]: c.con(n,e,s)
    c.rel('2*x+u','=',0,'z^2係数0はVietaの恒等式a+b+c=0（実部）。解から求めた値ではない。')
    c.rel('2*y+v','=',0,'a+b+c=0（虚部）。')
    c.rel('x**2+y**2+u**2+y**2+x**2+v**2','=',250,'原文の|a|^2+|b|^2+|c|^2=250。')
    c.rel('u','>','x','直角の第1辺の正値。')
    c.rel('v','>','y','直角の第2辺、鏡映固定。')
    c.target('Distance(B, C)**2','指定された斜辺の平方h^2。')
    out.append(c)

    c = Case('AIME-2014-I-01','','長方形の指定幅50、長さ80を保つ。原文の経路は図の固定6斜線と始点側1横線。各自由端の最短余長200を加える。')
    for i in range(4):
        c.con(f'L{i}',f'Point(0, {i}*80/3)','長辺上の等間隔の4穴。3区間で全長80。')
        c.con(f'R{i}',f'Point(50, {i}*80/3)','対辺上の4穴、幅50。')
    c.target('Distance(L0, R0) + '+' + '.join(f'Distance(L{i}, R{i+1}) + Distance(R{i}, L{i+1})' for i in range(3))+' + 2*200','固定された靴紐経路の長さ+両端それぞれ最低200。全配置の最適化はなく余長の下限を足すだけ。')
    out.append(c)

    c = Case('AIME-2014-I-10','theta','大円中心E=(0,0)、最初の接点A=(5,0)、小円中心C=(5+1,0)。転がり方向は反時計回りを選ぶ。')
    for n,e,s in [('E','Point(0, 0)','大円中心。'),('A','Point(5, 0)','原文の大円半径5の接点。'),('C','Point(5+1, 0)','小円半径1、外接。'),('D','Point((5+1)*cos(theta), (5+1)*sin(theta))','転がった小円中心は距離5+1の円周上。'),('B','Point(D.x-1, D.y)','小円が正確に1回転し、初期の中心から接点への半径(-1,0)が戻る。')]: c.con(n,e,s)
    c.rel('(5+1)*theta','=', '2*pi*1','滑りなしの転がり。接触に対する相対回転は5*theta/1、中心の向きthetaを加えた絶対回転が2*pi。解角度は入力しない。')
    c.rel('theta','>',0,'正方向で最初の1回転。')
    c.rel('theta','<','2*pi','1回転に対応する中心の移動範囲。')
    c.target('sin(Angle(B, E, A))**2','原文のsin^2角BEAそのもの。')
    out.append(c)

    c = Case('AIME-2014-II-10','x y u v','複素平面全体を回転しzを正実数2014へ。1/(z+w)=1/z+1/wの分母は非零。共役や根の値は決め打ちしない。')
    for n,e,s in [('Z','Point(2014, 0)','|z|=2014と回転固定。'),('W1','Point(x, y)','第1のw。'),('W2','Point(u, v)','第2のw。')]: c.con(n,e,s)
    for a,b in [('x','y'),('u','v')]:
        c.rel(f'{a}**2-{b}**2+2014*{a}+2014**2','=',0,'分母を払った恒等式w^2+zw+z^2=0の実部。')
        c.rel(f'2*{a}*{b}+2014*{b}','=',0,'同じ式の虚部。')
        c.rel(f'{a}**2+{b}**2','>',0,'w!=0、元の分母条件。')
        c.rel(f'({a}+2014)**2+{b}**2','>',0,'z+w!=0、元の分母条件。')
    c.rel('y','>',0,'根の名前交換で上側をW1。実根は実二次式が正なので存在しない。')
    c.rel('v','<',0,'W2を下側。実係数二次式の非実根は共役対なのでこの2点が全根。')
    c.target('Area(Z, W1, W2)','原文の多角形の面積。sqrt(3)の係数と剰余は採点側。')
    out.append(c)
    c = Case('AIME-2001-II-04','p q','指定された直交座標系をそのまま使う。PとQのx座標を自由変数にする。')
    c.con('P','Point(p, 15*p/8)','Pは8y=15x上。')
    c.con('Q','Point(q, 3*q/10)','Qは10y=3x上。')
    c.con('R','Point(8, 6)','原文のR=(8,6)。')
    c.con('M','Midpoint(P, Q)','線分PQの中点の定義。')
    c.rel('M.x','=', 'R.x','RがPQの中点（x座標）。')
    c.rel('M.y','=', 'R.y','RがPQの中点（y座標）。')
    c.rel('Distance(P, Q)','>',0,'非退化な線分PQ。')
    c.target('Distance(P, Q)','線分PQの長さ。')
    out.append(c)

    c = Case('AIME-2001-II-13','ax ay cx cy','B=(0,0),D=(10,0)、Aを上、Cを下に置く。原文の四角形の順序と対角線BDを保持。')
    for n,e,s in [('B','Point(0, 0)','原点。'),('D','Point(10, 0)','原文BD=10。'),('A','Point(ax, ay)','AはBDの上側。'),('C','Point(cx, cy)','CはBDの反対側。')]: c.con(n,e,s)
    c.rel('Distance(A, B)','=',8,'原文AB=8。')
    c.rel('Distance(B, C)','=',6,'原文BC=6。')
    c.rel('Angle(B, A, D)','=', 'Angle(A, D, C)','原文角BAD=角ADC。')
    c.rel('Angle(A, B, D)','=', 'Angle(B, C, D)','原文角ABD=角BCD。')
    c.rel('ay','>',0,'鏡映固定。')
    c.rel('cy','<',0,'対角線BDの両側にA,C。')
    c.pred('ConvexPolygon([A, B, C, D])','通常の内角を指定した四角形の枝。内角A=Dと角C=角ABDの枝を保持。')
    c.target('Distance(C, D)','辺長CD。')
    out.append(c)
    c = Case('AIME-2019-I-12','x','原文の複素座標系を保持。zの虚部11と正の実部だけを使い、出力形式のm,nは変数にしない。')
    c.con('Z','Point(x, 11)','原文z=m+sqrt(n)+11iの虚部。m,n>0より実部は正。')
    c.con('F','Point(x**2-11**2-19*x, 2*11*x-19*11)','原文f(z)=z^2-19zを実部・虚部で直接評価。')
    c.con('G','Point(F.x**2-F.y**2-19*F.x, 2*F.x*F.y-19*F.y)','原文のf(f(z))を同じ定義で評価。')
    c.rel('Dot(Vector(Z, F), Vector(F, G))','=',0,'頂点f(z)で直角。内積の符号は0条件に影響しない。')
    c.rel('Distance(Z, F)','>',0,'直角三角形の第1辺が非退化。')
    c.rel('Distance(F, G)','>',0,'直角三角形の第2辺が非退化。')
    c.rel('x','>',0,'原文m,n>0に対応する実部の正の枝。整数性は出力形式なので入力しない。')
    c.target('Z.x','点zの実座標そのもの。m+nは採点側で抽出。')
    out.append(c)
    return sorted(out, key=lambda c:(int(c.id.split('-')[1]),len(c.id.split('-')[2]),int(c.id.split('-')[3])))


def main():
    assert not (HERE/'prediction.lock.json').exists(), 'prediction is locked'
    (HERE/'dsl').mkdir(exist_ok=True)
    cases=definitions()
    for c in cases:
        assert c.dsl['target']
        (HERE/'dsl'/f'{c.id}.json').write_text(json.dumps(c.dsl,ensure_ascii=False,indent=2)+'\n')
    (HERE/'mapping.json').write_text(json.dumps([c.mapping for c in cases],ensure_ascii=False,indent=2)+'\n')
    print('authored',len(cases),'DSLs; no solver/search imports')


if __name__=='__main__': main()
