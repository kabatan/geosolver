# Q2対応カード集（暫定）

指定cards.mdがないため条件別表を採用。各原文・全構成・全条件・目標を対応づけた。

# HMMT-2012-FEB-GUTS-01 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=354
- 原文SHA-256: `c7a5746a659875dcf675ed3dae29cc6009e6d890bb40f749435b5a50b939f3de`
- 入力SHA-256（JSONファイルの全bytes）: `313cfb118f2e6a515463eb234419a3c10a3ff79fadc9f812120e7bee9b40e227`
- 座標固定・同値性: Aを原点、ABを正のx軸、正方形を上側。平行移動・回転・鏡映だけ。尺度2を保持。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Square $A B C D$ has side length 2 , and $X$ is a point outside the square such that $A X=X B=\sqrt{2}$. What is the length of the longest diagonal of pentagon $A X B C D$ ?

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| square ABCD, side 2 / 座標原点 | `constructions[0]` | `A = Point(0, 0)` |
| square ABCD, side 2 | `constructions[1]` | `B = Point(2, 0)` |
| square ABCD, side 2 | `constructions[2]` | `C = Point(2, 2)` |
| square ABCD, side 2 | `constructions[3]` | `D = Point(0, 2)` |
| X is outside the square / 未知点 | `constructions[4]` | `X = Point(x, y)` |
| AX = sqrt(2) | `conditions[0]` | `Distance(A, X) = sqrt(2)` |
| XB = sqrt(2) | `conditions[1]` | `Distance(X, B) = sqrt(2)` |
| X outside square / 正方形の閉領域の外 | `conditions[2]` | `(x < 0) or (x > 2) or (y < 0) or (y > 2)` |
| longest diagonal of AXBCD / 頂点順から得る全5本の対角線の最大値 | `target` | `max([Distance(A, B), Distance(A, C), Distance(X, C), Distance(X, D), Distance(B, D)])` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2013-FEB-TEAM-03 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=199
- 原文SHA-256: `d346676026e102ad900899d3d8f2c549128e3057081e7b34349d1051ac9a4267`
- 入力SHA-256（JSONファイルの全bytes）: `c20487e7f105b3f6ab9f1d7b1b78bbbbb4e0f3316b6c779bbe196566ddd4e69a`
- 座標固定・同値性: Bを原点、Cを正のx軸、Aを上半平面。合同移動のみ。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C$ be a triangle with circumcenter $O$ such that $A C=7$. Suppose that the circumcircle of $A O C$ is tangent to $B C$ at $C$ and intersects the line $A B$ at $A$ and $F$. Let $F O$ intersect $B C$ at $E$. Compute $B E$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| triangle ABC / 座標原点 | `constructions[0]` | `B = Point(0, 0)` |
| triangle ABC / BCをx軸 | `constructions[1]` | `C = Point(c, 0)` |
| triangle ABC / 未知頂点 | `constructions[2]` | `A = Point(ax, ay)` |
| circumcenter O | `constructions[3]` | `O = Circumcenter(A, B, C)` |
| circumcircle of AOC | `constructions[4]` | `omega = Circumcircle(A, O, C)` |
| line AB meets circle AOC at A and F / A以外 | `constructions[5]` | `F = Intersect(Line(A, B), omega, exclude=A)` |
| FO intersects BC at E | `constructions[6]` | `E = Intersect(Line(F, O), Line(B, C))` |
| BCの長さは正 / 非退化三角形 | `conditions[0]` | `c > 0` |
| 鏡映による向き固定 | `conditions[1]` | `ay > 0` |
| AC = 7 | `conditions[2]` | `Distance(A, C) = 7` |
| circumcircle AOCが定義される | `conditions[3]` | `Area(A, O, C) > 0` |
| circle AOC is tangent to BC at C / Cは構成上円上 | `conditions[4]` | `IsTangent(Line(B, C), omega) = 0` |
| A and F are distinct intersections | `conditions[5]` | `Distance(A, F) > 0` |
| line FOが定義される | `conditions[6]` | `Distance(F, O) > 0` |
| Compute BE | `target` | `Distance(B, E)` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2014-FEB-TEAM-08 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=148
- 原文SHA-256: `13784ca4fb5e7ceedbd9a8223bf05c1dbca2fbaddbeb14a2d19bda10817ecc2d`
- 入力SHA-256（JSONファイルの全bytes）: `f8cdba7960fd49d2b2a4075a569b812c06d24ace51ba1f6256477911b8b18e80`
- 座標固定・同値性: B=(0,0), C=(6,0), ay>0。合同移動のみ。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C$ be an acute triangle with circumcenter $O$ such that $A B=4, A C=5$, and $B C=6$. Let $D$ be the foot of the altitude from $A$ to $B C$, and $E$ be the intersection of $A O$ with $B C$. Suppose that $X$ is on $B C$ between $D$ and $E$ such that there is a point $Y$ on $A D$ satisfying $X Y \| A O$ and $Y O \perp A X$. Determine the length of $B X$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| BC = 6 / 座標原点 | `constructions[0]` | `B = Point(0, 0)` |
| BC = 6 | `constructions[1]` | `C = Point(6, 0)` |
| triangle ABC / 未知頂点 | `constructions[2]` | `A = Point(ax, ay)` |
| circumcenter O | `constructions[3]` | `O = Circumcenter(A, B, C)` |
| D is the foot from A to BC | `constructions[4]` | `D = FootOfPerpendicular(A, Line(B, C))` |
| E = AO intersection BC | `constructions[5]` | `E = Intersect(Line(A, O), Line(B, C))` |
| X between D and E on BC | `constructions[6]` | `X = PointOnSegment(D, E, t)` |
| Y on AD | `constructions[7]` | `Y = PointOnSegment(A, D, s)` |
| 鏡映による向き固定 | `conditions[0]` | `ay > 0` |
| AB = 4 | `conditions[1]` | `Distance(A, B) = 4` |
| AC = 5 | `conditions[2]` | `Distance(A, C) = 5` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[3]` | `((B.x-A.x)*(C.x-A.x)+(B.y-A.y)*(C.y-A.y)) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[4]` | `((A.x-B.x)*(C.x-B.x)+(A.y-B.y)*(C.y-B.y)) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[5]` | `((A.x-C.x)*(B.x-C.x)+(A.y-C.y)*(B.y-C.y)) > 0` |
| X strictly between D and E | `conditions[6]` | `t > 0` |
| X strictly between D and E | `conditions[7]` | `t < 1` |
| Y on segment AD | `conditions[8]` | `s >= 0` |
| Y on segment AD | `conditions[9]` | `s <= 1` |
| XY parallel AO | `conditions[10]` | `Parallel(Line(X, Y), Line(A, O)) = 0` |
| YO perpendicular AX | `conditions[11]` | `Perpendicular(Line(Y, O), Line(A, X)) = 0` |
| line AOが定義される | `conditions[12]` | `Distance(A, O) > 0` |
| between D and E / 区間非退化 | `conditions[13]` | `Distance(D, E) > 0` |
| line XYが定義される | `conditions[14]` | `Distance(X, Y) > 0` |
| line YOが定義される | `conditions[15]` | `Distance(Y, O) > 0` |
| Determine BX | `target` | `Distance(B, X)` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2015-FEB-GUTS-02 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=2060
- 原文SHA-256: `f460d44625ecd7b7c1e51d241b61110efae41021eaa362a5069ea5766a52b463`
- 入力SHA-256（JSONファイルの全bytes）: `5ff4313c102fe91dbeafbf9e5df8d2554ac4a8a823c4ab435798a877a79c9778`
- 座標固定・同値性: A=(0,0), B=(1,0)。凸多角形の向きを鏡映で反時計回りにする。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C D E$ be a convex pentagon such that $\angle A B C=\angle A C D=\angle A D E=90^{\circ}$ and $A B=B C=$ $C D=D E=1$. Compute $A E$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| AB = 1 / 座標原点 | `constructions[0]` | `A = Point(0, 0)` |
| AB = 1 | `constructions[1]` | `B = Point(1, 0)` |
| convex pentagon ABCDE / 未知点 | `constructions[2]` | `C = Point(cx, cy)` |
| convex pentagon ABCDE / 未知点 | `constructions[3]` | `D = Point(dx, dy)` |
| convex pentagon ABCDE / 未知点 | `constructions[4]` | `E = Point(ex, ey)` |
| angle ABC = 90 degrees | `conditions[0]` | `Perpendicular(Line(A, B), Line(B, C)) = 0` |
| angle ACD = 90 degrees | `conditions[1]` | `Perpendicular(Line(A, C), Line(C, D)) = 0` |
| angle ADE = 90 degrees | `conditions[2]` | `Perpendicular(Line(A, D), Line(D, E)) = 0` |
| BC = 1 | `conditions[3]` | `Distance(B, C) = 1` |
| CD = 1 | `conditions[4]` | `Distance(C, D) = 1` |
| DE = 1 | `conditions[5]` | `Distance(D, E) = 1` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[6]` | `((B.x-A.x)*(C.y-A.y)-(B.y-A.y)*(C.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[7]` | `((B.x-A.x)*(D.y-A.y)-(B.y-A.y)*(D.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[8]` | `((B.x-A.x)*(E.y-A.y)-(B.y-A.y)*(E.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[9]` | `((C.x-B.x)*(A.y-B.y)-(C.y-B.y)*(A.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[10]` | `((C.x-B.x)*(D.y-B.y)-(C.y-B.y)*(D.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[11]` | `((C.x-B.x)*(E.y-B.y)-(C.y-B.y)*(E.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[12]` | `((D.x-C.x)*(A.y-C.y)-(D.y-C.y)*(A.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[13]` | `((D.x-C.x)*(B.y-C.y)-(D.y-C.y)*(B.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[14]` | `((D.x-C.x)*(E.y-C.y)-(D.y-C.y)*(E.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[15]` | `((E.x-D.x)*(A.y-D.y)-(E.y-D.y)*(A.x-D.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[16]` | `((E.x-D.x)*(B.y-D.y)-(E.y-D.y)*(B.x-D.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[17]` | `((E.x-D.x)*(C.y-D.y)-(E.y-D.y)*(C.x-D.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[18]` | `((A.x-E.x)*(B.y-E.y)-(A.y-E.y)*(B.x-E.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[19]` | `((A.x-E.x)*(C.y-E.y)-(A.y-E.y)*(C.x-E.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[20]` | `((A.x-E.x)*(D.y-E.y)-(A.y-E.y)*(D.x-E.x)) > 0` |
| Compute AE | `target` | `Distance(A, E)` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2016-FEB-GEO-01 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2016-geo-problems.txt` / saved_pdf_text / row_idx=1
- 原文SHA-256: `dbd326627b84cf97821be42d5e03f5781a9aa49e9c42650d756453cddccbfaf6`
- 入力SHA-256（JSONファイルの全bytes）: `40f7619eabc820552c73d68a1a2220eb0e2ea3c4113561ee37cc32db6ebba736`
- 座標固定・同値性: Q=(0,0), W=(2,0)。合同移動だけ。隣接辺の直交から全辺が軸平行。鏡映・凹凸の枝は残す。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Dodecagon QW ART ZSP HIN X has all side lengths equal to 2, is not self-intersecting (in particular,
    the twelve vertices are all distinct), and moreover each interior angle is either 90◦ or 270◦ . What are
    all possible values of the area of 4SIX?

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| all side lengths 2 / 座標原点 | `constructions[0]` | `Q = Point(0, 0)` |
| QW = 2 | `constructions[1]` | `W = Point(2, 0)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[2]` | `A = Point(ax, ay)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[3]` | `R = Point(rx, ry)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[4]` | `T = Point(tx, ty)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[5]` | `Z = Point(zx, zy)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[6]` | `S = Point(sx, sy)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[7]` | `P = Point(px, py)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[8]` | `H = Point(hx, hy)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[9]` | `I = Point(ix, iy)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[10]` | `N = Point(nx, ny)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[11]` | `X = Point(xx, xy)` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[0]` | `Perpendicular(Line(Q, W), Line(W, A)) = 0` |
| all twelve side lengths equal 2 | `conditions[1]` | `Distance(W, A) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[2]` | `Perpendicular(Line(W, A), Line(A, R)) = 0` |
| all twelve side lengths equal 2 | `conditions[3]` | `Distance(A, R) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[4]` | `Perpendicular(Line(A, R), Line(R, T)) = 0` |
| all twelve side lengths equal 2 | `conditions[5]` | `Distance(R, T) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[6]` | `Perpendicular(Line(R, T), Line(T, Z)) = 0` |
| all twelve side lengths equal 2 | `conditions[7]` | `Distance(T, Z) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[8]` | `Perpendicular(Line(T, Z), Line(Z, S)) = 0` |
| all twelve side lengths equal 2 | `conditions[9]` | `Distance(Z, S) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[10]` | `Perpendicular(Line(Z, S), Line(S, P)) = 0` |
| all twelve side lengths equal 2 | `conditions[11]` | `Distance(S, P) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[12]` | `Perpendicular(Line(S, P), Line(P, H)) = 0` |
| all twelve side lengths equal 2 | `conditions[13]` | `Distance(P, H) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[14]` | `Perpendicular(Line(P, H), Line(H, I)) = 0` |
| all twelve side lengths equal 2 | `conditions[15]` | `Distance(H, I) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[16]` | `Perpendicular(Line(H, I), Line(I, N)) = 0` |
| all twelve side lengths equal 2 | `conditions[17]` | `Distance(I, N) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[18]` | `Perpendicular(Line(I, N), Line(N, X)) = 0` |
| all twelve side lengths equal 2 | `conditions[19]` | `Distance(N, X) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[20]` | `Perpendicular(Line(N, X), Line(X, Q)) = 0` |
| all twelve side lengths equal 2 | `conditions[21]` | `Distance(X, Q) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[22]` | `Perpendicular(Line(X, Q), Line(Q, W)) = 0` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[23]` | `(max(Q.x,W.x)<min(A.x,R.x)) or (max(A.x,R.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(A.y,R.y)) or (max(A.y,R.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[24]` | `(max(Q.x,W.x)<min(R.x,T.x)) or (max(R.x,T.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(R.y,T.y)) or (max(R.y,T.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[25]` | `(max(Q.x,W.x)<min(T.x,Z.x)) or (max(T.x,Z.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(T.y,Z.y)) or (max(T.y,Z.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[26]` | `(max(Q.x,W.x)<min(Z.x,S.x)) or (max(Z.x,S.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(Z.y,S.y)) or (max(Z.y,S.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[27]` | `(max(Q.x,W.x)<min(S.x,P.x)) or (max(S.x,P.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(S.y,P.y)) or (max(S.y,P.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[28]` | `(max(Q.x,W.x)<min(P.x,H.x)) or (max(P.x,H.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(P.y,H.y)) or (max(P.y,H.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[29]` | `(max(Q.x,W.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[30]` | `(max(Q.x,W.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[31]` | `(max(Q.x,W.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[32]` | `(max(W.x,A.x)<min(R.x,T.x)) or (max(R.x,T.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(R.y,T.y)) or (max(R.y,T.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[33]` | `(max(W.x,A.x)<min(T.x,Z.x)) or (max(T.x,Z.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(T.y,Z.y)) or (max(T.y,Z.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[34]` | `(max(W.x,A.x)<min(Z.x,S.x)) or (max(Z.x,S.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(Z.y,S.y)) or (max(Z.y,S.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[35]` | `(max(W.x,A.x)<min(S.x,P.x)) or (max(S.x,P.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(S.y,P.y)) or (max(S.y,P.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[36]` | `(max(W.x,A.x)<min(P.x,H.x)) or (max(P.x,H.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(P.y,H.y)) or (max(P.y,H.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[37]` | `(max(W.x,A.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[38]` | `(max(W.x,A.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[39]` | `(max(W.x,A.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[40]` | `(max(W.x,A.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[41]` | `(max(A.x,R.x)<min(T.x,Z.x)) or (max(T.x,Z.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(T.y,Z.y)) or (max(T.y,Z.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[42]` | `(max(A.x,R.x)<min(Z.x,S.x)) or (max(Z.x,S.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(Z.y,S.y)) or (max(Z.y,S.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[43]` | `(max(A.x,R.x)<min(S.x,P.x)) or (max(S.x,P.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(S.y,P.y)) or (max(S.y,P.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[44]` | `(max(A.x,R.x)<min(P.x,H.x)) or (max(P.x,H.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(P.y,H.y)) or (max(P.y,H.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[45]` | `(max(A.x,R.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[46]` | `(max(A.x,R.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[47]` | `(max(A.x,R.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[48]` | `(max(A.x,R.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[49]` | `(max(R.x,T.x)<min(Z.x,S.x)) or (max(Z.x,S.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(Z.y,S.y)) or (max(Z.y,S.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[50]` | `(max(R.x,T.x)<min(S.x,P.x)) or (max(S.x,P.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(S.y,P.y)) or (max(S.y,P.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[51]` | `(max(R.x,T.x)<min(P.x,H.x)) or (max(P.x,H.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(P.y,H.y)) or (max(P.y,H.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[52]` | `(max(R.x,T.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[53]` | `(max(R.x,T.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[54]` | `(max(R.x,T.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[55]` | `(max(R.x,T.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[56]` | `(max(T.x,Z.x)<min(S.x,P.x)) or (max(S.x,P.x)<min(T.x,Z.x)) or (max(T.y,Z.y)<min(S.y,P.y)) or (max(S.y,P.y)<min(T.y,Z.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[57]` | `(max(T.x,Z.x)<min(P.x,H.x)) or (max(P.x,H.x)<min(T.x,Z.x)) or (max(T.y,Z.y)<min(P.y,H.y)) or (max(P.y,H.y)<min(T.y,Z.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[58]` | `(max(T.x,Z.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(T.x,Z.x)) or (max(T.y,Z.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(T.y,Z.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[59]` | `(max(T.x,Z.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(T.x,Z.x)) or (max(T.y,Z.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(T.y,Z.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[60]` | `(max(T.x,Z.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(T.x,Z.x)) or (max(T.y,Z.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(T.y,Z.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[61]` | `(max(T.x,Z.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(T.x,Z.x)) or (max(T.y,Z.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(T.y,Z.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[62]` | `(max(Z.x,S.x)<min(P.x,H.x)) or (max(P.x,H.x)<min(Z.x,S.x)) or (max(Z.y,S.y)<min(P.y,H.y)) or (max(P.y,H.y)<min(Z.y,S.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[63]` | `(max(Z.x,S.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(Z.x,S.x)) or (max(Z.y,S.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(Z.y,S.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[64]` | `(max(Z.x,S.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(Z.x,S.x)) or (max(Z.y,S.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(Z.y,S.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[65]` | `(max(Z.x,S.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(Z.x,S.x)) or (max(Z.y,S.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(Z.y,S.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[66]` | `(max(Z.x,S.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(Z.x,S.x)) or (max(Z.y,S.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(Z.y,S.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[67]` | `(max(S.x,P.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(S.x,P.x)) or (max(S.y,P.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(S.y,P.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[68]` | `(max(S.x,P.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(S.x,P.x)) or (max(S.y,P.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(S.y,P.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[69]` | `(max(S.x,P.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(S.x,P.x)) or (max(S.y,P.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(S.y,P.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[70]` | `(max(S.x,P.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(S.x,P.x)) or (max(S.y,P.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(S.y,P.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[71]` | `(max(P.x,H.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(P.x,H.x)) or (max(P.y,H.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(P.y,H.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[72]` | `(max(P.x,H.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(P.x,H.x)) or (max(P.y,H.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(P.y,H.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[73]` | `(max(P.x,H.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(P.x,H.x)) or (max(P.y,H.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(P.y,H.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[74]` | `(max(H.x,I.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(H.x,I.x)) or (max(H.y,I.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(H.y,I.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[75]` | `(max(H.x,I.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(H.x,I.x)) or (max(H.y,I.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(H.y,I.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[76]` | `(max(I.x,N.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(I.x,N.x)) or (max(I.y,N.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(I.y,N.y))` |
| all possible areas of triangle SIX / DSLは各許容配置の面積を返す | `target` | `Area(S, I, X)` |

## 残る制約

原問は可能な面積の集合を問う。値の列挙はしていない。集合の完全な採点と網羅性は後続担当で設計が必要。非隣接辺の矩形分離は軸平行性の下で線分非交差と同値。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2016-FEB-GUTS-03 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=317
- 原文SHA-256: `e1ec215f55fea15321ed2b0ac7b8cce58d47d08e665a49ab9ab06d85d42225dc`
- 入力SHA-256（JSONファイルの全bytes）: `d1fb9bf24c8b4e78a6942569cabce083a685e37b5d646c5b7478d8ebce09e0b7`
- 座標固定・同値性: 円の中心を原点、P=(1,0)。鏡映で頂点を反時計回り。半径1は原文。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $P R O B L E M Z$ be a regular octagon inscribed in a circle of unit radius. Diagonals $M R, O Z$ meet at $I$. Compute $L I$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[0]` | `P = Point(cos(0*pi/4), sin(0*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[1]` | `R = Point(cos(1*pi/4), sin(1*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[2]` | `O = Point(cos(2*pi/4), sin(2*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[3]` | `B = Point(cos(3*pi/4), sin(3*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[4]` | `L = Point(cos(4*pi/4), sin(4*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[5]` | `E = Point(cos(5*pi/4), sin(5*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[6]` | `M = Point(cos(6*pi/4), sin(6*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[7]` | `Z = Point(cos(7*pi/4), sin(7*pi/4))` |
| diagonals MR and OZ meet at I | `constructions[8]` | `I = Intersect(Line(M, R), Line(O, Z))` |
| Compute LI | `target` | `Distance(L, I)` |

## 残る制約

変数0も選定から除かない。頂点は正八角形の定義であって、解答の座標ではない。文字Oは頂点。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2016-FEB-TEAM-03 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / train / row_idx=457
- 原文SHA-256: `769b42bd36650e9b2b05a915c6eaa28b2b9a06afa02369fe8fb32da04dfbd1e7`
- 入力SHA-256（JSONファイルの全bytes）: `951d79daa648bf6ccf00fbd7068152c0830a11584c6867208a1604a7d3aad7fe`
- 座標固定・同値性: B=(0,0), C=(144,0), ay>0。合同移動のみ。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C$ be an acute triangle with incenter $I$ and circumcenter $O$. Assume that $\angle O I A=90^{\circ}$. Given that $A I=97$ and $B C=144$, compute the area of $\triangle A B C$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| BC = 144 / 座標原点 | `constructions[0]` | `B = Point(0, 0)` |
| BC = 144 | `constructions[1]` | `C = Point(144, 0)` |
| acute triangle ABC / 未知頂点 | `constructions[2]` | `A = Point(ax, ay)` |
| incenter I | `constructions[3]` | `I = Incenter(A, B, C)` |
| circumcenter O | `constructions[4]` | `O = Circumcenter(A, B, C)` |
| 鏡映による向き固定 | `conditions[0]` | `ay > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[1]` | `((B.x-A.x)*(C.x-A.x)+(B.y-A.y)*(C.y-A.y)) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[2]` | `((A.x-B.x)*(C.x-B.x)+(A.y-B.y)*(C.y-B.y)) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[3]` | `((A.x-C.x)*(B.x-C.x)+(A.y-C.y)*(B.y-C.y)) > 0` |
| AI = 97 | `conditions[4]` | `Distance(A, I) = 97` |
| angle OIA = 90 degrees | `conditions[5]` | `Perpendicular(Line(O, I), Line(A, I)) = 0` |
| angle OIAが定義される / OとIは相異なる | `conditions[6]` | `Distance(O, I) > 0` |
| Compute area ABC | `target` | `Area(A, B, C)` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2016-FEB-GUTS-10 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=1486
- 原文SHA-256: `8ce9ea19008557446d595303bdc0a54bb39f7e8cdbd52bdaca29154975abfe62`
- 入力SHA-256（JSONファイルの全bytes）: `689c97d307e6a8f035ae7827493a0c4871d0f4b245094c4aea3ec1e01ca56ed7`
- 座標固定・同値性: B=(0,0), C=(14,0), ay>0。合同移動のみ。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C$ be a triangle with $A B=13, B C=14, C A=15$. Let $O$ be the circumcenter of $A B C$. Find the distance between the circumcenters of triangles $A O B$ and $A O C$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| BC = 14 / 座標原点 | `constructions[0]` | `B = Point(0, 0)` |
| BC = 14 | `constructions[1]` | `C = Point(14, 0)` |
| triangle ABC / 未知頂点 | `constructions[2]` | `A = Point(ax, ay)` |
| circumcenter O of ABC | `constructions[3]` | `O = Circumcenter(A, B, C)` |
| circumcenter of AOB | `constructions[4]` | `U = Circumcenter(A, O, B)` |
| circumcenter of AOC | `constructions[5]` | `V = Circumcenter(A, O, C)` |
| 鏡映による向き固定 | `conditions[0]` | `ay > 0` |
| AB = 13 | `conditions[1]` | `Distance(A, B) = 13` |
| CA = 15 | `conditions[2]` | `Distance(A, C) = 15` |
| triangle AOB has a circumcenter | `conditions[3]` | `Area(A, O, B) > 0` |
| triangle AOC has a circumcenter | `conditions[4]` | `Area(A, O, C) > 0` |
| distance between the two circumcenters | `target` | `Distance(U, V)` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2017-FEB-GUTS-06 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=144
- 原文SHA-256: `6088e1b39c35b300c4f34f2713d099a015008203c8b928aaa05a488848e601cd`
- 入力SHA-256（JSONファイルの全bytes）: `651c1227a28e07084cd971dbfe1b27f2d4ad4e290b1152c3465bd6ad2baafb32`
- 座標固定・同値性: A=(0,0), C=(7,0)。合同移動と鏡映による凸四角形の向き固定のみ。図の自由度は残す。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C D$ be a convex quadrilateral with $A C=7$ and $B D=17$. Let $M, P, N, Q$ be the midpoints of sides $A B, B C, C D, D A$ respectively. Compute $M N^{2}+P Q^{2}$

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| AC = 7 / 座標原点 | `constructions[0]` | `A = Point(0, 0)` |
| AC = 7 | `constructions[1]` | `C = Point(7, 0)` |
| convex quadrilateral ABCD / 未知点 | `constructions[2]` | `B = Point(bx, by)` |
| convex quadrilateral ABCD / 未知点 | `constructions[3]` | `D = Point(dx, dy)` |
| M midpoint of AB | `constructions[4]` | `M = Midpoint(A, B)` |
| P midpoint of BC | `constructions[5]` | `P = Midpoint(B, C)` |
| N midpoint of CD | `constructions[6]` | `N = Midpoint(C, D)` |
| Q midpoint of DA | `constructions[7]` | `Q = Midpoint(D, A)` |
| BD = 17 | `conditions[0]` | `Distance(B, D) = 17` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[1]` | `((B.x-A.x)*(C.y-A.y)-(B.y-A.y)*(C.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[2]` | `((B.x-A.x)*(D.y-A.y)-(B.y-A.y)*(D.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[3]` | `((C.x-B.x)*(A.y-B.y)-(C.y-B.y)*(A.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[4]` | `((C.x-B.x)*(D.y-B.y)-(C.y-B.y)*(D.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[5]` | `((D.x-C.x)*(A.y-C.y)-(D.y-C.y)*(A.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[6]` | `((D.x-C.x)*(B.y-C.y)-(D.y-C.y)*(B.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[7]` | `((A.x-D.x)*(B.y-D.y)-(A.y-D.y)*(B.x-D.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[8]` | `((A.x-D.x)*(C.y-D.y)-(A.y-D.y)*(C.x-D.x)) > 0` |
| Compute MN^2 + PQ^2 | `target` | `Distance(M, N)**2 + Distance(P, Q)**2` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2020-FEB-GUTS-02 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=2086
- 原文SHA-256: `51dcf0322958169634a8779ddd29cb3b9f63c1393827eb6bf335f6a3e566c017`
- 入力SHA-256（JSONファイルの全bytes）: `b712d9961fa8ad073e5c9aca81073ecb16f238b830b253f9a881a9f047d823d6`
- 座標固定・同値性: 絶対長の指定がなく目標は角度なので半径1に相似正規化。O原点、回転でM=(1,0)。鏡映枝は両方残す。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C$ be a triangle and $\omega$ be its circumcircle. The point $M$ is the midpoint of arc $B C$ not containing $A$ on $\omega$ and $D$ is chosen so that $D M$ is tangent to $\omega$ and is on the same side of $A M$ as $C$. It is given that $A M=A C$ and $\angle D M C=38^{\circ}$. Find the measure of angle $\angle A C B$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| circumcircle / 中心を原点 | `constructions[0]` | `O = Point(0, 0)` |
| circumcircle / 相似正規化 | `constructions[1]` | `omega = Circle(O, 1)` |
| arc midpoint M / 回転でMを固定 | `constructions[2]` | `M = Point(1, 0)` |
| A on circumcircle | `constructions[3]` | `A = Point(ax, ay)` |
| B on circumcircle | `constructions[4]` | `B = Point(bx, by)` |
| C on circumcircle | `constructions[5]` | `C = Point(cx, cy)` |
| DM tangent at M / 単位円のMでの接線上の点 | `constructions[6]` | `D = Point(1, dy)` |
| A on circumcircle | `conditions[0]` | `OnCircle(A, omega) = 0` |
| B on circumcircle | `conditions[1]` | `OnCircle(B, omega) = 0` |
| C on circumcircle | `conditions[2]` | `OnCircle(C, omega) = 0` |
| M midpoint of arc BC / 両端への弦長が等しい | `conditions[3]` | `Distance(M, B) = Distance(M, C)` |
| arc BC not containing A / AとMは弦BCの反対側 | `conditions[4]` | `((C.x-B.x)*(A.y-B.y)-(C.y-B.y)*(A.x-B.x))*((C.x-B.x)*(M.y-B.y)-(C.y-B.y)*(M.x-B.x)) < 0` |
| AM = AC | `conditions[5]` | `Distance(A, M) = Distance(A, C)` |
| angle DMC = 38 degrees | `conditions[6]` | `Angle(D, M, C) = 38*pi/180` |
| D and C on same side of AM | `conditions[7]` | `((M.x-A.x)*(D.y-A.y)-(M.y-A.y)*(D.x-A.x))*((M.x-A.x)*(C.y-A.y)-(M.y-A.y)*(C.x-A.x)) > 0` |
| nondegenerate triangle ABC | `conditions[8]` | `Area(A, B, C) > 0` |
| line AMが定義される | `conditions[9]` | `Distance(A, M) > 0` |
| arc midpoint distinct from endpoints | `conditions[10]` | `Distance(B, M) > 0` |
| arc midpoint distinct from endpoints | `conditions[11]` | `Distance(C, M) > 0` |
| angle DMCが定義される | `conditions[12]` | `Distance(D, M) > 0` |
| measure angle ACB / 度単位 | `target` | `Degrees(Angle(A, C, B))` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2021-FEB-GUTS-03 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=2382
- 原文SHA-256: `c98b18c4b323e70ab9011f2149c5b0ed95e7e7a108adc0cfcdb64cf52dfc18ee`
- 入力SHA-256（JSONファイルの全bytes）: `d3b5dc0fb2f2d5822e45c8fabb253d8041ced67d2c4bfc21d6811f28da15cd53`
- 座標固定・同値性: O原点、OAを正x軸、半円を鏡映で上側。半径2021は保持。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

A semicircle with radius 2021 has diameter $A B$ and center $O$. Points $C$ and $D$ lie on the semicircle such that $\angle A O C<\angle A O D=90^{\circ}$. A circle of radius $r$ is inscribed in the sector bounded by $O A$ and $O C$ and is tangent to the semicircle at $E$. If $C D=C E$, compute $\lfloor r\rfloor$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| center O | `constructions[0]` | `O = Point(0, 0)` |
| radius 2021 / OAを正x軸 | `constructions[1]` | `A = Point(2021, 0)` |
| diameter AB | `constructions[2]` | `B = Point(-2021, 0)` |
| angle AOD = 90 degrees | `constructions[3]` | `D = Point(0, 2021)` |
| C on semicircle / 未知点 | `constructions[4]` | `C = Point(cx, cy)` |
| center of the inscribed circle / 補助未知点 | `constructions[5]` | `J = Point(jx, jy)` |
| circle of radius r inscribed in sector AOC | `constructions[6]` | `small = Circle(J, r)` |
| internal tangency E / 中心線OJ上の大円との接点 | `constructions[7]` | `E = Point(2021*jx/Distance(O, J), 2021*jy/Distance(O, J))` |
| C on semicircle radius 2021 | `conditions[0]` | `Distance(O, C) = 2021` |
| angle AOC < 90 degrees | `conditions[1]` | `cx > 0` |
| nondegenerate sector on chosen upper semicircle | `conditions[2]` | `cy > 0` |
| positive radius of inscribed circle | `conditions[3]` | `r > 0` |
| tangency to ray OA / 垂足が正の半直線上 | `conditions[4]` | `jx > 0` |
| tangent to OA from inside sector / 上半平面 | `conditions[5]` | `jy = r` |
| tangent to OC from sector interior / 内向き符号付き距離 | `conditions[6]` | `cy*jx-cx*jy = 2021*r` |
| internal tangency to semicircle | `conditions[7]` | `Distance(O, J) + r = 2021` |
| unique tangency point E is defined | `conditions[8]` | `Distance(O, J) > 0` |
| CD = CE | `conditions[9]` | `Distance(C, D) = Distance(C, E)` |
| Compute floor(r) | `target` | `r // 1` |

## 残る制約

接円の二つの線への接条件と内接接条件は原文の定義。rの解を導いていない。床関数は目標だけ。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2021-FEB-GUTS-09 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=2629
- 原文SHA-256: `db6fb259ac58205255ec7e064843f935513fb9c75bdbadfd226805e4341ea116`
- 入力SHA-256（JSONファイルの全bytes）: `78a43411f568b7c8ce022dae1c310b372d6b1b9598398b61abc7d39ab051e48c`
- 座標固定・同値性: 共通中点を原点、ADをx軸、Aを正側。合同移動だけ。B,Cの向きは条件で定め鏡映は残す。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A D, B E$, and $C F$ be segments sharing a common midpoint, with $A B<A E$ and $B C<B F$. Suppose that each pair of segments forms a $60^{\circ}$ angle, and that $A D=7, B E=10$, and $C F=18$. Let $K$ denote the sum of the areas of the six triangles $\triangle A B C, \triangle B C D, \triangle C D E, \triangle D E F, \triangle E F A$, and $\triangle F A B$. Compute $K \sqrt{3}$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| common midpoint of AD, BE, CF | `constructions[0]` | `O = Point(0, 0)` |
| AD = 7 | `constructions[1]` | `A = Point(7/2, 0)` |
| AD = 7 and midpoint O | `constructions[2]` | `D = Point(-7/2, 0)` |
| BE = 10 / 未知端点 | `constructions[3]` | `B = Point(bx, by)` |
| BE midpoint O | `constructions[4]` | `E = Point(-bx, -by)` |
| CF = 18 / 未知端点 | `constructions[5]` | `C = Point(cx, cy)` |
| CF midpoint O | `constructions[6]` | `F = Point(-cx, -cy)` |
| BE = 10 | `conditions[0]` | `Distance(B, E) = 10` |
| CF = 18 | `conditions[1]` | `Distance(C, F) = 18` |
| AD and BE form 60 degrees / 無向直線のcos^2=1/4 | `conditions[2]` | `4*bx**2 = bx**2+by**2` |
| AD and CF form 60 degrees / 無向直線のcos^2=1/4 | `conditions[3]` | `4*cx**2 = cx**2+cy**2` |
| BE and CF form 60 degrees | `conditions[4]` | `4*(bx*cx+by*cy)**2 = (bx**2+by**2)*(cx**2+cy**2)` |
| AB < AE | `conditions[5]` | `Distance(A, B) < Distance(A, E)` |
| BC < BF | `conditions[6]` | `Distance(B, C) < Distance(B, F)` |
| K is the sum of the six stated triangle areas; compute K*sqrt(3) | `target` | `sqrt(3)*(Area(A, B, C)+Area(B, C, D)+Area(C, D, E)+Area(D, E, F)+Area(E, F, A)+Area(F, A, B))` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2022-FEB-GUTS-01 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=1167
- 原文SHA-256: `51f385517d2f1f8955901a22faa1d8bc1024ed5ff6cac93de531bde2c52f98a2`
- 入力SHA-256（JSONファイルの全bytes）: `245ebd5d0cb564e7a429242f303e3ad0f92a8fc4b1da4ddb0d16cd6b6c37faba`
- 座標固定・同値性: 中心原点、Pを正x軸。鏡映で隣頂点を上側。絶対周長6.28は有理数157/25で保持。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

A regular 2022-gon has perimeter 6.28. To the nearest positive integer, compute the area of the 2022-gon.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| regular 2022-gon / 中心 | `constructions[0]` | `O = Point(0, 0)` |
| regular 2022-gon / 一頂点 | `constructions[1]` | `P = Point(r, 0)` |
| regular 2022-gon / 隣の頂点、中心角の定義 | `constructions[2]` | `Q = Point(r*cos(2*pi/2022), r*sin(2*pi/2022))` |
| positive circumradius | `conditions[0]` | `r > 0` |
| perimeter 6.28 / 同長の2022辺の和 | `conditions[1]` | `2022*Distance(P, Q) = 157/25` |
| area to nearest positive integer / 中心から2022枚に分割して面積を加算 | `target` | `(2022*Area(O, P, Q)+1/2) // 1` |

## 残る制約

2022個の等しい中心三角形という正多角形の定義的分割。最適化や解答由来の式は使わない。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2022-FEB-TEAM-03 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=31
- 原文SHA-256: `de69cda4c071d7be5bcb638aaed3e3e2d1ef480d3dd791da493bef6cdd50c4b1`
- 入力SHA-256（JSONファイルの全bytes）: `cbebab77bf813e4d823a774e9aa54262871a1aede013a8997ace0557c51058c8`
- 座標固定・同値性: 原問の長さはRのみで全条件が相似不変。半径を1、O原点、A=(1,0)。鏡映は残す。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let triangle $A B C$ be an acute triangle with circumcircle $\Gamma$. Let $X$ and $Y$ be the midpoints of minor arcs $\widehat{A B}$ and $\widehat{A C}$ of $\Gamma$, respectively. If line $X Y$ is tangent to the incircle of triangle $A B C$ and the radius of $\Gamma$ is $R$, find, with proof, the value of $X Y$ in terms of $R$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| circumcircle center / 相似正規化 | `constructions[0]` | `O = Point(0, 0)` |
| circumradius R=1 | `constructions[1]` | `Gamma = Circle(O, 1)` |
| A on Gamma / 回転固定 | `constructions[2]` | `A = Point(1, 0)` |
| B on Gamma | `constructions[3]` | `B = Point(bx, by)` |
| C on Gamma | `constructions[4]` | `C = Point(cx, cy)` |
| minor arc AB midpoint / 弦中点の方向 | `constructions[5]` | `U = Midpoint(A, B)` |
| minor arc AC midpoint / 弦中点の方向 | `constructions[6]` | `V = Midpoint(A, C)` |
| X midpoint of minor arc AB / 弦中点方向を円へ延長 | `constructions[7]` | `X = Point(U.x/Distance(O, U), U.y/Distance(O, U))` |
| Y midpoint of minor arc AC | `constructions[8]` | `Y = Point(V.x/Distance(O, V), V.y/Distance(O, V))` |
| incircle of ABC | `constructions[9]` | `omega = Incircle(A, B, C)` |
| B on circumcircle | `conditions[0]` | `OnCircle(B, Gamma) = 0` |
| C on circumcircle | `conditions[1]` | `OnCircle(C, Gamma) = 0` |
| nondegenerate triangle ABC | `conditions[2]` | `Area(A, B, C) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[3]` | `((B.x-A.x)*(C.x-A.x)+(B.y-A.y)*(C.y-A.y)) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[4]` | `((A.x-B.x)*(C.x-B.x)+(A.y-B.y)*(C.y-B.y)) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[5]` | `((A.x-C.x)*(B.x-C.x)+(A.y-C.y)*(B.y-C.y)) > 0` |
| minor arc midpoint defined / AB not a diameter | `conditions[6]` | `Distance(O, U) > 0` |
| minor arc midpoint defined / AC not a diameter | `conditions[7]` | `Distance(O, V) > 0` |
| line XY is defined | `conditions[8]` | `Distance(X, Y) > 0` |
| XY tangent to incircle | `conditions[9]` | `IsTangent(Line(X, Y), omega) = 0` |
| XY in terms of R / R=1で係数XY/Rを問う | `target` | `Distance(X, Y)` |

## 残る制約

係数から原問の長さはR倍で復元する。公式答えの係数変換は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2022-FEB-GEO-07 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2022-geo-problems.txt` / saved_pdf_text / row_idx=7
- 原文表記: PDF第1ページ画像を目視し、抽出で崩れた根号・分数をASCII表記で転記。raw_excerptも保持。
- 原文SHA-256: `d8a8dfbf740166536807bb3f2ce312ea5f842342c76827ae21c56062f885394c`
- 入力SHA-256（JSONファイルの全bytes）: `243b7dec3e96f2a9eed6ba61a8246b4ed9cec9257a71c9bce2a20e42da15ac84`
- 座標固定・同値性: A=(0,0), B=(10,0), 正方形を上側。合同移動のみ。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Point P is located inside a square ABCD of side length 10. Let O1, O2, O3, O4 be the circumcenters of PAB, PBC, PCD, and PDA, respectively. Given that PA + PB + PC + PD = 23 sqrt(2) and the area of O1O2O3O4 is 50, the second largest of the lengths O1O2, O2O3, O3O4, O4O1 can be written as sqrt(a/b), where a and b are relatively prime positive integers. Compute 100a + b.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| square ABCD of side 10 | `constructions[0]` | `A = Point(0, 0)` |
| square ABCD of side 10 | `constructions[1]` | `B = Point(10, 0)` |
| square ABCD of side 10 | `constructions[2]` | `C = Point(10, 10)` |
| square ABCD of side 10 | `constructions[3]` | `D = Point(0, 10)` |
| P inside square | `constructions[4]` | `P = Point(x, y)` |
| circumcenter of PAB | `constructions[5]` | `O1 = Circumcenter(P, A, B)` |
| circumcenter of PBC | `constructions[6]` | `O2 = Circumcenter(P, B, C)` |
| circumcenter of PCD | `constructions[7]` | `O3 = Circumcenter(P, C, D)` |
| circumcenter of PDA | `constructions[8]` | `O4 = Circumcenter(P, D, A)` |
| P strictly inside square | `conditions[0]` | `x > 0` |
| P strictly inside square | `conditions[1]` | `x < 10` |
| P strictly inside square | `conditions[2]` | `y > 0` |
| P strictly inside square | `conditions[3]` | `y < 10` |
| PA+PB+PC+PD = 23 sqrt(2) | `conditions[4]` | `Distance(P,A)+Distance(P,B)+Distance(P,C)+Distance(P,D) = 23*sqrt(2)` |
| area O1O2O3O4 = 50 | `conditions[5]` | `Area(O1, O2, O3, O4) = 50` |
| second largest length is sqrt(a/b) / 全6組のminのmaxが2番目に大きい値 | `conditions[6]` | `(max([min(Distance(O1, O2), Distance(O2, O3)), min(Distance(O1, O2), Distance(O3, O4)), min(Distance(O1, O2), Distance(O4, O1)), min(Distance(O2, O3), Distance(O3, O4)), min(Distance(O2, O3), Distance(O4, O1)), min(Distance(O3, O4), Distance(O4, O1))]))**2 = a/b` |
| a,bは正整数、h,kは既約性の整数証人 | `conditions[7]` | `IsInteger(a) = 0` |
| a,bは正整数、h,kは既約性の整数証人 | `conditions[8]` | `IsInteger(b) = 0` |
| a,bは正整数、h,kは既約性の整数証人 | `conditions[9]` | `IsInteger(h) = 0` |
| a,bは正整数、h,kは既約性の整数証人 | `conditions[10]` | `IsInteger(k) = 0` |
| positive integer numerator | `conditions[11]` | `a > 0` |
| positive integer denominator | `conditions[12]` | `b > 0` |
| a,b are relatively prime / Bezoutの同値な定義的条件 | `conditions[13]` | `h*a+k*b = 1` |
| Compute 100a+b | `target` | `100*a+b` |

## 残る制約

整数補助変数は既約分数という原問の出力指定を保持するため。探索しやすさでは採否を決めない。PDF画像で根号と分数を確認。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2022-FEB-GEO-08 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2022-geo-problems.txt` / saved_pdf_text / row_idx=8
- 原文SHA-256: `9239d35d4984e1860bd60e38ec3cf8eecf2093151d5f70ade74e5b48e290ad4a`
- 入力SHA-256（JSONファイルの全bytes）: `044153464a2f3a8ac6eb0310f7b741815cee84f0f026b672229f7f07d804e078`
- 座標固定・同値性: 楕円の中心を原点、長軸をx軸、Aを負側。合同移動と鏡映のみ。長短軸の指定50,14を保持。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let E be an ellipse with foci A and B. Suppose there exists a parabola P such that
      • P passes through A and B,
      • the focus F of P lies on E,
      • the orthocenter H of △F AB lies on the directrix of P.
    If the major and minor axes of E have lengths 50 and 14, respectively, compute AH 2 + BH 2 .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| ellipse focus A / 対称中心を原点 | `constructions[0]` | `A = Point(-f, 0)` |
| ellipse focus B | `constructions[1]` | `B = Point(f, 0)` |
| minor axis length 14 / 短軸端点を定義 | `constructions[2]` | `T = Point(0, 7)` |
| focus F of parabola lies on ellipse | `constructions[3]` | `F = Point(fx, fy)` |
| orthocenter H of FAB | `constructions[4]` | `H = Orthocenter(F, A, B)` |
| directrix through H / 未知方向 | `constructions[5]` | `W = Point(H.x+dx, H.y+dy)` |
| H lies on the directrix | `constructions[6]` | `line_d = Line(H, W)` |
| distance from A to directrix | `constructions[7]` | `U = FootOfPerpendicular(A, line_d)` |
| distance from B to directrix | `constructions[8]` | `V = FootOfPerpendicular(B, line_d)` |
| nondegenerate parabola / focus not on directrix | `constructions[9]` | `K = FootOfPerpendicular(F, line_d)` |
| ellipse with major 50 and minor 14 has distinct foci | `conditions[0]` | `f > 0` |
| ellipse definition: distances from short-axis endpoint sum to major-axis length | `conditions[1]` | `Distance(T, A)+Distance(T, B) = 50` |
| F lies on ellipse with foci A,B and major axis 50 | `conditions[2]` | `Distance(F, A)+Distance(F, B) = 50` |
| triangle FAB nondegenerate / 鏡映でFを上側 | `conditions[3]` | `fy > 0` |
| directrix direction is normalized / 表示だけの冗長な尺度を除く | `conditions[4]` | `dx**2+dy**2 = 1` |
| parabola passes through A / 焦点と準線への等距離という定義 | `conditions[5]` | `Distance(A, F) = Distance(A, U)` |
| parabola passes through B | `conditions[6]` | `Distance(B, F) = Distance(B, V)` |
| focus is not on directrix / proper parabola | `conditions[7]` | `Distance(F, K) > 0` |
| Compute AH^2+BH^2 | `target` | `Distance(A, H)**2+Distance(B, H)**2` |

## 残る制約

楕円・放物線の焦点/準線の定義で記述し、解答由来の焦点距離やF,Hの座標は使わない。PDF両ページで原文確認。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2023-FEB-GEO-06 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2023-geo-problems.txt` / saved_pdf_text / row_idx=6
- 原文SHA-256: `23a1336c0aefdd57ecf374165ad56c3cf0fef07a99b0d33c0e3f3576408469b3`
- 入力SHA-256（JSONファイルの全bytes）: `b878de21b4753343976d47a908b007e1af0de8bcd0a1974bba8f5a88c42aa76b`
- 座標固定・同値性: 絶対長の指定がなく目標が角度なのでAB=1に相似正規化。凸四角形を反時計回りに鏡映。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Convex quadrilateral ABCD satisfies ∠CAB = ∠ADB = 30◦ , ∠ABD = 77◦ , BC = CD, and
    ∠BCD = n◦ for some positive integer n. Compute n.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| convex quadrilateral ABCD / 座標原点 | `constructions[0]` | `A = Point(0, 0)` |
| ABを相似正規化 | `constructions[1]` | `B = Point(1, 0)` |
| convex quadrilateral ABCD / 未知点 | `constructions[2]` | `C = Point(cx, cy)` |
| convex quadrilateral ABCD / 未知点 | `constructions[3]` | `D = Point(dx, dy)` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[0]` | `((B.x-A.x)*(C.y-A.y)-(B.y-A.y)*(C.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[1]` | `((B.x-A.x)*(D.y-A.y)-(B.y-A.y)*(D.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[2]` | `((C.x-B.x)*(A.y-B.y)-(C.y-B.y)*(A.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[3]` | `((C.x-B.x)*(D.y-B.y)-(C.y-B.y)*(D.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[4]` | `((D.x-C.x)*(A.y-C.y)-(D.y-C.y)*(A.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[5]` | `((D.x-C.x)*(B.y-C.y)-(D.y-C.y)*(B.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[6]` | `((A.x-D.x)*(B.y-D.y)-(A.y-D.y)*(B.x-D.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[7]` | `((A.x-D.x)*(C.y-D.y)-(A.y-D.y)*(C.x-D.x)) > 0` |
| angle CAB = 30 degrees | `conditions[8]` | `Angle(C, A, B) = 30*pi/180` |
| angle ADB = 30 degrees | `conditions[9]` | `Angle(A, D, B) = 30*pi/180` |
| angle ABD = 77 degrees | `conditions[10]` | `Angle(A, B, D) = 77*pi/180` |
| BC = CD | `conditions[11]` | `Distance(B, C) = Distance(C, D)` |
| angle BCD = n degrees | `conditions[12]` | `Angle(B, C, D) = n*pi/180` |
| n is an integer | `conditions[13]` | `IsInteger(n) = 0` |
| n is positive | `conditions[14]` | `n > 0` |
| Compute n | `target` | `n` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2024-FEB-GUTS-06 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=1769
- 原文SHA-256: `a1625b938644e95009e53e9c9b7429371c99258859bdbc0f8e1c35f32d13ed11`
- 入力SHA-256（JSONファイルの全bytes）: `b1835a5e644475fabe725fe842dfccbf589f3aa53ee0efaf4b0153004ee35e6a`
- 座標固定・同値性: B=(0,0), C=(1,0), ay>0。P,Qの交換で条件は変わらない。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

In triangle $A B C$, points $M$ and $N$ are the midpoints of $A B$ and $A C$, respectively, and points $P$ and $Q$ trisect $B C$. Given that $A, M, N, P$, and $Q$ lie on a circle and $B C=1$, compute the area of triangle $A B C$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| BC = 1 / 座標原点 | `constructions[0]` | `B = Point(0, 0)` |
| BC = 1 | `constructions[1]` | `C = Point(1, 0)` |
| triangle ABC / 未知頂点 | `constructions[2]` | `A = Point(ax, ay)` |
| M midpoint of AB | `constructions[3]` | `M = Midpoint(A, B)` |
| N midpoint of AC | `constructions[4]` | `N = Midpoint(A, C)` |
| P,Q trisect BC / Bから1/3 | `constructions[5]` | `P = PointOnSegment(B, C, 1/3)` |
| P,Q trisect BC / Bから2/3 | `constructions[6]` | `Q = PointOnSegment(B, C, 2/3)` |
| A,M,N,P,Q lie on a circle / A,P,Qで定義 | `constructions[7]` | `omega = Circumcircle(A, P, Q)` |
| 鏡映による向き固定 / 三角形非退化 | `conditions[0]` | `ay > 0` |
| M on same circle as A,P,Q | `conditions[1]` | `OnCircle(M, omega) = 0` |
| N on same circle as A,P,Q | `conditions[2]` | `OnCircle(N, omega) = 0` |
| Compute area ABC | `target` | `Area(A, B, C)` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。
