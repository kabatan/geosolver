"""Questionだけから作成したv3の直接翻訳。式の評価・解の計算はしない。"""
from __future__ import annotations

DEFINITIONS = {}


def pt(n, x, y, clause):
    return n, f"Point({x}, {y})", clause


def eq(a, b, clause):
    return str(a), "=", str(b), clause


def gt(a, b, clause):
    return str(a), ">", str(b), clause


def cross(a, b, c):
    return f"(({b}.x-{a}.x)*({c}.y-{a}.y)-({b}.y-{a}.y)*({c}.x-{a}.x))"


def dot(a, b, c):
    return f"(({a}.x-{b}.x)*({c}.x-{b}.x)+({a}.y-{b}.y)*({c}.y-{b}.y))"


def inside(p, a="A", b="B", c="C"):
    return [gt(cross(u, v, p), 0, f"{p} strictly inside {a}{b}{c} / 各辺の内側")
            for u, v in [(a, b), (b, c), (c, a)]]


def convex(names):
    return [gt(cross(a, names[(i+1) % len(names)], c), 0,
               "頂点順の狭義凸性 / 各辺の他の頂点はすべて左側")
            for i, a in enumerate(names) for c in names
            if c not in (a, names[(i+1) % len(names)])]


def unit_interval(t, clause):
    return [gt(t, 0, clause), gt(1, t, clause)]


def coprime(m="m", n="n", positive=True):
    out = [eq(f"IsInteger({v})", 0, "既約分数の整数分子分母・Bezout整数証人")
           for v in (m, n, "u", "v")]
    out += [gt(n, 0, "分母は正"), eq(f"u*{m}+v*{n}", 1, "互いに素の定義的同値条件（Bezout）")]
    if positive:
        out += [gt(m, 0, "分子は正")]
    return out


def integer_radical(a="a", b="b"):
    return [eq(f"IsInteger({x})", 0, "原問の整数係数") for x in (a, b)] + [
        (b, ">=", "0", "平方根の定義域")]


def add(key, variables, constructions, conditions, target, clause, gauge, notes=""):
    cid = "AIME-" + key
    d = dict(id=cid, variables=variables,
             constructions=[dict(name=n, expression=e) for n, e, _ in constructions],
             conditions=[], target=target)
    mapping = [dict(path=f"constructions[{i}]", source_clause=c, expression=f"{n} = {e}")
               for i, (n, e, c) in enumerate(constructions)]
    for i, item in enumerate(conditions):
        if len(item) == 2:
            expression, text = item
            condition = dict(predicate=expression)
        else:
            left, op, right, text = item
            condition = dict(left=str(left), operator=op, right=str(right))
            expression = f"{left} {op} {right}"
        d["conditions"].append(condition)
        mapping.append(dict(path=f"conditions[{i}]", source_clause=text, expression=expression))
    mapping.append(dict(path="target", source_clause=clause, expression=target))
    assert cid not in DEFINITIONS
    DEFINITIONS[cid] = dict(dsl=d, mapping=mapping, gauge=gauge, notes=notes)


def parallel_cuts():
    """Pを通る各辺平行線と、三角形の残り2辺の交点。"""
    constructions = []
    for x, y, z in [("A", "B", "C"), ("B", "C", "A"), ("C", "A", "B")]:
        constructions += [
            pt("W"+x, f"P.x+{z}.x-{y}.x", f"P.y+{z}.y-{y}.y", f"Pを通り{y}{z}に平行な方向点"),
            ("L"+x, f"Line(P, W{x})", f"Pを通る辺{y}{z}の平行線"),
            ("E"+x, f"Intersect(L{x}, Line({x}, {y}))", "平行線と辺の交点"),
            ("F"+x, f"Intersect(L{x}, Line({x}, {z}))", "平行線と辺の交点")]
    return constructions


def definitions():
    if DEFINITIONS:
        return DEFINITIONS
    add("1983-04", ["x", "y"], [
        pt("B", 0, 0, "right angle ABC / 直角頂点を原点"),
        pt("A", 0, 6, "AB=6"), pt("C", 2, 0, "BC=2"),
        pt("O", "x", "y", "円の中心は未知"),
        ("omega", "Circle(O, sqrt(50))", "circle radius sqrt(50)")], [
        eq("OnCircle(A, omega)", 0, "図の円周上の端点A"),
        eq("OnCircle(C, omega)", 0, "図の円周上の端点C"),
        gt("sqrt(50)", "Distance(O, B)", "notched circle / Bは元の円盤の内部")],
        "Distance(B, O)**2", "square of distance from B to center",
        "直角の二辺AB,BCを座標軸に固定。長さ6,2は原文。合同移動・鏡映だけ。",
        "asyはA,Cが円周上、Bが内部という接続情報にのみ使用。描画用座標は制約に転記しない。")

    add("1983-12", ["a", "b", "h", "p", "q"], [
        pt("O", 0, 0, "circle center"),
        pt("A", "-(10*a+b)/2", 0, "diameter AB has two-digit length 10a+b"),
        pt("B", "(10*a+b)/2", 0, "diameter AB"),
        pt("H", "h", 0, "perpendicular diameter/chord intersection"),
        pt("C", "h", "(10*b+a)/2", "reversed-digit chord CD, perpendicular to AB"),
        pt("D", "h", "-(10*b+a)/2", "CD / 円の中心からの垂線が弦を二等分"),
        ("omega", "Circle(O, (10*a+b)/2)", "circle with diameter AB")], [
        *[eq(f"IsInteger({x})", 0, "decimal digits / rational witnesses") for x in ("a", "b", "p", "q")],
        ("a", ">=", "1", "十の位"), ("a", "<=", "9", "十の位"),
        ("b", ">=", "0", "一の位（反転後の先頭0を排除しない）"), ("b", "<=", "9", "一の位"),
        gt("h", 0, "positive distance OH / 鏡映でHを右側"),
        gt("p", 0, "positive rational numerator witness"), gt("q", 0, "positive rational denominator witness"),
        eq("h", "p/q", "OH is rational（既約性の指定はない）"),
        eq("OnCircle(C, omega)", 0, "C on circle"), eq("OnCircle(D, omega)", 0, "D on circle")],
        "Distance(A, B)", "determine AB", "O原点、ABをx軸。OHの正側は鏡映で固定。",
        "画像は欠落しているが、径・垂直弦・交点・全数値は本文だけで定義できる。")

    add("1983-14", ["px", "py", "qx", "qy", "rx", "ry"], [
        pt("O1", 0, 0, "center of radius-8 circle"), pt("O2", 12, 0, "centers 12 apart"),
        ("c1", "Circle(O1, 8)", "radius 8"), ("c2", "Circle(O2, 6)", "radius 6"),
        pt("P", "px", "py", "one intersection P"), pt("Q", "qx", "qy", "other endpoint Q of chord QP"),
        pt("R", "rx", "ry", "other endpoint R of chord PR")], [
        gt("py", 0, "鏡映で上側交点"),
        eq("OnCircle(P,c1)", 0, "P on first circle"), eq("OnCircle(P,c2)", 0, "P on second circle"),
        eq("OnCircle(Q,c1)", 0, "Q on first circle"), eq("OnCircle(R,c2)", 0, "R on second circle"),
        eq("OnLine(R,Line(Q,P))", 0, "straight line QPR"),
        eq("Distance(Q,P)", "Distance(P,R)", "equal chords"), gt("Distance(Q,P)", 0, "distinct chord endpoints"),
        gt("0", dot("Q", "P", "R"), "図のPはQ,Rの間（反対方向の二弦）")],
        "Distance(Q,P)**2", "square of QP", "中心間をx軸に固定、鏡映でP.y>0。",
        "asy内の描画補助円の半径sqrt(130)は答えを埋め込んだ値かもしれないため一切使用しない。使用する図情報はQ-P-Rの順序だけ。")

    add("1984-03", ["b", "cx", "cy", "px", "py"], [
        pt("A", 0, 0, "triangle ABC"), pt("B", "b", 0, "AB horizontal"), pt("C", "cx", "cy", "unknown C"),
        pt("P", "px", "py", "interior point P"), *parallel_cuts()], [
        gt("b", 0, "AB positive"), gt("cy", 0, "鏡映でCを上側"), *inside("P"),
        eq("Area(P, EA, FB)", 4, "t1: Pと辺AB上の二交点の小三角形"),
        eq("Area(P, FA, EC)", 9, "t2: Pと辺AC上の二交点の小三角形"),
        eq("Area(P, EB, FC)", 49, "t3: Pと辺BC上の二交点の小三角形")],
        "Area(A,B,C)", "area of ABC", "A原点、ABをx軸、Cを上側。尺度は固定しない。",
        "本文とasyの接続から三平行線を記述。asyの頂点ラベルはコードの変数名と異なるため表示ラベルA,B,Cを使用。描画座標・分割率は使わない。")

    # 各円盤を直線の一方に切る面積は円弧と三角形の定義式。clampで接しない場合も含む。
    cap = lambda d: f"(9*acos(-({d})/3)+({d})*sqrt(9-({d})**2))"
    da = "max([-3,min([3,-3*nx+16*ny])])"
    dc = "max([-3,min([3,2*nx+8*ny])])"
    add("1984-06", ["nx", "ny"], [
        pt("A", 14, 92, "first circle center"), pt("B", 17, 76, "second circle center / line passes through B"),
        pt("C", 19, 84, "third circle center"),
        pt("W", "17-ny", "76+nx", "line direction perpendicular to unit normal (nx,ny)"),
        ("ell", "Line(B,W)", "unknown bisecting line")], [
        eq("nx**2+ny**2", 1, "normal normalization removes only representation scale"),
        gt("ny", 0, "法線の符号を固定 / 有限傾き"),
        eq(cap(da)+"+9*pi/2+"+cap(dc), "27*pi/2", "三円盤の同じ側の部分の面積和が全体の半分")],
        "abs(nx/ny)", "absolute value of line slope", "原文の座標・半径3をそのまま保持。",
        "符号付き中心距離dに対する半平面円盤面積はr² acos(-d/r)+d sqrt(r²-d²)。dを[-r,r]にclampする。未知の配置での有限3円の切片面積を直接記述し、二等分線の解は求めない。")

    add("1985-09", ["r", "y2", "y3", "y4", "alpha", "beta", "m", "n", "u", "v"], [
        pt("O", 0, 0, "circle center"), ("omega", "Circle(O,r)", "unknown radius"),
        *[pt(name, x, f"y{length}", f"horizontal chord of length {length}")
          for length, names in [(2, "AB"), (3, "CD"), (4, "EF")]
          for name, x in [(names[0], f"-{length}/2"), (names[1], f"{length}/2")]]] , [
        gt("r", 0, "circle positive radius"),
        *[eq(f"OnCircle({p},omega)", 0, "parallel chord endpoints on circle") for p in "ABCDEF"],
        eq("Angle(A,O,B)", "alpha", "length2 chord central angle alpha"),
        eq("Angle(C,O,D)", "beta", "length3 chord central angle beta"),
        eq("Angle(E,O,F)", "alpha+beta", "length4 chord central angle alpha+beta"),
        gt("alpha", 0, "positive central angle"), gt("beta", 0, "positive central angle"),
        gt("pi", "alpha+beta", "alpha+beta < pi"), gt("cos(alpha)", 0, "positive rational cos alpha"),
        eq("cos(alpha)", "m/n", "cos alpha = reduced rational"), *coprime()],
        "m+n", "sum of numerator and denominator", "O原点、三弦を水平。弦中点をy軸上に置くのは円の定義から。上下の分枝は残す。")

    add("1985-11", ["t", "L"], [
        pt("F1", 9, 20, "ellipse first focus"), pt("F2", 49, 55, "ellipse second focus"),
        pt("T", "t", 0, "tangency point on x-axis")], [
        eq("Distance(T,F1)+Distance(T,F2)", "L", "ellipse definition / major axis length L"),
        eq("(t-9)/Distance(T,F1)+(t-49)/Distance(T,F2)", 0,
           "x-axis tangency: ellipse defining distance sum has zero x derivative at T"),
        gt("L", "Distance(F1,F2)", "nondegenerate ellipse")],
        "L", "length of major axis", "指定座標を保持。接点も長軸長も未知変数。",
        "両焦点はx軸の上側。距離和の水平微分0が接線水平を表す定義条件。最小値自体を事前計算しない。")

    add("1986-09", ["cx", "cy", "px", "py", "d"], [
        pt("A", 0, 0, "triangle ABC"), pt("B", 425, 0, "AB=425"), pt("C", "cx", "cy", "unknown C"),
        pt("P", "px", "py", "interior P"), *parallel_cuts()], [
        gt("cy", 0, "鏡映でCを上側"), eq("Distance(B,C)", 450, "BC=450"),
        eq("Distance(A,C)", 510, "AC=510"), *inside("P"), gt("d", 0, "positive common segment length"),
        *[eq(f"Distance(E{x},F{x})", "d", "Pを通る三本の平行切片は同長d") for x in "ABC"]],
        "d", "common length d", "A原点、ABをx軸、鏡映でC.y>0。長さは原文通り。")

    add("1986-15", ["ax", "ay", "bx", "by", "cx", "cy"], [
        pt("A", "ax", "ay", "vertex A"), pt("B", "bx", "by", "vertex B"), pt("C", "cx", "cy", "right vertex C"),
        ("M", "Midpoint(B,C)", "median through A"), ("N", "Midpoint(A,C)", "median through B")], [
        eq("Distance(A,B)", 60, "hypotenuse AB=60"), eq(dot("A", "C", "B"), 0, "right angle C"),
        gt("Area(A,B,C)", 0, "nondegenerate triangle"),
        eq("A.y", "A.x+3", "A on its median line y=x+3"), eq("M.y", "M.x+3", "BC midpoint on same median"),
        eq("B.y", "2*B.x+4", "B on its median line y=2x+4"), eq("N.y", "2*N.x+4", "AC midpoint on same median")],
        "Area(A,B,C)", "area of ABC", "指定された二直線が絶対座標を決めるので座標の正規化なし。")

    add("1987-09", ["a", "c", "x", "y"], [
        pt("B", 0, 0, "right vertex B"), pt("A", "a", 0, "leg BA"), pt("C", 0, "c", "leg BC"),
        pt("P", "x", "y", "interior P")], [
        gt("a", 0, "positive leg BA"), gt("c", 0, "positive leg BC"),
        gt("x", 0, "interior P"), gt("y", 0, "interior P"), gt(1, "x/a+y/c", "P below hypotenuse"),
        eq("Distance(P,A)", 10, "PA=10"), eq("Distance(P,B)", 6, "PB=6"),
        eq("Angle(A,P,B)", "Angle(B,P,C)", "angle APB = BPC"),
        eq("Angle(B,P,C)", "Angle(C,P,A)", "angle BPC = CPA")],
        "Distance(P,C)", "PC", "B原点、二直角辺を正x軸・正y軸。合同移動・鏡映だけ。",
        "欠落画像を使わず本文で全条件を表現できる。角の値を解いて入力へ追加しない。")

    add("1988-07", ["h"], [
        pt("B", 0, 0, "one base endpoint"), pt("C", "3+17", 0, "altitude divides BC into 3 and17"),
        pt("H", 3, 0, "altitude foot between B,C"), pt("A", 3, "h", "altitude AH")], [
        gt("h", 0, "鏡映でAを上側"), eq("tan(Angle(C,A,B))", "22/7", "tan angle CAB=22/7"),
        gt("pi/2", "Angle(C,A,B)", "tan is positive for an interior triangle angle")],
        "Area(A,B,C)", "area of ABC", "B,C交換で足から3の側をBとする。角Aと面積は交換に不変。長さ保持。")

    add("1988-14", ["b", "c", "d", "k"], [
        pt("O", 0, 0, "origin"), pt("W", 1, 2, "reflection axis y=2x"), ("ell", "Line(O,W)", "axis"),
        pt("E1", 1, 0, "coordinate basis"), pt("E2", 0, 1, "coordinate basis"),
        ("U", "Reflect(E1,ell)", "reflection of first basis vector"),
        ("V", "Reflect(E2,ell)", "reflection of second basis vector")], [
        eq("k*U.x*U.y", 12, "reflected xy=1 equation: x² coefficient is 12"),
        eq("k*(U.x*V.y+V.x*U.y)", "b", "xy coefficient"),
        eq("k*V.x*V.y", "c", "y² coefficient"), eq("-k", "d", "constant coefficient"),
        ("k != 0", "nonzero equation multiplier")],
        "b*c", "product bc", "指定座標・鏡映軸を保持。",
        "鏡映は線形かつ逆写像が同じ。逆写像(x,y)=(U.x*x+V.x*y,U.y*x+V.y*y)をxy=1へ代入し、指定二次式と係数比較する定義的翻訳。係数値は求めない。")

    add("1990-07", ["a", "c"], [
        pt("P", -8, 5, "P=(-8,5)"), pt("Q", -15, -19, "Q=(-15,-19)"), pt("R", 1, -7, "R=(1,-7)"),
        ("I", "Incenter(P,Q,R)", "内角二等分線上の内心")], [
        eq("a*P.x+2*P.y+c", 0, "bisector equation at P"),
        eq("a*I.x+2*I.y+c", 0, "bisector equation at incenter")],
        "a+c", "a+c", "原文の絶対座標を保持。内心は内角二等分線の定義。")

    cons = [pt("A", 0, 0, "rectangle vertex"), pt("B", 4, 0, "AB=4"),
            pt("C", 4, 3, "CB=3"), pt("D", 0, 3, "rectangle vertex")]
    terms = ["Distance(A,C)"]
    for k in range(1, 168):
        for name, start, end in [("P", "A", "B"), ("Q", "C", "B"), ("U", "A", "D"), ("V", "C", "D")]:
            cons.append((f"{name}{k}", f"PointOnSegment({start},{end},{k}/168)",
                         f"{start}{end}を168等分する第{k}点（端点の順序は本文）"))
        terms += [f"Distance(P{k},Q{k})", f"Distance(U{k},V{k})"]
    add("1991-02", [], cons, [], "+".join(terms), "335 segments: 167+167+diagonal ACの長さの和",
        "A原点、AB水平、AD垂直、辺長4,3を保持。",
        "有限167回の定義的作図を全て展開した。和の公式への置換・長さの事前評価はしない。")

    add("1991-12", ["w", "h", "rx", "sy", "m", "n", "u", "v"], [
        pt("A", 0, 0, "rectangle"), pt("B", "w", 0, "rectangle"), pt("C", "w", "h", "rectangle"), pt("D", 0, "h", "rectangle"),
        pt("P", "w-15", 0, "P on AB, PB=15"), pt("Q", "w", 20, "Q on BC, BQ=20"),
        pt("R", "rx", "h", "R on CD"), pt("S", 0, "sy", "S on DA")], [
        gt("w", 15, "P interior of AB"), gt("h", 20, "Q interior of BC"), gt("rx", 0, "R interior CD"),
        gt("w", "rx", "R interior CD"), gt("sy", 0, "S interior DA"), gt("h", "sy", "S interior DA"),
        eq("Distance(P,Q)", "Distance(Q,R)", "rhombus equal sides"),
        eq("Distance(Q,R)", "Distance(R,S)", "rhombus equal sides"),
        eq("Distance(R,S)", "Distance(S,P)", "rhombus equal sides"),
        eq("Distance(P,R)", 30, "PR=30"), eq("Distance(Q,S)", 40, "QS=40"),
        eq("2*(w+h)", "m/n", "rectangle perimeter in lowest terms"), *coprime()],
        "m+n", "sum numerator and denominator", "長方形を第一象限に合同固定。尺度は保持。")

    add("1991-14", [f"{p}{s}" for p in "cdef" for s in "xy"], [
        pt("A", 0, 0, "hexagon AB C D E F"), pt("B", 31, 0, "sixth side AB=31"),
        *[pt(p.upper(), p+"x", p+"y", "remaining vertices in cyclic order") for p in "cdef"],
        ("omega", "Circumcircle(A,B,C)", "circumcircle of hexagon")], [
        *convex("ABCDEF"),
        *[eq(f"Distance({a},{b})", 81, "five sides have length81") for a,b in zip("BCDEF", "CDEFA")],
        *[eq(f"OnCircle({p},omega)", 0, "hexagon inscribed in one circle") for p in "DEF"]],
        "Distance(A,C)+Distance(A,D)+Distance(A,E)", "three diagonals drawn from A",
        "A原点、ABを正x軸、頂点を反時計回り。AB=31を保持。")

    add("1992-09", ["dx", "h", "p", "r", "m", "n", "u", "v"], [
        pt("A", 0, 0, "AB=92"), pt("B", 92, 0, "AB=92"), pt("D", "dx", "h", "parallel top side"),
        pt("C", "dx+19", "h", "CD=19 and AB parallel CD"), pt("P", "p", 0, "circle center on AB"),
        ("omega", "Circle(P,r)", "unknown radius"),
        ("E", "FootOfPerpendicular(P,Line(B,C))", "tangency foot on BC"),
        ("F", "FootOfPerpendicular(P,Line(A,D))", "tangency foot on AD")], [
        gt("h", 0, "positive trapezoid height"), eq("Distance(B,C)", 50, "BC=50"), eq("Distance(A,D)",70,"AD=70"),
        ("p", ">=", "0", "P on AB"), ("p", "<=", "92", "P on AB"), gt("r",0,"positive radius"),
        eq("Distance(P,E)", "r", "circle tangent BC"), eq("Distance(P,F)","r","circle tangent AD"),
        eq("Distance(B,E)+Distance(E,C)","Distance(B,C)","contact on segment BC"),
        eq("Distance(A,F)+Distance(F,D)","Distance(A,D)","contact on segment AD"),
        eq("Distance(A,P)","m/n","AP in lowest terms"), *coprime()],
        "m+n", "m+n", "ABを水平、台形を上側。4辺長は保持。")

    add("1992-14", ["cx", "cy", "t", "s", "q", "ox", "oy"], [
        pt("A",0,0,"triangle"),pt("B",1,0,"similarity scale AB=1"),pt("C","cx","cy","unknown C"),
        ("Ap","PointOnSegment(B,C,t)","A' on BC"),("Bp","PointOnSegment(A,C,s)","B' on AC"),
        ("Cp","PointOnSegment(A,B,q)","C' on AB"),pt("O","ox","oy","concurrent point")], [
        gt("cy",0,"nondegenerate triangle / upper orientation"),
        *unit_interval("t","A' strictly on BC / endpoint would make cevian ratios undefined"),
        *unit_interval("s","B' strictly on AC"), *unit_interval("q","C' strictly on AB"), *inside("O"),
        *[eq(f"OnLine(O,Line({a},{a}p))",0,"three cevians concurrent") for a in "ABC"],
        *[gt(f"Distance(O,{a}p)",0,"ratio denominator nonzero") for a in "ABC"],
        eq("Distance(A,O)/Distance(O,Ap)+Distance(B,O)/Distance(O,Bp)+Distance(C,O)/Distance(O,Cp)",92,
           "given sum of three ratios")],
        "(Distance(A,O)/Distance(O,Ap))*(Distance(B,O)/Distance(O,Bp))*(Distance(C,O)/Distance(O,Cp))",
        "product of three ratios", "相似不変の比だけなのでAB=1。Cの形状自由度は残す。")

    cons = [pt("P0",0,0,"starting point")]
    for day in range(1,41):
        dx, dy = [(f"{day}**2/2","0"),("0",f"{day}**2/2"),(f"-{day}**2/2","0"),("0",f"-{day}**2/2")][(day-1)%4]
        cons.append(pt(f"P{day}",f"P{day-1}.x+({dx})",f"P{day-1}.y+({dy})",f"day {day}: east,north,west,south cyclic; length day²/2"))
    add("1993-02",[],cons,[],"Distance(P0,P40)","distance after day40",
        "出発点を原点、東x正、北y正。40日の移動定義をそのまま展開。")

    cons = [pt("A",0,0,"A"),pt("B",0,420,"B"),pt("C",560,0,"C"),pt("P1","k","m","initial interior point")]
    cond = [gt("k",0,"P1 inside triangle"),gt("m",0,"P1 inside triangle"),gt(1,"k/560+m/420","inside hypotenuse")]
    for i in range(1,7):
        cons += [pt(f"L{i}",f"560 if z{i} == 2 else 0",f"420 if z{i} == 1 else 0","die label A=0,B=1,C=2"),
                 (f"P{i+1}",f"Midpoint(P{i},L{i})",f"midpoint rule at step{i}")]
        cond.append((f"(z{i} == 0) or (z{i} == 1) or (z{i} == 2)","one of three die labels; no probability target"))
    cond += [eq("P7.x",14,"given terminal x"),eq("P7.y",92,"given terminal y")]
    add("1993-12",["k","m",*[f"z{i}" for i in range(1,7)]],cons,cond,"k+m","initial k+m",
        "原文座標を保持。有限6回の実現したラベル列も変数とdisjunctionで残す。",
        "確率・期待値を求める問題ではない。終点条件を満たす有限配置をそのまま表現し、ラベル列の列挙や逆算をしない。")

    add("1993-13",["j","k","t","m","n","u","v"],[
        pt("O",0,0,"building center"),pt("J0","j",-100,"Jenny path 100ft below center"),pt("K0","k",100,"Kenny path100ft above"),
        pt("J1","j+t",-100,"Jenny speed1 same direction"),pt("K1","k+3*t",100,"Kenny speed3"),
        ("F0","FootOfPerpendicular(O,Line(J0,K0))","initial sightline contact"),
        ("F1","FootOfPerpendicular(O,Line(J1,K1))","next sightline contact")],[
        eq("Distance(J0,K0)",200,"initial separation200"),eq("Distance(O,F0)",50,"first tangent to diameter100 building"),
        eq("Distance(O,F1)",50,"next tangency / sight resumes"),gt("t",0,"positive elapsed time"),
        gt(0,"j+k","entry: initial tangent is on approaching (left) side as both move right"),
        eq("Distance(J0,F0)+Distance(F0,K0)","Distance(J0,K0)","initial contact between people"),
        eq("Distance(J1,F1)+Distance(F1,K1)","Distance(J1,K1)","final contact between people"),
        eq("t","m/n","time in lowest terms"),*coprime()],
        "m+n","numerator+denominator of time","建物中心原点、進行方向をx正、経路をy=±100に合同固定。",
        "二つの接触時刻を未知配置のまま記述。接触点が視線の線分上にあることと入口側をguardに含む。")

    add("1993-15",["cx","cy","m","n","u","v"],[
        pt("A",0,0,"A"),pt("B",1995,0,"AB1995"),pt("C","cx","cy","C"),
        ("H","FootOfPerpendicular(C,Line(A,B))","altitude CH"),
        ("I1","Incenter(A,C,H)","incircle of ACH"),("I2","Incenter(B,C,H)","incircle of BCH"),
        ("R","FootOfPerpendicular(I1,Line(C,H))","first incircle tangency to CH"),
        ("S","FootOfPerpendicular(I2,Line(C,H))","second incircle tangency to CH")],[
        gt("cy",0,"mirror / nondegenerate"),eq("Distance(A,C)",1994,"AC1994"),eq("Distance(B,C)",1993,"BC1993"),
        gt("H.x",0,"altitude foot strictly on AB"),gt(1995,"H.x","altitude foot strictly on AB"),
        eq("Distance(R,S)","m/n","RS in lowest terms"),*coprime()],
        "m+n","sum numerator denominator","A原点、ABをx軸、Cを上側。指定長さを保持。")

    add("1994-02",["s","y","m","n"],[
        pt("O",0,0,"large center"),pt("P",-20,0,"internal tangency P"),pt("Q","-20+10",0,"PQ diameter10"),
        pt("U","-20+10/2",0,"small circle center"),
        ("big","Circle(O,20)","large radius20"),("small","Circle(U,10/2)","small diameter10"),
        pt("A","Q.x+s","y","square to right of tangent CD"),pt("B","Q.x+s","y+s","square"),
        pt("C","Q.x","y+s","CD tangent at Q"),pt("D","Q.x","y","CD tangent at Q")],[
        gt("s",0,"positive square side"),gt(0,"y","Q on CD"),gt("y+s",0,"Q on CD"),
        eq("OnCircle(A,big)",0,"A on big circle"),eq("OnCircle(B,big)",0,"B on big circle"),
        eq("s","m+sqrt(n)","AB=m+sqrt(n) integers"),*integer_radical("m","n")],
        "m+n","m+n","中心線PQをx軸、Pを左側に合同固定。CDの右に正方形を置き小円は外側。ABの縦位置は未知のまま。")

    add("1994-08",["a","b"],[pt("O",0,0,"first vertex"),pt("A","a",11,"second vertex"),pt("B","b",37,"third vertex")],[
        eq("Distance(O,A)","Distance(A,B)","equilateral"),eq("Distance(A,B)","Distance(B,O)","equilateral"),
        gt("Area(O,A,B)",0,"nondegenerate equilateral triangle")],"a*b","ab","原文の絶対座標をそのまま保持。")

    add("1994-10",["a","b","c","m","n","u","v"],[
        pt("B",0,0,"vertex B"),pt("C","b",0,"right vertex C / BC=b"),pt("A","b","a","AC=a"),
        ("D","FootOfPerpendicular(C,Line(A,B))","altitude CD")],[
        *[eq(f"IsInteger({x})",0,"integer side lengths") for x in "abc"],
        *[gt(x,0,"positive side length") for x in "abc"],eq("Distance(A,B)","c","hypotenuse integer c"),
        eq("Distance(B,D)","29**3","BD=29³"),eq("cos(Angle(A,B,C))","m/n","cos B in lowest terms"),*coprime()],
        "m+n","m+n","B原点、BCをx軸、Aを上側。未知の整数辺をそのまま保持。")

    add("1995-04",["x","y","nx","ny","h","ax","ay","bx","by"],[
        pt("O",0,0,"radius9 center"),pt("U","9-3",0,"radius3 internally tangent / center distance9-3"),
        pt("V","x","y","radius6 center"),pt("A","ax","ay","chord endpoint"),pt("B","bx","by","chord endpoint"),
        ("big","Circle(O,9)","outer circle")],[
        eq("Distance(O,V)","9-6","radius6 internally tangent"),eq("Distance(U,V)","3+6","small circles externally tangent"),
        eq("nx**2+ny**2",1,"unit line normal"),
        eq("nx*U.x+ny*U.y-h",3,"common external tangent / both centers same signed side"),
        eq("nx*V.x+ny*V.y-h",6,"common external tangent"),
        eq("nx*A.x+ny*A.y", "h", "chord A on tangent line"),eq("nx*B.x+ny*B.y","h","chord B on line"),
        eq("OnCircle(A,big)",0,"A on big circle"),eq("OnCircle(B,big)",0,"B on big circle"),gt("Distance(A,B)",0,"distinct endpoints")],
        "Distance(A,B)**2","square of chord length","大円中心原点、半径3の中心を正x側。接する中心距離だけ定義から表す。")

    add("1995-09",["s","a","b"],[
        pt("M",0,0,"altitude foot"),pt("A",0,11,"AM=11"),pt("B","-s",0,"isosceles base endpoint"),pt("C","s",0,"isosceles base endpoint"),
        pt("D",0,"11-10","D on AM, AD=10")],[
        gt("s",0,"nondegenerate isosceles"),eq("Angle(B,D,C)","3*Angle(B,A,C)","angle BDC=3 BAC"),
        eq("Distance(A,B)+Distance(A,C)+Distance(B,C)","a+sqrt(b)","perimeter a+sqrt(b) integers"),*integer_radical()],
        "a+b","a+b","M原点、AMを縦軸、等辺性からB,Cを左右対称に表示。AMの長さ保持。")

    add("1996-13",["cx","cy","t","m","n","u","v"],[
        pt("A",0,0,"A"),pt("B","sqrt(30)",0,"AB=sqrt30"),pt("C","cx","cy","C"),
        ("M","Midpoint(B,C)","AD bisects BC"),
        pt("D","A.x+t*(M.x-A.x)","A.y+t*(M.y-A.y)","D on line AM / full line, not arbitrary chosen ray")],[
        gt("cy",0,"upper nondegenerate triangle"),eq("Distance(A,C)","sqrt(6)","ACsqrt6"),eq("Distance(B,C)","sqrt(15)","BCsqrt15"),
        gt("Distance(A,D)",0,"angle ADB defined"),gt("Distance(B,D)",0,"angle ADB defined"),
        eq(dot("A","D","B"),0,"angle ADB=90°"),eq("Area(A,D,B)/Area(A,B,C)","m/n","area ratio reduced"),*coprime()],
        "m+n","m+n","A原点、AB水平、C上側。Dの根番号やtの符号を選ばない。")

    add("1996-15",["dx","dy","r"],[
        pt("A",0,0,"parallelogram"),pt("B",1,0,"similarity AB=1"),pt("D","dx","dy","D"),pt("C","1+dx","dy","C=B+D-A"),
        ("O","Midpoint(A,C)","diagonals intersection")],[
        gt("dy",0,"nondegenerate parallelogram / orientation"),
        eq("Angle(C,A,B)","2*Angle(D,B,A)","CAB twice DBA"),eq("Angle(D,B,C)","2*Angle(D,B,A)","DBC twice DBA"),
        eq("Angle(A,C,B)","r*Angle(A,O,B)","ACB=r AOB"),gt("r",0,"positive angle ratio")],
        "(1000*r) // 1","greatest integer <=1000r","角度比のみなのでAB=1で相似正規化。鏡映でdy>0。")

    add("1997-04",["cx","cy","dx","dy","r","m","n","u","v"],[
        pt("A",0,0,"first radius5 center"),pt("B","5+5",0,"second radius5 center"),pt("C","cx","cy","radius8 center"),pt("D","dx","dy","radius r center")],[
        gt("cy",0,"mirror choice for center C"),gt("r",0,"positive fourth radius"),
        eq("Distance(A,C)","5+8","external tangent"),eq("Distance(B,C)","5+8","external tangent"),
        eq("Distance(A,D)","5+r","external tangent"),eq("Distance(B,D)","5+r","external tangent"),eq("Distance(C,D)","8+r","external tangent"),
        eq("r","m/n","fourth radius reduced"),*coprime()],"m+n","m+n","5,5の二中心を水平固定。Cだけ鏡映で上側。第4中心の分枝は残す。")

    add("1997-07",["t1","t2"],[
        pt("C1","2*t1/3",0,"car east speed2/3 at t1"),pt("S1","t1/2","110-t1/2","storm southeast speed sqrt2/2 at t1"),
        pt("C2","2*t2/3",0,"car at t2"),pt("S2","t2/2","110-t2/2","storm at t2")],[
        gt("t1",0,"entry after t0"),gt("t2","t1","exit later than entry"),
        eq("Distance(C1,S1)",51,"entry boundary"),eq("Distance(C2,S2)",51,"exit boundary")],
        "(t1+t2)/2","half of entry+exit time","t0の車を原点、東x正・北y正。円の中心の運動を本文通りに記述。")

    add("1998-06",["b","dx","dy","t"],[
        pt("A",0,0,"parallelogram"),pt("B","b",0,"B"),pt("D","dx","dy","D"),pt("C","b+dx","dy","C=B+D-A"),
        pt("P","-t*dx","-t*dy","DA extended beyond A"),
        ("Q","Intersect(Line(P,C),Line(A,B))","PC meets AB"),("R","Intersect(Line(P,C),Line(D,B))","PC meets DB")],[
        gt("b",0,"AB positive"),gt("dy",0,"parallelogram nondegenerate / orientation"),gt("t",0,"P beyond A"),
        eq("Distance(P,Q)",735,"PQ735"),eq("Distance(Q,R)",112,"QR112"),
        eq("Distance(A,Q)+Distance(Q,B)","Distance(A,B)","Q on segment AB"),
        eq("Distance(D,R)+Distance(R,B)","Distance(D,B)","R on diagonal DB"),
        eq("Distance(P,Q)+Distance(Q,R)+Distance(R,C)","Distance(P,C)","order P-Q-R-C / segment intersections")],
        "Distance(R,C)","RC","A原点、AB水平、D上側。長さがあるため相似尺度は固定しない。")

    # congruent cut polygons: all 6 pairwise distances under 8 cyclic/reversed correspondences.
    left = ["X","V1","V2","Y"]
    right = ["Y","V3","V0","X"]
    congruent = []
    for sign in (1,-1):
        for shift in range(4):
            images = [right[(shift+sign*i)%4] for i in range(4)]
            congruent.append("("+" and ".join(f"Distance({left[i]},{left[j]}) == Distance({images[i]},{images[j]})"
                                             for i in range(4) for j in range(i+1,4))+")")
    add("1999-02",["e","p","q","m","n","u","v"],[
        pt("A",10,45,"given vertex"),pt("B",10,114,"given vertex"),pt("C",28,153,"given vertex"),pt("D",28,84,"given vertex"),
        pt("O",0,0,"cut line through origin"),
        *[(f"V{i}",f"{a} if e == 0 else {b}","choose either pair of opposite cut edges") for i,(a,b) in enumerate(zip("ABCD","BCDA"))],
        ("X","PointOnSegment(V0,V1,p)","first cut endpoint"),("Y","PointOnSegment(V2,V3,q)","opposite cut endpoint")],[
        ("(e == 0) or (e == 1)","two possible pairs of opposite edges"),*unit_interval("p","interior edge intersection"),*unit_interval("q","interior opposite intersection"),
        eq("X.y*n","X.x*m","cut line y=(m/n)x through origin"),eq("Y.y*n","Y.x*m","same cut line"),
        (" or ".join(congruent),"two quadrilateral pieces congruent / all pair distances under cyclic/reversed bijection"),*coprime()],
        "m+n","slope reduced numerator+denominator","絶対座標保持。中心を通ると解いて仮定せず、両切断片の合同を直接制約化。",
        "凸四角形で合同な二片は頂点数も等しいため切断は対辺同士（隣辺だと三角形と五角形）。各片の頂点順と8通りの合同対応を全て残す。")

    add("1999-09",["a","b","m","n","u","v"],[
        pt("O",0,0,"origin"),pt("E",1,0,"unit complex input"),pt("W","a","b","image of 1 under multiplication a+bi")],[
        gt("a",0,"a positive"),gt("b",0,"b positive"),eq("Distance(O,W)",8,"modulus a+bi=8"),
        eq("Distance(W,E)","Distance(W,O)","image equidistant from input and origin / homogeneity"),
        eq("b**2","m/n","b² reduced"),*coprime()],
        "m+n","m+n","複素平面の指定原点と単位を保持。",
        "任意zに対する二距離は|z|倍の|(a+bi)-1|と|a+bi|。したがってz=1の等距離条件が全zの性質と定義的に同値。a,bの値を算出しない。")

    add("1999-12",["cx","cy"],[
        pt("A",0,0,"A"),pt("B","23+27",0,"AB=AP+PB"),pt("C","cx","cy","unknown C"),pt("P",23,0,"AP23 PB27"),
        ("I","Incenter(A,B,C)","incircle center"),("T","FootOfPerpendicular(I,Line(A,B))","incircle contact with AB")],[
        gt("cy",0,"nondegenerate / mirror"),eq("T.x","P.x","incircle tangent at P"),eq("T.y","P.y","same contact"),
        eq("Distance(I,T)",21,"inradius21")],
        "Distance(A,B)+Distance(B,C)+Distance(C,A)","triangle perimeter","A原点、AB水平、C上側。AP,PB,rを保持。")

    add("1999-14",["cx","cy","px","py","m","n","u","v"],[
        pt("A",0,0,"A"),pt("B",13,0,"AB13"),pt("C","cx","cy","C"),pt("P","px","py","interior P")],[
        gt("cy",0,"mirror / nondegenerate"),eq("Distance(B,C)",14,"BC14"),eq("Distance(C,A)",15,"CA15"),*inside("P"),
        eq("Angle(P,A,B)","Angle(P,B,C)","angles PAB and PBC equal"),eq("Angle(P,B,C)","Angle(P,C,A)","angles PBC and PCA equal"),
        eq("tan(Angle(P,A,B))","m/n","tangent in lowest terms"),*coprime()],
        "m+n","m+n","A原点、AB正x、C上側。角値やP座標は未知のまま。")
    return DEFINITIONS
