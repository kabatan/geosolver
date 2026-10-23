# HMMT-2016-FEB-GUTS-14

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: A=(0,0), B=(13,0), Cは上半平面。剛体変換と鏡映のみ。

## 原文（PDF照合用転記）

Let ABC be a triangle such that AB=13, BC=14, CA=15 and let E,F be the feet of the altitudes from B,C, respectively. Let the circumcircle of triangle AEF be omega. We draw three lines, tangent to the circumcircle of triangle AEF at A,E,F. Compute the area of the triangle these three lines determine.

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 座標固定 | `constructions[0]` | `Point(0, 0)` |
| AB=13 | `constructions[1]` | `Point(13, 0)` |
| 未知頂点C | `constructions[2]` | `Point(cx, cy)` |
| BC=14 | `conditions[0]` | `Distance(B,C) = 14` |
| CA=15 | `conditions[1]` | `Distance(C,A) = 15` |
| 非退化・鏡映固定 | `conditions[2]` | `cy > 0` |
| BからACへの垂足 | `constructions[3]` | `FootOfPerpendicular(Line(A,C),B)` |
| CからABへの垂足 | `constructions[4]` | `FootOfPerpendicular(Line(A,B),C)` |
| AEFの外接円 | `constructions[5]` | `Circumcircle(A,E,F)` |
| 接線は接点の半径に垂直な直線という定義 | `constructions[6]` | `PerpendicularLine(Line(Center(omega),A),A)` |
| 接線は接点の半径に垂直な直線という定義 | `constructions[7]` | `PerpendicularLine(Line(Center(omega),E),E)` |
| 接線は接点の半径に垂直な直線という定義 | `constructions[8]` | `PerpendicularLine(Line(Center(omega),F),F)` |
| 指定3接線の交点 | `constructions[9]` | `IntersectLines(lA,lE)` |
| 指定3接線の交点 | `constructions[10]` | `IntersectLines(lE,lF)` |
| 指定3接線の交点 | `constructions[11]` | `IntersectLines(lF,lA)` |
| 3接線が囲む三角形の面積 | `target` | `Area(U,V,W)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
