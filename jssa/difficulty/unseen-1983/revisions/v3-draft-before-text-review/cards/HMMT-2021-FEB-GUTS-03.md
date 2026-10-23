# HMMT-2021-FEB-GUTS-03 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=2382
- 原文SHA-256: `c98b18c4b323e70ab9011f2149c5b0ed95e7e7a108adc0cfcdb64cf52dfc18ee`
- 入力SHA-256（JSONファイルの全bytes）: `d3b5dc0fb2f2d5822e45c8fabb253d8041ced67d2c4bfc21d6811f28da15cd53`
- 座標固定・同値性: O原点、OAを正x軸、半円を鏡映で上側。半径2021は保持。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

A semicircle with radius 2021 has diameter $A B$ and center $O$. Points $C$ and $D$ lie on the semicircle such that $\angle A O C<\angle A O D=90^{\circ}$. A circle of radius $r$ is inscribed in the sector bounded by $O A$ and $O C$ and is tangent to the semicircle at $E$. If $C D=C E$, compute $\lfloor r\rfloor$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| center O | `constructions[0]` | `O = Point(0, 0)` |
| radius 2021 / OAを正x軸 | `constructions[1]` | `A = Point(2021, 0)` |
| diameter AB | `constructions[2]` | `B = Point(-2021, 0)` |
| angle AOD = 90 degrees | `constructions[3]` | `D = Point(0, 2021)` |
| C on semicircle / 未知点 | `constructions[4]` | `C = Point(cx, cy)` |
| center of the inscribed circle / 補助未知点 | `constructions[5]` | `J = Point(jx, jy)` |
| circle of radius r inscribed in sector AOC | `constructions[6]` | `small = Circle(J, r)` |
| internal tangency E / 中心線OJ上の大円との接点 | `constructions[7]` | `E = Point(2021*jx/Distance(O, J), 2021*jy/Distance(O, J))` |
| C on semicircle radius 2021 | `conditions[0]` | `Distance(O, C) = 2021` |
| angle AOC < 90 degrees | `conditions[1]` | `cx > 0` |
| nondegenerate sector on chosen upper semicircle | `conditions[2]` | `cy > 0` |
| positive radius of inscribed circle | `conditions[3]` | `r > 0` |
| tangency to ray OA / 垂足が正の半直線上 | `conditions[4]` | `jx > 0` |
| tangent to OA from inside sector / 上半平面 | `conditions[5]` | `jy = r` |
| tangent to OC from sector interior / 内向き符号付き距離 | `conditions[6]` | `cy*jx-cx*jy = 2021*r` |
| internal tangency to semicircle | `conditions[7]` | `Distance(O, J) + r = 2021` |
| unique tangency point E is defined | `conditions[8]` | `Distance(O, J) > 0` |
| CD = CE | `conditions[9]` | `Distance(C, D) = Distance(C, E)` |
| Compute floor(r) | `target` | `r // 1` |

## 残る制約

接円の二つの線への接条件と内接接条件は原文の定義。rの解を導いていない。床関数は目標だけ。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。
