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
