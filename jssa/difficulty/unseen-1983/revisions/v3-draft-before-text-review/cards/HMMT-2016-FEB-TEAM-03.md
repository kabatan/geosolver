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
