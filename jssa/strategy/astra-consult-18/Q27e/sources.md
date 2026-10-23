# 文献の確認範囲（2026-10-23）

検索結果の日付を刊行年に使わず、一次資料の表題・版と本文を確認した。文献が実在すること、定理が適用できること、本件の現象をその定理で説明したことを分ける。

| 一次資料 | 今回確認した範囲 | 本件で言えること／言えないこと |
|---|---|---|
| Jonathan D. Hauenstein, Frank Sottile, **alphaCertified: certifying solutions to polynomial systems**, arXiv:1011.1091v2（2011-09-20）。[本文](https://arxiv.org/html/1011.1091) | Definition 1、Theorem 2、Theorem 4、過剰決定系の注意 | α<0.157671の二次収束保証、α<0.03で半径1/(20γ)の同一根保証を確認。正解点のκだけで本件の時間比やLM成功率を保証する理論ではない。 |
| David H. Bailey, J. M. Borwein, **PSLQ: An Algorithm to Discover Integer Relations**。[著者公開PDF](https://www.davidhbailey.com/dhbpapers/pslq-comp-alg.pdf) | 表紙May 14, 2020、pp.1–2の関係の長さ×係数桁数、単項式ベクトル | 必要精度の尺度を述べる資料。個別入力・実装の正確な閾値や人間難度の逆転は保証しない。2009年の同題記録と、今回読んだ2020年付PDFを混同しない。 |
| Helaman R. P. Ferguson, David H. Bailey, **A Polynomial Time, Numerically Stable Integer Relation Algorithm**, RNR Technical Report RNR-91-032、July 14, 1992。[著者公開PDF](https://www.davidhbailey.com/dhbpapers/pslq.pdf) | 表紙、要旨、導入の最小多項式同定の説明 | 整数関係検出と数値から代数式の同定が既知の別段階であること。今回の実装・候補全体を認証したものではない。 |
| Helaman R. P. Ferguson, David H. Bailey, Steve Arno, **Analysis of PSLQ, an Integer Relation Finding Algorithm**, Mathematics of Computation 68(225), 351–369（1999）。[出版社PDF](https://www.ams.org/mcom/1999-68-225/S0025-5718-99-00995-3/S0025-5718-99-00995-3.pdf) | 検索収録の表題・著者・書誌・要旨。直接取得は403 | 本文詳細は**未確認**。本件の精度の定数や厳密下界の根拠には使わない。 |
| Ryan Krueger, Jesse Michael Han, Daniel Selsam, **Automatically Building Diagrams for Olympiad Geometry Problems**, arXiv:2012.02590v2（2021-05-01）。[本文](https://arxiv.org/html/2012.02590v2) | 要旨、§3、§4–5 | パラメータ化・直接計算・最適化する制約を分ける既存設計を確認。図生成と求値は同じ課題ではない。論文の成功率を今回の136検査行や131問のhumanへ転用しない。 |
| Mucong Dingほか、**Easy2Hard-Bench: Standardized Difficulty Labels for Profiling LLM Performance and Generalization**, arXiv:2409.18433v1（2024-09-27）。[本文](https://arxiv.org/html/2409.18433v1) | §3.1、Appendix D.1–D.2 | 正答統計とIRTに基づくdifficulty ratingの意味を確認。本人の解答時間や直感の実験ではない。今回のCSVとの同一性は既存Eのsource-join監査も参照した。 |

Kannan–Lenstra–Lovászの代数数復元定理については、Q21bに一次資料の書誌・確認記録があることは確認したが、今回その原論文を再読して本実装への定量適用を検証していない。従って本文では適用の細部を**未確認**とした。理論名だけで今回の候補を有望にしていない。

今回の逆転について新規性を支える先行研究の不存在は確認できていない。検索で見つからないことを新規性の証拠としていない。
