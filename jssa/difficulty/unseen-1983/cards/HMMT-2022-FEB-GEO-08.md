# HMMT-2022-FEB-GEO-08 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2022-geo-problems.txt` / saved_pdf_text / row_idx=8
- 原文SHA-256: `9239d35d4984e1860bd60e38ec3cf8eecf2093151d5f70ade74e5b48e290ad4a`
- 入力SHA-256（JSONファイルの全bytes）: `044153464a2f3a8ac6eb0310f7b741815cee84f0f026b672229f7f07d804e078`
- 座標固定・同値性: 楕円の中心を原点、長軸をx軸、Aを負側。合同移動と鏡映のみ。長短軸の指定50,14を保持。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let E be an ellipse with foci A and B. Suppose there exists a parabola P such that
      • P passes through A and B,
      • the focus F of P lies on E,
      • the orthocenter H of △F AB lies on the directrix of P.
    If the major and minor axes of E have lengths 50 and 14, respectively, compute AH 2 + BH 2 .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| ellipse focus A / 対称中心を原点 | `constructions[0]` | `A = Point(-f, 0)` |
| ellipse focus B | `constructions[1]` | `B = Point(f, 0)` |
| minor axis length 14 / 短軸端点を定義 | `constructions[2]` | `T = Point(0, 7)` |
| focus F of parabola lies on ellipse | `constructions[3]` | `F = Point(fx, fy)` |
| orthocenter H of FAB | `constructions[4]` | `H = Orthocenter(F, A, B)` |
| directrix through H / 未知方向 | `constructions[5]` | `W = Point(H.x+dx, H.y+dy)` |
| H lies on the directrix | `constructions[6]` | `line_d = Line(H, W)` |
| distance from A to directrix | `constructions[7]` | `U = FootOfPerpendicular(A, line_d)` |
| distance from B to directrix | `constructions[8]` | `V = FootOfPerpendicular(B, line_d)` |
| nondegenerate parabola / focus not on directrix | `constructions[9]` | `K = FootOfPerpendicular(F, line_d)` |
| ellipse with major 50 and minor 14 has distinct foci | `conditions[0]` | `f > 0` |
| ellipse definition: distances from short-axis endpoint sum to major-axis length | `conditions[1]` | `Distance(T, A)+Distance(T, B) = 50` |
| F lies on ellipse with foci A,B and major axis 50 | `conditions[2]` | `Distance(F, A)+Distance(F, B) = 50` |
| triangle FAB nondegenerate / 鏡映でFを上側 | `conditions[3]` | `fy > 0` |
| directrix direction is normalized / 表示だけの冗長な尺度を除く | `conditions[4]` | `dx**2+dy**2 = 1` |
| parabola passes through A / 焦点と準線への等距離という定義 | `conditions[5]` | `Distance(A, F) = Distance(A, U)` |
| parabola passes through B | `conditions[6]` | `Distance(B, F) = Distance(B, V)` |
| focus is not on directrix / proper parabola | `conditions[7]` | `Distance(F, K) > 0` |
| Compute AH^2+BH^2 | `target` | `Distance(A, H)**2+Distance(B, H)**2` |

## 残る制約

楕円・放物線の焦点/準線の定義で記述し、解答由来の焦点距離やF,Hの座標は使わない。PDF両ページで原文確認。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。
