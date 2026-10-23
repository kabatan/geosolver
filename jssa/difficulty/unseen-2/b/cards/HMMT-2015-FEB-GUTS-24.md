# HMMT-2015-FEB-GUTS-24

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: A=(0,0), B=(10,0)。Dを上半平面に置く鏡映固定。尺度は変更しない。円omegaが四角形に内包されるとは追加しない。

## 原文（PDF照合用転記）

ABCD is a cyclic quadrilateral with sides AB=10, BC=8, CD=25, and DA=12. A circle omega is tangent to segments DA, AB, and BC. Find the radius of omega.

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 原文の点、接円の未知中心W | `constructions[0]` | `Point(0, 0)` |
| 原文の点、接円の未知中心W | `constructions[1]` | `Point(10, 0)` |
| 原文の点、接円の未知中心W | `constructions[2]` | `Point(cx, cy)` |
| 原文の点、接円の未知中心W | `constructions[3]` | `Point(dx, dy)` |
| 原文の点、接円の未知中心W | `constructions[4]` | `Point(wx, wy)` |
| ABCDの共円条件のための円ABC | `constructions[5]` | `Circumcircle(A,B,C)` |
| BC=8 | `conditions[0]` | `Distance(B,C) = 8` |
| CD=25 | `conditions[1]` | `Distance(C,D) = 25` |
| DA=12 | `conditions[2]` | `Distance(D,A) = 12` |
| Dも円ABC上 | `conditions[3]` | `Distance(Center(Gamma),D) = Radius(Gamma)` |
| 接点は中心WからDAへの垂足 | `constructions[6]` | `FootOfPerpendicular(Line(D,A),W)` |
| 半径rの円が直線DAに接する | `conditions[4]` | `Distance(W,T0) = r` |
| 接点が線分DA上（延長線ではない） | `conditions[5]` | `(T0.x-D.x)*(A.x-D.x)+(T0.y-D.y)*(A.y-D.y) >= 0` |
| 接点が線分DA上（延長線ではない） | `conditions[6]` | `(T0.x-D.x)*(A.x-D.x)+(T0.y-D.y)*(A.y-D.y) <= Distance(D,A)**2` |
| 接点は中心WからABへの垂足 | `constructions[7]` | `FootOfPerpendicular(Line(A,B),W)` |
| 半径rの円が直線ABに接する | `conditions[7]` | `Distance(W,T1) = r` |
| 接点が線分AB上（延長線ではない） | `conditions[8]` | `(T1.x-A.x)*(B.x-A.x)+(T1.y-A.y)*(B.y-A.y) >= 0` |
| 接点が線分AB上（延長線ではない） | `conditions[9]` | `(T1.x-A.x)*(B.x-A.x)+(T1.y-A.y)*(B.y-A.y) <= Distance(A,B)**2` |
| 接点は中心WからBCへの垂足 | `constructions[8]` | `FootOfPerpendicular(Line(B,C),W)` |
| 半径rの円が直線BCに接する | `conditions[10]` | `Distance(W,T2) = r` |
| 接点が線分BC上（延長線ではない） | `conditions[11]` | `(T2.x-B.x)*(C.x-B.x)+(T2.y-B.y)*(C.y-B.y) >= 0` |
| 接点が線分BC上（延長線ではない） | `conditions[12]` | `(T2.x-B.x)*(C.x-B.x)+(T2.y-B.y)*(C.y-B.y) <= Distance(B,C)**2` |
| 通常の非自己交差な共円四角形の頂点順 | `conditions[13]` | `ConvexPolygon([A,B,C,D])` |
| 鏡映固定 | `conditions[14]` | `dy > 0` |
| 円の半径は正 | `conditions[15]` | `r > 0` |
| 接円omegaの半径 | `target` | `r` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
