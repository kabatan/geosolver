# HMMT-2018-FEB-GUTS-01

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: 正方形を軸に沿わせる。辺長sは未知。原図の中線による四等分をそのまま構成。

## 原文（PDF照合用転記）

A square can be divided into four congruent figures as shown (the diagram is a square split by its horizontal and vertical midlines into four equal squares). If each of the congruent figures has area 1, what is the area of the square?

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 外側の正方形 | `constructions[0]` | `Point(0, 0)` |
| 外側の正方形 | `constructions[1]` | `Point(s, 0)` |
| 外側の正方形 | `constructions[2]` | `Point(s, s)` |
| 外側の正方形 | `constructions[3]` | `Point(0, s)` |
| 原図の中点・中心 | `constructions[4]` | `Midpoint(A,C)` |
| 原図の中点・中心 | `constructions[5]` | `Midpoint(A,B)` |
| 原図の中点・中心 | `constructions[6]` | `Midpoint(B,C)` |
| 原図の中点・中心 | `constructions[7]` | `Midpoint(C,D)` |
| 原図の中点・中心 | `constructions[8]` | `Midpoint(D,A)` |
| 4つの合同な小正方形は各面積1 | `conditions[0]` | `Area(A,M,O,Q) = 1` |
| 4つの合同な小正方形は各面積1 | `conditions[1]` | `Area(M,B,N,O) = 1` |
| 4つの合同な小正方形は各面積1 | `conditions[2]` | `Area(O,N,C,P) = 1` |
| 4つの合同な小正方形は各面積1 | `conditions[3]` | `Area(Q,O,P,D) = 1` |
| 正方形の辺長は正 | `conditions[4]` | `s > 0` |
| 外側の正方形の面積 | `target` | `Area(A,B,C,D)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
