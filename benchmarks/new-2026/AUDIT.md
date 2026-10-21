# 2026年新規問題 DSL監査表

規則: [authoring-rules.md](authoring-rules.md)。検算方法: `verify/check_dsl.py`（GeoSolverの探索は使わず、DSL評価層＋SciPy多点開始＋60桁Gauss-Newton）。

| id | 公式の答え | 検算 | 実行可能配置の目標値 | 備考 |
|---|---|---|---|---|
| HMMT-2026-FEB-GEO-01 | 18 | PASS | 18.0（計300点開始） |  |
| HMMT-2026-FEB-GEO-02 | 191 | PASS | 191.0（計1800点開始） |  |
| HMMT-2026-FEB-GEO-03 | 5*sqrt(5) | PASS | 11.18033988749（計300点開始） |  |
| HMMT-2026-FEB-GEO-04 | 7*sqrt(3)/3 | PASS | 4.041451884327（計300点開始） |  |
| HMMT-2026-FEB-GEO-05 | 8*sqrt(6) | PASS（図の条件込み） | 19.59591794226（計3300点開始） | 図の配置条件（各小円は接する2本の弦についてOと反対側）を入れた版で一意。原文のみの版（verify/HMMT-2026-FEB-GEO-05.textonly.json）では3000点開始で36種類以上の値が出るため、図の情報は不可欠。 |
| HMMT-2026-FEB-GEO-06 | sqrt(17) - 1 | PASS | 3.123105625617（計300点開始） |  |
| HMMT-2026-FEB-GEO-07 | 74 | PASS | 74.0（計1800点開始） |  |
| HMMT-2026-FEB-GEO-08 | sqrt(69) | PASS | 8.306623862918（計300点開始） |  |
| HMMT-2026-FEB-GEO-09 | 3 + sqrt(11) | PASS（退化のみ） | 6.316624790355（計3300点開始） | BC≈2の点は A がBC上に潰れ Γ の半径→0 となる退化配置（ay≈6e-8, rho≈1e-8）。60桁精密化で棄却。公式の答え以外の実解は無し。 |
| HMMT-2026-FEB-GEO-10 | sqrt(580/3) | PASS（退化のみ） | 13.90443574307（計3300点開始） | BC≈2, 24 は AC−AB, AB+AC に当たる退化三角形（ay≈1e-7）。60桁精密化で棄却。公式の答え以外の実解は無し。 |
| HMMT-2026-FEB-GUTS-03 | 4 | PASS | 4.0（計300点開始） | 図では終点が上辺。原文のみでも、終点を右辺・左辺・下辺に置くと周長が等しくなる位置が辺の外に出る（それぞれ y=12, y=18, x=22）ことを手計算で確認。図に依存せず答えは一意。 |
| HMMT-2026-FEB-GUTS-05 | 7*sqrt(11)/11 | PASS | 2.110579412044（計300点開始） |  |
| HMMT-2026-FEB-GUTS-09 | 768/25 | PASS | 30.72（計300点開始） |  |
| HMMT-2026-FEB-GUTS-16 | 3*sqrt(30) | PASS | 16.43167672515（計300点開始） |  |
| HMMT-2026-FEB-GUTS-18 | 165/2 | PASS | 82.5（計3300点開始） |  |
| HMMT-2026-FEB-GUTS-28 | 136*sqrt(3)/13 | PASS | 18.11991614072（計300点開始） |  |
| HMMT-2026-FEB-GUTS-30 | 45 | PASS | 45.0（計300点開始） |  |
| JMO-2026-PRE-03 | 11*sqrt(6)/24 | PASS | 1.122682798775（計3300点開始） |  |
| JMO-2026-PRE-06 | sqrt(41) - 3 | PASS | 3.403124237432（計300点開始） |  |
| JMO-2026-PRE-09 | 48*sqrt(7)/25 | PASS | 5.079842517244（計3300点開始） |  |

## HMMT-2026-FEB-GEO-01

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf

**原文**

> Let $ABCD$ and $WXYZ$ be squares such that $W$ lies on segment $AD$, $X$ lies on segment $AB$, and points $Y$ and $Z$ lie strictly inside $ABCD$. Given that $AW = 4$, $AX = 5$, and $AB = 12$, compute the area of triangle $\triangle BCY$.

公式の答え: `18` → 参照値 `18`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| ABCD is a square, AB = 12 | `A=(0,0), B=(12,0), C=(12,12), D=(0,12)` | 合同の正規化（Aを原点、ABをx軸正、Dを上側）。12は原文のAB |
| W lies on segment AD | `W = PointOnSegment(A, D, tw)` | 閉線分 |
| X lies on segment AB | `X = PointOnSegment(A, B, tx)` | 閉線分 |
| WXYZ is a square | `WX=XY=YZ=ZW, WY=XZ, ConvexPolygon([W,X,Y,Z])` | 4辺等長＋対角線等長＝正方形。向きは固定しない |
| Y and Z lie strictly inside ABCD | `0<yx,yy,zx,zy<12` | 開区間 |
| AW = 4, AX = 5 | `Distance(A,W)=4, Distance(A,X)=5` |  |
| area of triangle BCY | `target Area(B, C, Y)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(A, W)",
   "operator": "=",
   "right": 4
  },
  {
   "left": "Distance(A, X)",
   "operator": "=",
   "right": 5
  },
  {
   "left": "Distance(W, X)",
   "operator": "=",
   "right": "Distance(X, Y)"
  },
  {
   "left": "Distance(X, Y)",
   "operator": "=",
   "right": "Distance(Y, Z)"
  },
  {
   "left": "Distance(Y, Z)",
   "operator": "=",
   "right": "Distance(Z, W)"
  },
  {
   "left": "Distance(W, Y)",
   "operator": "=",
   "right": "Distance(X, Z)"
  },
  {
   "predicate": "ConvexPolygon([W, X, Y, Z])"
  },
  {
   "left": "yx",
   "operator": ">",
   "right": 0
  },
  {
   "left": "yx",
   "operator": "<",
   "right": 12
  },
  {
   "left": "yy",
   "operator": ">",
   "right": 0
  },
  {
   "left": "yy",
   "operator": "<",
   "right": 12
  },
  {
   "left": "zx",
   "operator": ">",
   "right": 0
  },
  {
   "left": "zx",
   "operator": "<",
   "right": 12
  },
  {
   "left": "zy",
   "operator": ">",
   "right": 0
  },
  {
   "left": "zy",
   "operator": "<",
   "right": 12
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "A"
  },
  {
   "expression": "Point(12, 0)",
   "name": "B"
  },
  {
   "expression": "Point(12, 12)",
   "name": "C"
  },
  {
   "expression": "Point(0, 12)",
   "name": "D"
  },
  {
   "expression": "PointOnSegment(A, D, tw)",
   "name": "W"
  },
  {
   "expression": "PointOnSegment(A, B, tx)",
   "name": "X"
  },
  {
   "expression": "Point(yx, yy)",
   "name": "Y"
  },
  {
   "expression": "Point(zx, zy)",
   "name": "Z"
  }
 ],
 "id": "HMMT-2026-FEB-GEO-01",
 "target": "Area(B, C, Y)",
 "variables": [
  "tw",
  "tx",
  "yx",
  "yy",
  "zx",
  "zy"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GEO-01  vars=['tw', 'tx', 'yx', 'yy', 'zx', 'zy']  residuals=6
  validate issues: none
  starts=300 converged=300 feasible=100
  value=18.0  hits=100  |res|=8.8e-61  official_match=['18']
     at tw=0.333333333333, tx=0.416666666667, yx=9.0, yy=5.0, zx=4.0, zy=9.0
  missing_official=none  extra_values=none  => PASS
```

## HMMT-2026-FEB-GEO-02

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf

**原文**

> Let $HORSE$ be a convex pentagon such that $\angle EHO = \angle ORS = \angle SEH = 90^\circ$ and $\angle HOR = \angle RSE = 135^\circ$. Given that $HO = 20$, $SE = 26$, and $OS = 10$, compute the area of $HORSE$.

公式の答え: `191` → 参照値 `191`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| HORSE is a convex pentagon | `ConvexPolygon([H,O,R,S,E])` | 頂点順は原文どおり |
| HO = 20 | `H=(0,0), O=(20,0)` | 合同の正規化 |
| (orientation) | `ey > 0` | 鏡映の正規化（五角形をHOの上側に置く） |
| ∠EHO = ∠ORS = ∠SEH = 90° | `Degrees(Angle(·))=90 ×3` | Angleは0〜180°の無向角。凸なので内角と一致 |
| ∠HOR = ∠RSE = 135° | `Degrees(Angle(·))=135 ×2` |  |
| SE = 26, OS = 10 | `Distance(S,E)=26, Distance(O,S)=10` | OSは対角線 |
| area of HORSE | `target Area(H,O,R,S,E)` | 靴紐公式の絶対値 |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Degrees(Angle(E, H, O))",
   "operator": "=",
   "right": 90
  },
  {
   "left": "Degrees(Angle(O, R, S))",
   "operator": "=",
   "right": 90
  },
  {
   "left": "Degrees(Angle(S, E, H))",
   "operator": "=",
   "right": 90
  },
  {
   "left": "Degrees(Angle(H, O, R))",
   "operator": "=",
   "right": 135
  },
  {
   "left": "Degrees(Angle(R, S, E))",
   "operator": "=",
   "right": 135
  },
  {
   "left": "Distance(S, E)",
   "operator": "=",
   "right": 26
  },
  {
   "left": "Distance(O, S)",
   "operator": "=",
   "right": 10
  },
  {
   "predicate": "ConvexPolygon([H, O, R, S, E])"
  },
  {
   "left": "ey",
   "operator": ">",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "H"
  },
  {
   "expression": "Point(20, 0)",
   "name": "O"
  },
  {
   "expression": "Point(rx, ry)",
   "name": "R"
  },
  {
   "expression": "Point(sx, sy)",
   "name": "S"
  },
  {
   "expression": "Point(ex, ey)",
   "name": "E"
  }
 ],
 "id": "HMMT-2026-FEB-GEO-02",
 "target": "Area(H, O, R, S, E)",
 "variables": [
  "rx",
  "ry",
  "sx",
  "sy",
  "ex",
  "ey"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GEO-02  vars=['rx', 'ry', 'sx', 'sy', 'ex', 'ey']  residuals=7
  validate issues: none
  starts=300 converged=65 feasible=62
  value=191.0  hits=62  |res|=1.99e-59  official_match=['191']
     at rx=27.0, ry=7.0, sx=26.0, sy=8.0, ex=9.61595431918e-61, ey=8.0
  missing_official=none  extra_values=none  => PASS
# HMMT-2026-FEB-GEO-02  vars=['rx', 'ry', 'sx', 'sy', 'ex', 'ey']  residuals=7
  validate issues: none
  starts=1500 converged=353 feasible=342
  value=191.0  hits=342  |res|=2.99e-59  official_match=['191']
     at rx=27.0, ry=7.0, sx=26.0, sy=8.0, ex=-8.15345701421e-61, ey=8.0
  missing_official=none  extra_values=none  => PASS
```

## HMMT-2026-FEB-GEO-03

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf

**原文**

> Let $ABCD$ be a rectangle with $AB = 12$ and $BC = 16$. Points $W$, $X$, $Y$, and $Z$ lie on sides $AB$, $BC$, $CD$, and $DA$, respectively, such that $WXYZ$ is a rhombus with area $120$. Compute $XY$.

公式の答え: `5\sqrt{5}` → 参照値 `5*sqrt(5)`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| ABCD rectangle, AB = 12, BC = 16 | `A=(0,0), B=(12,0), C=(12,16), D=(0,16)` | 合同の正規化 |
| W, X, Y, Z on sides AB, BC, CD, DA | `PointOnSegment on each side` | 閉線分（辺） |
| WXYZ is a rhombus | `WX=XY=YZ=ZW, ConvexPolygon([W,X,Y,Z])` | 4辺等長の凸四角形＝ひし形 |
| area 120 | `Area(W,X,Y,Z)=120` |  |
| Compute XY | `target Distance(X,Y)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(W, X)",
   "operator": "=",
   "right": "Distance(X, Y)"
  },
  {
   "left": "Distance(X, Y)",
   "operator": "=",
   "right": "Distance(Y, Z)"
  },
  {
   "left": "Distance(Y, Z)",
   "operator": "=",
   "right": "Distance(Z, W)"
  },
  {
   "predicate": "ConvexPolygon([W, X, Y, Z])"
  },
  {
   "left": "Area(W, X, Y, Z)",
   "operator": "=",
   "right": 120
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "A"
  },
  {
   "expression": "Point(12, 0)",
   "name": "B"
  },
  {
   "expression": "Point(12, 16)",
   "name": "C"
  },
  {
   "expression": "Point(0, 16)",
   "name": "D"
  },
  {
   "expression": "PointOnSegment(A, B, tw)",
   "name": "W"
  },
  {
   "expression": "PointOnSegment(B, C, tx)",
   "name": "X"
  },
  {
   "expression": "PointOnSegment(C, D, ty)",
   "name": "Y"
  },
  {
   "expression": "PointOnSegment(D, A, tz)",
   "name": "Z"
  }
 ],
 "id": "HMMT-2026-FEB-GEO-03",
 "target": "Distance(X, Y)",
 "variables": [
  "tw",
  "tx",
  "ty",
  "tz"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GEO-03  vars=['tw', 'tx', 'ty', 'tz']  residuals=4
  validate issues: none
  starts=300 converged=275 feasible=275
  value=11.180339887498948482045868343656381  hits=275  |res|=0.0  official_match=['5*sqrt(5)']
     at tw=0.166666666667, tx=0.3125, ty=0.166666666667, tz=0.3125
  missing_official=none  extra_values=none  => PASS
```

## HMMT-2026-FEB-GEO-04

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf

**原文**

> Let $ABC$ be a triangle with $\angle BAC = 90^\circ$. Points $X$ and $Y$ are such that $B$, $X$, $Y$, and $C$ lie on segment $BC$ in that order, $BX = 4$, $XY = 5$, and $YC = 3$. Let $T$ be a point lying on segment $AC$ such that $TA = TX = TY = \ell$ for some $\ell$. Compute $\ell$.

公式の答え: `\frac{7}{3}\sqrt{3}` → 参照値 `7*sqrt(3)/3`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| B, X, Y, C on segment BC in that order; BX=4, XY=5, YC=3 | `B=(0,0), X=(4,0), Y=(9,0), C=(12,0)` | 合同の正規化。9=4+5, 12=4+5+3 は与えられた長さの和（順序から直接） |
| ∠BAC = 90° | `A=(ax,ay), Degrees(Angle(B,A,C))=90, ay>0` | ay>0は鏡映の正規化 |
| T on segment AC | `T = PointOnSegment(A, C, t)` | 閉線分 |
| TA = TX = TY = ℓ | `TA=TX, TA=TY` |  |
| Compute ℓ | `target Distance(T, A)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Degrees(Angle(B, A, C))",
   "operator": "=",
   "right": 90
  },
  {
   "left": "Distance(T, A)",
   "operator": "=",
   "right": "Distance(T, X)"
  },
  {
   "left": "Distance(T, A)",
   "operator": "=",
   "right": "Distance(T, Y)"
  },
  {
   "left": "ay",
   "operator": ">",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "B"
  },
  {
   "expression": "Point(4, 0)",
   "name": "X"
  },
  {
   "expression": "Point(9, 0)",
   "name": "Y"
  },
  {
   "expression": "Point(12, 0)",
   "name": "C"
  },
  {
   "expression": "Point(ax, ay)",
   "name": "A"
  },
  {
   "expression": "PointOnSegment(A, C, t)",
   "name": "T"
  }
 ],
 "id": "HMMT-2026-FEB-GEO-04",
 "target": "Distance(T, A)",
 "variables": [
  "ax",
  "ay",
  "t"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GEO-04  vars=['ax', 'ay', 't']  residuals=3
  validate issues: none
  starts=300 converged=273 feasible=273
  value=4.0414518843273803515640414635137022  hits=273  |res|=8.8e-61  official_match=['7*sqrt(3)/3']
     at ax=3.0, ay=5.19615242271, t=0.388888888889
  missing_official=none  extra_values=none  => PASS
```

## HMMT-2026-FEB-GEO-05

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf

**原文**

> In the diagram below, three circles of radius $2$ are internally tangent to a circle $\Omega$ centered at $O$ of radius $11$, and three chords of $\Omega$ are each tangent to two of the three circles. Given that $O$ lies inside the triangle formed by the three chords and two of the chords have length $4\sqrt{30}$, compute the length of the third chord.

図の情報（収集時のメモ）: Figure (read from PDF, no solution consulted): left-right symmetric picture. One horizontal chord in the lower part of Omega; two slanted chords run from the lower ends near the horizontal chord up to the top of Omega and cross each other above O, forming a narrow 'X' near the top. One small circle sits at the top, inside the wedge above the crossing point of the two slanted chords, internally tangent to Omega. The other two small circles sit below the horizontal chord, one near each lower-left/lower-right end, each tangent to the horizontal chord and one slanted chord and internally tangent to Omega. O is inside the triangle bounded by the three chord lines (apex = crossing of the slanted chords, base = horizontal chord). By the symmetry of the figure the two slanted chords are the ones of length 4*sqrt(30); the horizontal chord is the third.

公式の答え: `8\sqrt{6}` → 参照値 `8*sqrt(6)`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| Ω centered at O, radius 11 | `O=(0,0), Omega=Circle(O,11)` |  |
| three circles of radius 2 internally tangent to Ω | `中心K1,K2,K3は |OKi| = 11-2` | 内接の定義（中心距離＝半径の差）。K1=(0,9)は回転の正規化 |
| three chords, each tangent to two of the circles | `弦 l1=E1F1（K1,K2に接）, l2=E2F2（K1,K3）, l3=E3F3（K2,K3）。Distance(Ki, lj)=2` | 端点はΩ上。接点は小円上なのでΩ内部＝弦の上 |
| two of the chords have length 4√30 | `|E1F1| = |E2F2| = 4√30` | どの2本でも、共有する小円をK1と名付ければこの形（ラベルの付け替え） |
| O lies inside the triangle formed by the three chords | `各弦の直線について、Oと向かいの頂点が同じ側` | V12,V13,V23は直線の交点 |
| (figure) each small circle lies in the vertical angle outside the triangle | `各小円の中心は、接する2本の弦についてOと反対側` | 図から読んだ情報（notes参照）。原文だけでは決まらない可能性あり |
| compute the length of the third chord | `target Distance(E3, F3)` |  |

注: 図の読み取りに依存。原文のみ版の答え集合は検算で別途確認する。

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(O, K2)",
   "operator": "=",
   "right": "11 - 2"
  },
  {
   "left": "Distance(O, K3)",
   "operator": "=",
   "right": "11 - 2"
  },
  {
   "left": "Distance(K1, l1)",
   "operator": "=",
   "right": 2
  },
  {
   "left": "Distance(K2, l1)",
   "operator": "=",
   "right": 2
  },
  {
   "left": "Distance(K1, l2)",
   "operator": "=",
   "right": 2
  },
  {
   "left": "Distance(K3, l2)",
   "operator": "=",
   "right": 2
  },
  {
   "left": "Distance(K2, l3)",
   "operator": "=",
   "right": 2
  },
  {
   "left": "Distance(K3, l3)",
   "operator": "=",
   "right": 2
  },
  {
   "left": "Distance(E1, F1)",
   "operator": "=",
   "right": "4*sqrt(30)"
  },
  {
   "left": "Distance(E2, F2)",
   "operator": "=",
   "right": "4*sqrt(30)"
  },
  {
   "left": "Dot(Vector(FootOfPerpendicular(O, l1), O), Vector(FootOfPerpendicular(V23, l1), V23))",
   "operator": ">",
   "right": 0
  },
  {
   "left": "Dot(Vector(FootOfPerpendicular(O, l2), O), Vector(FootOfPerpendicular(V13, l2), V13))",
   "operator": ">",
   "right": 0
  },
  {
   "left": "Dot(Vector(FootOfPerpendicular(O, l3), O), Vector(FootOfPerpendicular(V12, l3), V12))",
   "operator": ">",
   "right": 0
  },
  {
   "left": "Dot(Vector(FootOfPerpendicular(K1, l1), K1), Vector(FootOfPerpendicular(O, l1), O))",
   "operator": "<",
   "right": 0
  },
  {
   "left": "Dot(Vector(FootOfPerpendicular(K1, l2), K1), Vector(FootOfPerpendicular(O, l2), O))",
   "operator": "<",
   "right": 0
  },
  {
   "left": "Dot(Vector(FootOfPerpendicular(K2, l1), K2), Vector(FootOfPerpendicular(O, l1), O))",
   "operator": "<",
   "right": 0
  },
  {
   "left": "Dot(Vector(FootOfPerpendicular(K2, l3), K2), Vector(FootOfPerpendicular(O, l3), O))",
   "operator": "<",
   "right": 0
  },
  {
   "left": "Dot(Vector(FootOfPerpendicular(K3, l2), K3), Vector(FootOfPerpendicular(O, l2), O))",
   "operator": "<",
   "right": 0
  },
  {
   "left": "Dot(Vector(FootOfPerpendicular(K3, l3), K3), Vector(FootOfPerpendicular(O, l3), O))",
   "operator": "<",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "O"
  },
  {
   "expression": "Circle(O, 11)",
   "name": "Omega"
  },
  {
   "expression": "Point(0, 9)",
   "name": "K1"
  },
  {
   "expression": "Point(x2, y2)",
   "name": "K2"
  },
  {
   "expression": "Point(x3, y3)",
   "name": "K3"
  },
  {
   "expression": "PointOnCircle(Omega, a1)",
   "name": "E1"
  },
  {
   "expression": "PointOnCircle(Omega, b1)",
   "name": "F1"
  },
  {
   "expression": "PointOnCircle(Omega, a2)",
   "name": "E2"
  },
  {
   "expression": "PointOnCircle(Omega, b2)",
   "name": "F2"
  },
  {
   "expression": "PointOnCircle(Omega, a3)",
   "name": "E3"
  },
  {
   "expression": "PointOnCircle(Omega, b3)",
   "name": "F3"
  },
  {
   "expression": "Line(E1, F1)",
   "name": "l1"
  },
  {
   "expression": "Line(E2, F2)",
   "name": "l2"
  },
  {
   "expression": "Line(E3, F3)",
   "name": "l3"
  },
  {
   "expression": "Intersect(l1, l2)",
   "name": "V12"
  },
  {
   "expression": "Intersect(l1, l3)",
   "name": "V13"
  },
  {
   "expression": "Intersect(l2, l3)",
   "name": "V23"
  }
 ],
 "id": "HMMT-2026-FEB-GEO-05",
 "target": "Distance(E3, F3)",
 "variables": [
  "x2",
  "y2",
  "x3",
  "y3",
  "a1",
  "b1",
  "a2",
  "b2",
  "a3",
  "b3"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GEO-05  vars=['x2', 'y2', 'x3', 'y3', 'a1', 'b1', 'a2', 'b2', 'a3', 'b3']  residuals=10
  validate issues: none
  starts=300 converged=299 feasible=1
  value=19.595917942265424785578272597647131  hits=1  |res|=6.96e-58  official_match=['8*sqrt(6)']
     at x2=-5.65685424949, y2=-7.0, x3=5.65685424949, y3=-7.0, a1=0.681424641097, b1=0.210401910933, a2=0.818575358903, b2=0.289598089067, a3=1.57509914386, b3=1.92490085614
  missing_official=none  extra_values=none  => PASS
# HMMT-2026-FEB-GEO-05  vars=['x2', 'y2', 'x3', 'y3', 'a1', 'b1', 'a2', 'b2', 'a3', 'b3']  residuals=10
  validate issues: none
  starts=3000 converged=2960 feasible=9
  value=19.595917942265424785578272597647131  hits=9  |res|=8.11e-59  official_match=['8*sqrt(6)']
     at x2=-5.65685424949, y2=-7.0, x3=5.65685424949, y3=-7.0, a1=1.6814246411, b1=1.21040191093, a2=1.28959808907, b2=0.818575358903, a3=0.575099143859, b3=-0.0750991438595
  missing_official=none  extra_values=none  => PASS
```

判定の補足: 図の配置条件（各小円は接する2本の弦についてOと反対側）を入れた版で一意。原文のみの版（verify/HMMT-2026-FEB-GEO-05.textonly.json）では3000点開始で36種類以上の値が出るため、図の情報は不可欠。

## HMMT-2026-FEB-GEO-06

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf

**原文**

> Let $ABC$ be a triangle, and $M$ be the midpoint of segment $\overline{BC}$. Points $P$ and $Q$ lie on segments $\overline{AB}$ and $\overline{AC}$, respectively, so that $\angle PMB = \angle QMC = \frac{1}{2}\angle BAC$. Given that $AP = 1$, $AQ = 3$, and $BC = 8$, compute $BP$.

公式の答え: `\sqrt{17}-1` → 参照値 `sqrt(17) - 1`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| triangle ABC, BC = 8 | `B=(-4,0), C=(4,0), A=(ax,ay), ay>0` | 合同・鏡映の正規化 |
| M midpoint of BC | `M = Midpoint(B, C)` |  |
| P on segment AB, Q on segment AC | `PointOnSegment` | 閉線分 |
| ∠PMB = ∠QMC = ½∠BAC | `Angle(P,M,B) = Angle(B,A,C)/2 など` | ラジアンのまま比較 |
| AP = 1, AQ = 3 | `Distance` |  |
| Compute BP | `target Distance(B, P)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Angle(P, M, B)",
   "operator": "=",
   "right": "Angle(B, A, C) / 2"
  },
  {
   "left": "Angle(Q, M, C)",
   "operator": "=",
   "right": "Angle(B, A, C) / 2"
  },
  {
   "left": "Distance(A, P)",
   "operator": "=",
   "right": 1
  },
  {
   "left": "Distance(A, Q)",
   "operator": "=",
   "right": 3
  },
  {
   "left": "ay",
   "operator": ">",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(-4, 0)",
   "name": "B"
  },
  {
   "expression": "Point(4, 0)",
   "name": "C"
  },
  {
   "expression": "Midpoint(B, C)",
   "name": "M"
  },
  {
   "expression": "Point(ax, ay)",
   "name": "A"
  },
  {
   "expression": "PointOnSegment(A, B, p)",
   "name": "P"
  },
  {
   "expression": "PointOnSegment(A, C, q)",
   "name": "Q"
  }
 ],
 "id": "HMMT-2026-FEB-GEO-06",
 "target": "Distance(B, P)",
 "variables": [
  "ax",
  "ay",
  "p",
  "q"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GEO-06  vars=['ax', 'ay', 'p', 'q']  residuals=4
  validate issues: none
  starts=300 converged=287 feasible=234
  value=3.123105625617660549821409855974077  hits=234  |res|=1.1e-61  official_match=['sqrt(17) - 1']
     at ax=-1.2807764064, ay=3.09932622485, p=0.242535625036, q=0.489947452066
  missing_official=none  extra_values=none  => PASS
```

## HMMT-2026-FEB-GEO-07

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf

**原文**

> Let $ABC$ be an isosceles triangle with $AB = AC$. Points $P$ and $Q$ are located inside triangle $ABC$ such that $BP = PQ = QC$. Suppose that $\angle BAP = 20^\circ$, $\angle PAQ = 46^\circ$, and $\angle QAC = 26^\circ$. Compute the measure of $\angle APC$.

公式の答え: `74^\circ` → 参照値 `74`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| isosceles triangle, AB = AC | `A=(0,0), B=(1,0), C=(cx,cy), AC=AB, cy>0` | 相似の正規化（AB=1、求める量は角度で相似不変）と鏡映の正規化 |
| P, Q inside triangle ABC | `P = A + s1·AB + u1·AC（s1,u1>0, s1+u1<1）, Qも同様` | 三角形内部の重心座標表示（開集合） |
| BP = PQ = QC | `BP=PQ, PQ=QC` |  |
| ∠BAP=20°, ∠PAQ=46°, ∠QAC=26° | `Degrees(Angle(·))` | ∠BACの値（92°）は書かない |
| measure of ∠APC | `target Degrees(Angle(A,P,C))` | 答え74は度数 |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(A, C)",
   "operator": "=",
   "right": "Distance(A, B)"
  },
  {
   "left": "Distance(B, P)",
   "operator": "=",
   "right": "Distance(P, Q)"
  },
  {
   "left": "Distance(P, Q)",
   "operator": "=",
   "right": "Distance(Q, C)"
  },
  {
   "left": "Degrees(Angle(B, A, P))",
   "operator": "=",
   "right": 20
  },
  {
   "left": "Degrees(Angle(P, A, Q))",
   "operator": "=",
   "right": 46
  },
  {
   "left": "Degrees(Angle(Q, A, C))",
   "operator": "=",
   "right": 26
  },
  {
   "left": "cy",
   "operator": ">",
   "right": 0
  },
  {
   "left": "s1",
   "operator": ">",
   "right": 0
  },
  {
   "left": "u1",
   "operator": ">",
   "right": 0
  },
  {
   "left": "s1 + u1",
   "operator": "<",
   "right": 1
  },
  {
   "left": "s2",
   "operator": ">",
   "right": 0
  },
  {
   "left": "u2",
   "operator": ">",
   "right": 0
  },
  {
   "left": "s2 + u2",
   "operator": "<",
   "right": 1
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "A"
  },
  {
   "expression": "Point(1, 0)",
   "name": "B"
  },
  {
   "expression": "Point(cx, cy)",
   "name": "C"
  },
  {
   "expression": "Point(s1 + u1 * cx, u1 * cy)",
   "name": "P"
  },
  {
   "expression": "Point(s2 + u2 * cx, u2 * cy)",
   "name": "Q"
  }
 ],
 "id": "HMMT-2026-FEB-GEO-07",
 "target": "Degrees(Angle(A, P, C))",
 "variables": [
  "cx",
  "cy",
  "s1",
  "u1",
  "s2",
  "u2"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GEO-07  vars=['cx', 'cy', 's1', 'u1', 's2', 'u2']  residuals=6
  validate issues: none
  starts=300 converged=139 feasible=93
  value=74.0  hits=93  |res|=5.57e-60  official_match=['74']
     at cx=-0.0348994967025, cy=0.999390827019, s1=0.553593498296, u1=0.199083991737, s2=0.293313776992, u2=0.61125252106
  missing_official=none  extra_values=none  => PASS
# HMMT-2026-FEB-GEO-07  vars=['cx', 'cy', 's1', 'u1', 's2', 'u2']  residuals=6
  validate issues: none
  starts=1500 converged=760 feasible=534
  value=74.0  hits=534  |res|=5.57e-60  official_match=['74']
     at cx=-0.0348994967025, cy=0.999390827019, s1=0.553593498296, u1=0.199083991737, s2=0.293313776992, u2=0.61125252106
  missing_official=none  extra_values=none  => PASS
```

## HMMT-2026-FEB-GEO-08

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf

**原文**

> Let $ABC$ be a triangle with orthocenter $H$. The internal angle bisector of $\angle BAC$ meets the circumcircles of triangles $ABH$, $ACH$, and $ABC$ again at points $P$, $Q$, and $M$, respectively. Suppose that points $A$, $P$, $Q$, and $M$ are distinct and lie on the internal angle bisector of $\angle BAC$ in that order. Given that $AP = 4$, $AQ = 5$, and $BC = 7$, compute $AM$.

公式の答え: `\sqrt{69}` → 参照値 `sqrt(69)`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| triangle ABC, BC = 7 | `B=(0,0), C=(7,0), A=(ax,ay), ay>0` | 合同・鏡映の正規化 |
| orthocenter H | `H = Orthocenter(A,B,C)` |  |
| internal bisector of ∠BAC meets circumcircles of ABH, ACH, ABC again at P, Q, M | `bis = AngleBisector(B,A,C); Intersect(bis, Circumcircle(·), exclude=A)` | againはAを除く交点 |
| A, P, Q, M distinct, in that order on the bisector | `AP·AQ>0, AQ·AM>0（同じ向き）かつ AP<AQ<AM` |  |
| AP = 4, AQ = 5 | `Distance` |  |
| Compute AM | `target Distance(A, M)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(A, P)",
   "operator": "=",
   "right": 4
  },
  {
   "left": "Distance(A, Q)",
   "operator": "=",
   "right": 5
  },
  {
   "left": "Dot(Vector(A, P), Vector(A, Q))",
   "operator": ">",
   "right": 0
  },
  {
   "left": "Dot(Vector(A, Q), Vector(A, M))",
   "operator": ">",
   "right": 0
  },
  {
   "left": "Distance(A, P)",
   "operator": "<",
   "right": "Distance(A, Q)"
  },
  {
   "left": "Distance(A, Q)",
   "operator": "<",
   "right": "Distance(A, M)"
  },
  {
   "left": "ay",
   "operator": ">",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "B"
  },
  {
   "expression": "Point(7, 0)",
   "name": "C"
  },
  {
   "expression": "Point(ax, ay)",
   "name": "A"
  },
  {
   "expression": "Orthocenter(A, B, C)",
   "name": "H"
  },
  {
   "expression": "AngleBisector(B, A, C)",
   "name": "bis"
  },
  {
   "expression": "Intersect(bis, Circumcircle(A, B, H), exclude=A)",
   "name": "P"
  },
  {
   "expression": "Intersect(bis, Circumcircle(A, C, H), exclude=A)",
   "name": "Q"
  },
  {
   "expression": "Intersect(bis, Circumcircle(A, B, C), exclude=A)",
   "name": "M"
  }
 ],
 "id": "HMMT-2026-FEB-GEO-08",
 "target": "Distance(A, M)",
 "variables": [
  "ax",
  "ay"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GEO-08  vars=['ax', 'ay']  residuals=2
  validate issues: none
  starts=300 converged=298 feasible=281
  value=8.306623862918074852584262744907492  hits=281  |res|=1.56e-60  official_match=['sqrt(69)']
     at ax=2.90666972408, ay=6.37722042054
  missing_official=none  extra_values=none  => PASS
```

## HMMT-2026-FEB-GEO-09

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf

**原文**

> Let $ABC$ be triangle with incenter $I$ and incircle $\omega$. The circumcircle of triangle $BIC$ intersects $\omega$ at points $E$ and $F$. Suppose that $\Gamma \neq \omega$ is a circle passing through $E$ and $F$ and tangent to lines $AB$ and $AC$. If $AB = 5$, $AC = 7$, and $\Gamma$ has twice the radius of $\omega$, compute $BC$.

公式の答え: `3+\sqrt{11}` → 参照値 `3 + sqrt(11)`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| triangle ABC, AB = 5, AC = 7 | `B=(0,0), C=(a,0), A=(ax,ay); AB=5, AC=7, a>0, ay>0` | 合同・鏡映の正規化 |
| incenter I, incircle ω | `Incenter, Incircle` |  |
| circumcircle of BIC intersects ω at E and F | `K = Circumcircle(B,I,C); E = Intersect(K, omega, n=1), F = 他方の交点（exclude=E）` | EとFは対称な役割なので番号づけは任意 |
| Γ ≠ ω through E and F, tangent to lines AB and AC | `Gamma = Circle(Z, rho); OnCircle(E/F)=0, IsTangent(Line(A,B)/Line(A,C))=0` | Γ≠ωは半径条件から自動的に成り立つ |
| Γ has twice the radius of ω | `Radius(Gamma) = 2·Radius(omega)` |  |
| compute BC | `target Distance(B, C)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(A, B)",
   "operator": "=",
   "right": 5
  },
  {
   "left": "Distance(A, C)",
   "operator": "=",
   "right": 7
  },
  {
   "left": "OnCircle(E, Gamma)",
   "operator": "=",
   "right": 0
  },
  {
   "left": "OnCircle(F, Gamma)",
   "operator": "=",
   "right": 0
  },
  {
   "left": "IsTangent(Line(A, B), Gamma)",
   "operator": "=",
   "right": 0
  },
  {
   "left": "IsTangent(Line(A, C), Gamma)",
   "operator": "=",
   "right": 0
  },
  {
   "left": "Radius(Gamma)",
   "operator": "=",
   "right": "2 * Radius(omega)"
  },
  {
   "left": "a",
   "operator": ">",
   "right": 0
  },
  {
   "left": "ay",
   "operator": ">",
   "right": 0
  },
  {
   "left": "rho",
   "operator": ">",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "B"
  },
  {
   "expression": "Point(a, 0)",
   "name": "C"
  },
  {
   "expression": "Point(ax, ay)",
   "name": "A"
  },
  {
   "expression": "Incenter(A, B, C)",
   "name": "I"
  },
  {
   "expression": "Incircle(A, B, C)",
   "name": "omega"
  },
  {
   "expression": "Circumcircle(B, I, C)",
   "name": "K"
  },
  {
   "expression": "Intersect(K, omega, n=1)",
   "name": "E"
  },
  {
   "expression": "Intersect(K, omega, exclude=E)",
   "name": "F"
  },
  {
   "expression": "Circle(Point(zx, zy), rho)",
   "name": "Gamma"
  }
 ],
 "id": "HMMT-2026-FEB-GEO-09",
 "target": "Distance(B, C)",
 "variables": [
  "a",
  "ax",
  "ay",
  "zx",
  "zy",
  "rho"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GEO-09  vars=['a', 'ax', 'ay', 'zx', 'zy', 'rho']  residuals=7
  validate issues: none
  starts=300 converged=36 feasible=36
  value=6.3166247903553998491149327366706867  hits=36  |res|=9.02e-59  official_match=['3 + sqrt(11)']
     at a=6.31662479036, ax=1.25856365305, ay=4.83900997429, zx=3.05806113731, zy=-1.50147254977, rho=3.33753742452
  missing_official=none  extra_values=none  => PASS
# HMMT-2026-FEB-GEO-09  vars=['a', 'ax', 'ay', 'zx', 'zy', 'rho']  residuals=7
  validate issues: none
  starts=3000 converged=336 feasible=333
  value~2.0: 1 hits, HP polish failed/infeasible
  value=6.3166247903553998491149327366706867  hits=332  |res|=4.73e-53  official_match=['3 + sqrt(11)']
     at a=6.31662479036, ax=1.25856365305, ay=4.83900997429, zx=3.05806113731, zy=-1.50147254977, rho=3.33753742452
  missing_official=none  extra_values=[2.0]  => CHECK
```

判定の補足: BC≈2の点は A がBC上に潰れ Γ の半径→0 となる退化配置（ay≈6e-8, rho≈1e-8）。60桁精密化で棄却。公式の答え以外の実解は無し。

## HMMT-2026-FEB-GEO-10

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf

**原文**

> Let $ABC$ be a triangle with centroid $G$ and circumcenter $O$. Suppose that the orthocenter of triangle $AGO$ lies on line $BC$. Given that $AB = 11$ and $AC = 13$, compute $BC$.

公式の答え: `\sqrt{\frac{580}{3}} = \frac{\sqrt{1740}}{3}` → 参照値 `sqrt(580/3)`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| triangle ABC, AB = 11, AC = 13 | `B=(0,0), C=(a,0), A=(ax,ay)` | 合同・鏡映の正規化 |
| centroid G, circumcenter O | `Centroid, Circumcenter` |  |
| orthocenter of AGO lies on line BC | `OnLine(Orthocenter(A,G,O), Line(B,C)) = 0` | 三角形AGOの非退化は構成の定義域で要求 |
| compute BC | `target Distance(B, C)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(A, B)",
   "operator": "=",
   "right": 11
  },
  {
   "left": "Distance(A, C)",
   "operator": "=",
   "right": 13
  },
  {
   "left": "OnLine(Hh, Line(B, C))",
   "operator": "=",
   "right": 0
  },
  {
   "left": "a",
   "operator": ">",
   "right": 0
  },
  {
   "left": "ay",
   "operator": ">",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "B"
  },
  {
   "expression": "Point(a, 0)",
   "name": "C"
  },
  {
   "expression": "Point(ax, ay)",
   "name": "A"
  },
  {
   "expression": "Centroid(A, B, C)",
   "name": "G"
  },
  {
   "expression": "Circumcenter(A, B, C)",
   "name": "O"
  },
  {
   "expression": "Orthocenter(A, G, O)",
   "name": "Hh"
  }
 ],
 "id": "HMMT-2026-FEB-GEO-10",
 "target": "Distance(B, C)",
 "variables": [
  "a",
  "ax",
  "ay"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GEO-10  vars=['a', 'ax', 'ay']  residuals=3
  validate issues: none
  starts=300 converged=106 feasible=94
  value~2.0: 2 hits, HP polish failed/infeasible
  value=13.904435743076140136984469072420141  hits=82  |res|=2.25e-59  official_match=['sqrt(580/3)']
     at a=13.9044357431, ax=5.22614998619, ay=9.67922291932
  value~24.0: 10 hits, HP polish failed/infeasible
  missing_official=none  extra_values=[24.0, 2.0]  => CHECK
# HMMT-2026-FEB-GEO-10  vars=['a', 'ax', 'ay']  residuals=3
  validate issues: none
  starts=3000 converged=1189 feasible=1016
  value~2.0: 55 hits, HP polish failed/infeasible
  value=13.904435743076140136984469072420141  hits=885  |res|=1.5e-59  official_match=['sqrt(580/3)']
     at a=13.9044357431, ax=5.22614998619, ay=9.67922291932
  value~24.0: 76 hits, HP polish failed/infeasible
  missing_official=none  extra_values=[2.0, 24.0]  => CHECK
```

判定の補足: BC≈2, 24 は AC−AB, AB+AC に当たる退化三角形（ay≈1e-7）。60桁精密化で棄却。公式の答え以外の実解は無し。

## HMMT-2026-FEB-GUTS-03

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/guts/problems.pdf

**原文**

> A rectangle with length $4$ and height $2$ is placed in the bottom left corner of a square with side length $10$. Regions $A$ and $B$ are separated by a line segment drawn from the rectangle's upper right corner to some point on the boundary of the square. Given that regions $A$ and $B$ have the same perimeter, compute the positive difference between the areas of regions $A$ and $B$.

図の情報（収集時のメモ）: Figure: square with corners (0,0)-(10,10); shaded 4x2 rectangle in the bottom-left corner [0,4]x[0,2]. The dividing segment goes from (4,2) up and to the right to a point on the top side of the square (roughly x=7 to 8 in the picture). Region A = left/upper part, B = right part. Answer is the positive difference, so labelling does not matter. One line of the official solution was visible in a cropped answer-box image; it was not used.

公式の答え: `4` → 参照値 `4`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| square of side 10; 4×2 rectangle in the bottom-left corner | `正方形 [0,10]², 長方形 [0,4]×[0,2]` | 合同の正規化 |
| segment from the rectangle's upper right corner (4,2) to a point on the boundary | `P = PointOnSegment((0,10),(10,10), t)` | 図: 終点は上辺（x≈7〜8）。図から読んだ情報 |
| regions A and B | `A = 多角形(0,2),(4,2),P,(0,10)、B = (4,2),(4,0),(10,0),(10,10),P` | 図: 長方形は網掛けで、A・Bは正方形から長方形を除いたL字領域を分けたもの |
| same perimeter | `周の長さの等式（各辺のDistanceの和）` |  |
| positive difference between the areas | `target abs(Area(A) - Area(B))` |  |

注: 領域の形は図に依存。DSLの多角形の頂点は、終点Pが上辺にあるという図の読みから書いている。

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(R3, R2) + Distance(R2, P) + Distance(P, S3) + Distance(S3, R3)",
   "operator": "=",
   "right": "Distance(R2, R1) + Distance(R1, S1) + Distance(S1, S2) + Distance(S2, P) + Distance(P, R2)"
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "S0"
  },
  {
   "expression": "Point(10, 0)",
   "name": "S1"
  },
  {
   "expression": "Point(10, 10)",
   "name": "S2"
  },
  {
   "expression": "Point(0, 10)",
   "name": "S3"
  },
  {
   "expression": "Point(4, 0)",
   "name": "R1"
  },
  {
   "expression": "Point(4, 2)",
   "name": "R2"
  },
  {
   "expression": "Point(0, 2)",
   "name": "R3"
  },
  {
   "expression": "PointOnSegment(S3, S2, t)",
   "name": "P"
  }
 ],
 "id": "HMMT-2026-FEB-GUTS-03",
 "target": "abs(Area(R3, R2, P, S3) - Area(R2, R1, S1, S2, P))",
 "variables": [
  "t"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GUTS-03  vars=['t']  residuals=1
  validate issues: none
  starts=300 converged=300 feasible=300
  value=4.0  hits=300  |res|=0.0  official_match=['4']
     at t=0.8
  missing_official=none  extra_values=none  => PASS
```

判定の補足: 図では終点が上辺。原文のみでも、終点を右辺・左辺・下辺に置くと周長が等しくなる位置が辺の外に出る（それぞれ y=12, y=18, x=22）ことを手計算で確認。図に依存せず答えは一意。

## HMMT-2026-FEB-GUTS-05

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/guts/problems.pdf

**原文**

> Let $ABC$ be a right triangle with $\angle ABC = 90^\circ$ and $AB < BC$. Let $M$ be the midpoint of $AC$. Let $T$ be the unique point lying on the segment $BC$ such that $\angle BMT = 90^\circ$. Given that $AB = 5$ and $MT = 3$, compute $CT$.

公式の答え: `\frac{7}{\sqrt{11}} = \frac{7\sqrt{11}}{11}` → 参照値 `7*sqrt(11)/11`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| right triangle, ∠ABC = 90°, AB = 5 | `B=(0,0), A=(0,5), C=(c,0)` | 合同の正規化（直角の頂点を原点、脚を座標軸） |
| AB < BC | `c > 5` |  |
| M midpoint of AC | `Midpoint(A, C)` |  |
| T on segment BC with ∠BMT = 90° | `T = PointOnSegment(B,C,t), Degrees(Angle(B,M,T))=90` | uniqueは条件として書かない |
| MT = 3 | `Distance(M,T)=3` |  |
| compute CT | `target Distance(C, T)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Degrees(Angle(B, M, T))",
   "operator": "=",
   "right": 90
  },
  {
   "left": "Distance(M, T)",
   "operator": "=",
   "right": 3
  },
  {
   "left": "c",
   "operator": ">",
   "right": 5
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "B"
  },
  {
   "expression": "Point(0, 5)",
   "name": "A"
  },
  {
   "expression": "Point(c, 0)",
   "name": "C"
  },
  {
   "expression": "Midpoint(A, C)",
   "name": "M"
  },
  {
   "expression": "PointOnSegment(B, C, t)",
   "name": "T"
  }
 ],
 "id": "HMMT-2026-FEB-GUTS-05",
 "target": "Distance(C, T)",
 "variables": [
  "c",
  "t"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GUTS-05  vars=['c', 't']  residuals=2
  validate issues: none
  starts=300 converged=300 feasible=300
  value=2.110579412044345358527684468790437  hits=300  |res|=0.0  official_match=['7*sqrt(11)/11']
     at c=7.53778361444, t=0.72
  missing_official=none  extra_values=none  => PASS
```

## HMMT-2026-FEB-GUTS-09

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/guts/problems.pdf

**原文**

> Let $ABCD$ be a rectangle. Let $E$ be the reflection of $C$ over $B$. The circumcircle of triangle $ACE$ intersects line $CD$ at a point $F \neq C$. Given that $AC = 8$ and $AF = 6$, compute the area of rectangle $ABCD$.

公式の答え: `\frac{768}{25} = 30.72` → 参照値 `768/25`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| rectangle ABCD | `A=(0,0), B=(w,0), C=(w,h), D=(0,h)` | 合同の正規化 |
| E reflection of C over B | `E = 2B − C = (2w−w, 2·0−h)` | 点対称を座標式で表記 |
| circumcircle of ACE meets line CD at F ≠ C | `Intersect(Line(C,D), Circumcircle(A,C,E), exclude=C)` |  |
| AC = 8, AF = 6 | `Distance` |  |
| area of ABCD | `target Area(A,B,C,D)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(A, C)",
   "operator": "=",
   "right": 8
  },
  {
   "left": "Distance(A, F)",
   "operator": "=",
   "right": 6
  },
  {
   "left": "w",
   "operator": ">",
   "right": 0
  },
  {
   "left": "h",
   "operator": ">",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "A"
  },
  {
   "expression": "Point(w, 0)",
   "name": "B"
  },
  {
   "expression": "Point(w, h)",
   "name": "C"
  },
  {
   "expression": "Point(0, h)",
   "name": "D"
  },
  {
   "expression": "Point(2 * w - w, 2 * 0 - h)",
   "name": "E"
  },
  {
   "expression": "Intersect(Line(C, D), Circumcircle(A, C, E), exclude=C)",
   "name": "F"
  }
 ],
 "id": "HMMT-2026-FEB-GUTS-09",
 "target": "Area(A, B, C, D)",
 "variables": [
  "w",
  "h"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GUTS-09  vars=['w', 'h']  residuals=2
  validate issues: none
  starts=300 converged=300 feasible=300
  value=30.72  hits=300  |res|=8.8e-61  official_match=['768/25']
     at w=6.4, h=4.8
  missing_official=none  extra_values=none  => PASS
```

## HMMT-2026-FEB-GUTS-16

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/guts/problems.pdf

**原文**

> Let $O$ and $G$ be the circumcenter and centroid of triangle $ABC$, respectively, and let $M$ be the midpoint of side $\overline{BC}$. Given that $OG = 1$, $OM = \sqrt{2}$, and $GM = \sqrt{3}$, compute the area of triangle $ABC$.

公式の答え: `3\sqrt{30} = \sqrt{270}` → 参照値 `3*sqrt(30)`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| triangle ABC | `B=(-b,0), C=(b,0), A=(ax,ay), b>0, ay>0` | 合同・鏡映の正規化（BCの中点を原点） |
| circumcenter O, centroid G, midpoint M of BC | `Circumcenter, Centroid, Midpoint` |  |
| OG = 1, OM = √2, GM = √3 | `Distance` |  |
| area of ABC | `target Area(A,B,C)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(O, G)",
   "operator": "=",
   "right": 1
  },
  {
   "left": "Distance(O, M)",
   "operator": "=",
   "right": "sqrt(2)"
  },
  {
   "left": "Distance(G, M)",
   "operator": "=",
   "right": "sqrt(3)"
  },
  {
   "left": "b",
   "operator": ">",
   "right": 0
  },
  {
   "left": "ay",
   "operator": ">",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(-b, 0)",
   "name": "B"
  },
  {
   "expression": "Point(b, 0)",
   "name": "C"
  },
  {
   "expression": "Point(ax, ay)",
   "name": "A"
  },
  {
   "expression": "Circumcenter(A, B, C)",
   "name": "O"
  },
  {
   "expression": "Centroid(A, B, C)",
   "name": "G"
  },
  {
   "expression": "Midpoint(B, C)",
   "name": "M"
  }
 ],
 "id": "HMMT-2026-FEB-GUTS-16",
 "target": "Area(A, B, C)",
 "variables": [
  "b",
  "ax",
  "ay"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GUTS-16  vars=['b', 'ax', 'ay']  residuals=3
  validate issues: none
  starts=300 converged=296 feasible=231
  value=16.431676725154983403709093484024064  hits=231  |res|=3.21e-61  official_match=['3*sqrt(30)']
     at b=3.87298334621, ax=-3.0, ay=4.24264068712
  missing_official=none  extra_values=none  => PASS
```

## HMMT-2026-FEB-GUTS-18

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/guts/problems.pdf

**原文**

> Let $ABCD$ be a trapezoid with side $AB$ parallel to side $CD$. Let $P$ be the intersection of diagonals $AC$ and $BD$. Given that the distances from $P$ to sides $AB$, $BC$, $CD$, and $DA$ are $3$, $6$, $8$, and $8$, respectively, compute the perimeter of $ABCD$.

公式の答え: `\frac{165}{2} = 82.5` → 参照値 `165/2`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| trapezoid ABCD with AB ∥ CD | `A=(0,0), B=(b,0), C=(cx,h), D=(dx,h), ConvexPolygon` | 合同・鏡映の正規化。平行は座標で表す |
| P intersection of diagonals AC, BD | `Intersect(Line(A,C), Line(B,D))` | 凸なので線分の交点と一致 |
| distances from P to sides AB, BC, CD, DA are 3, 6, 8, 8 | `Distance(P, Line(·))` | 辺を含む直線への距離 |
| perimeter | `target 4辺の和` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(P, Line(A, B))",
   "operator": "=",
   "right": 3
  },
  {
   "left": "Distance(P, Line(B, C))",
   "operator": "=",
   "right": 6
  },
  {
   "left": "Distance(P, Line(C, D))",
   "operator": "=",
   "right": 8
  },
  {
   "left": "Distance(P, Line(D, A))",
   "operator": "=",
   "right": 8
  },
  {
   "predicate": "ConvexPolygon([A, B, C, D])"
  },
  {
   "left": "b",
   "operator": ">",
   "right": 0
  },
  {
   "left": "h",
   "operator": ">",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "A"
  },
  {
   "expression": "Point(b, 0)",
   "name": "B"
  },
  {
   "expression": "Point(cx, h)",
   "name": "C"
  },
  {
   "expression": "Point(dx, h)",
   "name": "D"
  },
  {
   "expression": "Intersect(Line(A, C), Line(B, D))",
   "name": "P"
  }
 ],
 "id": "HMMT-2026-FEB-GUTS-18",
 "target": "Distance(A, B) + Distance(B, C) + Distance(C, D) + Distance(D, A)",
 "variables": [
  "b",
  "cx",
  "dx",
  "h"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GUTS-18  vars=['b', 'cx', 'dx', 'h']  residuals=4
  validate issues: none
  starts=300 converged=155 feasible=138
  value=82.5  hits=138  |res|=6.22e-61  official_match=['165/2']
     at b=13.75, cx=28.4166666667, dx=-8.25, h=11.0
  missing_official=none  extra_values=none  => PASS
# HMMT-2026-FEB-GUTS-18  vars=['b', 'cx', 'dx', 'h']  residuals=4
  validate issues: none
  starts=3000 converged=1630 feasible=1465
  value=82.5  hits=1465  |res|=6.22e-61  official_match=['165/2']
     at b=13.75, cx=28.4166666667, dx=-8.25, h=11.0
  missing_official=none  extra_values=none  => PASS
```

## HMMT-2026-FEB-GUTS-28

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/guts/problems.pdf

**原文**

> Let $ABC$ be a triangle such that $\angle BAC = 105^\circ$, $AB = 12\sqrt{2}$, and $AC = 17$. Let $P$ be a point such that $P$ and $A$ lie on different sides of line $BC$, and $\angle APB = \angle APC = 60^\circ$. Compute $AP$.

公式の答え: `\frac{136\sqrt{3}}{13}` → 参照値 `136*sqrt(3)/13`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| ∠BAC = 105°, AB = 12√2, AC = 17 | `A=(0,0), B=(12√2,0), C=17(cos105°, sin105°)` | 合同の正規化。与えられた2辺と挟角の座標化 |
| P and A on different sides of line BC | `垂線の足からのベクトルの内積 < 0` |  |
| ∠APB = ∠APC = 60° | `Degrees(Angle(·))=60` |  |
| compute AP | `target Distance(A,P)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Degrees(Angle(A, P, B))",
   "operator": "=",
   "right": 60
  },
  {
   "left": "Degrees(Angle(A, P, C))",
   "operator": "=",
   "right": 60
  },
  {
   "left": "Dot(Vector(FootOfPerpendicular(P, Line(B, C)), P), Vector(FootOfPerpendicular(A, Line(B, C)), A))",
   "operator": "<",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "A"
  },
  {
   "expression": "Point(12 * sqrt(2), 0)",
   "name": "B"
  },
  {
   "expression": "Point(17 * cos(105 * pi / 180), 17 * sin(105 * pi / 180))",
   "name": "C"
  },
  {
   "expression": "Point(px, py)",
   "name": "P"
  }
 ],
 "id": "HMMT-2026-FEB-GUTS-28",
 "target": "Distance(A, P)",
 "variables": [
  "px",
  "py"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GUTS-28  vars=['px', 'py']  residuals=2
  validate issues: none
  starts=300 converged=248 feasible=248
  value=18.11991614072056245536405403421528  hits=248  |res|=4.98e-60  official_match=['136*sqrt(3)/13']
     at px=11.0607559667, py=14.3523878986
  missing_official=none  extra_values=none  => PASS
```

## HMMT-2026-FEB-GUTS-30

出典: https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/guts/problems.pdf

**原文**

> Let $ABC$ be a triangle with $AB = 60$, $AC = 67$, and $BC = 69$. The incircle $\omega$ of triangle $ABC$ touches sides $BC$, $CA$, and $AB$ at $D$, $E$, and $F$, respectively. Let $D'$ be the point diametrically opposite to $D$ in $\omega$. Let the common chord of the circumcircles of triangles $BD'F$ and $CD'E$ meet line $BC$ at $X$. Compute $BX$.

公式の答え: `45` → 参照値 `45`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| triangle ABC, AB=60, AC=67, BC=69 | `B=(0,0), C=(69,0), A=(ax,ay), AB=60, AC=67, ay>0` | 合同・鏡映の正規化。Aの座標は条件で与える |
| incircle ω touches BC, CA, AB at D, E, F | `IncircleContactPoint(side=…)` |  |
| D' diametrically opposite to D in ω | `Dp = Intersect(Line(D,I), ω, exclude=D)` | 中心Iを通る直線と円の他方の交点 |
| common chord of circumcircles of BD'F and CD'E | `共有点D'ともう一つの交点Yを結ぶ直線` |  |
| meets line BC at X | `Intersect(Line(Dp,Y), Line(B,C))` |  |
| compute BX | `target Distance(B, X)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(A, B)",
   "operator": "=",
   "right": 60
  },
  {
   "left": "Distance(A, C)",
   "operator": "=",
   "right": 67
  },
  {
   "left": "ay",
   "operator": ">",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "B"
  },
  {
   "expression": "Point(69, 0)",
   "name": "C"
  },
  {
   "expression": "Point(ax, ay)",
   "name": "A"
  },
  {
   "expression": "Incenter(A, B, C)",
   "name": "I"
  },
  {
   "expression": "Incircle(A, B, C)",
   "name": "omega"
  },
  {
   "expression": "IncircleContactPoint(A, B, C, side='BC')",
   "name": "D"
  },
  {
   "expression": "IncircleContactPoint(A, B, C, side='CA')",
   "name": "E"
  },
  {
   "expression": "IncircleContactPoint(A, B, C, side='AB')",
   "name": "F"
  },
  {
   "expression": "Intersect(Line(D, I), omega, exclude=D)",
   "name": "Dp"
  },
  {
   "expression": "Circumcircle(B, Dp, F)",
   "name": "K1"
  },
  {
   "expression": "Circumcircle(C, Dp, E)",
   "name": "K2"
  },
  {
   "expression": "Intersect(K1, K2, exclude=Dp)",
   "name": "Y"
  },
  {
   "expression": "Intersect(Line(Dp, Y), Line(B, C))",
   "name": "X"
  }
 ],
 "id": "HMMT-2026-FEB-GUTS-30",
 "target": "Distance(B, X)",
 "variables": [
  "ax",
  "ay"
 ]
}
```

**検算**

```
# HMMT-2026-FEB-GUTS-30  vars=['ax', 'ay']  residuals=2
  validate issues: none
  starts=300 converged=300 feasible=300
  value=45.0  hits=300  |res|=0.0  official_match=['45']
     at ax=28.0579710145, ay=53.0353680345
  missing_official=none  extra_values=none  => PASS
```

## JMO-2026-PRE-03

出典: https://www.imojp.org/archive/mo2026/jmo/problems/jmo36yqa.pdf

**原文**

> 円周上に 5 点 $A, B, C, D, E$ がこの順にある．線分 $BE$ と線分 $AC, AD$ の交点をそれぞれ $P, Q$ とすると，$BP = PQ = QE$ が成り立った．三角形 $BCP$，三角形 $APQ$，三角形 $DEQ$ の面積がそれぞれ $2, 9, 3$ であるとき，$\dfrac{AC}{AD}$ の値を求めよ．ただし，$XY$ で線分 $XY$ の長さを表すものとする．

図の情報（収集時のメモ）: Figure: A near the top of the circle, B at the left and E at the right with chord BE drawn roughly horizontal; C (lower left) and D (lower right) below BE, consistent with the cyclic order A,B,C,D,E. P = BE∩AC lies left of Q = BE∩AD. Shaded triangles: BCP (area 2) below BE on the left, APQ (area 9) above BE, DEQ (area 3) below BE on the right.

公式の答え: `\frac{11\sqrt{6}}{24}` → 参照値 `11*sqrt(6)/24`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| 円周上に5点A,B,C,D,Eがこの順にある | `Omega=Circle(O,R)、A..EをPointOnCircleで 0=tA<tB<tC<tD<tE<1` | Aの位置（t=0）は回転、反時計回りは鏡映の正規化。半径Rは未知 |
| 線分BEと線分AC, ADの交点P, Q | `Intersect(Line(B,E), Line(A,C/AD))` | 円周上の順序から線分どうしが交わる |
| BP = PQ = QE | `BP=PQ, PQ=QE` |  |
| 三角形BCP, APQ, DEQの面積が2, 9, 3 | `Area(·)` |  |
| AC/ADを求めよ | `target Distance(A,C)/Distance(A,D)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(B, P)",
   "operator": "=",
   "right": "Distance(P, Q)"
  },
  {
   "left": "Distance(P, Q)",
   "operator": "=",
   "right": "Distance(Q, E)"
  },
  {
   "left": "Area(B, C, P)",
   "operator": "=",
   "right": 2
  },
  {
   "left": "Area(A, P, Q)",
   "operator": "=",
   "right": 9
  },
  {
   "left": "Area(D, E, Q)",
   "operator": "=",
   "right": 3
  },
  {
   "left": "R",
   "operator": ">",
   "right": 0
  },
  {
   "left": "tb",
   "operator": ">",
   "right": 0
  },
  {
   "left": "tc",
   "operator": ">",
   "right": "tb"
  },
  {
   "left": "td",
   "operator": ">",
   "right": "tc"
  },
  {
   "left": "te",
   "operator": ">",
   "right": "td"
  },
  {
   "left": "te",
   "operator": "<",
   "right": 1
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "O"
  },
  {
   "expression": "Circle(O, R)",
   "name": "Omega"
  },
  {
   "expression": "PointOnCircle(Omega, 0)",
   "name": "A"
  },
  {
   "expression": "PointOnCircle(Omega, tb)",
   "name": "B"
  },
  {
   "expression": "PointOnCircle(Omega, tc)",
   "name": "C"
  },
  {
   "expression": "PointOnCircle(Omega, td)",
   "name": "D"
  },
  {
   "expression": "PointOnCircle(Omega, te)",
   "name": "E"
  },
  {
   "expression": "Intersect(Line(B, E), Line(A, C))",
   "name": "P"
  },
  {
   "expression": "Intersect(Line(B, E), Line(A, D))",
   "name": "Q"
  }
 ],
 "id": "JMO-2026-PRE-03",
 "target": "Distance(A, C) / Distance(A, D)",
 "variables": [
  "R",
  "tb",
  "tc",
  "td",
  "te"
 ]
}
```

**検算**

```
# JMO-2026-PRE-03  vars=['R', 'tb', 'tc', 'td', 'te']  residuals=5
  validate issues: none
  starts=300 converged=18 feasible=3
  value=1.1226827987756232950070885342402002  hits=3  |res|=9.77e-59  official_match=['11*sqrt(6)/24']
     at R=5.30796161596, tb=0.5, tc=0.563835888354, td=0.662255179152, te=0.796115415553
  missing_official=none  extra_values=none  => PASS
# JMO-2026-PRE-03  vars=['R', 'tb', 'tc', 'td', 'te']  residuals=5
  validate issues: none
  starts=3000 converged=174 feasible=59
  value=1.1226827987756232950070885342402002  hits=59  |res|=1.91e-59  official_match=['11*sqrt(6)/24']
     at R=5.30796161596, tb=0.5, tc=0.563835888354, td=0.662255179152, te=0.796115415553
  missing_official=none  extra_values=none  => PASS
```

## JMO-2026-PRE-06

出典: https://www.imojp.org/archive/mo2026/jmo/problems/jmo36yqa.pdf

**原文**

> 平行四辺形 $ABCD$ の辺 $CD$ 上（端点を除く）に点 $E$ がある．線分 $AE$ の中点を $M$ とし，直線 $BM$ と辺 $AD$ の交点を $F$ とすると，$CE = DF = 3$ が成り立った．$MB = 5$, $MC = 4$ のとき，線分 $AB$ の長さを求めよ．ただし，$XY$ で線分 $XY$ の長さを表すものとする．

公式の答え: `\sqrt{41}-3` → 参照値 `sqrt(41) - 3`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| 平行四辺形ABCD | `A=(0,0), B=(b,0), D=(dx,dy), C=B+D−A` | 合同・鏡映の正規化。平行四辺形の定義の座標化 |
| 辺CD上（端点を除く）に点E | `PointOnSegment(C,D,e), 0<e<1` |  |
| 線分AEの中点M | `Midpoint(A,E)` |  |
| 直線BMと辺ADの交点F | `Intersect(Line(B,M), Line(A,D)), FA·FD ≤ 0` | Fが辺AD上（閉線分） |
| CE = DF = 3, MB = 5, MC = 4 | `Distance` |  |
| ABの長さ | `target Distance(A,B)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "predicate": "Bound(e, (0, 1), inclusive=False)"
  },
  {
   "left": "Dot(Vector(F, A), Vector(F, D))",
   "operator": "<=",
   "right": 0
  },
  {
   "left": "Distance(C, E)",
   "operator": "=",
   "right": 3
  },
  {
   "left": "Distance(D, F)",
   "operator": "=",
   "right": 3
  },
  {
   "left": "Distance(M, B)",
   "operator": "=",
   "right": 5
  },
  {
   "left": "Distance(M, C)",
   "operator": "=",
   "right": 4
  },
  {
   "left": "b",
   "operator": ">",
   "right": 0
  },
  {
   "left": "dy",
   "operator": ">",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "A"
  },
  {
   "expression": "Point(b, 0)",
   "name": "B"
  },
  {
   "expression": "Point(dx, dy)",
   "name": "D"
  },
  {
   "expression": "Point(b + dx, dy)",
   "name": "C"
  },
  {
   "expression": "PointOnSegment(C, D, e)",
   "name": "E"
  },
  {
   "expression": "Midpoint(A, E)",
   "name": "M"
  },
  {
   "expression": "Intersect(Line(B, M), Line(A, D))",
   "name": "F"
  }
 ],
 "id": "JMO-2026-PRE-06",
 "target": "Distance(A, B)",
 "variables": [
  "b",
  "dx",
  "dy",
  "e"
 ]
}
```

**検算**

```
# JMO-2026-PRE-06  vars=['b', 'dx', 'dy', 'e']  residuals=4
  validate issues: none
  starts=300 converged=295 feasible=289
  value=3.4031242374328486864882176746218133  hits=289  |res|=3.11e-61  official_match=['sqrt(41) - 3']
     at b=3.40312423743, dx=-1.405563857, dy=6.24695047554, e=0.881542897259
  missing_official=none  extra_values=none  => PASS
```

## JMO-2026-PRE-09

出典: https://www.imojp.org/archive/mo2026/jmo/problems/jmo36yqa.pdf

**原文**

> $AB = AC$ なる二等辺三角形 $ABC$ は $BC = 21$ をみたしている．辺 $BC, CA, AB$ 上（端点を除く）にそれぞれ点 $D, E, F$ を $\angle EDF = 180^\circ - \frac{1}{2}\angle BAC$ をみたすようにとる．線分 $BD$ の垂直二等分線と直線 $DE$ の交点を $P$ とし，線分 $CD$ の垂直二等分線と直線 $DF$ の交点を $Q$ とする．さらに直線 $BP$ と直線 $CQ$ の交点を $R$ とすると，$EP = 12$, $FQ = 16$, $AR = 6\sqrt{7}$ が成り立った．このとき，三角形 $DPQ$ の面積を求めよ．ただし，$XY$ で線分 $XY$ の長さを表すものとする．

公式の答え: `\frac{48\sqrt{7}}{25}` → 参照値 `48*sqrt(7)/25`

**原文とDSLの対応**

| 原文 | DSL | 根拠・正規化・枝 |
|---|---|---|
| AB = AC の二等辺三角形、BC = 21 | `B=(0,0), C=(21,0), A=(ax,ay), AB=AC, ay>0` | 合同・鏡映の正規化。Aの座標は条件で与える |
| 辺BC, CA, AB上（端点を除く）にD, E, F | `PointOnSegment＋開区間のBound` |  |
| ∠EDF = 180° − ½∠BAC | `Degrees(Angle(E,D,F)) = 180 − Degrees(Angle(B,A,C))/2` |  |
| 線分BDの垂直二等分線と直線DEの交点P | `Intersect(PerpendicularBisector(B,D), Line(D,E))` |  |
| 線分CDの垂直二等分線と直線DFの交点Q | `Intersect(PerpendicularBisector(C,D), Line(D,F))` |  |
| 直線BPと直線CQの交点R | `Intersect(Line(B,P), Line(C,Q))` |  |
| EP = 12, FQ = 16, AR = 6√7 | `Distance` |  |
| 三角形DPQの面積 | `target Area(D,P,Q)` |  |

**DSL**

```json
{
 "conditions": [
  {
   "left": "Distance(A, B)",
   "operator": "=",
   "right": "Distance(A, C)"
  },
  {
   "predicate": "Bound(d, (0, 1), inclusive=False)"
  },
  {
   "predicate": "Bound(e, (0, 1), inclusive=False)"
  },
  {
   "predicate": "Bound(f, (0, 1), inclusive=False)"
  },
  {
   "left": "Degrees(Angle(E, D, F))",
   "operator": "=",
   "right": "180 - Degrees(Angle(B, A, C)) / 2"
  },
  {
   "left": "Distance(E, P)",
   "operator": "=",
   "right": 12
  },
  {
   "left": "Distance(F, Q)",
   "operator": "=",
   "right": 16
  },
  {
   "left": "Distance(A, R)",
   "operator": "=",
   "right": "6*sqrt(7)"
  },
  {
   "left": "ay",
   "operator": ">",
   "right": 0
  }
 ],
 "constructions": [
  {
   "expression": "Point(0, 0)",
   "name": "B"
  },
  {
   "expression": "Point(21, 0)",
   "name": "C"
  },
  {
   "expression": "Point(ax, ay)",
   "name": "A"
  },
  {
   "expression": "PointOnSegment(B, C, d)",
   "name": "D"
  },
  {
   "expression": "PointOnSegment(C, A, e)",
   "name": "E"
  },
  {
   "expression": "PointOnSegment(A, B, f)",
   "name": "F"
  },
  {
   "expression": "Intersect(PerpendicularBisector(B, D), Line(D, E))",
   "name": "P"
  },
  {
   "expression": "Intersect(PerpendicularBisector(C, D), Line(D, F))",
   "name": "Q"
  },
  {
   "expression": "Intersect(Line(B, P), Line(C, Q))",
   "name": "R"
  }
 ],
 "id": "JMO-2026-PRE-09",
 "target": "Area(D, P, Q)",
 "variables": [
  "ax",
  "ay",
  "d",
  "e",
  "f"
 ]
}
```

**検算**

```
# JMO-2026-PRE-09  vars=['ax', 'ay', 'd', 'e', 'f']  residuals=5
  validate issues: none
  starts=300 converged=30 feasible=30
  value=5.07984251724401393376310224698738  hits=30  |res|=8.04e-59  official_match=['48*sqrt(7)/25']
     at ax=10.5, ay=11.9058808998, d=0.857917648376, e=0.069685291154, f=0.562905867864
  missing_official=none  extra_values=none  => PASS
# JMO-2026-PRE-09  vars=['ax', 'ay', 'd', 'e', 'f']  residuals=5
  validate issues: none
  starts=3000 converged=333 feasible=333
  value=5.07984251724401393376310224698738  hits=333  |res|=2.04e-59  official_match=['48*sqrt(7)/25']
     at ax=10.5, ay=11.9058808998, d=0.857917648376, e=0.069685291154, f=0.562905867864
  missing_official=none  extra_values=none  => PASS
```

