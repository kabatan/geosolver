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
