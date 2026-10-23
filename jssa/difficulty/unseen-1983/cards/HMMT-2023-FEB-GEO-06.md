# HMMT-2023-FEB-GEO-06 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2023-geo-problems.txt` / saved_pdf_text / row_idx=6
- 原文SHA-256: `23a1336c0aefdd57ecf374165ad56c3cf0fef07a99b0d33c0e3f3576408469b3`
- 入力SHA-256（JSONファイルの全bytes）: `b878de21b4753343976d47a908b007e1af0de8bcd0a1974bba8f5a88c42aa76b`
- 座標固定・同値性: 絶対長の指定がなく目標が角度なのでAB=1に相似正規化。凸四角形を反時計回りに鏡映。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Convex quadrilateral ABCD satisfies ∠CAB = ∠ADB = 30◦ , ∠ABD = 77◦ , BC = CD, and
    ∠BCD = n◦ for some positive integer n. Compute n.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| convex quadrilateral ABCD / 座標原点 | `constructions[0]` | `A = Point(0, 0)` |
| ABを相似正規化 | `constructions[1]` | `B = Point(1, 0)` |
| convex quadrilateral ABCD / 未知点 | `constructions[2]` | `C = Point(cx, cy)` |
| convex quadrilateral ABCD / 未知点 | `constructions[3]` | `D = Point(dx, dy)` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[0]` | `((B.x-A.x)*(C.y-A.y)-(B.y-A.y)*(C.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[1]` | `((B.x-A.x)*(D.y-A.y)-(B.y-A.y)*(D.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[2]` | `((C.x-B.x)*(A.y-B.y)-(C.y-B.y)*(A.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[3]` | `((C.x-B.x)*(D.y-B.y)-(C.y-B.y)*(D.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[4]` | `((D.x-C.x)*(A.y-C.y)-(D.y-C.y)*(A.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[5]` | `((D.x-C.x)*(B.y-C.y)-(D.y-C.y)*(B.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[6]` | `((A.x-D.x)*(B.y-D.y)-(A.y-D.y)*(B.x-D.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[7]` | `((A.x-D.x)*(C.y-D.y)-(A.y-D.y)*(C.x-D.x)) > 0` |
| angle CAB = 30 degrees | `conditions[8]` | `Angle(C, A, B) = 30*pi/180` |
| angle ADB = 30 degrees | `conditions[9]` | `Angle(A, D, B) = 30*pi/180` |
| angle ABD = 77 degrees | `conditions[10]` | `Angle(A, B, D) = 77*pi/180` |
| BC = CD | `conditions[11]` | `Distance(B, C) = Distance(C, D)` |
| angle BCD = n degrees | `conditions[12]` | `Angle(B, C, D) = n*pi/180` |
| n is an integer | `conditions[13]` | `IsInteger(n) = 0` |
| n is positive | `conditions[14]` | `n > 0` |
| Compute n | `target` | `n` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。
