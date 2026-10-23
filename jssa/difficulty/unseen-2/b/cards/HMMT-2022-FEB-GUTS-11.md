# HMMT-2022-FEB-GUTS-11

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: 原文の単位円を中心原点、P1=(1,0)に剛体固定。円弧領域の面積を、原文の放射線で分かれる扇形から三角形OXYを除いた定義式で表す。

## 原文（PDF照合用転記）

A regular dodecagon P1 P2 ... P12 is inscribed in a unit circle with center O. Let X be the intersection of P1P5 and OP2, and Y the intersection of P1P5 and OP4. Let A be the area of the region bounded by XY, XP2, YP4, and minor arc P2P4. Compute floor(120*A).

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 単位円の中心 | `constructions[0]` | `Point(0, 0)` |
| 正12角形の中心角の定義。中心原点、半径1。 | `constructions[1]` | `Point(cos(2*pi*0/12), sin(2*pi*0/12))` |
| 正12角形の中心角の定義。中心原点、半径1。 | `constructions[2]` | `Point(cos(2*pi*1/12), sin(2*pi*1/12))` |
| 正12角形の中心角の定義。中心原点、半径1。 | `constructions[3]` | `Point(cos(2*pi*2/12), sin(2*pi*2/12))` |
| 正12角形の中心角の定義。中心原点、半径1。 | `constructions[4]` | `Point(cos(2*pi*3/12), sin(2*pi*3/12))` |
| 正12角形の中心角の定義。中心原点、半径1。 | `constructions[5]` | `Point(cos(2*pi*4/12), sin(2*pi*4/12))` |
| 正12角形の中心角の定義。中心原点、半径1。 | `constructions[6]` | `Point(cos(2*pi*5/12), sin(2*pi*5/12))` |
| 正12角形の中心角の定義。中心原点、半径1。 | `constructions[7]` | `Point(cos(2*pi*6/12), sin(2*pi*6/12))` |
| 正12角形の中心角の定義。中心原点、半径1。 | `constructions[8]` | `Point(cos(2*pi*7/12), sin(2*pi*7/12))` |
| 正12角形の中心角の定義。中心原点、半径1。 | `constructions[9]` | `Point(cos(2*pi*8/12), sin(2*pi*8/12))` |
| 正12角形の中心角の定義。中心原点、半径1。 | `constructions[10]` | `Point(cos(2*pi*9/12), sin(2*pi*9/12))` |
| 正12角形の中心角の定義。中心原点、半径1。 | `constructions[11]` | `Point(cos(2*pi*10/12), sin(2*pi*10/12))` |
| 正12角形の中心角の定義。中心原点、半径1。 | `constructions[12]` | `Point(cos(2*pi*11/12), sin(2*pi*11/12))` |
| 指定の交点X | `constructions[13]` | `IntersectLines(Line(P1,P5),Line(O,P2))` |
| 指定の交点Y | `constructions[14]` | `IntersectLines(Line(P1,P5),Line(O,P4))` |
| 半径1の小扇形の面積theta/2から三角形OXYを引いた領域面積A。床変換は入力に置かない。 | `target` | `Angle(P2,O,P4)/2-Area(O,X,Y)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
