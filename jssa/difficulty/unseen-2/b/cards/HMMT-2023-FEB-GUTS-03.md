# HMMT-2023-FEB-GUTS-03

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: B=(0,0), D=(d,0), d>0。ABDが直角なのでA=(0,a)、鏡映によりa>0。

## 原文（PDF照合用転記）

Let ABCD be a convex quadrilateral such that angle ABD=angle BCD=90 degrees, and let M be the midpoint of BD. Suppose CM=2 and AM=3. Compute AD.

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 原文の頂点と直角ABDの座標表現 | `constructions[0]` | `Point(0, 0)` |
| 原文の頂点と直角ABDの座標表現 | `constructions[1]` | `Point(d, 0)` |
| 原文の頂点と直角ABDの座標表現 | `constructions[2]` | `Point(0, a)` |
| 原文の頂点と直角ABDの座標表現 | `constructions[3]` | `Point(cx, cy)` |
| BDの中点 | `constructions[4]` | `Midpoint(B,D)` |
| BCD=90度 | `conditions[0]` | `Angle(B,C,D) = pi/2` |
| CM=2 | `conditions[1]` | `Distance(C,M) = 2` |
| AM=3 | `conditions[2]` | `Distance(A,M) = 3` |
| BDは正 | `conditions[3]` | `d > 0` |
| 鏡映固定 | `conditions[4]` | `a > 0` |
| 原文の凸四角形 | `conditions[5]` | `ConvexPolygon([A,B,C,D])` |
| ADの長さ | `target` | `Distance(A,D)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
