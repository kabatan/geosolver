# HMMT-2010-FEB-TEAM1-07

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: 角度だけなのでA=(0,0),Q=(1,0)。Fを下半平面に置く鏡映固定。P=F+D-Qは平行四辺形FPDQの定義。

## 原文（PDF照合用転記）

Point P lies inside a convex pentagon AFQDC such that FPDQ is a parallelogram. Given that angle FAQ=angle PAC=10 degrees, and angle PFA=angle PDC=15 degrees. What is angle AQC?

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| 原文の頂点、平行四辺形によるPの定義 | `constructions[0]` | `Point(0, 0)` |
| 原文の頂点、平行四辺形によるPの定義 | `constructions[1]` | `Point(1, 0)` |
| 原文の頂点、平行四辺形によるPの定義 | `constructions[2]` | `Point(fx, fy)` |
| 原文の頂点、平行四辺形によるPの定義 | `constructions[3]` | `Point(dx, dy)` |
| 原文の頂点、平行四辺形によるPの定義 | `constructions[4]` | `Point(cx, cy)` |
| 原文の頂点、平行四辺形によるPの定義 | `constructions[5]` | `Point(fx+dx-1, fy+dy)` |
| 指定角10度 | `conditions[0]` | `Angle(F,A,Q) = 10*pi/180` |
| 指定角10度 | `conditions[1]` | `Angle(P,A,C) = 10*pi/180` |
| 指定角15度 | `conditions[2]` | `Angle(P,F,A) = 15*pi/180` |
| 指定角15度 | `conditions[3]` | `Angle(P,D,C) = 15*pi/180` |
| 原文の凸五角形 | `conditions[4]` | `ConvexPolygon([A,F,Q,D,C])` |
| 鏡映固定 | `conditions[5]` | `fy < 0` |
| Pは凸五角形の内部。各有向辺の内側にあることを表す。 | `conditions[6]` | `(F.x-A.x)*(P.y-A.y)-(F.y-A.y)*(P.x-A.x) > 0` |
| Pは凸五角形の内部。各有向辺の内側にあることを表す。 | `conditions[7]` | `(Q.x-F.x)*(P.y-F.y)-(Q.y-F.y)*(P.x-F.x) > 0` |
| Pは凸五角形の内部。各有向辺の内側にあることを表す。 | `conditions[8]` | `(D.x-Q.x)*(P.y-Q.y)-(D.y-Q.y)*(P.x-Q.x) > 0` |
| Pは凸五角形の内部。各有向辺の内側にあることを表す。 | `conditions[9]` | `(C.x-D.x)*(P.y-D.y)-(C.y-D.y)*(P.x-D.x) > 0` |
| Pは凸五角形の内部。各有向辺の内側にあることを表す。 | `conditions[10]` | `(A.x-C.x)*(P.y-C.y)-(A.y-C.y)*(P.x-C.x) > 0` |
| 角AQC（ラジアン）。公式答pi/12。 | `target` | `Angle(A,Q,C)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
