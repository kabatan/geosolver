# HMMT-2022-FEB-GUTS-01 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=1167
- 原文SHA-256: `51f385517d2f1f8955901a22faa1d8bc1024ed5ff6cac93de531bde2c52f98a2`
- 入力SHA-256（JSONファイルの全bytes）: `245ebd5d0cb564e7a429242f303e3ad0f92a8fc4b1da4ddb0d16cd6b6c37faba`
- 座標固定・同値性: 中心原点、Pを正x軸。鏡映で隣頂点を上側。絶対周長6.28は有理数157/25で保持。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

A regular 2022-gon has perimeter 6.28. To the nearest positive integer, compute the area of the 2022-gon.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| regular 2022-gon / 中心 | `constructions[0]` | `O = Point(0, 0)` |
| regular 2022-gon / 一頂点 | `constructions[1]` | `P = Point(r, 0)` |
| regular 2022-gon / 隣の頂点、中心角の定義 | `constructions[2]` | `Q = Point(r*cos(2*pi/2022), r*sin(2*pi/2022))` |
| positive circumradius | `conditions[0]` | `r > 0` |
| perimeter 6.28 / 同長の2022辺の和 | `conditions[1]` | `2022*Distance(P, Q) = 157/25` |
| area to nearest positive integer / 中心から2022枚に分割して面積を加算 | `target` | `(2022*Area(O, P, Q)+1/2) // 1` |

## 残る制約

2022個の等しい中心三角形という正多角形の定義的分割。最適化や解答由来の式は使わない。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。
