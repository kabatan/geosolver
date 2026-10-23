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
