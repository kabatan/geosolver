# HMMT-2019-FEB-GUTS-17

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: B=(0,0), C=(4,0), Aは上半平面。Pを内心とする解法は入力に使用しない。

## 原文（PDF照合用転記）

Let ABC be a triangle with AB=3, BC=4, CA=5. Let A1,A2 be points on side BC, B1,B2 points on side CA, and C1,C2 points on side AB. Suppose that there exists a point P such that PA1A2, PB1B2, and PC1C2 are congruent equilateral triangles. Find the area of convex hexagon A1A2B1B2C1C2.

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 座標固定 | `constructions[0]` | `Point(0, 0)` |
| BC=4 | `constructions[1]` | `Point(4, 0)` |
| 未知頂点 | `constructions[2]` | `Point(ax, ay)` |
| 原文で存在する点P | `constructions[3]` | `Point(px, py)` |
| AB=3 | `conditions[0]` | `Distance(A,B) = 3` |
| CA=5 | `conditions[1]` | `Distance(C,A) = 5` |
| 非退化・鏡映固定 | `conditions[2]` | `ay > 0` |
| 3つの合同な正三角形の未知辺長 | `conditions[3]` | `s > 0` |
| A1は辺BC上 | `constructions[4]` | `PointOnSegment(B,C,t1)` |
| A1は線分上 | `conditions[4]` | `t1 >= 0` |
| A1は線分上 | `conditions[5]` | `t1 <= 1` |
| A2は辺BC上 | `constructions[5]` | `PointOnSegment(B,C,t2)` |
| A2は線分上 | `conditions[6]` | `t2 >= 0` |
| A2は線分上 | `conditions[7]` | `t2 <= 1` |
| 3つの合同な正三角形の9辺が共通長s | `conditions[8]` | `Distance(P,A1) = s` |
| 3つの合同な正三角形の9辺が共通長s | `conditions[9]` | `Distance(P,A2) = s` |
| 3つの合同な正三角形の9辺が共通長s | `conditions[10]` | `Distance(A1,A2) = s` |
| B1は辺CA上 | `constructions[6]` | `PointOnSegment(C,A,u1)` |
| B1は線分上 | `conditions[11]` | `u1 >= 0` |
| B1は線分上 | `conditions[12]` | `u1 <= 1` |
| B2は辺CA上 | `constructions[7]` | `PointOnSegment(C,A,u2)` |
| B2は線分上 | `conditions[13]` | `u2 >= 0` |
| B2は線分上 | `conditions[14]` | `u2 <= 1` |
| 3つの合同な正三角形の9辺が共通長s | `conditions[15]` | `Distance(P,B1) = s` |
| 3つの合同な正三角形の9辺が共通長s | `conditions[16]` | `Distance(P,B2) = s` |
| 3つの合同な正三角形の9辺が共通長s | `conditions[17]` | `Distance(B1,B2) = s` |
| C1は辺AB上 | `constructions[8]` | `PointOnSegment(A,B,v1)` |
| C1は線分上 | `conditions[18]` | `v1 >= 0` |
| C1は線分上 | `conditions[19]` | `v1 <= 1` |
| C2は辺AB上 | `constructions[9]` | `PointOnSegment(A,B,v2)` |
| C2は線分上 | `conditions[20]` | `v2 >= 0` |
| C2は線分上 | `conditions[21]` | `v2 <= 1` |
| 3つの合同な正三角形の9辺が共通長s | `conditions[22]` | `Distance(P,C1) = s` |
| 3つの合同な正三角形の9辺が共通長s | `conditions[23]` | `Distance(P,C2) = s` |
| 3つの合同な正三角形の9辺が共通長s | `conditions[24]` | `Distance(C1,C2) = s` |
| 原文の凸六角形とラベル順序 | `conditions[25]` | `ConvexPolygon([A1,A2,B1,B2,C1,C2])` |
| 凸六角形の面積 | `target` | `Area(A1,A2,B1,B2,C1,C2)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
