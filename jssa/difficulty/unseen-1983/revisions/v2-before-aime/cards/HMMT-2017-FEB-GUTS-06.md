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
