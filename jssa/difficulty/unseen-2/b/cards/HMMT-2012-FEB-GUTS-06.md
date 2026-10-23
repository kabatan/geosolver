# HMMT-2012-FEB-GUTS-06

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: ABをx軸、ADをy軸に置く。長さ20,12は原文どおり。

## 原文（PDF照合用転記）

Let rectangle ABCD have lengths AB=20 and BC=12. Extend ray BC to Z such that CZ=18. Let E be the point in the interior of ABCD such that the perpendicular distance from E to AB is 6 and the perpendicular distance from E to AD is 6. Let line EZ intersect AB at X and CD at Y. Find the area of quadrilateral AXYD.

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 長方形ABCD、BCのC側への延長CZ=18、内部点Eの定義 | `constructions[0]` | `Point(0, 0)` |
| 長方形ABCD、BCのC側への延長CZ=18、内部点Eの定義 | `constructions[1]` | `Point(20, 0)` |
| 長方形ABCD、BCのC側への延長CZ=18、内部点Eの定義 | `constructions[2]` | `Point(20, 12)` |
| 長方形ABCD、BCのC側への延長CZ=18、内部点Eの定義 | `constructions[3]` | `Point(0, 12)` |
| 長方形ABCD、BCのC側への延長CZ=18、内部点Eの定義 | `constructions[4]` | `Point(20, 12+18)` |
| 長方形ABCD、BCのC側への延長CZ=18、内部点Eの定義 | `constructions[5]` | `Point(ex, ey)` |
| EZとABの交点 | `constructions[6]` | `IntersectLines(Line(E,Z),Line(A,B))` |
| EZとCDの交点 | `constructions[7]` | `IntersectLines(Line(E,Z),Line(C,D))` |
| EからABの垂直距離6 | `conditions[0]` | `Distance(E,Line(A,B)) = 6` |
| EからADの垂直距離6 | `conditions[1]` | `Distance(E,Line(A,D)) = 6` |
| Eは長方形内部 | `conditions[2]` | `ex > 0` |
| Eは長方形内部 | `conditions[3]` | `ex < 20` |
| Eは長方形内部 | `conditions[4]` | `ey > 0` |
| Eは長方形内部 | `conditions[5]` | `ey < 12` |
| 四角形AXYDの面積 | `target` | `Area(A,X,Y,D)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
