# 確認した文献

確認日：2026-10-23。書誌・本文・要旨の確認範囲を分ける。検索で見つかったことだけを全文確認としない。以下の文献はいずれも今回の20組の人間難度を測定していない。

| 文献 | 確認できた範囲 | 今回使った点／使わない点 |
|---|---|---|
| Warstadt, A., et al. (2020). **BLiMP: The Benchmark of Linguistic Minimal Pairs for English.** Transactions of the Association for Computational Linguistics, 8, 377–392. DOI: 10.1162/tacl_a_00321. [ACL一次資料](https://aclanthology.org/2020.tacl-1.25/) | ACLの書誌、要旨、公開論文を確認 | 一つの言語的操作を隔離する対と、人間による検証という方法。言語的許容性の検査を幾何の難度尺度へそのまま移さない |
| Kotovsky, K., Hayes, J. R., & Simon, H. A. (1985). **Why Are Some Problems Hard? Evidence from Tower of Hanoi.** Cognitive Psychology, 17, 248–294. [CMU所蔵の一次資料](https://iiif.library.cmu.edu/file/Simon_box00068_fld05213_bdl0001_doc0001/Simon_box00068_fld05213_bdl0001_doc0001.pdf) | 書誌と検索索引に現れたPDF冒頭の要旨を確認。PDFの直接取得は失敗し、全文は未確認 | 同型課題の表現差を比較する心理学の先例。具体的な実験効果量や本人工問題への転用はしない |
| Koedinger, K. R., & Anderson, J. R. (1990). **Abstract Planning and Perceptual Chunks: Elements of Expertise in Geometry.** Cognitive Science, 14(4), 511–550. DOI: 10.1207/s15516709cog1404_2. [出版社](https://onlinelibrary.wiley.com/doi/10.1207/s15516709cog1404_2)、[著者公開PDF](https://pact.cs.cmu.edu/koedinger/pubs/koedinger_and_anderson_90.pdf) | 出版社の書誌・要旨、著者PDFの検索表示の冒頭を確認。PDF直読は502で、全文は未確認 | 人間の熟達と解法選択への注意。H01〜H10の「大きな難化」の証拠にはしない |
| Beck, A., Stoica, P., & Li, J. (2008). **Exact and Approximate Solutions of Source Localization Problems.** IEEE Transactions on Signal Processing, 56(5), 1770–1778. DOI: 10.1109/TSP.2007.909342. [著者公開本文](https://www.tau.ac.il/~becka/SLfinal.pdf)、[大学書誌](https://cris.tau.ac.il/en/publications/exact-and-approximate-solutions-of-source-localization-problems/) | 9ページの著者公開本文を開き、要旨・§I・§IIのrange/squared-range LSの定式化と扱いを確認。大学書誌も照合 | 距離と二乗距離のLSが異なること、非凸性、二乗距離LSに対する大域的な扱いの先行研究。今回の特定の無雑音四次式やpの数値が同論文の結果だとはしない |
| Hsu, H.-Y., & Silver, E. A. (2026; online 2025-11-17). **Cognitive complexity of geometric proof and geometric calculation: a problem-solving perspective.** Educational Studies in Mathematics, 121, 29–50. DOI: 10.1007/s10649-025-10434-9. [出版社一次資料](https://link.springer.com/article/10.1007/s10649-025-10434-9) | 出版社の書誌・公開要旨・導入の表示を確認。全文の精読は未実施 | 図・解答段階などの複雑さと課題種別を区別する根拠。台湾の中学生の結果を競技専門家や新しい20組へ外挿しない |
| **SciPy 1.18.0, least_squares documentation.** [公式文書](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html) | method、max_nfev、nfev、Notesを確認。実行環境も1.18.0 | LMのm<n制限、max_nfev/nfevが数値Jacobian用呼び出しを含まないこと。局所探索の結果を一般の大域最適化保証と取り違えない |

数式・解析解は[theory.md](theory.md)と[prepare.py](prepare.py)に独立に記した。Euler/Feuerbachという名前だけを根拠に人間の解答時間を推定していない。GeoGebraによる同一20組の実行、厳密な大域ソルバの実行、全20組に対応した人間実験は未実施。
