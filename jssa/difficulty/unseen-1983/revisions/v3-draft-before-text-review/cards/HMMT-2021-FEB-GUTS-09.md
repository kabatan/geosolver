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
