"""オフラインQ2候補の再生成。solver、数値評価、ネットワークは呼ばない。

採否とDSLはanswer/rating/solutionを参照しない。参照答の転記は入力とmanifestの
書出し後にだけ行い、official_answerは未照合なのでnullのままにする。
実行: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src 指定Python このファイル
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
CORPUS = ROOT / "jssa/strategy/astra-consult-14/E/e2h-rows.jsonl"
SAVED = Path("/home/kabatan/work/solver-research-assets/corpus97-sources")
PRIOR = Path("/home/kabatan/work/solver-research-assets/corpus97-diagnostic-v1/dsl")
DEFINITIONS = {}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))


def add(key, variables, constructions, conditions, target, target_clause, gauge, notes=""):
    cid = "HMMT-" + key
    dsl = dict(id=cid, variables=variables,
               constructions=[dict(name=n, expression=e) for n, e, _ in constructions],
               conditions=[], target=target)
    mapping = [dict(path=f"constructions[{i}]", source_clause=c,
                    expression=f"{n} = {e}") for i, (n, e, c) in enumerate(constructions)]
    for i, item in enumerate(conditions):
        if len(item) == 2:
            predicate, clause = item
            cond = dict(predicate=predicate)
            expression = predicate
        else:
            left, operator, right, clause = item
            cond = dict(left=left, operator=operator, right=right)
            expression = f"{left} {operator} {right}"
        dsl["conditions"].append(cond)
        mapping.append(dict(path=f"conditions[{i}]", source_clause=clause, expression=expression))
    mapping.append(dict(path="target", source_clause=target_clause, expression=target))
    DEFINITIONS[cid] = dict(dsl=dsl, mapping=mapping, gauge=gauge, notes=notes)


def point(name, x, y, clause):
    return (name, f"Point({x}, {y})", clause)


def positive(expr, clause):
    return (expr, ">", 0, clause)


def dot(a, b, c):
    return f"(({a}.x-{b}.x)*({c}.x-{b}.x)+({a}.y-{b}.y)*({c}.y-{b}.y))"


def cross(a, b, c):
    return f"(({b}.x-{a}.x)*({c}.y-{a}.y)-({b}.y-{a}.y)*({c}.x-{a}.x))"


def acute():
    return [positive(dot(a, b, c), "acute triangle / 鋭角三角形: 各頂点の内積が正")
            for a, b, c in [("B", "A", "C"), ("A", "B", "C"), ("A", "C", "B")]]


def convex(names):
    # 各有向辺の左側に他の全頂点。単なる隣接辺の回転符号より強く、星形を除く。
    return [positive(cross(a, b, c), "convex / 狭義凸: 各辺の他の頂点はすべて内側")
            for i, a in enumerate(names)
            for b in [names[(i + 1) % len(names)]]
            for c in names if c not in (a, b)]


def definitions():
    add("2012-FEB-GUTS-01", ["x", "y"], [
        point("A", 0, 0, "square ABCD, side 2 / 座標原点"),
        point("B", 2, 0, "square ABCD, side 2"),
        point("C", 2, 2, "square ABCD, side 2"),
        point("D", 0, 2, "square ABCD, side 2"),
        point("X", "x", "y", "X is outside the square / 未知点"),
    ], [
        ("Distance(A, X)", "=", "sqrt(2)", "AX = sqrt(2)"),
        ("Distance(X, B)", "=", "sqrt(2)", "XB = sqrt(2)"),
        ("(x < 0) or (x > 2) or (y < 0) or (y > 2)", "X outside square / 正方形の閉領域の外"),
    ], "max([Distance(A, B), Distance(A, C), Distance(X, C), Distance(X, D), Distance(B, D)])",
        "longest diagonal of AXBCD / 頂点順から得る全5本の対角線の最大値",
        "Aを原点、ABを正のx軸、正方形を上側。平行移動・回転・鏡映だけ。尺度2を保持。")

    add("2013-FEB-TEAM-03", ["ax", "ay", "c"], [
        point("B", 0, 0, "triangle ABC / 座標原点"), point("C", "c", 0, "triangle ABC / BCをx軸"),
        point("A", "ax", "ay", "triangle ABC / 未知頂点"),
        ("O", "Circumcenter(A, B, C)", "circumcenter O"),
        ("omega", "Circumcircle(A, O, C)", "circumcircle of AOC"),
        ("F", "Intersect(Line(A, B), omega, exclude=A)", "line AB meets circle AOC at A and F / A以外"),
        ("E", "Intersect(Line(F, O), Line(B, C))", "FO intersects BC at E"),
    ], [positive("c", "BCの長さは正 / 非退化三角形"), positive("ay", "鏡映による向き固定"),
        ("Distance(A, C)", "=", 7, "AC = 7"),
        positive("Area(A, O, C)", "circumcircle AOCが定義される"),
        ("IsTangent(Line(B, C), omega)", "=", 0, "circle AOC is tangent to BC at C / Cは構成上円上"),
        positive("Distance(A, F)", "A and F are distinct intersections"),
        positive("Distance(F, O)", "line FOが定義される"),
    ], "Distance(B, E)", "Compute BE", "Bを原点、Cを正のx軸、Aを上半平面。合同移動のみ。")

    add("2014-FEB-TEAM-08", ["ax", "ay", "t", "s"], [
        point("B", 0, 0, "BC = 6 / 座標原点"), point("C", 6, 0, "BC = 6"),
        point("A", "ax", "ay", "triangle ABC / 未知頂点"),
        ("O", "Circumcenter(A, B, C)", "circumcenter O"),
        ("D", "FootOfPerpendicular(A, Line(B, C))", "D is the foot from A to BC"),
        ("E", "Intersect(Line(A, O), Line(B, C))", "E = AO intersection BC"),
        ("X", "PointOnSegment(D, E, t)", "X between D and E on BC"),
        ("Y", "PointOnSegment(A, D, s)", "Y on AD"),
    ], [positive("ay", "鏡映による向き固定"),
        ("Distance(A, B)", "=", 4, "AB = 4"), ("Distance(A, C)", "=", 5, "AC = 5"),
        *acute(), ("t", ">", 0, "X strictly between D and E"), ("t", "<", 1, "X strictly between D and E"),
        ("s", ">=", 0, "Y on segment AD"), ("s", "<=", 1, "Y on segment AD"),
        ("Parallel(Line(X, Y), Line(A, O))", "=", 0, "XY parallel AO"),
        ("Perpendicular(Line(Y, O), Line(A, X))", "=", 0, "YO perpendicular AX"),
        positive("Distance(A, O)", "line AOが定義される"),
        positive("Distance(D, E)", "between D and E / 区間非退化"),
        positive("Distance(X, Y)", "line XYが定義される"),
        positive("Distance(Y, O)", "line YOが定義される"),
    ], "Distance(B, X)", "Determine BX", "B=(0,0), C=(6,0), ay>0。合同移動のみ。")

    add("2015-FEB-GUTS-02", ["cx", "cy", "dx", "dy", "ex", "ey"], [
        point("A", 0, 0, "AB = 1 / 座標原点"), point("B", 1, 0, "AB = 1"),
        point("C", "cx", "cy", "convex pentagon ABCDE / 未知点"),
        point("D", "dx", "dy", "convex pentagon ABCDE / 未知点"),
        point("E", "ex", "ey", "convex pentagon ABCDE / 未知点"),
    ], [
        ("Perpendicular(Line(A, B), Line(B, C))", "=", 0, "angle ABC = 90 degrees"),
        ("Perpendicular(Line(A, C), Line(C, D))", "=", 0, "angle ACD = 90 degrees"),
        ("Perpendicular(Line(A, D), Line(D, E))", "=", 0, "angle ADE = 90 degrees"),
        ("Distance(B, C)", "=", 1, "BC = 1"), ("Distance(C, D)", "=", 1, "CD = 1"),
        ("Distance(D, E)", "=", 1, "DE = 1"), *convex(list("ABCDE")),
    ], "Distance(A, E)", "Compute AE", "A=(0,0), B=(1,0)。凸多角形の向きを鏡映で反時計回りにする。")

    add("2016-FEB-GUTS-03", [], [
        point(name, f"cos({j}*pi/4)", f"sin({j}*pi/4)",
              "regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義")
        for j, name in enumerate("PROBLEMZ")
    ] + [("I", "Intersect(Line(M, R), Line(O, Z))", "diagonals MR and OZ meet at I")], [],
        "Distance(L, I)", "Compute LI", "円の中心を原点、P=(1,0)。鏡映で頂点を反時計回り。半径1は原文。",
        "変数0も選定から除かない。頂点は正八角形の定義であって、解答の座標ではない。文字Oは頂点。")

    add("2016-FEB-TEAM-03", ["ax", "ay"], [
        point("B", 0, 0, "BC = 144 / 座標原点"), point("C", 144, 0, "BC = 144"),
        point("A", "ax", "ay", "acute triangle ABC / 未知頂点"),
        ("I", "Incenter(A, B, C)", "incenter I"), ("O", "Circumcenter(A, B, C)", "circumcenter O"),
    ], [positive("ay", "鏡映による向き固定"), *acute(),
        ("Distance(A, I)", "=", 97, "AI = 97"),
        ("Perpendicular(Line(O, I), Line(A, I))", "=", 0, "angle OIA = 90 degrees"),
        positive("Distance(O, I)", "angle OIAが定義される / OとIは相異なる"),
    ], "Area(A, B, C)", "Compute area ABC", "B=(0,0), C=(144,0), ay>0。合同移動のみ。")

    add("2016-FEB-GUTS-10", ["ax", "ay"], [
        point("B", 0, 0, "BC = 14 / 座標原点"), point("C", 14, 0, "BC = 14"),
        point("A", "ax", "ay", "triangle ABC / 未知頂点"),
        ("O", "Circumcenter(A, B, C)", "circumcenter O of ABC"),
        ("U", "Circumcenter(A, O, B)", "circumcenter of AOB"),
        ("V", "Circumcenter(A, O, C)", "circumcenter of AOC"),
    ], [positive("ay", "鏡映による向き固定"),
        ("Distance(A, B)", "=", 13, "AB = 13"), ("Distance(A, C)", "=", 15, "CA = 15"),
        positive("Area(A, O, B)", "triangle AOB has a circumcenter"),
        positive("Area(A, O, C)", "triangle AOC has a circumcenter"),
    ], "Distance(U, V)", "distance between the two circumcenters",
        "B=(0,0), C=(14,0), ay>0。合同移動のみ。")

    add("2017-FEB-GUTS-06", ["bx", "by", "dx", "dy"], [
        point("A", 0, 0, "AC = 7 / 座標原点"), point("C", 7, 0, "AC = 7"),
        point("B", "bx", "by", "convex quadrilateral ABCD / 未知点"),
        point("D", "dx", "dy", "convex quadrilateral ABCD / 未知点"),
        ("M", "Midpoint(A, B)", "M midpoint of AB"), ("P", "Midpoint(B, C)", "P midpoint of BC"),
        ("N", "Midpoint(C, D)", "N midpoint of CD"), ("Q", "Midpoint(D, A)", "Q midpoint of DA"),
    ], [("Distance(B, D)", "=", 17, "BD = 17"), *convex(list("ABCD"))],
        "Distance(M, N)**2 + Distance(P, Q)**2", "Compute MN^2 + PQ^2",
        "A=(0,0), C=(7,0)。合同移動と鏡映による凸四角形の向き固定のみ。図の自由度は残す。")

    add("2020-FEB-GUTS-02", ["ax", "ay", "bx", "by", "cx", "cy", "dy"], [
        point("O", 0, 0, "circumcircle / 中心を原点"), ("omega", "Circle(O, 1)", "circumcircle / 相似正規化"),
        point("M", 1, 0, "arc midpoint M / 回転でMを固定"),
        point("A", "ax", "ay", "A on circumcircle"), point("B", "bx", "by", "B on circumcircle"),
        point("C", "cx", "cy", "C on circumcircle"),
        point("D", 1, "dy", "DM tangent at M / 単位円のMでの接線上の点"),
    ], [*( (f"OnCircle({p}, omega)", "=", 0, f"{p} on circumcircle") for p in "ABC"),
        ("Distance(M, B)", "=", "Distance(M, C)", "M midpoint of arc BC / 両端への弦長が等しい"),
        (f"{cross('B','C','A')}*{cross('B','C','M')}", "<", 0,
         "arc BC not containing A / AとMは弦BCの反対側"),
        ("Distance(A, M)", "=", "Distance(A, C)", "AM = AC"),
        ("Angle(D, M, C)", "=", "38*pi/180", "angle DMC = 38 degrees"),
        positive(f"{cross('A','M','D')}*{cross('A','M','C')}", "D and C on same side of AM"),
        positive("Area(A, B, C)", "nondegenerate triangle ABC"),
        positive("Distance(A, M)", "line AMが定義される"),
        positive("Distance(B, M)", "arc midpoint distinct from endpoints"),
        positive("Distance(C, M)", "arc midpoint distinct from endpoints"),
        positive("Distance(D, M)", "angle DMCが定義される"),
    ], "Degrees(Angle(A, C, B))", "measure angle ACB / 度単位",
        "絶対長の指定がなく目標は角度なので半径1に相似正規化。O原点、回転でM=(1,0)。鏡映枝は両方残す。")

    add("2021-FEB-GUTS-03", ["cx", "cy", "jx", "jy", "r"], [
        point("O", 0, 0, "center O"), point("A", 2021, 0, "radius 2021 / OAを正x軸"),
        point("B", -2021, 0, "diameter AB"), point("D", 0, 2021, "angle AOD = 90 degrees"),
        point("C", "cx", "cy", "C on semicircle / 未知点"),
        point("J", "jx", "jy", "center of the inscribed circle / 補助未知点"),
        ("small", "Circle(J, r)", "circle of radius r inscribed in sector AOC"),
        point("E", "2021*jx/Distance(O, J)", "2021*jy/Distance(O, J)",
              "internal tangency E / 中心線OJ上の大円との接点"),
    ], [
        ("Distance(O, C)", "=", 2021, "C on semicircle radius 2021"),
        positive("cx", "angle AOC < 90 degrees"), positive("cy", "nondegenerate sector on chosen upper semicircle"),
        positive("r", "positive radius of inscribed circle"), positive("jx", "tangency to ray OA / 垂足が正の半直線上"),
        ("jy", "=", "r", "tangent to OA from inside sector / 上半平面"),
        ("cy*jx-cx*jy", "=", "2021*r", "tangent to OC from sector interior / 内向き符号付き距離"),
        ("Distance(O, J) + r", "=", 2021, "internal tangency to semicircle"),
        positive("Distance(O, J)", "unique tangency point E is defined"),
        ("Distance(C, D)", "=", "Distance(C, E)", "CD = CE"),
    ], "r // 1", "Compute floor(r)", "O原点、OAを正x軸、半円を鏡映で上側。半径2021は保持。",
        "接円の二つの線への接条件と内接接条件は原文の定義。rの解を導いていない。床関数は目標だけ。")

    add("2021-FEB-GUTS-09", ["bx", "by", "cx", "cy"], [
        point("O", 0, 0, "common midpoint of AD, BE, CF"),
        point("A", "7/2", 0, "AD = 7"), point("D", "-7/2", 0, "AD = 7 and midpoint O"),
        point("B", "bx", "by", "BE = 10 / 未知端点"), point("E", "-bx", "-by", "BE midpoint O"),
        point("C", "cx", "cy", "CF = 18 / 未知端点"), point("F", "-cx", "-cy", "CF midpoint O"),
    ], [
        ("Distance(B, E)", "=", 10, "BE = 10"), ("Distance(C, F)", "=", 18, "CF = 18"),
        ("4*bx**2", "=", "bx**2+by**2", "AD and BE form 60 degrees / 無向直線のcos^2=1/4"),
        ("4*cx**2", "=", "cx**2+cy**2", "AD and CF form 60 degrees / 無向直線のcos^2=1/4"),
        ("4*(bx*cx+by*cy)**2", "=", "(bx**2+by**2)*(cx**2+cy**2)", "BE and CF form 60 degrees"),
        ("Distance(A, B)", "<", "Distance(A, E)", "AB < AE"),
        ("Distance(B, C)", "<", "Distance(B, F)", "BC < BF"),
    ], "sqrt(3)*(Area(A, B, C)+Area(B, C, D)+Area(C, D, E)+Area(D, E, F)+Area(E, F, A)+Area(F, A, B))",
        "K is the sum of the six stated triangle areas; compute K*sqrt(3)",
        "共通中点を原点、ADをx軸、Aを正側。合同移動だけ。B,Cの向きは条件で定め鏡映は残す。")

    add("2022-FEB-GUTS-01", ["r"], [
        point("O", 0, 0, "regular 2022-gon / 中心"), point("P", "r", 0, "regular 2022-gon / 一頂点"),
        point("Q", "r*cos(2*pi/2022)", "r*sin(2*pi/2022)", "regular 2022-gon / 隣の頂点、中心角の定義"),
    ], [positive("r", "positive circumradius"),
        ("2022*Distance(P, Q)", "=", "157/25", "perimeter 6.28 / 同長の2022辺の和"),
    ], "(2022*Area(O, P, Q)+1/2) // 1", "area to nearest positive integer / 中心から2022枚に分割して面積を加算",
        "中心原点、Pを正x軸。鏡映で隣頂点を上側。絶対周長6.28は有理数157/25で保持。",
        "2022個の等しい中心三角形という正多角形の定義的分割。最適化や解答由来の式は使わない。")

    add("2022-FEB-TEAM-03", ["bx", "by", "cx", "cy"], [
        point("O", 0, 0, "circumcircle center / 相似正規化"), ("Gamma", "Circle(O, 1)", "circumradius R=1"),
        point("A", 1, 0, "A on Gamma / 回転固定"),
        point("B", "bx", "by", "B on Gamma"), point("C", "cx", "cy", "C on Gamma"),
        ("U", "Midpoint(A, B)", "minor arc AB midpoint / 弦中点の方向"),
        ("V", "Midpoint(A, C)", "minor arc AC midpoint / 弦中点の方向"),
        point("X", "U.x/Distance(O, U)", "U.y/Distance(O, U)", "X midpoint of minor arc AB / 弦中点方向を円へ延長"),
        point("Y", "V.x/Distance(O, V)", "V.y/Distance(O, V)", "Y midpoint of minor arc AC"),
        ("omega", "Incircle(A, B, C)", "incircle of ABC"),
    ], [("OnCircle(B, Gamma)", "=", 0, "B on circumcircle"),
        ("OnCircle(C, Gamma)", "=", 0, "C on circumcircle"),
        positive("Area(A, B, C)", "nondegenerate triangle ABC"), *acute(),
        positive("Distance(O, U)", "minor arc midpoint defined / AB not a diameter"),
        positive("Distance(O, V)", "minor arc midpoint defined / AC not a diameter"),
        positive("Distance(X, Y)", "line XY is defined"),
        ("IsTangent(Line(X, Y), omega)", "=", 0, "XY tangent to incircle"),
    ], "Distance(X, Y)", "XY in terms of R / R=1で係数XY/Rを問う",
        "原問の長さはRのみで全条件が相似不変。半径を1、O原点、A=(1,0)。鏡映は残す。",
        "係数から原問の長さはR倍で復元する。公式答えの係数変換は未実施。")

    add("2024-FEB-GUTS-06", ["ax", "ay"], [
        point("B", 0, 0, "BC = 1 / 座標原点"), point("C", 1, 0, "BC = 1"),
        point("A", "ax", "ay", "triangle ABC / 未知頂点"),
        ("M", "Midpoint(A, B)", "M midpoint of AB"), ("N", "Midpoint(A, C)", "N midpoint of AC"),
        ("P", "PointOnSegment(B, C, 1/3)", "P,Q trisect BC / Bから1/3"),
        ("Q", "PointOnSegment(B, C, 2/3)", "P,Q trisect BC / Bから2/3"),
        ("omega", "Circumcircle(A, P, Q)", "A,M,N,P,Q lie on a circle / A,P,Qで定義"),
    ], [positive("ay", "鏡映による向き固定 / 三角形非退化"),
        ("OnCircle(M, omega)", "=", 0, "M on same circle as A,P,Q"),
        ("OnCircle(N, omega)", "=", 0, "N on same circle as A,P,Q"),
    ], "Area(A, B, C)", "Compute area ABC", "B=(0,0), C=(1,0), ay>0。P,Qの交換で条件は変わらない。")

    lengths = ["Distance(O1, O2)", "Distance(O2, O3)", "Distance(O3, O4)", "Distance(O4, O1)"]
    second = "max([" + ", ".join(f"min({u}, {v})" for i, u in enumerate(lengths) for v in lengths[i+1:]) + "])"
    add("2022-FEB-GEO-07", ["x", "y", "a", "b", "h", "k"], [
        point("A", 0, 0, "square ABCD of side 10"), point("B", 10, 0, "square ABCD of side 10"),
        point("C", 10, 10, "square ABCD of side 10"), point("D", 0, 10, "square ABCD of side 10"),
        point("P", "x", "y", "P inside square"),
        ("O1", "Circumcenter(P, A, B)", "circumcenter of PAB"),
        ("O2", "Circumcenter(P, B, C)", "circumcenter of PBC"),
        ("O3", "Circumcenter(P, C, D)", "circumcenter of PCD"),
        ("O4", "Circumcenter(P, D, A)", "circumcenter of PDA"),
    ], [("x", ">", 0, "P strictly inside square"), ("x", "<", 10, "P strictly inside square"),
        ("y", ">", 0, "P strictly inside square"), ("y", "<", 10, "P strictly inside square"),
        ("Distance(P,A)+Distance(P,B)+Distance(P,C)+Distance(P,D)", "=", "23*sqrt(2)", "PA+PB+PC+PD = 23 sqrt(2)"),
        ("Area(O1, O2, O3, O4)", "=", 50, "area O1O2O3O4 = 50"),
        (f"({second})**2", "=", "a/b", "second largest length is sqrt(a/b) / 全6組のminのmaxが2番目に大きい値"),
        *[(f"IsInteger({v})", "=", 0, "a,bは正整数、h,kは既約性の整数証人") for v in ["a", "b", "h", "k"]],
        positive("a", "positive integer numerator"), positive("b", "positive integer denominator"),
        ("h*a+k*b", "=", 1, "a,b are relatively prime / Bezoutの同値な定義的条件"),
    ], "100*a+b", "Compute 100a+b", "A=(0,0), B=(10,0), 正方形を上側。合同移動のみ。",
        "整数補助変数は既約分数という原問の出力指定を保持するため。探索しやすさでは採否を決めない。PDF画像で根号と分数を確認。")

    add("2022-FEB-GEO-08", ["f", "fx", "fy", "dx", "dy"], [
        point("A", "-f", 0, "ellipse focus A / 対称中心を原点"), point("B", "f", 0, "ellipse focus B"),
        point("T", 0, 7, "minor axis length 14 / 短軸端点を定義"),
        point("F", "fx", "fy", "focus F of parabola lies on ellipse"),
        ("H", "Orthocenter(F, A, B)", "orthocenter H of FAB"),
        point("W", "H.x+dx", "H.y+dy", "directrix through H / 未知方向"),
        ("line_d", "Line(H, W)", "H lies on the directrix"),
        ("U", "FootOfPerpendicular(A, line_d)", "distance from A to directrix"),
        ("V", "FootOfPerpendicular(B, line_d)", "distance from B to directrix"),
        ("K", "FootOfPerpendicular(F, line_d)", "nondegenerate parabola / focus not on directrix"),
    ], [positive("f", "ellipse with major 50 and minor 14 has distinct foci"),
        ("Distance(T, A)+Distance(T, B)", "=", 50, "ellipse definition: distances from short-axis endpoint sum to major-axis length"),
        ("Distance(F, A)+Distance(F, B)", "=", 50, "F lies on ellipse with foci A,B and major axis 50"),
        positive("fy", "triangle FAB nondegenerate / 鏡映でFを上側"),
        ("dx**2+dy**2", "=", 1, "directrix direction is normalized / 表示だけの冗長な尺度を除く"),
        ("Distance(A, F)", "=", "Distance(A, U)", "parabola passes through A / 焦点と準線への等距離という定義"),
        ("Distance(B, F)", "=", "Distance(B, V)", "parabola passes through B"),
        positive("Distance(F, K)", "focus is not on directrix / proper parabola"),
    ], "Distance(A, H)**2+Distance(B, H)**2", "Compute AH^2+BH^2",
        "楕円の中心を原点、長軸をx軸、Aを負側。合同移動と鏡映のみ。長短軸の指定50,14を保持。",
        "楕円・放物線の焦点/準線の定義で記述し、解答由来の焦点距離やF,Hの座標は使わない。PDF両ページで原文確認。")

    add("2023-FEB-GEO-06", ["cx", "cy", "dx", "dy", "n"], [
        point("A", 0, 0, "convex quadrilateral ABCD / 座標原点"), point("B", 1, 0, "ABを相似正規化"),
        point("C", "cx", "cy", "convex quadrilateral ABCD / 未知点"),
        point("D", "dx", "dy", "convex quadrilateral ABCD / 未知点"),
    ], [*convex(list("ABCD")),
        ("Angle(C, A, B)", "=", "30*pi/180", "angle CAB = 30 degrees"),
        ("Angle(A, D, B)", "=", "30*pi/180", "angle ADB = 30 degrees"),
        ("Angle(A, B, D)", "=", "77*pi/180", "angle ABD = 77 degrees"),
        ("Distance(B, C)", "=", "Distance(C, D)", "BC = CD"),
        ("Angle(B, C, D)", "=", "n*pi/180", "angle BCD = n degrees"),
        ("IsInteger(n)", "=", 0, "n is an integer"), positive("n", "n is positive"),
    ], "n", "Compute n", "絶対長の指定がなく目標が角度なのでAB=1に相似正規化。凸四角形を反時計回りに鏡映。")

    names = list("QWARTZSPHINX")
    edges = [(names[i], names[(i+1) % 12]) for i in range(12)]
    cs = [point("Q", 0, 0, "all side lengths 2 / 座標原点"), point("W", 2, 0, "QW = 2")]
    variables = []
    for p in names[2:]:
        variables += [p.lower()+"x", p.lower()+"y"]
        cs.append(point(p, variables[-2], variables[-1], "dodecagon QWARTZSPHINX / 未知頂点"))
    conditions = []
    for i, (a, b) in enumerate(edges):
        if i:
            conditions.append((f"Distance({a}, {b})", "=", 2, "all twelve side lengths equal 2"))
        c = names[(i+2) % 12]
        conditions.append((f"Perpendicular(Line({a}, {b}), Line({b}, {c}))", "=", 0,
                           "each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用"))
    for i, (a, b) in enumerate(edges):
        for j in range(i+1, 12):
            c, d = edges[j]
            if set((a, b)) & set((c, d)):
                continue
            predicate = (f"(max({a}.x,{b}.x)<min({c}.x,{d}.x)) or "
                         f"(max({c}.x,{d}.x)<min({a}.x,{b}.x)) or "
                         f"(max({a}.y,{b}.y)<min({c}.y,{d}.y)) or "
                         f"(max({c}.y,{d}.y)<min({a}.y,{b}.y))")
            conditions.append((predicate, "not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない"))
    add("2016-FEB-GEO-01", variables, cs, conditions,
        "Area(S, I, X)", "all possible areas of triangle SIX / DSLは各許容配置の面積を返す",
        "Q=(0,0), W=(2,0)。合同移動だけ。隣接辺の直交から全辺が軸平行。鏡映・凹凸の枝は残す。",
        "原問は可能な面積の集合を問う。値の列挙はしていない。集合の完全な採点と網羅性は後続担当で設計が必要。非隣接辺の矩形分離は軸平行性の下で線分非交差と同値。")


# 原文を全件読んでつけた、平面図を含むが採用できないものの理由。
SPECIAL_EXCLUSIONS = {
    "2010-FEB-GUTS-10": ("expectation", "無作為な3点の面積の期待値。積分/確率を除いて図の目標に置換しない。"),
    "2012-FEB-ALG-03": ("nonscalar_target", "平面の二項演算だが求めるxは順序対。単一スカラーへの変更をしない。"),
    "2012-FEB-ALG-04": ("algebraic_sequence", "複素数の累乗による2013項の歩行。経路和の代数変換が必要で、直接の幾何求値として採らない。"),
    "2013-FEB-GUTS-10": ("infinite_optimization", "無限に拡張する図の面積上限。有限配置の求値に置換するには解法が必要。"),
    "2014-FEB-GUTS-07": ("optimization", "2直線を訪問する経路長の最小化。反射による最適性の導出を入力にしない。"),
    "2014-FEB-TEAM-07": ("count_optimization", "凸六角形の同長対角線の本数の最大化。有限図の単一目標と異なる。"),
    "2014-FEB-GUTS-09": ("not_planar", "半球内の最大立方体。立体かつ最適化。"),
    "2015-FEB-GUTS-06": ("counting", "正十角形の非合同三角形の個数。単一配置の測定値ではない。"),
    "2017-FEB-GUTS-10": ("limit_optimization", "全平面の点上の最小化のn→∞極限。有限図に置換しない。"),
    "2018-FEB-GUTS-01": ("missing_figure", "原文の分割図がない。総面積だけは加算できるが、図形・合同条件の対応を監査できないため保留。"),
    "2019-FEB-GUTS-08": ("greedy_covering", "貪欲に最大正三角形を配置する被覆過程の回数。最適化/反復過程。"),
    "2020-FEB-GUTS-06": ("integer_optimization", "条件を満たす正n角形の最小整数n。未知頂点数と整数最適化。"),
    "2021-FEB-GUTS-04": ("counting", "格子経路すべてに対する面積の和。組合せ列挙であり単一図の求値ではない。"),
    "2021-FEB-GUTS-05": ("integer_optimization", "角分割条件を満たす最小整数n。未知頂点数と整数最適化。"),
    "2021-FEB-TEAM-05": ("not_planar", "凸多面体の最大面数。立体の組合せ最適化。"),
    "2022-FEB-GUTS-02": ("probability", "正五角形から3頂点を選ぶ確率。組合せ列挙を図の目標に置換しない。"),
    "2022-FEB-GUTS-06": ("counting", "正多角形の配置における長さONの可能値の個数。単一値の測定とは異なる。"),
    "2022-FEB-TEAM-10": ("not_planar", "3次元の6ベクトルの操作と最大化。"),
    "2023-FEB-TEAM-05": ("count_optimization", "格子点を通る相異なる平行直線の最大本数。離散最適化。"),
    "2023-FEB-GUTS-07": ("not_planar", "2球面の交円。断面への変換はできるが、原問が平面幾何でないため除外。"),
}

RAW_EXCLUSIONS = {
    "2008-GEO-01": ("not_planar", "立方体の3頂点による角の個数。立体。"),
    "2008-GEO-08": ("optimization", "円から三辺を訪問する最短経路。"),
    "2009-GEO-02": ("not_planar", "立方体の切断と高さ。"),
    "2009-GEO-03": ("locus_area", "全ての平行四辺形中心の軌跡の面積。軌跡境界を解法から追加しない。"),
    "2009-GEO-05": ("locus_area", "存在条件を満たす中心全体の軌跡面積。抽出テキストの根号にも欠落。"),
    "2009-GEO-06": ("integer_optimization", "格子三角形の内接半径の逆数の最大化。"),
    "2010-GEO-03": ("continuum_union", "半円族の連続合併の面積。"),
    "2010-GEO-04": ("optimization", "面積条件下で距離ECを最小化。"),
    "2010-GEO-05": ("not_planar", "2010次元球面の共通点数。"),
    "2010-GEO-07": ("reachable_set_area", "距離が単調な全経路の到達集合面積。"),
    "2010-GEO-08": ("optimization", "面積最大化という制約を含む。"),
    "2011-ALGGEO-02": ("counting", "BCの可能な整数値の個数。"),
    "2011-ALGGEO-04": ("robust_optimization", "全ての頂点変位に対する凸性保証の閾値。"),
    "2011-ALGGEO-12": ("prior_authored_input", "別名の過去DSL HMMT-2011-equilateral-hexagon.json が存在。未使用と扱わない。"),
    "2011-ALGGEO-14": ("optimization", "対角線BDの最小値。"),
    "2011-ALGGEO-16": ("optimization", "点P,Q上の最小化を図形全体で最大化。"),
    "2011-ALGGEO-20": ("prior_authored_input", "別名の過去DSL HMMT-2011-two-circles-tangent-line.json が存在。未使用と扱わない。"),
    "2013-GEO-01": ("optimization", "剛体三角形の向き・位置全体で最小の高さ。"),
    "2013-GEO-06": ("optimization", "DFの最小値と最大値の積。"),
    "2013-GEO-09": ("prior_authored_input", "過去DSL HMMT-2013-FEB-GEO-09.json が存在。抽出原文の分数・根号にも欠落。"),
    "2016-GEO-05": ("count_optimization", "円の根軸の交点数の最大化。"),
    "2016-GEO-07": ("not_euclidean", "有限体上の剰余距離。ユークリッド平面幾何の入力とは異なる。"),
    "2016-GEO-08": ("expectation", "無作為な6点の凸包頂点数の期待値。"),
    "2017-GEO-02": ("optimization", "周長二等分条件下の最大面積。"),
    "2017-GEO-03": ("optimization", "全2017点集合で最適な上下界を求める順序対。"),
    "2017-GEO-08": ("optimization", "外接・内接半径指定下のsin(A/2)最大化。"),
    "2018-GEO-02": ("optimization", "ACの最小値と最大値の順序対。"),
    "2018-GEO-03": ("counting", "指定辺長・角を持つ非合同三角形の個数。"),
    "2018-GEO-04": ("not_planar", "空間で紙を折ってできる四面体の最大体積。"),
    "2018-GEO-06": ("functional_identity", "全xに対する面積公式の係数b,cの順序対。図を有限サンプルで代用しない。"),
    "2018-GEO-07": ("expectation_optimization", "期待線分長を最大にする点。"),
    "2018-GEO-09": ("expectation", "無作為100点による領域数の期待値。"),
    "2019-GEO-01": ("universal_optimization", "全ての四角形に対する角の閾値。"),
    "2019-GEO-03": ("locus_area", "存在条件を満たす平面の全点集合の面積。"),
    "2019-GEO-04": ("optimization", "六角形の最小面積。"),
    "2019-GEO-06": ("optimization", "円板鎖の包絡円半径の最大最小の差。"),
    "2019-GEO-09": ("not_planar", "直方体を平面で切る空間幾何。"),
    "2020-GEO-01": ("aggregate_values", "全ての配置の可能な面積値の積。単一配置の目標とは異なる。"),
    "2020-GEO-03": ("optimization", "トロミノを二等分する最長線分。"),
    "2020-GEO-10": ("aggregate_values", "2020接円列の存在と全friendly円面積の和。"),
    "2021-GEO-01": ("optimization", "単位円板を内部に含む円の最大半径。"),
    "2021-GEO-02": ("iterated_set_area", "21回の集合の距離膨張の面積係数。"),
    "2021-GEO-07": ("optimization", "存在条件下でfloor(r)の最小値。"),
    "2021-GEO-08": ("optimization", "2円上の直角三角形の最大面積。"),
    "2021-GEO-10": ("aggregate_values", "全ての可能な半径二乗の和。抽出テキストの根号にも欠落。"),
    "2022-GEO-04": ("probability", "面積と周長上の一様選択確率。"),
    "2022-GEO-09": ("optimization", "三角形群の重心三角形の最大面積。"),
    "2023-GEO-03": ("counting", "周長の可能な整数値の個数。"),
    "2023-GEO-09": ("optimization", "存在条件下のXGの最大値。"),
}

COMB_ALG_ALIAS = {2:2, 3:1, 4:3, 5:4, 6:6, 7:8, 9:10, 11:12, 13:14, 15:15, 16:16, 18:18, 20:20}


def local_text_rows():
    rows = []
    for path in sorted(SAVED.glob("hmmt-*-problems.txt")):
        match = re.fullmatch(r"hmmt-(\d+)-(geo|alggeo|combgeo)-problems.txt", path.name)
        if not match:
            continue
        year, part = match.groups()
        text = path.read_text()
        starts, expected = [], 1
        for m in re.finditer(r"^\s*(\d{1,2})\. (?:\[\d+\] )?", text, re.M):
            if int(m.group(1)) == expected:
                starts.append(m)
                expected += 1
        assert expected == (11 if part == "geo" else 21), path
        for i, m in enumerate(starts):
            body = text[m.end():starts[i+1].start() if i+1<len(starts) else len(text)].strip()
            # 最後の問題の後の名前/採点欄は本文ではない。raw excerptは別保存する。
            raw = body
            body = re.split(r"\f\s*(?:HMMT|\d+th Annual)", body)[0].strip()
            row = dict(contest="HMMT", year=int(year), month="Feb", subtest=part,
                       index=i+1, problem=body, raw_excerpt=raw, split="saved_pdf_text", row_idx=i+1,
                       source_kind="saved_pdf_text", source_path=str(path), truncated_cells=[])
            if (year, part, i+1) == ("2022", "geo", 7):
                row["problem"] = (
                    "Point P is located inside a square ABCD of side length 10. Let O1, O2, O3, O4 be the circumcenters "
                    "of PAB, PBC, PCD, and PDA, respectively. Given that PA + PB + PC + PD = 23 sqrt(2) and the area "
                    "of O1O2O3O4 is 50, the second largest of the lengths O1O2, O2O3, O3O4, O4O1 can be written as "
                    "sqrt(a/b), where a and b are relatively prime positive integers. Compute 100a + b.")
                row["transcription_note"] = "PDF第1ページ画像を目視し、抽出で崩れた根号・分数をASCII表記で転記。raw_excerptも保持。"
            rows.append(row)
    return rows


def canonical_id(value):
    # AIME I/II、大文字/小文字、ゼロ埋めの相違を同一視する。
    parts = value.upper().split("-")
    parts = [{"I": "1", "II": "2"}.get(x, x) for x in parts]
    return "-".join(str(int(x)) if x.isdigit() else x for x in parts)


def main():
    definitions()
    for name in ("dsl", "cards"):
        (OUT / name).mkdir(exist_ok=True)
    old_files = [ROOT / "benchmarks/cases.jsonl", ROOT / "jssa/difficulty/new2026/cases.jsonl"]
    old = [json.loads(line) for p in old_files for line in p.read_text().splitlines()]
    old_ids = {canonical_id(c["id"]) for c in old}
    old_dsls = {sha(json.dumps(c["dsl"], sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()) for c in old}
    all_rows = [json.loads(s) for s in CORPUS.read_text().splitlines()]
    corpus_rows = [dict(r, source_kind="corpus", source_path=str(CORPUS.relative_to(ROOT)))
                   for r in all_rows if r["contest"] == "HMMT" and r["month"] == "Feb"]
    merged = {(r["year"], r["subtest"], r["index"]): r for r in corpus_rows}
    raw_rows = local_text_rows()
    for r in raw_rows:
        key = (r["year"], r["subtest"], r["index"])
        if key in merged:
            merged[key].setdefault("alternate_source_paths", []).append(r["source_path"])
        else:
            merged[key] = r
    candidates = sorted(merged.values(),
                        key=lambda r: (r["year"], r["index"], r["subtest"], r["split"], r["row_idx"]))
    selected, statements, manifest, card_texts = [], [], [], []
    for year in range(1983, 2000):
        for number in range(1, 16):
            manifest.append(dict(id=f"AIME-{year}-{number:02}", status="pending_source",
                                 reason_code="missing_statement", exclusion_reason="原文未入手。分野・DSL表現可能性は未判定。",
                                 statement_sha256=None, input_sha256=None, dsl_path=None))
    for row in candidates:
        cid = f"HMMT-{row['year']}-FEB-{row['subtest'].upper()}-{row['index']:02}"
        key = cid.removeprefix("HMMT-")
        statement = row["problem"]
        entry = dict(id=cid, source_row=dict(split=row["split"], row_idx=row["row_idx"]),
                     source_path=row["source_path"], source_kind=row["source_kind"],
                     id_status="corpus_index_unverified" if row["source_kind"] == "corpus" else "saved_booklet_number",
                     statement_sha256=sha(statement.encode()),
                     input_sha256=None, dsl_path=None)
        statements.append(dict(id=cid, **entry["source_row"], problem_statement=statement,
                               statement_sha256=entry["statement_sha256"],
                               truncated_cells=row.get("truncated_cells", []), source=row["source_kind"],
                               source_path=row["source_path"], alternate_source_paths=row.get("alternate_source_paths", []),
                               raw_excerpt=row.get("raw_excerpt"), transcription_note=row.get("transcription_note")))
        if row["subtest"] == "combgeo" and row["index"] in COMB_ALG_ALIAS:
            alias = f"HMMT-2011-FEB-ALGGEO-{COMB_ALG_ALIAS[row['index']]:02}"
            entry.update(status="excluded", reason_code="same_problem_other_round", exclusion_reason=f"同一原問を部門違いで重複収録。{alias}側に一本化。", alias_of=alias)
        elif canonical_id(cid) in old_ids:
            entry.update(status="excluded", reason_code="existing_id", exclusion_reason="既存323問または2026年20問と正規化IDが一致。")
        elif row.get("truncated_cells"):
            entry.update(status="excluded", reason_code="truncated_source", exclusion_reason="二次資料のセル欠落/省略。原文を復元しない。")
        elif cid in DEFINITIONS:
            definition = DEFINITIONS[cid]
            dsl = definition["dsl"]
            assert sha(json.dumps(dsl, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()) not in old_dsls
            path = OUT / "dsl" / (cid + ".json")
            dump(path, dsl)
            entry.update(status="selected_candidate", reason_code="direct_planar_value", exclusion_reason=None,
                         input_sha256=sha(path.read_bytes()), dsl_path=str(path.relative_to(OUT)),
                         card_path=f"cards/{cid}.md", n_variables=len(dsl["variables"]))
            selected.append(dict(id=cid, dsl_path=entry["dsl_path"], dsl=dsl,
                                 source="HMMT February / " + row["source_kind"],
                                 problem_statement=statement))
            card = f"# {cid} 原文→入力対応カード\n\n"
            card += "状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。\n\n"
            card += f"- 保存資料: `{row['source_path']}` / {row['split']} / row_idx={row['row_idx']}\n"
            if row.get("transcription_note"):
                card += f"- 原文表記: {row['transcription_note']}\n"
            card += f"- 原文SHA-256: `{entry['statement_sha256']}`\n- 入力SHA-256（JSONファイルの全bytes）: `{entry['input_sha256']}`\n"
            card += f"- 座標固定・同値性: {definition['gauge']}\n- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。\n"
            card += "- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。\n\n"
            card += "## 手元の原文（保存資料）\n\n" + statement + "\n\n"
            card += "## 対応\n\n| 原文の条件・定義 | DSL位置 | 入力 |\n|---|---|---|\n"
            for m in definition["mapping"]:
                fields = [m["source_clause"], f"`{m['path']}`", f"`{m['expression']}`"]
                card += "| " + " | ".join(f.replace("|", "&#124;").replace("\n", " ") for f in fields) + " |\n"
            card += f"\n## 残る制約\n\n{definition['notes'] or '公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。'}\n"
            card += "\nAST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。\n"
            (OUT / entry["card_path"]).write_text(card)
            card_texts.append(card)
        else:
            raw_key = f"{row['year']}-{row['subtest'].upper()}-{row['index']:02}"
            code, reason = SPECIAL_EXCLUSIONS.get(key, RAW_EXCLUSIONS.get(raw_key,
                ("not_planar_value", "代数・整数・組合せ・確率等の問題で、平面図の単一の求値問題ではない。")))
            entry.update(status="excluded", reason_code=code, exclusion_reason=reason)
        manifest.append(entry)
    assert {r["id"] for r in selected} == set(DEFINITIONS), "定義と採用集合の不一致"
    jsonl(OUT / "statements.jsonl", statements)
    jsonl(OUT / "cases.jsonl", selected)
    (OUT / "cards.md").write_text("# Q2対応カード集（暫定）\n\n指定cards.mdがないため条件別表を採用。各原文・全構成・全条件・目標を対応づけた。\n\n" + "\n\n---\n\n".join(card_texts))
    source_paths = [CORPUS, *old_files, *sorted({Path(r['source_path']) for r in raw_rows}),
                    SAVED / "hmmt-2022-geo-problems.pdf",
                    *[PRIOR / n for n in ["HMMT-2011-equilateral-hexagon.json", "HMMT-2011-two-circles-tangent-line.json", "HMMT-2013-FEB-GEO-09.json"]]]
    dump(OUT / "manifest.json", dict(schema_version=2, status="incomplete_offline_candidates",
         selection_rule_file="authoring-rules.md", selection_rule_sha256=sha((OUT / "authoring-rules.md").read_bytes()),
         hash_contract="input_sha256 = SHA256 of the exact UTF-8 dsl/<id>.json bytes, including final LF; statement_sha256 = SHA256 of UTF-8 statement only",
         target_count=[24, 30], selected_count=len(selected), pending_aime_count=255,
         ready_for_main_validation=False, official_answers_verified=0,
         local_feb_corpus_rows=len(corpus_rows), saved_text_rows=len(raw_rows), merged_feb_rows=len(candidates),
         counts=dict(Counter(x["reason_code"] for x in manifest)),
         sources=[dict(path=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p), sha256=sha(p.read_bytes())) for p in source_paths],
         old_case_count=len(old), source_frame_note="既存研究が収集・保存した614行に条件づけた補完母集団。大会全体の網羅性はない。",
         solver_run=False, local_search_run=False, rows=manifest))
    # 入力、採否、対応カードを全て書き出した後でだけ、参照答を別ファイルに転記する。
    by_id = {f"HMMT-{r['year']}-FEB-{r['subtest'].upper()}-{r['index']:02}": r for r in candidates}
    jsonl(OUT / "official_answers.jsonl", [dict(id=r["id"], official_answer=None,
          official_source=None, status="official_not_available",
          corpus_reference_answer=by_id[r["id"]].get("answer"),
          reference_source=dict(path=by_id[r["id"]]["source_path"], split=by_id[r["id"]]["split"], row_idx=by_id[r["id"]]["row_idx"]),
          reference_usage="未評価・公式未照合。採否とDSLに未使用。2022 TEAM-03は原問R付きの答えを未変換で保存。")
          for r in selected])
    print(json.dumps(dict(selected=len(selected), pending_aime=255, local_feb_rows=len(candidates),
                         exclusions=dict(Counter(x["reason_code"] for x in manifest))), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
