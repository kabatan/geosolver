# ruff: noqa: E501, SIM115
"""Single source for the 2026 held-out DSLs, references and audit tables.

Each entry keeps the DSL next to its clause-by-clause mapping to the source
statement, so the files under dsl/, cases.jsonl and AUDIT.md never diverge.
Run: uv run python benchmarks/new-2026/build_cases.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def eq(left, right):
    return {"left": left, "operator": "=", "right": right}


def rel(left, op, right):
    return {"left": left, "operator": op, "right": right}


def pred(expression):
    return {"predicate": expression}


def pt(name, expression):
    return {"name": name, "expression": expression}


def side_opposite(p, q, line):
    """P and Q strictly on different sides of a line (perpendicular feet)."""
    return rel(
        f"Dot(Vector(FootOfPerpendicular({p}, {line}), {p}), "
        f"Vector(FootOfPerpendicular({q}, {line}), {q}))",
        "<",
        0,
    )


def side_same(p, q, line):
    return rel(
        f"Dot(Vector(FootOfPerpendicular({p}, {line}), {p}), "
        f"Vector(FootOfPerpendicular({q}, {line}), {q}))",
        ">",
        0,
    )


HMMT_GEO = "https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf"
HMMT_GUTS = "https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/guts/problems.pdf"
JMO = "https://www.imojp.org/archive/mo2026/jmo/problems/jmo36yqa.pdf"

CASES = []


def case(identifier, source, answer, variables, constructions, conditions, target, mapping,
         notes=""):
    CASES.append(
        {
            "id": identifier,
            "source": source,
            "answer": answer,
            "dsl": {
                "id": identifier,
                "variables": variables,
                "constructions": constructions,
                "conditions": conditions,
                "target": target,
            },
            "mapping": mapping,
            "notes": notes,
        }
    )


# ---------------------------------------------------------------- HMMT Geometry
case(
    "HMMT-2026-FEB-GEO-01", HMMT_GEO, ["18"],
    ["tw", "tx", "yx", "yy", "zx", "zy"],
    [
        pt("A", "Point(0, 0)"), pt("B", "Point(12, 0)"),
        pt("C", "Point(12, 12)"), pt("D", "Point(0, 12)"),
        pt("W", "PointOnSegment(A, D, tw)"), pt("X", "PointOnSegment(A, B, tx)"),
        pt("Y", "Point(yx, yy)"), pt("Z", "Point(zx, zy)"),
    ],
    [
        eq("Distance(A, W)", 4), eq("Distance(A, X)", 5),
        eq("Distance(W, X)", "Distance(X, Y)"), eq("Distance(X, Y)", "Distance(Y, Z)"),
        eq("Distance(Y, Z)", "Distance(Z, W)"), eq("Distance(W, Y)", "Distance(X, Z)"),
        pred("ConvexPolygon([W, X, Y, Z])"),
        rel("yx", ">", 0), rel("yx", "<", 12), rel("yy", ">", 0), rel("yy", "<", 12),
        rel("zx", ">", 0), rel("zx", "<", 12), rel("zy", ">", 0), rel("zy", "<", 12),
    ],
    "Area(B, C, Y)",
    [
        ("ABCD is a square, AB = 12", "A=(0,0), B=(12,0), C=(12,12), D=(0,12)", "合同の正規化（Aを原点、ABをx軸正、Dを上側）。12は原文のAB"),
        ("W lies on segment AD", "W = PointOnSegment(A, D, tw)", "閉線分"),
        ("X lies on segment AB", "X = PointOnSegment(A, B, tx)", "閉線分"),
        ("WXYZ is a square", "WX=XY=YZ=ZW, WY=XZ, ConvexPolygon([W,X,Y,Z])", "4辺等長＋対角線等長＝正方形。向きは固定しない"),
        ("Y and Z lie strictly inside ABCD", "0<yx,yy,zx,zy<12", "開区間"),
        ("AW = 4, AX = 5", "Distance(A,W)=4, Distance(A,X)=5", ""),
        ("area of triangle BCY", "target Area(B, C, Y)", ""),
    ],
)

case(
    "HMMT-2026-FEB-GEO-02", HMMT_GEO, ["191"],
    ["rx", "ry", "sx", "sy", "ex", "ey"],
    [
        pt("H", "Point(0, 0)"), pt("O", "Point(20, 0)"),
        pt("R", "Point(rx, ry)"), pt("S", "Point(sx, sy)"), pt("E", "Point(ex, ey)"),
    ],
    [
        eq("Degrees(Angle(E, H, O))", 90), eq("Degrees(Angle(O, R, S))", 90),
        eq("Degrees(Angle(S, E, H))", 90), eq("Degrees(Angle(H, O, R))", 135),
        eq("Degrees(Angle(R, S, E))", 135),
        eq("Distance(S, E)", 26), eq("Distance(O, S)", 10),
        pred("ConvexPolygon([H, O, R, S, E])"),
        rel("ey", ">", 0),
    ],
    "Area(H, O, R, S, E)",
    [
        ("HORSE is a convex pentagon", "ConvexPolygon([H,O,R,S,E])", "頂点順は原文どおり"),
        ("HO = 20", "H=(0,0), O=(20,0)", "合同の正規化"),
        ("(orientation)", "ey > 0", "鏡映の正規化（五角形をHOの上側に置く）"),
        ("∠EHO = ∠ORS = ∠SEH = 90°", "Degrees(Angle(·))=90 ×3", "Angleは0〜180°の無向角。凸なので内角と一致"),
        ("∠HOR = ∠RSE = 135°", "Degrees(Angle(·))=135 ×2", ""),
        ("SE = 26, OS = 10", "Distance(S,E)=26, Distance(O,S)=10", "OSは対角線"),
        ("area of HORSE", "target Area(H,O,R,S,E)", "靴紐公式の絶対値"),
    ],
)

case(
    "HMMT-2026-FEB-GEO-03", HMMT_GEO, ["5*sqrt(5)"],
    ["tw", "tx", "ty", "tz"],
    [
        pt("A", "Point(0, 0)"), pt("B", "Point(12, 0)"),
        pt("C", "Point(12, 16)"), pt("D", "Point(0, 16)"),
        pt("W", "PointOnSegment(A, B, tw)"), pt("X", "PointOnSegment(B, C, tx)"),
        pt("Y", "PointOnSegment(C, D, ty)"), pt("Z", "PointOnSegment(D, A, tz)"),
    ],
    [
        eq("Distance(W, X)", "Distance(X, Y)"), eq("Distance(X, Y)", "Distance(Y, Z)"),
        eq("Distance(Y, Z)", "Distance(Z, W)"),
        pred("ConvexPolygon([W, X, Y, Z])"),
        eq("Area(W, X, Y, Z)", 120),
    ],
    "Distance(X, Y)",
    [
        ("ABCD rectangle, AB = 12, BC = 16", "A=(0,0), B=(12,0), C=(12,16), D=(0,16)", "合同の正規化"),
        ("W, X, Y, Z on sides AB, BC, CD, DA", "PointOnSegment on each side", "閉線分（辺）"),
        ("WXYZ is a rhombus", "WX=XY=YZ=ZW, ConvexPolygon([W,X,Y,Z])", "4辺等長の凸四角形＝ひし形"),
        ("area 120", "Area(W,X,Y,Z)=120", ""),
        ("Compute XY", "target Distance(X,Y)", ""),
    ],
)

case(
    "HMMT-2026-FEB-GEO-04", HMMT_GEO, ["7*sqrt(3)/3"],
    ["ax", "ay", "t"],
    [
        pt("B", "Point(0, 0)"), pt("X", "Point(4, 0)"), pt("Y", "Point(9, 0)"),
        pt("C", "Point(12, 0)"), pt("A", "Point(ax, ay)"),
        pt("T", "PointOnSegment(A, C, t)"),
    ],
    [
        eq("Degrees(Angle(B, A, C))", 90),
        eq("Distance(T, A)", "Distance(T, X)"), eq("Distance(T, A)", "Distance(T, Y)"),
        rel("ay", ">", 0),
    ],
    "Distance(T, A)",
    [
        ("B, X, Y, C on segment BC in that order; BX=4, XY=5, YC=3", "B=(0,0), X=(4,0), Y=(9,0), C=(12,0)", "合同の正規化。9=4+5, 12=4+5+3 は与えられた長さの和（順序から直接）"),
        ("∠BAC = 90°", "A=(ax,ay), Degrees(Angle(B,A,C))=90, ay>0", "ay>0は鏡映の正規化"),
        ("T on segment AC", "T = PointOnSegment(A, C, t)", "閉線分"),
        ("TA = TX = TY = ℓ", "TA=TX, TA=TY", ""),
        ("Compute ℓ", "target Distance(T, A)", ""),
    ],
)

case(
    "HMMT-2026-FEB-GEO-05", HMMT_GEO, ["8*sqrt(6)"],
    ["x2", "y2", "x3", "y3", "a1", "b1", "a2", "b2", "a3", "b3"],
    [
        pt("O", "Point(0, 0)"), pt("Omega", "Circle(O, 11)"),
        pt("K1", "Point(0, 9)"), pt("K2", "Point(x2, y2)"), pt("K3", "Point(x3, y3)"),
        pt("E1", "PointOnCircle(Omega, a1)"), pt("F1", "PointOnCircle(Omega, b1)"),
        pt("E2", "PointOnCircle(Omega, a2)"), pt("F2", "PointOnCircle(Omega, b2)"),
        pt("E3", "PointOnCircle(Omega, a3)"), pt("F3", "PointOnCircle(Omega, b3)"),
        pt("l1", "Line(E1, F1)"), pt("l2", "Line(E2, F2)"), pt("l3", "Line(E3, F3)"),
        pt("V12", "Intersect(l1, l2)"), pt("V13", "Intersect(l1, l3)"),
        pt("V23", "Intersect(l2, l3)"),
    ],
    [
        eq("Distance(O, K2)", "11 - 2"), eq("Distance(O, K3)", "11 - 2"),
        eq("Distance(K1, l1)", 2), eq("Distance(K2, l1)", 2),
        eq("Distance(K1, l2)", 2), eq("Distance(K3, l2)", 2),
        eq("Distance(K2, l3)", 2), eq("Distance(K3, l3)", 2),
        eq("Distance(E1, F1)", "4*sqrt(30)"), eq("Distance(E2, F2)", "4*sqrt(30)"),
        side_same("O", "V23", "l1"), side_same("O", "V13", "l2"), side_same("O", "V12", "l3"),
        side_opposite("K1", "O", "l1"), side_opposite("K1", "O", "l2"),
        side_opposite("K2", "O", "l1"), side_opposite("K2", "O", "l3"),
        side_opposite("K3", "O", "l2"), side_opposite("K3", "O", "l3"),
    ],
    "Distance(E3, F3)",
    [
        ("Ω centered at O, radius 11", "O=(0,0), Omega=Circle(O,11)", ""),
        ("three circles of radius 2 internally tangent to Ω", "中心K1,K2,K3は |OKi| = 11-2", "内接の定義（中心距離＝半径の差）。K1=(0,9)は回転の正規化"),
        ("three chords, each tangent to two of the circles", "弦 l1=E1F1（K1,K2に接）, l2=E2F2（K1,K3）, l3=E3F3（K2,K3）。Distance(Ki, lj)=2", "端点はΩ上。接点は小円上なのでΩ内部＝弦の上"),
        ("two of the chords have length 4√30", "|E1F1| = |E2F2| = 4√30", "どの2本でも、共有する小円をK1と名付ければこの形（ラベルの付け替え）"),
        ("O lies inside the triangle formed by the three chords", "各弦の直線について、Oと向かいの頂点が同じ側", "V12,V13,V23は直線の交点"),
        ("(figure) each small circle lies in the vertical angle outside the triangle", "各小円の中心は、接する2本の弦についてOと反対側", "図から読んだ情報（notes参照）。原文だけでは決まらない可能性あり"),
        ("compute the length of the third chord", "target Distance(E3, F3)", ""),
    ],
    notes="図の読み取りに依存。原文のみ版の答え集合は検算で別途確認する。",
)

case(
    "HMMT-2026-FEB-GEO-06", HMMT_GEO, ["sqrt(17) - 1"],
    ["ax", "ay", "p", "q"],
    [
        pt("B", "Point(-4, 0)"), pt("C", "Point(4, 0)"), pt("M", "Midpoint(B, C)"),
        pt("A", "Point(ax, ay)"),
        pt("P", "PointOnSegment(A, B, p)"), pt("Q", "PointOnSegment(A, C, q)"),
    ],
    [
        eq("Angle(P, M, B)", "Angle(B, A, C) / 2"), eq("Angle(Q, M, C)", "Angle(B, A, C) / 2"),
        eq("Distance(A, P)", 1), eq("Distance(A, Q)", 3),
        rel("ay", ">", 0),
    ],
    "Distance(B, P)",
    [
        ("triangle ABC, BC = 8", "B=(-4,0), C=(4,0), A=(ax,ay), ay>0", "合同・鏡映の正規化"),
        ("M midpoint of BC", "M = Midpoint(B, C)", ""),
        ("P on segment AB, Q on segment AC", "PointOnSegment", "閉線分"),
        ("∠PMB = ∠QMC = ½∠BAC", "Angle(P,M,B) = Angle(B,A,C)/2 など", "ラジアンのまま比較"),
        ("AP = 1, AQ = 3", "Distance", ""),
        ("Compute BP", "target Distance(B, P)", ""),
    ],
)

case(
    "HMMT-2026-FEB-GEO-07", HMMT_GEO, ["74"],
    ["cx", "cy", "s1", "u1", "s2", "u2"],
    [
        pt("A", "Point(0, 0)"), pt("B", "Point(1, 0)"), pt("C", "Point(cx, cy)"),
        pt("P", "Point(s1 + u1 * cx, u1 * cy)"), pt("Q", "Point(s2 + u2 * cx, u2 * cy)"),
    ],
    [
        eq("Distance(A, C)", "Distance(A, B)"),
        eq("Distance(B, P)", "Distance(P, Q)"), eq("Distance(P, Q)", "Distance(Q, C)"),
        eq("Degrees(Angle(B, A, P))", 20), eq("Degrees(Angle(P, A, Q))", 46),
        eq("Degrees(Angle(Q, A, C))", 26),
        rel("cy", ">", 0),
        rel("s1", ">", 0), rel("u1", ">", 0), rel("s1 + u1", "<", 1),
        rel("s2", ">", 0), rel("u2", ">", 0), rel("s2 + u2", "<", 1),
    ],
    "Degrees(Angle(A, P, C))",
    [
        ("isosceles triangle, AB = AC", "A=(0,0), B=(1,0), C=(cx,cy), AC=AB, cy>0", "相似の正規化（AB=1、求める量は角度で相似不変）と鏡映の正規化"),
        ("P, Q inside triangle ABC", "P = A + s1·AB + u1·AC（s1,u1>0, s1+u1<1）, Qも同様", "三角形内部の重心座標表示（開集合）"),
        ("BP = PQ = QC", "BP=PQ, PQ=QC", ""),
        ("∠BAP=20°, ∠PAQ=46°, ∠QAC=26°", "Degrees(Angle(·))", "∠BACの値（92°）は書かない"),
        ("measure of ∠APC", "target Degrees(Angle(A,P,C))", "答え74は度数"),
    ],
)

case(
    "HMMT-2026-FEB-GEO-08", HMMT_GEO, ["sqrt(69)"],
    ["ax", "ay"],
    [
        pt("B", "Point(0, 0)"), pt("C", "Point(7, 0)"), pt("A", "Point(ax, ay)"),
        pt("H", "Orthocenter(A, B, C)"), pt("bis", "AngleBisector(B, A, C)"),
        pt("P", "Intersect(bis, Circumcircle(A, B, H), exclude=A)"),
        pt("Q", "Intersect(bis, Circumcircle(A, C, H), exclude=A)"),
        pt("M", "Intersect(bis, Circumcircle(A, B, C), exclude=A)"),
    ],
    [
        eq("Distance(A, P)", 4), eq("Distance(A, Q)", 5),
        rel("Dot(Vector(A, P), Vector(A, Q))", ">", 0),
        rel("Dot(Vector(A, Q), Vector(A, M))", ">", 0),
        rel("Distance(A, P)", "<", "Distance(A, Q)"),
        rel("Distance(A, Q)", "<", "Distance(A, M)"),
        rel("ay", ">", 0),
    ],
    "Distance(A, M)",
    [
        ("triangle ABC, BC = 7", "B=(0,0), C=(7,0), A=(ax,ay), ay>0", "合同・鏡映の正規化"),
        ("orthocenter H", "H = Orthocenter(A,B,C)", ""),
        ("internal bisector of ∠BAC meets circumcircles of ABH, ACH, ABC again at P, Q, M", "bis = AngleBisector(B,A,C); Intersect(bis, Circumcircle(·), exclude=A)", "againはAを除く交点"),
        ("A, P, Q, M distinct, in that order on the bisector", "AP·AQ>0, AQ·AM>0（同じ向き）かつ AP<AQ<AM", ""),
        ("AP = 4, AQ = 5", "Distance", ""),
        ("Compute AM", "target Distance(A, M)", ""),
    ],
)

case(
    "HMMT-2026-FEB-GEO-09", HMMT_GEO, ["3 + sqrt(11)"],
    ["a", "ax", "ay", "zx", "zy", "rho"],
    [
        pt("B", "Point(0, 0)"), pt("C", "Point(a, 0)"), pt("A", "Point(ax, ay)"),
        pt("I", "Incenter(A, B, C)"), pt("omega", "Incircle(A, B, C)"),
        pt("K", "Circumcircle(B, I, C)"),
        pt("E", "Intersect(K, omega, n=1)"), pt("F", "Intersect(K, omega, exclude=E)"),
        pt("Gamma", "Circle(Point(zx, zy), rho)"),
    ],
    [
        eq("Distance(A, B)", 5), eq("Distance(A, C)", 7),
        eq("OnCircle(E, Gamma)", 0), eq("OnCircle(F, Gamma)", 0),
        eq("IsTangent(Line(A, B), Gamma)", 0), eq("IsTangent(Line(A, C), Gamma)", 0),
        eq("Radius(Gamma)", "2 * Radius(omega)"),
        rel("a", ">", 0), rel("ay", ">", 0), rel("rho", ">", 0),
    ],
    "Distance(B, C)",
    [
        ("triangle ABC, AB = 5, AC = 7", "B=(0,0), C=(a,0), A=(ax,ay); AB=5, AC=7, a>0, ay>0", "合同・鏡映の正規化"),
        ("incenter I, incircle ω", "Incenter, Incircle", ""),
        ("circumcircle of BIC intersects ω at E and F", "K = Circumcircle(B,I,C); E = Intersect(K, omega, n=1), F = 他方の交点（exclude=E）", "EとFは対称な役割なので番号づけは任意"),
        ("Γ ≠ ω through E and F, tangent to lines AB and AC", "Gamma = Circle(Z, rho); OnCircle(E/F)=0, IsTangent(Line(A,B)/Line(A,C))=0", "Γ≠ωは半径条件から自動的に成り立つ"),
        ("Γ has twice the radius of ω", "Radius(Gamma) = 2·Radius(omega)", ""),
        ("compute BC", "target Distance(B, C)", ""),
    ],
)

case(
    "HMMT-2026-FEB-GEO-10", HMMT_GEO, ["sqrt(580/3)"],
    ["a", "ax", "ay"],
    [
        pt("B", "Point(0, 0)"), pt("C", "Point(a, 0)"), pt("A", "Point(ax, ay)"),
        pt("G", "Centroid(A, B, C)"), pt("O", "Circumcenter(A, B, C)"),
        pt("Hh", "Orthocenter(A, G, O)"),
    ],
    [
        eq("Distance(A, B)", 11), eq("Distance(A, C)", 13),
        eq("OnLine(Hh, Line(B, C))", 0),
        rel("a", ">", 0), rel("ay", ">", 0),
    ],
    "Distance(B, C)",
    [
        ("triangle ABC, AB = 11, AC = 13", "B=(0,0), C=(a,0), A=(ax,ay)", "合同・鏡映の正規化"),
        ("centroid G, circumcenter O", "Centroid, Circumcenter", ""),
        ("orthocenter of AGO lies on line BC", "OnLine(Orthocenter(A,G,O), Line(B,C)) = 0", "三角形AGOの非退化は構成の定義域で要求"),
        ("compute BC", "target Distance(B, C)", ""),
    ],
)

# ---------------------------------------------------------------- HMMT Guts
case(
    "HMMT-2026-FEB-GUTS-03", HMMT_GUTS, ["4"],
    ["t"],
    [
        pt("S0", "Point(0, 0)"), pt("S1", "Point(10, 0)"), pt("S2", "Point(10, 10)"),
        pt("S3", "Point(0, 10)"),
        pt("R1", "Point(4, 0)"), pt("R2", "Point(4, 2)"), pt("R3", "Point(0, 2)"),
        pt("P", "PointOnSegment(S3, S2, t)"),
    ],
    [
        eq(
            "Distance(R3, R2) + Distance(R2, P) + Distance(P, S3) + Distance(S3, R3)",
            "Distance(R2, R1) + Distance(R1, S1) + Distance(S1, S2) + Distance(S2, P)"
            " + Distance(P, R2)",
        ),
    ],
    "abs(Area(R3, R2, P, S3) - Area(R2, R1, S1, S2, P))",
    [
        ("square of side 10; 4×2 rectangle in the bottom-left corner", "正方形 [0,10]², 長方形 [0,4]×[0,2]", "合同の正規化"),
        ("segment from the rectangle's upper right corner (4,2) to a point on the boundary", "P = PointOnSegment((0,10),(10,10), t)", "図: 終点は上辺（x≈7〜8）。図から読んだ情報"),
        ("regions A and B", "A = 多角形(0,2),(4,2),P,(0,10)、B = (4,2),(4,0),(10,0),(10,10),P", "図: 長方形は網掛けで、A・Bは正方形から長方形を除いたL字領域を分けたもの"),
        ("same perimeter", "周の長さの等式（各辺のDistanceの和）", ""),
        ("positive difference between the areas", "target abs(Area(A) - Area(B))", ""),
    ],
    notes="領域の形は図に依存。DSLの多角形の頂点は、終点Pが上辺にあるという図の読みから書いている。",
)

case(
    "HMMT-2026-FEB-GUTS-05", HMMT_GUTS, ["7*sqrt(11)/11"],
    ["c", "t"],
    [
        pt("B", "Point(0, 0)"), pt("A", "Point(0, 5)"), pt("C", "Point(c, 0)"),
        pt("M", "Midpoint(A, C)"), pt("T", "PointOnSegment(B, C, t)"),
    ],
    [
        eq("Degrees(Angle(B, M, T))", 90), eq("Distance(M, T)", 3),
        rel("c", ">", 5),
    ],
    "Distance(C, T)",
    [
        ("right triangle, ∠ABC = 90°, AB = 5", "B=(0,0), A=(0,5), C=(c,0)", "合同の正規化（直角の頂点を原点、脚を座標軸）"),
        ("AB < BC", "c > 5", ""),
        ("M midpoint of AC", "Midpoint(A, C)", ""),
        ("T on segment BC with ∠BMT = 90°", "T = PointOnSegment(B,C,t), Degrees(Angle(B,M,T))=90", "uniqueは条件として書かない"),
        ("MT = 3", "Distance(M,T)=3", ""),
        ("compute CT", "target Distance(C, T)", ""),
    ],
)

case(
    "HMMT-2026-FEB-GUTS-09", HMMT_GUTS, ["768/25"],
    ["w", "h"],
    [
        pt("A", "Point(0, 0)"), pt("B", "Point(w, 0)"), pt("C", "Point(w, h)"),
        pt("D", "Point(0, h)"),
        pt("E", "Point(2 * w - w, 2 * 0 - h)"),
        pt("F", "Intersect(Line(C, D), Circumcircle(A, C, E), exclude=C)"),
    ],
    [
        eq("Distance(A, C)", 8), eq("Distance(A, F)", 6),
        rel("w", ">", 0), rel("h", ">", 0),
    ],
    "Area(A, B, C, D)",
    [
        ("rectangle ABCD", "A=(0,0), B=(w,0), C=(w,h), D=(0,h)", "合同の正規化"),
        ("E reflection of C over B", "E = 2B − C = (2w−w, 2·0−h)", "点対称を座標式で表記"),
        ("circumcircle of ACE meets line CD at F ≠ C", "Intersect(Line(C,D), Circumcircle(A,C,E), exclude=C)", ""),
        ("AC = 8, AF = 6", "Distance", ""),
        ("area of ABCD", "target Area(A,B,C,D)", ""),
    ],
)

case(
    "HMMT-2026-FEB-GUTS-16", HMMT_GUTS, ["3*sqrt(30)"],
    ["b", "ax", "ay"],
    [
        pt("B", "Point(-b, 0)"), pt("C", "Point(b, 0)"), pt("A", "Point(ax, ay)"),
        pt("O", "Circumcenter(A, B, C)"), pt("G", "Centroid(A, B, C)"),
        pt("M", "Midpoint(B, C)"),
    ],
    [
        eq("Distance(O, G)", 1), eq("Distance(O, M)", "sqrt(2)"),
        eq("Distance(G, M)", "sqrt(3)"),
        rel("b", ">", 0), rel("ay", ">", 0),
    ],
    "Area(A, B, C)",
    [
        ("triangle ABC", "B=(-b,0), C=(b,0), A=(ax,ay), b>0, ay>0", "合同・鏡映の正規化（BCの中点を原点）"),
        ("circumcenter O, centroid G, midpoint M of BC", "Circumcenter, Centroid, Midpoint", ""),
        ("OG = 1, OM = √2, GM = √3", "Distance", ""),
        ("area of ABC", "target Area(A,B,C)", ""),
    ],
)

case(
    "HMMT-2026-FEB-GUTS-18", HMMT_GUTS, ["165/2"],
    ["b", "cx", "dx", "h"],
    [
        pt("A", "Point(0, 0)"), pt("B", "Point(b, 0)"), pt("C", "Point(cx, h)"),
        pt("D", "Point(dx, h)"),
        pt("P", "Intersect(Line(A, C), Line(B, D))"),
    ],
    [
        eq("Distance(P, Line(A, B))", 3), eq("Distance(P, Line(B, C))", 6),
        eq("Distance(P, Line(C, D))", 8), eq("Distance(P, Line(D, A))", 8),
        pred("ConvexPolygon([A, B, C, D])"),
        rel("b", ">", 0), rel("h", ">", 0),
    ],
    "Distance(A, B) + Distance(B, C) + Distance(C, D) + Distance(D, A)",
    [
        ("trapezoid ABCD with AB ∥ CD", "A=(0,0), B=(b,0), C=(cx,h), D=(dx,h), ConvexPolygon", "合同・鏡映の正規化。平行は座標で表す"),
        ("P intersection of diagonals AC, BD", "Intersect(Line(A,C), Line(B,D))", "凸なので線分の交点と一致"),
        ("distances from P to sides AB, BC, CD, DA are 3, 6, 8, 8", "Distance(P, Line(·))", "辺を含む直線への距離"),
        ("perimeter", "target 4辺の和", ""),
    ],
)

case(
    "HMMT-2026-FEB-GUTS-28", HMMT_GUTS, ["136*sqrt(3)/13"],
    ["px", "py"],
    [
        pt("A", "Point(0, 0)"), pt("B", "Point(12 * sqrt(2), 0)"),
        pt("C", "Point(17 * cos(105 * pi / 180), 17 * sin(105 * pi / 180))"),
        pt("P", "Point(px, py)"),
    ],
    [
        eq("Degrees(Angle(A, P, B))", 60), eq("Degrees(Angle(A, P, C))", 60),
        side_opposite("P", "A", "Line(B, C)"),
    ],
    "Distance(A, P)",
    [
        ("∠BAC = 105°, AB = 12√2, AC = 17", "A=(0,0), B=(12√2,0), C=17(cos105°, sin105°)", "合同の正規化。与えられた2辺と挟角の座標化"),
        ("P and A on different sides of line BC", "垂線の足からのベクトルの内積 < 0", ""),
        ("∠APB = ∠APC = 60°", "Degrees(Angle(·))=60", ""),
        ("compute AP", "target Distance(A,P)", ""),
    ],
)

case(
    "HMMT-2026-FEB-GUTS-30", HMMT_GUTS, ["45"],
    ["ax", "ay"],
    [
        pt("B", "Point(0, 0)"), pt("C", "Point(69, 0)"), pt("A", "Point(ax, ay)"),
        pt("I", "Incenter(A, B, C)"), pt("omega", "Incircle(A, B, C)"),
        pt("D", "IncircleContactPoint(A, B, C, side='BC')"),
        pt("E", "IncircleContactPoint(A, B, C, side='CA')"),
        pt("F", "IncircleContactPoint(A, B, C, side='AB')"),
        pt("Dp", "Intersect(Line(D, I), omega, exclude=D)"),
        pt("K1", "Circumcircle(B, Dp, F)"), pt("K2", "Circumcircle(C, Dp, E)"),
        pt("Y", "Intersect(K1, K2, exclude=Dp)"),
        pt("X", "Intersect(Line(Dp, Y), Line(B, C))"),
    ],
    [
        eq("Distance(A, B)", 60), eq("Distance(A, C)", 67),
        rel("ay", ">", 0),
    ],
    "Distance(B, X)",
    [
        ("triangle ABC, AB=60, AC=67, BC=69", "B=(0,0), C=(69,0), A=(ax,ay), AB=60, AC=67, ay>0", "合同・鏡映の正規化。Aの座標は条件で与える"),
        ("incircle ω touches BC, CA, AB at D, E, F", "IncircleContactPoint(side=…)", ""),
        ("D' diametrically opposite to D in ω", "Dp = Intersect(Line(D,I), ω, exclude=D)", "中心Iを通る直線と円の他方の交点"),
        ("common chord of circumcircles of BD'F and CD'E", "共有点D'ともう一つの交点Yを結ぶ直線", ""),
        ("meets line BC at X", "Intersect(Line(Dp,Y), Line(B,C))", ""),
        ("compute BX", "target Distance(B, X)", ""),
    ],
)

# ---------------------------------------------------------------- JMO 2026 予選
case(
    "JMO-2026-PRE-03", JMO, ["11*sqrt(6)/24"],
    ["R", "tb", "tc", "td", "te"],
    [
        pt("O", "Point(0, 0)"), pt("Omega", "Circle(O, R)"),
        pt("A", "PointOnCircle(Omega, 0)"), pt("B", "PointOnCircle(Omega, tb)"),
        pt("C", "PointOnCircle(Omega, tc)"), pt("D", "PointOnCircle(Omega, td)"),
        pt("E", "PointOnCircle(Omega, te)"),
        pt("P", "Intersect(Line(B, E), Line(A, C))"),
        pt("Q", "Intersect(Line(B, E), Line(A, D))"),
    ],
    [
        eq("Distance(B, P)", "Distance(P, Q)"), eq("Distance(P, Q)", "Distance(Q, E)"),
        eq("Area(B, C, P)", 2), eq("Area(A, P, Q)", 9), eq("Area(D, E, Q)", 3),
        rel("R", ">", 0), rel("tb", ">", 0), rel("tc", ">", "tb"), rel("td", ">", "tc"),
        rel("te", ">", "td"), rel("te", "<", 1),
    ],
    "Distance(A, C) / Distance(A, D)",
    [
        ("円周上に5点A,B,C,D,Eがこの順にある", "Omega=Circle(O,R)、A..EをPointOnCircleで 0=tA<tB<tC<tD<tE<1", "Aの位置（t=0）は回転、反時計回りは鏡映の正規化。半径Rは未知"),
        ("線分BEと線分AC, ADの交点P, Q", "Intersect(Line(B,E), Line(A,C/AD))", "円周上の順序から線分どうしが交わる"),
        ("BP = PQ = QE", "BP=PQ, PQ=QE", ""),
        ("三角形BCP, APQ, DEQの面積が2, 9, 3", "Area(·)", ""),
        ("AC/ADを求めよ", "target Distance(A,C)/Distance(A,D)", ""),
    ],
)

case(
    "JMO-2026-PRE-06", JMO, ["sqrt(41) - 3"],
    ["b", "dx", "dy", "e"],
    [
        pt("A", "Point(0, 0)"), pt("B", "Point(b, 0)"), pt("D", "Point(dx, dy)"),
        pt("C", "Point(b + dx, dy)"),
        pt("E", "PointOnSegment(C, D, e)"), pt("M", "Midpoint(A, E)"),
        pt("F", "Intersect(Line(B, M), Line(A, D))"),
    ],
    [
        pred("Bound(e, (0, 1), inclusive=False)"),
        rel("Dot(Vector(F, A), Vector(F, D))", "<=", 0),
        eq("Distance(C, E)", 3), eq("Distance(D, F)", 3),
        eq("Distance(M, B)", 5), eq("Distance(M, C)", 4),
        rel("b", ">", 0), rel("dy", ">", 0),
    ],
    "Distance(A, B)",
    [
        ("平行四辺形ABCD", "A=(0,0), B=(b,0), D=(dx,dy), C=B+D−A", "合同・鏡映の正規化。平行四辺形の定義の座標化"),
        ("辺CD上（端点を除く）に点E", "PointOnSegment(C,D,e), 0<e<1", ""),
        ("線分AEの中点M", "Midpoint(A,E)", ""),
        ("直線BMと辺ADの交点F", "Intersect(Line(B,M), Line(A,D)), FA·FD ≤ 0", "Fが辺AD上（閉線分）"),
        ("CE = DF = 3, MB = 5, MC = 4", "Distance", ""),
        ("ABの長さ", "target Distance(A,B)", ""),
    ],
)

case(
    "JMO-2026-PRE-09", JMO, ["48*sqrt(7)/25"],
    ["ax", "ay", "d", "e", "f"],
    [
        pt("B", "Point(0, 0)"), pt("C", "Point(21, 0)"), pt("A", "Point(ax, ay)"),
        pt("D", "PointOnSegment(B, C, d)"), pt("E", "PointOnSegment(C, A, e)"),
        pt("F", "PointOnSegment(A, B, f)"),
        pt("P", "Intersect(PerpendicularBisector(B, D), Line(D, E))"),
        pt("Q", "Intersect(PerpendicularBisector(C, D), Line(D, F))"),
        pt("R", "Intersect(Line(B, P), Line(C, Q))"),
    ],
    [
        eq("Distance(A, B)", "Distance(A, C)"),
        pred("Bound(d, (0, 1), inclusive=False)"), pred("Bound(e, (0, 1), inclusive=False)"),
        pred("Bound(f, (0, 1), inclusive=False)"),
        eq("Degrees(Angle(E, D, F))", "180 - Degrees(Angle(B, A, C)) / 2"),
        eq("Distance(E, P)", 12), eq("Distance(F, Q)", 16),
        eq("Distance(A, R)", "6*sqrt(7)"),
        rel("ay", ">", 0),
    ],
    "Area(D, P, Q)",
    [
        ("AB = AC の二等辺三角形、BC = 21", "B=(0,0), C=(21,0), A=(ax,ay), AB=AC, ay>0", "合同・鏡映の正規化。Aの座標は条件で与える"),
        ("辺BC, CA, AB上（端点を除く）にD, E, F", "PointOnSegment＋開区間のBound", ""),
        ("∠EDF = 180° − ½∠BAC", "Degrees(Angle(E,D,F)) = 180 − Degrees(Angle(B,A,C))/2", ""),
        ("線分BDの垂直二等分線と直線DEの交点P", "Intersect(PerpendicularBisector(B,D), Line(D,E))", ""),
        ("線分CDの垂直二等分線と直線DFの交点Q", "Intersect(PerpendicularBisector(C,D), Line(D,F))", ""),
        ("直線BPと直線CQの交点R", "Intersect(Line(B,P), Line(C,Q))", ""),
        ("EP = 12, FQ = 16, AR = 6√7", "Distance", ""),
        ("三角形DPQの面積", "target Area(D,P,Q)", ""),
    ],
)


def main():
    (HERE / "dsl").mkdir(exist_ok=True)
    rows = []
    for item in CASES:
        dsl = item["dsl"]
        path = HERE / "dsl" / f"{item['id']}.json"
        path.write_text(json.dumps(dsl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rows.append(
            {
                "answer": item["answer"],
                "authoring_status": "runnable",
                "dedupe_key": item["id"],
                "dsl": dsl,
                "dsl_path": f"dsl/{item['id']}.json",
                "id": item["id"],
                "problem_kind": "natural",
                "source": item["source"],
                "truth_basis": "official answer key; DSL target is the raw quantity",
                "truth_status": "verified",
            }
        )
    (HERE / "cases.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )
    json.dump(
        {c["id"]: {"mapping": c["mapping"], "notes": c["notes"]} for c in CASES},
        open(HERE / "mapping.json", "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )


if __name__ == "__main__":
    main()
