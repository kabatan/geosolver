# HMMT-2020-FEB-GUTS-13

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: C=(0,0), B=(1,0), Aは上半平面。原文は直線AC,BCなのでX,Yのパラメータの正負は制限せず、Cとの相違だけを課す。

## 原文（PDF照合用転記）

Let ABC be a triangle with AB=7, BC=1, CA=4*sqrt(3). The angle trisectors of C intersect AB at D and E, and lines AC and BC intersect the circumcircle of triangle CDE again at X and Y, respectively. Find the length of XY.

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 座標固定 | `constructions[0]` | `Point(0, 0)` |
| BC=1 | `constructions[1]` | `Point(1, 0)` |
| 未知頂点 | `constructions[2]` | `Point(ax, ay)` |
| 角三等分線とABの交点 | `constructions[3]` | `PointOnSegment(A,B,u)` |
| もう一方の三等分線とABの交点 | `constructions[4]` | `PointOnSegment(A,B,v)` |
| CDEの外接円 | `constructions[5]` | `Circumcircle(C,D,E)` |
| 直線CA上の未知の第2交点 | `constructions[6]` | `Point(tx*ax, tx*ay)` |
| 直線CB上の未知の第2交点 | `constructions[7]` | `Point(ty, 0)` |
| AB=7 | `conditions[0]` | `Distance(A,B) = 7` |
| CA=4sqrt(3) | `conditions[1]` | `Distance(C,A) = 4*sqrt(3)` |
| 三等分 | `conditions[2]` | `Angle(A,C,D) = Angle(D,C,E)` |
| 三等分 | `conditions[3]` | `Angle(D,C,E) = Angle(E,C,B)` |
| 第2交点が外接円上 | `conditions[4]` | `Distance(Center(omega),X) = Radius(omega)` |
| 第2交点が外接円上 | `conditions[5]` | `Distance(Center(omega),Y) = Radius(omega)` |
| 非退化・鏡映固定 | `conditions[6]` | `ay > 0` |
| 内角三等分線の交点 | `conditions[7]` | `u > 0` |
| 内角三等分線の交点 | `conditions[8]` | `u < 1` |
| D,EをAからBの順にラベル付け（原文のX,YはD,Eを交換しても同じ） | `conditions[9]` | `v > u` |
| D,EをAからBの順にラベル付け（原文のX,YはD,Eを交換しても同じ） | `conditions[10]` | `v < 1` |
| Xは既知交点C以外 | `conditions[11]` | `tx != 0` |
| Yは既知交点C以外 | `conditions[12]` | `ty != 0` |
| XYの長さ | `target` | `Distance(X,Y)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
