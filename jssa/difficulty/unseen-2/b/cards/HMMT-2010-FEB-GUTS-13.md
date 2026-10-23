# HMMT-2010-FEB-GUTS-13

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: 原文のxy座標を保持。頂点の任意ラベルA,B,Cを導入し、尺度・原点・回転を変えない。

## 原文（PDF照合用転記）

A triangle in the xy-plane is such that when projected onto the x-axis, y-axis, and the line y=x, the results are line segments whose endpoints are (1,0) and (5,0), (0,8) and (0,13), and (5,5) and (7.5,7.5), respectively. What is the triangle's area?

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 未知三角形の頂点 | `constructions[0]` | `Point(ax, ay)` |
| 未知三角形の頂点 | `constructions[1]` | `Point(bx, by)` |
| 未知三角形の頂点 | `constructions[2]` | `Point(cx, cy)` |
| 軸への射影線分の端点 | `conditions[0]` | `min(ax, bx, cx) = 1` |
| 軸への射影線分の端点 | `conditions[1]` | `max(ax, bx, cx) = 5` |
| 軸への射影線分の端点 | `conditions[2]` | `min(ay, by, cy) = 8` |
| 軸への射影線分の端点 | `conditions[3]` | `max(ay, by, cy) = 13` |
| y=xへの直交射影の座標の定義と下端(5,5) | `conditions[4]` | `min((ax+ay)/2, (bx+by)/2, (cx+cy)/2) = 5` |
| 同上、上端(7.5,7.5)。15/2は原文7.5の正確な表記。 | `conditions[5]` | `max((ax+ay)/2, (bx+by)/2, (cx+cy)/2) = 15/2` |
| 非退化な三角形 | `conditions[6]` | `Area(A,B,C) > 0` |
| 三角形の面積 | `target` | `Area(A,B,C)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
