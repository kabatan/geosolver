# HMMT-2022-FEB-GEO-07 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2022-geo-problems.txt` / saved_pdf_text / row_idx=7
- 原文表記: PDF第1ページ画像を目視し、抽出で崩れた根号・分数をASCII表記で転記。raw_excerptも保持。
- 原文SHA-256: `d8a8dfbf740166536807bb3f2ce312ea5f842342c76827ae21c56062f885394c`
- 入力SHA-256（JSONファイルの全bytes）: `243b7dec3e96f2a9eed6ba61a8246b4ed9cec9257a71c9bce2a20e42da15ac84`
- 座標固定・同値性: A=(0,0), B=(10,0), 正方形を上側。合同移動のみ。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Point P is located inside a square ABCD of side length 10. Let O1, O2, O3, O4 be the circumcenters of PAB, PBC, PCD, and PDA, respectively. Given that PA + PB + PC + PD = 23 sqrt(2) and the area of O1O2O3O4 is 50, the second largest of the lengths O1O2, O2O3, O3O4, O4O1 can be written as sqrt(a/b), where a and b are relatively prime positive integers. Compute 100a + b.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| square ABCD of side 10 | `constructions[0]` | `A = Point(0, 0)` |
| square ABCD of side 10 | `constructions[1]` | `B = Point(10, 0)` |
| square ABCD of side 10 | `constructions[2]` | `C = Point(10, 10)` |
| square ABCD of side 10 | `constructions[3]` | `D = Point(0, 10)` |
| P inside square | `constructions[4]` | `P = Point(x, y)` |
| circumcenter of PAB | `constructions[5]` | `O1 = Circumcenter(P, A, B)` |
| circumcenter of PBC | `constructions[6]` | `O2 = Circumcenter(P, B, C)` |
| circumcenter of PCD | `constructions[7]` | `O3 = Circumcenter(P, C, D)` |
| circumcenter of PDA | `constructions[8]` | `O4 = Circumcenter(P, D, A)` |
| P strictly inside square | `conditions[0]` | `x > 0` |
| P strictly inside square | `conditions[1]` | `x < 10` |
| P strictly inside square | `conditions[2]` | `y > 0` |
| P strictly inside square | `conditions[3]` | `y < 10` |
| PA+PB+PC+PD = 23 sqrt(2) | `conditions[4]` | `Distance(P,A)+Distance(P,B)+Distance(P,C)+Distance(P,D) = 23*sqrt(2)` |
| area O1O2O3O4 = 50 | `conditions[5]` | `Area(O1, O2, O3, O4) = 50` |
| second largest length is sqrt(a/b) / 全6組のminのmaxが2番目に大きい値 | `conditions[6]` | `(max([min(Distance(O1, O2), Distance(O2, O3)), min(Distance(O1, O2), Distance(O3, O4)), min(Distance(O1, O2), Distance(O4, O1)), min(Distance(O2, O3), Distance(O3, O4)), min(Distance(O2, O3), Distance(O4, O1)), min(Distance(O3, O4), Distance(O4, O1))]))**2 = a/b` |
| a,bは正整数、h,kは既約性の整数証人 | `conditions[7]` | `IsInteger(a) = 0` |
| a,bは正整数、h,kは既約性の整数証人 | `conditions[8]` | `IsInteger(b) = 0` |
| a,bは正整数、h,kは既約性の整数証人 | `conditions[9]` | `IsInteger(h) = 0` |
| a,bは正整数、h,kは既約性の整数証人 | `conditions[10]` | `IsInteger(k) = 0` |
| positive integer numerator | `conditions[11]` | `a > 0` |
| positive integer denominator | `conditions[12]` | `b > 0` |
| a,b are relatively prime / Bezoutの同値な定義的条件 | `conditions[13]` | `h*a+k*b = 1` |
| Compute 100a+b | `target` | `100*a+b` |

## 残る制約

整数補助変数は既約分数という原問の出力指定を保持するため。探索しやすさでは採否を決めない。PDF画像で根号と分数を確認。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。
