# HMMT-2024-FEB-GUTS-04

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: 角度は相似不変。正五角形の中心原点・外接半径1。反時計回りのAB,BCの外側へ60度回して正三角形の第3頂点を定義する。

## 原文（PDF照合用転記）

Equilateral triangles ABF and BCG are constructed outside regular pentagon ABCDE. Compute angle FEG.

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 正5角形の中心角の定義。中心原点、半径1。 | `constructions[0]` | `Point(cos(2*pi*0/5), sin(2*pi*0/5))` |
| 正5角形の中心角の定義。中心原点、半径1。 | `constructions[1]` | `Point(cos(2*pi*1/5), sin(2*pi*1/5))` |
| 正5角形の中心角の定義。中心原点、半径1。 | `constructions[2]` | `Point(cos(2*pi*2/5), sin(2*pi*2/5))` |
| 正5角形の中心角の定義。中心原点、半径1。 | `constructions[3]` | `Point(cos(2*pi*3/5), sin(2*pi*3/5))` |
| 正5角形の中心角の定義。中心原点、半径1。 | `constructions[4]` | `Point(cos(2*pi*4/5), sin(2*pi*4/5))` |
| 辺ABの外側の正三角形 | `constructions[5]` | `Rotate(B,-pi/3,A)` |
| 辺BCの外側の正三角形 | `constructions[6]` | `Rotate(C,-pi/3,B)` |
| 角FEG（ラジアン）。公式は4pi/15も明記。 | `target` | `Angle(F,E,G)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
