**Q21b 文献・既存資料の確認記録（2026-10-23）**

本文の理論は以下の一次資料と、対象版の実コードに限定した。検索結果の掲載日・クロール日は論文の刊行年に使っていない。

| 資料 | 確認できた範囲 | 本報告で使う内容・留保 |
|---|---|---|
| R. Kannan, A. K. Lenstra, L. Lovász, “Polynomial Factorization and Nonrandomness of Bits of Algebraic and Some Transcendental Numbers,” Mathematics of Computation 50(181), 235–250 (1988). [論文スキャン](https://www.math.cmu.edu/users/af1p/Teaching/AdditiveCombinatorics/LLLL.pdf) | 論文本文の抽出テキスト、表紙書誌、命題1.6、定理1.19、逆数への変換1.18を確認。161ページの合冊PDFのうち、この論文はPDFの0始まり6–21ページ、定理1.19は12ページ（誌面241）。スクリーンショット取得は一部失敗。 | 次数・高さの上界が既知の場合の格子法による復元の十分条件、非零多項式値の分離。現実装のPSLQの個別の必要桁数を保証する定理とは扱わない。 |
| H. R. P. Ferguson, D. H. Bailey, S. Arno, “Analysis of PSLQ, an Integer Relation Finding Algorithm,” Mathematics of Computation 68(225), 351–369 (1999), DOI: 10.1090/S0025-5718-99-00995-3. [出版社PDF](https://www.ams.org/mcom/1999-68-225/S0025-5718-99-00995-3/S0025-5718-99-00995-3.pdf) | AMSの検索収録本文の冒頭で書誌・著者・要旨を確認。PDF直接取得は403。関連する[NASA 1996年技術報告](https://www.nas.nasa.gov/assets/nas/pdf/techreports/1996/nas-96-005.pdf)も確認したが本文OCRが不十分。 | PSLQの原研究として記載。1999年版の全文・定理の細部は未確認。本報告の精度定数の根拠にはしていない。 |
| D. H. Bailey, J. M. Borwein, “PSLQ: An Algorithm to Discover Integer Relations.” [著者公開PDF](https://www.davidhbailey.com/dhbpapers/pslq-comp-alg.pdf) | 表紙の日付May 14, 2020、pp.1–2の入力精度の説明と単項式ベクトルを確認。 | 関係の長さ×最大係数の十進桁数という実用上の目安。[2009年の同題の公開記録](https://escholarship.org/uc/item/95p4255b)と版の日付を混同せず、ここでは確認した2020年付PDFとして引用。個々の数の厳密な情報論的下界とはしない。 |
| mpmath 1.3.0, Number identification. [公式ドキュメント](https://www.mpmath.org/doc/current/identification.html)、[公式PDF](https://mpmath.org/doc/current/mpmath.pdf) | 公式ページの検索収録本文と、使用環境のmpmath 1.3.0の`identification.py`を確認。HTML直接取得は一部403。 | `maxcoeff`の厳密な不等号、`tol`、段階的な次数探索。既定tolの説明と、本solverが上書きするtolを区別。 |
| S. Landau, “Simplification of Nested Radicals,” SIAM Journal on Computing 21(1), 85–110 (1992), DOI: 10.1137/0221009. [著者の業績一覧](https://privacyink.org/pdf/)、[出版社](https://doi.org/10.1137/0221009) | 著者の一覧で題名・年・巻・ページ・出版社リンクを確認。出版社書誌も検索確認。本文の定理・計算量の詳細は未確認。 | 根号の入れ子の解消が既存の記号計算研究であることのみ。本文の二つの平方根の例は直接計算で説明し、この論文の未確認の定理に依存しない。 |

**既存資料との重複を避けるための確認**

`jssa/strategy/codex-tasks-1023.md`の方針転換・Q20・追加判定基準・Q21と、`codex-session-01a1171a-summary.md`を出発点とした。相談16・17、本文v10、補足v10、astra-consult-17のG〜L・Q6〜Q10・Q12、Q3の実成果物`jssa/difficulty/wall-diagnostic/answer.md`、Q4の`jssa/difficulty/multiplicity/answer.md`、Q11の`jssa/difficulty/certify-all/answer.md`を参照した。指定のQ3〜Q5・Q11が全てastra-consult-17直下にあるわけではない。Q5の予定先`jssa/difficulty/full-solver-nohard/answer.md`は見つからず、結果を推測して使っていない。

特に、補足v10のS1.6に既に精度目安と許容値の注意、S2.7に次数189/117/2/8問と最大約43桁の表がある。今回の次数集計は既存`answer-poly.csv`と全件一致した。この再集計を新発見として数えない。壁・許容条件・退化・証明書・事前診断の既存候補の名称を変えた案も採用していない。

今回追加したものは、固定した桁数格子での同定の直接測定、保存値の有理シフト対照、係数上限の非単調性の追加診断、人間難度の大会別分布比較である。いずれも本研究の新しい中心成果に足りるとは判定しなかった。
