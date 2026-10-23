# HMMT-2025-FEB-GUTS-06

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: B=(0,0), D=(1,0), C=(1+4,0)。和1+4は原文の隣接線分BD,DCの配置。Aの座標は解かず未知にする。

## 原文（PDF照合用転記）

Let ABC be an equilateral triangle. Point D lies on segment BC such that BD=1 and DC=4. Points E and F lie on rays AC and AB, respectively, such that D is the midpoint of EF. Compute EF.

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 原文の線分BCと内部点D、未知頂点A | `constructions[0]` | `Point(0, 0)` |
| 原文の線分BCと内部点D、未知頂点A | `constructions[1]` | `Point(1, 0)` |
| 原文の線分BCと内部点D、未知頂点A | `constructions[2]` | `Point(1+4, 0)` |
| 原文の線分BCと内部点D、未知頂点A | `constructions[3]` | `Point(ax, ay)` |
| 半直線ACのパラメータt>=0 | `constructions[4]` | `Point(ax+t*(1+4-ax), ay*(1-t))` |
| 半直線ABのパラメータu>=0 | `constructions[5]` | `Point(ax*(1-u), ay*(1-u))` |
| 正三角形 | `conditions[0]` | `Distance(A,B) = Distance(B,C)` |
| 正三角形 | `conditions[1]` | `Distance(A,C) = Distance(B,C)` |
| DがEFの中点 | `conditions[2]` | `E.x+F.x = 2*D.x` |
| DがEFの中点 | `conditions[3]` | `E.y+F.y = 2*D.y` |
| 非退化・鏡映固定 | `conditions[4]` | `ay > 0` |
| Eは半直線AC上 | `conditions[5]` | `t >= 0` |
| Fは半直線AB上 | `conditions[6]` | `u >= 0` |
| EFの長さ | `target` | `Distance(E,F)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
