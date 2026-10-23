# Q7 文献一覧・確認範囲

調査日：2026-10-23。[結論と分析](answer.md)、[検索記録](search-log.md)。以下の「本文確認」は記載した箇所を読んだことを意味し、全論文の全証明を検証したという意味ではない。書誌だけ確認できた資料は末尾で区別する。

## R1　Progressive barrierの直接の先行記述

Charles Audet, J. E. Dennis Jr. (2009), **A Progressive Barrier for Derivative-Free Nonlinear Programming**, *SIAM Journal on Optimization* 20(1), 445–472. DOI: [10.1137/070692662](https://doi.org/10.1137/070692662)。[出版社](https://epubs.siam.org/doi/10.1137/070692662)、[GERADの対応記録](https://www.gerad.ca/en/papers/G-2007-37)。

- 本文確認：2007-06-26付著者稿 **A MADS algorithm with a progressive barrier for derivative-free nonlinear programming** の[PDF](https://www.researchgate.net/profile/J-Dennis/publication/228700465_A_mads_algorithm_with_a_progressive_barrier_for_derivative-free_nonlinear_programming/links/09e4150ca73980221b000000/A-mads-algorithm-with-a-progressive-barrier-for-derivative-free-nonlinear-programming.pdf)。§1、特に印刷p.3＝PDF第4ページの動機、§2.1の違反量とbarrier、§4.2の実験。
- 限界：結論に用いた動機の文章が2009年出版版でも逐語的に同じかは**未確認**。著者稿と出版書誌の対応は機関記録で確認した。

## R2　許容・非許容開始を扱うMADSのglobalization

Charles Audet, J. E. Dennis Jr., Sébastien Le Digabel (2010), **Globalization strategies for Mesh Adaptive Direct Search**, *Computational Optimization and Applications* 46(2), 193–215. DOI: [10.1007/s10589-009-9266-1](https://doi.org/10.1007/s10589-009-9266-1)。オンライン公開は2009年。[出版社](https://link.springer.com/article/10.1007/s10589-009-9266-1)。

- 本文確認：[著者公開の全文](https://www.researchgate.net/publication/225982893_Globalization_strategies_for_Mesh_Adaptive_Direct_Search)の§1、§5の導入、§5.1–5.3、§5.4冒頭。緩和可能性の区別と開始条件別の比較を読んだ。
- 限界：幾何求値LMの実験ではない。PBの一律優越を示す資料として使っていない。

## R3　非許容試行の拒否と早期収束

Ceres Solver, **Modeling FAQs**, version 2.2.0。[公式リポジトリの版固定ソース](https://raw.githubusercontent.com/ceres-solver/ceres-solver/2.2.0/docs/source/modeling_faqs.rst)。

- 確認箇所：不等式の質問、L50–63付近。`return false`による方法とその注意。
- 限界：論文ではなく公式技術文書。評価失敗と本件の有限段差penaltyは同一ではない。

## R4／R4b　LMの受理・停止の一次資料

MINPACK, **`lmder.f`**。[Netlib公開ソース](https://netlib.org/minpack/lmder.f)。SciPy, **`scipy.optimize.least_squares`**、確認時の文書版1.18.0。[公式仕様](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html)。

- 確認箇所：`lmder.f`の列尺度・正規化勾配、実減少・予測減少・ratio、trust region更新、受理点更新、指定許容誤差と機械精度による終了判定。SciPyの`method='lm'`、`ftol`、`xtol`、`gtol`、`jac`、`x_scale`の説明。
- 限界：実行されたSciPy nativeバイナリに対応するCソースとの逐行同一性は、本担当では**未確認**。Gのイベント記録と公開アルゴリズムに整合する機構として記述した。

## R5　制約を部分問題に含めるLM

Naoki Marumo, Takayuki Okuno, Akiko Takeda (2023), **Majorization-minimization-based Levenberg–Marquardt method for constrained nonlinear least squares**, *Computational Optimization and Applications* 84, 833–874. DOI: [10.1007/s10589-022-00447-y](https://doi.org/10.1007/s10589-022-00447-y)。[出版社全文](https://link.springer.com/article/10.1007/s10589-022-00447-y)。

- 本文確認：§1の問題(1)・モデル(2)・部分問題(3)、§1.1、Assumption 1とその周辺。閉凸集合、残差の滑らかさ、収束主張の前提を確認。
- 限界：任意の非凸・不連続な幾何条件にそのまま適用できる結果ではない。

## R6　非滑らかな正則化を扱うLM

Aleksandr Y. Aravkin, Robert Baraldi, Dominique Orban (2023), **A Levenberg-Marquardt Method for Nonsmooth Regularized Least Squares**, arXiv:2301.02347v1。[書誌](https://arxiv.org/abs/2301.02347)、[版指定本文](https://arxiv.org/html/2301.02347v1)。

- 本文確認：§1–2の問題・indicator関数、§4.1のModel Assumptions 4.1–4.2とTheorem 8周辺。非滑らかな項を局所モデルに含める構成を確認。
- 限界：本件の段差を通常の残差に加える実装の正当化ではない。雑誌出版情報は本調査では**未確認**で、preprintとして記載した。

## R7　CADでの不等式と枝刈り

Boris van Sosin, Gershon Elber (2017), **Solving piecewise polynomial constraint systems with decomposition and a subdivision-based solver**, *Computer-Aided Design* 90, 37–47. DOI: [10.1016/j.cad.2017.05.023](https://doi.org/10.1016/j.cad.2017.05.023)。[所属機関の書誌](https://cris.technion.ac.il/en/publications/solving-piecewise-polynomial-constraint-systems-with-decompositio)、[著者PDF](https://gershon.cs.technion.ac.il/papers/mv_solver_decomp2017.pdf)。

- 本文確認：著者稿の§2.3（印刷p.3）、Algorithm 5（p.7）、§3.5–4（pp.9–10）、§5.1（p.12）。不等式を早期に適用する箇所と幾何例・限界を読んだ。
- 限界：分割型解法の議論。局所LMの成功率や吸引域の測定ではない。

## R8　動的幾何の複素迂回

Ulrich H. Kortenkamp, Jürgen Richter-Gebert (2002), **A Dynamic Setup for Elementary Geometry**, in *Multimedia Tools for Communicating Mathematics*, pp.203–219. DOI: [10.1007/978-3-642-56240-2_12](https://doi.org/10.1007/978-3-642-56240-2_12)。[出版社](https://link.springer.com/chapter/10.1007/978-3-642-56240-2_12)、[著者稿PDF](https://cermat.org/sites/default/files/KortenkampRichter-Ge-DSEG-2001.pdf)。

- 本文確認：著者稿§1、§3–6、特に§5（印刷pp.6–8）。ファイル名の2001と出版年2002を区別した。
- 限界：作図の連続追跡であり、Q1の最小二乗実験ではない。

## R9　複素迂回の保証範囲

Stefan Kranich, **Generation of real algebraic loci via complex detours**, arXiv:1510.05464v3（初稿2015、確認版2016）。[版指定本文](https://arxiv.org/html/1510.05464v3)。

- 本文確認：§1、§2 Algorithm 2.1、§4 Conjecture 4.1、§5 Conjecture 5.1、§6.4のWatt linkage例・Remark 6.17。
- 限界：conjectureを証明済みの完全性保証として引用していない。

## R10　競技幾何の自動作図

Ryan Krueger, Jesse Michael Han, Daniel Selsam (2021), **Automatically Building Diagrams for Olympiad Geometry Problems**, CADE-28. DOI: [10.1007/978-3-030-79876-5_33](https://doi.org/10.1007/978-3-030-79876-5_33)。[出版社](https://link.springer.com/chapter/10.1007/978-3-030-79876-5_33)、[著者本文arXiv:2012.02590v2](https://arxiv.org/html/2012.02590v2)（初稿2020、確認版2021）。

- 本文確認：§1、§2.3、§3.2–3.5、§4の評価設定、§5の限界。parameterization、root selector、補助損失、最適化・候補検査を確認。
- 限界：Q1と同じhard除去・LM停止対照は確認していない。

## R11　複素ホモトピーと実根の選別

Dhagash Mehta, Yang-Hui He, Jonathan D. Hauenstein (2012), **Numerical algebraic geometry: a new perspective on gauge and string theories**, *Journal of High Energy Physics* 2012(7), 018. DOI: [10.1007/JHEP07(2012)018](https://doi.org/10.1007/JHEP07(2012)018)。[機関書誌](https://openaccess.city.ac.uk/id/eprint/12874/)、[著者稿PDF](https://academicweb.nd.edu/~jhauenst/preprints/mhhNPHC.pdf)。

- 本文確認：§2（印刷pp.4–6、式2.1–2.3）、§2.1.3（pp.8–9）。著者稿の題名では“String and Gauge”の順で、出版題名と異なる。
- 限界：本件の不等式・LMの比較実験ではない。経路追跡の保証を一般のDSL作図へ移していない。

## R12　実多項式不等式の扱い

Daniel A. Brake, Jonathan D. Hauenstein, Alan C. Liddell (2016), **Numerically validating the completeness of the real solution set of a system of polynomial equations**, arXiv:1602.00700。[書誌](https://arxiv.org/abs/1602.00700)、[本文](https://arxiv.org/html/1602.00700)。

- 本文確認：§1、§7 **Equalities and Inequalities**、§8.1の半代数条件の例。`r_i(x)-y_i²=0`による補助変数化と射影の扱い。
- 限界：非負の多項式不等式の記述であり、あらゆるstrict条件・作図domainをこの一式で処理できるとはしていない。実根集合のZariski閉包等に関する主張と、半代数集合の全位相の解明を区別した。

## 書誌は確認、本文は未確認

### U1　幾何制約のホモトピー解法

Hervé Lamure, Dominique Michelucci (1996), **Solving geometric constraints by homotopy**, *IEEE Transactions on Visualization and Computer Graphics* 2(1), 28–34. DOI: [10.1109/2945.489384](https://doi.org/10.1109/2945.489384)。

出版書誌・abstractを確認。**本文未確認**。不等式境界・吸引域についての詳細な先行結果があるとは推測していない。同名の会議版や不整合な検索サイトの日付を、雑誌版の書誌と混ぜていない。

### U2　LMの基礎論文

Jorge J. Moré (1978), **The Levenberg–Marquardt algorithm: Implementation and theory**, *Numerical Analysis*, Lecture Notes in Mathematics 630, pp.105–116. DOI: [10.1007/BFb0067700](https://doi.org/10.1007/BFb0067700)。[出版社書誌](https://link.springer.com/chapter/10.1007/BFb0067700)。

書誌を確認。**本文全体は未確認**。本稿の細かな受理・停止の説明はR4のソースコードに拠る。
