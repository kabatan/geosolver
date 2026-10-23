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
