# HMMT-2017-FEB-GUTS-02

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: X=(0,0), Y=(t,0), t>0, Zは上半平面。指定線分順序と長さを単位方向ベクトルで直接構成する。

## 原文（PDF照合用転記）

Let A,B,C,D,E,F be 6 points on a circle in that order. Let X be the intersection of AD and BE, Y the intersection of AD and CF, and Z the intersection of CF and BE. X lies on segments BZ and AY and Y lies on segment CZ. Given AX=3, BX=2, CY=4, DY=10, EZ=16, and FZ=12, find the perimeter of triangle XYZ.

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| AX=3, DY=10, A-X-Y-Dの順序 | `constructions[0]` | `Point(0, 0)` |
| AX=3, DY=10, A-X-Y-Dの順序 | `constructions[1]` | `Point(t, 0)` |
| AX=3, DY=10, A-X-Y-Dの順序 | `constructions[2]` | `Point(zx, zy)` |
| AX=3, DY=10, A-X-Y-Dの順序 | `constructions[3]` | `Point(-3, 0)` |
| AX=3, DY=10, A-X-Y-Dの順序 | `constructions[4]` | `Point(t+10, 0)` |
| BX=2, B-X-Zの順序 | `constructions[5]` | `Point(-2*zx/Distance(X,Z), -2*zy/Distance(X,Z))` |
| EZ=16, 円周上の順序よりB-X-Z-E | `constructions[6]` | `Point(zx+16*zx/Distance(X,Z), zy+16*zy/Distance(X,Z))` |
| CY=4, C-Y-Zの順序 | `constructions[7]` | `Point(t+4*(t-zx)/Distance(Y,Z), -4*zy/Distance(Y,Z))` |
| FZ=12, 円周上の順序よりC-Y-Z-F | `constructions[8]` | `Point(zx+12*(zx-t)/Distance(Y,Z), zy+12*zy/Distance(Y,Z))` |
| 原文の共通円 | `constructions[9]` | `Circumcircle(A,B,C)` |
| 6頂点が同一円周上 | `conditions[0]` | `Distance(Center(omega),D) = Radius(omega)` |
| 6頂点が同一円周上 | `conditions[1]` | `Distance(Center(omega),E) = Radius(omega)` |
| 6頂点が同一円周上 | `conditions[2]` | `Distance(Center(omega),F) = Radius(omega)` |
| X,Yの順序 | `conditions[3]` | `t > 0` |
| 非退化・鏡映固定 | `conditions[4]` | `zy > 0` |
| A,B,C,D,E,Fの円周順序 | `conditions[5]` | `ConvexPolygon([A,B,C,D,E,F])` |
| 三角形XYZの周長 | `target` | `Distance(X,Y)+Distance(Y,Z)+Distance(Z,X)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
