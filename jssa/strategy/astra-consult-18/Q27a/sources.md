# 文献・データの確認範囲

2026-10-23に検索し、以下の一次資料の公開本文・要旨を確認した。理論が知られていることと、今回のsolverの現象に適用できることを分ける。引用の逐語転載はしていない。

| 文献 | 確認できたこと | 今回確認していないこと |
|---|---|---|
| Carla P. Gomes, Bart Selman, Nuno Crato, Henry Kautz, *Heavy-Tailed Phenomena in Satisfiability and Constraint Satisfaction Problems*, Journal of Automated Reasoning 24, 67–100 (2000). [著者公開PDF](https://www.cs.cornell.edu/gomes/pdf/2000_gomes_jar_phenomena.pdf) | 本文冒頭・要旨・書誌。SAT/CSPのbacktrack実行時間の大きな変動・重い裾・再出発の効果が既に研究されている | 今回のLM/Powell記録が同じ分布族に属すること。原論文の全実験の追試 |
| Michael Luby, Alistair Sinclair, David Zuckerman, *Optimal Speedup of Las Vegas Algorithms* (1993). [著者公開稿](https://www.cs.utexas.edu/~diz/pubs/speedup.pdf)、[出版社書誌](https://www.sciencedirect.com/science/article/pii/0020019093900299) | 未知分布への普遍再出発が最適費用ℓに対してO(ℓ log ℓ)となること、対象が正答時に停止するLas Vegas算法であること | 今回の完成solverの正確性を前提から証明すること、今回の候補bが普遍系列であること。いずれも主張しない |
| Shlomi Reuveni, *Optimal Stochastic Restart Renders Fluctuations in First Passage Times Universal*, Physical Review Letters 116, 170601 (2016). [著者arXiv](https://arxiv.org/abs/1512.01600) | 公開要旨・書誌。非零の最適な一定率で再出発する初到達過程について相対標準偏差1という結果 | 証明の全仮定の独立監査は未実施。失敗終了を含むrawのNはその初到達時間ではなく、固定打切り方策への直接適用もしていない |
| Aaron Clauset, Cosma Rohilla Shalizi, M. E. J. Newman, *Power-Law Distributions in Empirical Data*, SIAM Review 51, 661–703 (2009). [著者arXiv](https://arxiv.org/abs/0706.1062)、[論文PDF](https://www.cs.cornell.edu/courses/cs6241/2020sp/readings/Clauset-2009-power-laws.pdf) | 要旨・論文冒頭。べき則の検討に最尤推定・適合度・代替分布比較を用いる枠組み | 今回はその完全な適合検定を実施していない。Hill値の閾値依存だけで「べき則ではない」と結論しない |
| Peter Bürgisser, Felipe Cucker, Martin Lotz, *The probability that a small perturbation of a numerical analysis problem is difficult*, 2006年arXiv版. [本文](https://arxiv.org/pdf/math/0610270) | 定義・定理1.1。円錐条件数、悪条件集合を含む次数制約付き代数集合、球面上の一様摂動、対数条件数の期待値上界。本文pp.3–4の式を確認 | 固定幾何問題の箱内開始分布との対応、N/Tと条件数との支配関係は未確認。実測の指数を定理から導いたとはしない |
| Jonathan D. Hauenstein, Frank Sottile, *alphaCertified: certifying solutions to polynomial systems*. [著者公開PDF・2011年稿](https://franksottile.github.io/research/pdf/alphaCertified.pdf)、[2010年arXiv](https://arxiv.org/abs/1011.1091) | 定義1と定理2。正方多項式系の通常Newton法に対するα閾値と二次収束保証 | 各候補のαは未計算。過剰決定・非多項式・guard付きLM/Powell・実装全体への保証は未確認 |

Pomeau–Mannevilleの間欠性も文献検索の語として調べたが、元論文本文を確認していない。**未確認の理論を今回の裾の説明・採択根拠に使っていない。** 数値時間にべき関数を当てるだけで、間欠性・カオス・普遍性を認定することもしない。

## データの出所

- 方針：[codex-tasks-1023.md](../../codex-tasks-1023.md)末尾の23:25方針・Q27、[本人の基準](../../codex-session-01a1171a-summary.md)。
- 局所記録：[basins-323.csv](../../../difficulty/minima/basins-323.csv)、raw-323、raw-323-seed1。全646JSONを確認集計。途中軌道の記録はない。
- 実装の読解：[probe_basins.py](../../../difficulty/probe_basins.py)、凍結版60db4b6の`src/geosolver/engine/standard/search/scipy_multistart_backend.py`。後者はローカルのgit showで読み、fetchせず、変更していない。
- 完成solver：[969行の段階別時間](../../../results/stage-profile-20261023/per-case.csv)、[説明](../../../results/stage-profile-20261023/per-case-README.md)、[遅い／失敗144行の分類](../../../difficulty/stage-taxonomy/README.md)。すべて同じ既存本計測に由来し、独立した実験3本ではない。
- 許容条件：start-feasibility-1023/per-problem.csv、per-problem-seed1.csv。
- 精密化：multiplicity/per-candidate.csv（505行）とruns内の原形O（101候補・34問）のprecision-stage history。完成solverの969実行の全候補履歴ではない。
- PSLQ：q21b-number-theory/precision.csv（316問331代数的答値×10精度）。元の323問のうち非代数的な値などはこの表に含まれない。
- msolve：astra-consult-17/H/sources/comparison-cases.csv。Hのprovenance.jsonにローカル保存の出所が記載されている。列`real_solutions`は実根数であり、全複素解数・Bézout上界・配置の種類数ではない。
- 作図展開：benchmarks/extra-variables/の15問60DSLを読んだ。元dose-responseのraw-extra60とbasins-extra60.csvは不在。minima/summary.mdの既存要約、別プロトコルのcommon-start/summary.csvは存在するが、元の時間曲線の代替にはしない。
- GMB：benchmarks/gmb_comparison/README.md、jssa/results/gmb-success-definition/README.mdとper-trial.csv（136行32問）。時間列と元のbenchmarks/local-evaluationディレクトリがないため時間分布は未検証。

集計に読んだファイルのパス・サイズ・SHA-256は3つの`input-manifest-*.json`にある。文書の説明と保存行数が違う場合は、実データを数えた分母を採用した。未使用問題群の追加取得は行っていない。
