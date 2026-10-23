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
