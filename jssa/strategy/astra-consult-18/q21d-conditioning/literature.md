**文献確認記録（2026-10-23）**

書誌と、今回の主張に必要な範囲を分けて確認した。以下の理論を競技幾何の問題群へ適用できることと、その問題群に新しい普遍性があることは別である。

| 文献 | 確認先・範囲 | この調査での位置づけ |
|---|---|---|
| John R. Rice, “A Theory of Condition,” *SIAM Journal on Numerical Analysis* 3(2), 287–310, 1966. DOI 10.1137/0703023 | [出版社](https://epubs.siam.org/doi/10.1137/0703023)で著者・題名・巻号・頁・年を確認。全文はアクセス制限があり**未確認** | 条件数の古典的背景。本文中の特定の定理を確認したとは主張しない。微分の作用素ノルムという定義は、次の全文公開論文の§1でも確認した |
| Mario Arioli, Marc Baboulin, Serge Gratton, “A Partial Condition Number for Linear Least Squares Problems,” *SIAM Journal on Matrix Analysis and Applications* 29(2), 413–433, 2007. DOI 10.1137/050643088 | [著者公開PDF](https://marcbab.github.io/SIMAX.pdf)、冒頭・§1を確認 | 解全体と線形な出力量の条件数を区別し、特異値・特異ベクトルから出力感度を求める先行研究。今回の非線形系の局所線形化に同じ考えを使うことは応用であり、新理論ではない |
| Desmond J. Higham, Nicholas J. Higham, “Backward Error and Condition of Structured Linear Systems,” *SIAM Journal on Matrix Analysis and Applications* 13(1), 162–175, 1992. DOI 10.1137/0613014 | [著者公開PDF](https://webhomes.maths.ed.ac.uk/~dhigham/Publications/P12.pdf)、冒頭・§1・§2前半を確認。[出版社](https://epubs.siam.org/doi/10.1137/0613014)で書誌・要旨も照合 | 許す摂動をパラメータで構造化するという区別は既知。競技幾何の「元の与件を連動して動かす」操作に移す際は、独立入力と実現可能な方向を別途定義する必要がある |
| Ryan N. Gutenkunst, Joshua J. Waterfall, Fergal P. Casey, Kevin S. Brown, Christopher R. Myers, James P. Sethna, “Universally Sloppy Parameter Sensitivities in Systems Biology Models,” *PLoS Computational Biology* 3(10), e189, 2007. DOI 10.1371/journal.pcbi.0030189 | [原論文](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.0030189)の要旨・本文・書誌を確認 | パラメータが不確かでも予測が安定し得るという動機。ただし対象は生物モデル。そこでの経験則を、本件の孤立した幾何解や「問題作者がきれいな数値を選ぶ」仮説の証拠にはしない |
| Mark K. Transtrum, Benjamin B. Machta, James P. Sethna, “Geometry of nonlinear least squares with applications to sloppy models and optimization,” *Physical Review E* 83, 036701, 2011. DOI 10.1103/PhysRevE.83.036701 | [出版社の書誌・要旨](https://journals.aps.org/pre/abstract/10.1103/PhysRevE.83.036701)と[著者プレプリント](https://arxiv.org/abs/1010.1449)を確認。プレプリントの題名には先頭に “The” がある | 最小二乗の地形・パラメータ化・局所の異方性を扱う先行研究。「細い谷があるから難しい」だけでは新しくない。今回、谷の形から大域的な成功率を導く定理は得ていない |

関連する幾何制約の資料として、Bridget M. Dixon・John F. Dannenhoffer III, “Geometric Sketch Constraint Solving with User Feedback” の[著者側公開PDF](https://acdl.mit.edu/esp/Publications/AIAApaper2013-0702.pdf)も確認した。Jacobianを用いた過不足・特異性の扱いが既に幾何制約ソルバーにあることは分かるが、今回の自然入力感度の公式そのものをこの論文の成果として引用しない。会議版と後の版の詳細な対応は未確認なので、ここでは巻号・頁を補っていない。

「競技幾何のきれいな入力は答えの停留点を過剰に選ぶ」「この323問で求値量が弱い方向を系統的に避ける」を既に示した原論文は、今回の検索では確認できなかった。これは新規性の証明ではなく、**未確認**という意味である。候補2・3の広がりを裏付ける先行実証があるかの網羅的調査も未実施。
