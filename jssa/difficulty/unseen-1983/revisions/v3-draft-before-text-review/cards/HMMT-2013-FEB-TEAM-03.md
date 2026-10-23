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
