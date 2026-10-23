# HMMT-2016-FEB-GUTS-03 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=317
- 原文SHA-256: `e1ec215f55fea15321ed2b0ac7b8cce58d47d08e665a49ab9ab06d85d42225dc`
- 入力SHA-256（JSONファイルの全bytes）: `d1fb9bf24c8b4e78a6942569cabce083a685e37b5d646c5b7478d8ebce09e0b7`
- 座標固定・同値性: 円の中心を原点、P=(1,0)。鏡映で頂点を反時計回り。半径1は原文。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $P R O B L E M Z$ be a regular octagon inscribed in a circle of unit radius. Diagonals $M R, O Z$ meet at $I$. Compute $L I$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[0]` | `P = Point(cos(0*pi/4), sin(0*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[1]` | `R = Point(cos(1*pi/4), sin(1*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[2]` | `O = Point(cos(2*pi/4), sin(2*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[3]` | `B = Point(cos(3*pi/4), sin(3*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[4]` | `L = Point(cos(4*pi/4), sin(4*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[5]` | `E = Point(cos(5*pi/4), sin(5*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[6]` | `M = Point(cos(6*pi/4), sin(6*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[7]` | `Z = Point(cos(7*pi/4), sin(7*pi/4))` |
| diagonals MR and OZ meet at I | `constructions[8]` | `I = Intersect(Line(M, R), Line(O, Z))` |
| Compute LI | `target` | `Distance(L, I)` |

## 残る制約

変数0も選定から除かない。頂点は正八角形の定義であって、解答の座標ではない。文字Oは頂点。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。
