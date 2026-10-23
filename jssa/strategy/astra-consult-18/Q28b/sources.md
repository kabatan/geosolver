Q28b：文献と既存資料の確認範囲（2026-10-23）

**原文を確認した文献**

1. E. Kostlan, *On the Distribution of Roots of Random Polynomials*, in *From Topology to Computation: Proceedings of the Smalefest*, 1993, pp. 419–431。書誌は[著者の掲載ページ](https://developmentserver.com/randompolynomials/odrrp)、本文は[著者公開PDF](https://developmentserver.com/randompolynomials/odrrp/paper.pdf)。確認箇所：Theorem 3.3、Corollary 3.4、§4 の分布の定義、Theorems 4.2・4.5。独立性と係数分散が重要で、実数の場合は直交不変性だけでは分布を一意に定めない。

2. A. Edelman and E. Kostlan, *How many zeros of a random polynomial are real?*, *Bulletin of the American Mathematical Society* 32 (1995), 1–37。[arXiv の書誌](https://arxiv.org/abs/math/9501224)、[著者公開PDF](https://math.mit.edu/~edelman/publications/how_many_zeros.pdf)。PDF は1994-07-23付の版で35ページ。確認箇所：§1、Theorem 3.1、§3.1.2、Theorem 7.1、§7.2。異なる次数の平方根則は §7.2 が Shub–Smale の結果として明記している。

3. D. Armentano, J.-M. Azaïs and J. R. León, *On a general Kac-Rice formula for the measure of a level set*, arXiv:2304.07424v3（2023-12-05）。[原文HTML](https://arxiv.org/html/2304.07424v3)。確認箇所：Theorems 2.1・2.2、式(2.9)、§7 の重み付き版の条件。非 Gaussian の拡張と、零点数の式に Jacobian の絶対行列式が入ることを確認した。正式刊行は *Annals of Applied Probability* 35(3), 1828–1851 (2025), DOI 10.1214/25-AAP2158 と[学会の号PDFの書誌表示](https://www.imstat.org/publications/aap/aap_35_3/aap_35_3.pdf)でも確認できるが、本ノートで確認した定理番号は arXiv v3 のもの。

**確認を限定した文献**

- M. Shub and S. Smale, *Complexity of Bézout’s theorem. II. Volumes and probabilities*, *Computational Algebraic Geometry*, Progress in Mathematics 109 (1993), 267–285。[著者の論文一覧](https://sites.google.com/site/shubmichael/publications)で書誌を確認。同一覧のPDFリンクは取得できず、**原論文本文・定理番号は未確認**。平方根則は上の Edelman–Kostlan の原文による照合であり、Shub–Smale本文を読んだとはしない。
- J.-M. Azaïs and M. Wschebor, *A self contained proof of the Rice formula for random fields*, 2006-12-22付。[著者PDF](https://www.math.univ-toulouse.fr/~azais/styles/other/preprint/completeproof.pdf)は検索結果で表紙・概要まで確認できたが、本文取得は403で失敗。**重みの定理の詳細は未確認**。根拠はこの文献に依存させず、上の取得できた Armentano–Azaïs–León を用いた。検索エンジンの収集日を出版年とは扱っていない。

**指定された既存資料**

- [23:25の方針・Q28](../../codex-tasks-1023.md)：4基準と早期打切り。
- [本人の面白さの基準](../../codex-session-01a1171a-summary.md)：既知現象、紙上での先取り、solver の観測器化は不可。
- [本文v10](../../../draft/report-draft-v10.md)、[補足v10](../../../draft/supplement-v10.md)：局所 p と完成 solver の違い、精密化・PSLQ、正次元系と代数化の留保。
- [q20a](../q20a-algebraic/answer.md)：配置数から吸引域の測度は決まらない。既知のモノドロミーで検証に成功しても solver 固有の能力にはならない。
- [q21c](../q21c-complexity/answer.md)：解の存在・作図可能性等だけでは容易なクラスや分布を特定できない。
- [q21e](../q21e-phase-transition/answer.md)：planted 人工距離系と競技系を同じ相図へ載せる橋渡しがなく、普通の最小二乗でも得られる。
- [q21f](../q21f-homotopy/answer.md)：経路数・実根数・配置数・成功率は別。順位逆転の実例だけでは新しい機構にならない。

今回は上記資料の既存数値を背景として読み、新しい raw 再集計はしていない。封印tarと unseen-1983 の solver 結果は参照していない。
