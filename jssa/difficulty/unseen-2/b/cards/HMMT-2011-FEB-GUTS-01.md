# HMMT-2011-FEB-GUTS-01

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: B=(0,0), C=(b,0), b>0, Aは上半平面。剛体変換と鏡映だけ。面積1なので尺度固定しない。

## 原文（PDF照合用転記）

Let ABC be a triangle with area 1. Let points D and E lie on AB and AC, respectively, such that DE is parallel to BC and DE/BC=1/3. If F is the reflection of A across DE, find the area of triangle FBC.

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 座標固定 | `constructions[0]` | `Point(0, 0)` |
| 座標固定 | `constructions[1]` | `Point(b, 0)` |
| 未知頂点 | `constructions[2]` | `Point(x, y)` |
| DはAB上 | `constructions[3]` | `PointOnSegment(A,B,u)` |
| EはAC上 | `constructions[4]` | `PointOnSegment(A,C,v)` |
| Aの直線DEに関する鏡像 | `constructions[5]` | `Reflect(A,Line(D,E))` |
| 面積1 | `conditions[0]` | `Area(A,B,C) = 1` |
| DEとBCは平行 | `conditions[1]` | `Parallel(Line(D,E),Line(B,C)) = 0` |
| DE/BC=1/3 | `conditions[2]` | `Distance(D,E)/Distance(B,C) = 1/3` |
| BC>0 | `conditions[3]` | `b > 0` |
| 非退化・鏡映固定 | `conditions[4]` | `y > 0` |
| DはAB上 | `conditions[5]` | `u >= 0` |
| DはAB上 | `conditions[6]` | `u <= 1` |
| EはAC上 | `conditions[7]` | `v >= 0` |
| EはAC上 | `conditions[8]` | `v <= 1` |
| FBCの面積 | `target` | `Area(F,B,C)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
