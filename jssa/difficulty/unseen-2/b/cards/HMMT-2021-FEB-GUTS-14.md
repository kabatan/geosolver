# HMMT-2021-FEB-GUTS-14

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: A=(0,0), B=(b,0), b>0, Cは上半平面。a,bの整数出力表現は導入せず、幾何量ABを求める。DSLのbは辺長の実数パラメータ。

## 原文（PDF照合用転記）

In triangle ABC, angle A=2*angle C. Suppose AC=6, BC=8, and AB=sqrt(a)-b, where a and b are positive integers. Compute 100a+b.

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 座標固定 | `constructions[0]` | `Point(0, 0)` |
| 未知辺長AB | `constructions[1]` | `Point(b, 0)` |
| 未知頂点 | `constructions[2]` | `Point(cx, cy)` |
| AC=6 | `conditions[0]` | `Distance(A,C) = 6` |
| BC=8 | `conditions[1]` | `Distance(B,C) = 8` |
| 角A=2角C | `conditions[2]` | `Angle(B,A,C) = 2*Angle(B,C,A)` |
| 辺長は正 | `conditions[3]` | `b > 0` |
| 非退化・鏡映固定 | `conditions[4]` | `cy > 0` |
| 幾何量AB。sqrt(a)-bから100a+bへの変換は参照答側に分離。 | `target` | `Distance(A,B)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
