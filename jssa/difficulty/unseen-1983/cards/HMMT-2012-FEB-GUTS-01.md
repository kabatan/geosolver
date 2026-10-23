# HMMT-2012-FEB-GUTS-01 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=354
- 原文SHA-256: `c7a5746a659875dcf675ed3dae29cc6009e6d890bb40f749435b5a50b939f3de`
- 入力SHA-256（JSONファイルの全bytes）: `313cfb118f2e6a515463eb234419a3c10a3ff79fadc9f812120e7bee9b40e227`
- 座標固定・同値性: Aを原点、ABを正のx軸、正方形を上側。平行移動・回転・鏡映だけ。尺度2を保持。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Square $A B C D$ has side length 2 , and $X$ is a point outside the square such that $A X=X B=\sqrt{2}$. What is the length of the longest diagonal of pentagon $A X B C D$ ?

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| square ABCD, side 2 / 座標原点 | `constructions[0]` | `A = Point(0, 0)` |
| square ABCD, side 2 | `constructions[1]` | `B = Point(2, 0)` |
| square ABCD, side 2 | `constructions[2]` | `C = Point(2, 2)` |
| square ABCD, side 2 | `constructions[3]` | `D = Point(0, 2)` |
| X is outside the square / 未知点 | `constructions[4]` | `X = Point(x, y)` |
| AX = sqrt(2) | `conditions[0]` | `Distance(A, X) = sqrt(2)` |
| XB = sqrt(2) | `conditions[1]` | `Distance(X, B) = sqrt(2)` |
| X outside square / 正方形の閉領域の外 | `conditions[2]` | `(x < 0) or (x > 2) or (y < 0) or (y > 2)` |
| longest diagonal of AXBCD / 頂点順から得る全5本の対角線の最大値 | `target` | `max([Distance(A, B), Distance(A, C), Distance(X, C), Distance(X, D), Distance(B, D)])` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。
