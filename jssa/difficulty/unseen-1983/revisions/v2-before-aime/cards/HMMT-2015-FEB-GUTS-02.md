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
