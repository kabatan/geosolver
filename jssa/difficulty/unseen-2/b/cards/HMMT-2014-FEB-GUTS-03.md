# HMMT-2014-FEB-GUTS-03

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: 面積比なので中心を原点、外接半径を1に固定できる。

## 原文（PDF照合用転記）

Let ABCDEF be a regular hexagon. Let P be the circle inscribed in triangle BDF. Find the ratio of the area of circle P to the area of rectangle ABDE.

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 正6角形の中心角の定義。中心原点、半径1。 | `constructions[0]` | `Point(cos(2*pi*0/6), sin(2*pi*0/6))` |
| 正6角形の中心角の定義。中心原点、半径1。 | `constructions[1]` | `Point(cos(2*pi*1/6), sin(2*pi*1/6))` |
| 正6角形の中心角の定義。中心原点、半径1。 | `constructions[2]` | `Point(cos(2*pi*2/6), sin(2*pi*2/6))` |
| 正6角形の中心角の定義。中心原点、半径1。 | `constructions[3]` | `Point(cos(2*pi*3/6), sin(2*pi*3/6))` |
| 正6角形の中心角の定義。中心原点、半径1。 | `constructions[4]` | `Point(cos(2*pi*4/6), sin(2*pi*4/6))` |
| 正6角形の中心角の定義。中心原点、半径1。 | `constructions[5]` | `Point(cos(2*pi*5/6), sin(2*pi*5/6))` |
| BDFの内接円 | `constructions[6]` | `Incircle(B,D,F)` |
| 円Pの面積/長方形ABDEの面積 | `target` | `pi*Radius(P)**2/Area(A,B,D,E)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
