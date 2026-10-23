# 文献確認（2026-10-23）

検索語：`Albersmeyer Diehl lifted Newton 2010`、`Hiding quiet solutions random constraint satisfaction`、`msolve polynomial systems 2021`、`Smale alpha theory alphaCertified`、`rigidity transition random graphs`。以下の原論文・著者稿を今回開いた。検索結果の第三者要約から定理は採用していない。

| 一次資料 | 確認範囲 | 今回への含意と限界 |
|---|---|---|
| Jan Albersmeyer, Moritz Diehl, *The Lifted Newton Method and Its Application in Optimization*, SIAM J. Optimization 20(3), 1655–1684 (2010), DOI 10.1137/080724885. [著者側PDF](https://publications.syscop.de/Albersmeyer2010.pdf) | 表題・著者・年・巻頁、Abstract、Introduction | 中間変数と同値制約を足して収束域・収束速度を改善する研究は既存。今回の有限予算hit率を予言する定理は確認していない |
| Florent Krzakala, Lenka Zdeborová, *Hiding Quiet Solutions in Random Constraint Satisfaction Problems* (2009), arXiv:0901.2130v2. [本文](https://arxiv.org/html/0901.2130v2) | 書誌、Abstract、冒頭の集団・植え込みの説明 | 特定の離散planted CSPの易難易は既知。競技幾何の混合集団がquiet plantedであることは未確認 |
| Shiva Prasad Kasiviswanathan, Cristopher Moore, Louis Theran, *The Rigidity Transition in Random Graphs*, arXiv:1010.3605v2 (2010、SODA'11予定との書誌). [著者稿](https://arxiv.org/abs/1010.3605) | 書誌・Abstract | genericな平面bar-jointとErdős–Rényi G(n,c/n)の巨大剛性成分の閾値c≈3.588。作図消去後のm/d、LM到達率、全点固定性とは違う量で、閾値を転用しない |
| Jonathan D. Hauenstein, Frank Sottile, *alphaCertified: certifying solutions to polynomial systems*, arXiv:1011.1091v2 (2011). [著者稿](https://arxiv.org/abs/1011.1091) | 書誌・Abstract | 正方多項式系のNewton局所二次収束認証。混合solverの開始分布全域の成功確率を与えない。今回への適用条件は未検証 |
| Jérémy Berthomieu, Christian Eder, Mohab Safey El Din, *msolve: A Library for Solving Polynomial Systems*, ISSAC 2021. [著者稿](https://arxiv.org/abs/2104.03572)、[公式書誌](https://msolve.lip6.fr/team/index.html) | 著者・年・タイトル、Abstract、公式書誌 | 零次元系、Gröbner基底、単変数実根計算。Bézout上界・実根数・許容配置数は別 |
| Ryan Krueger, Jesse Michael Han, Daniel Selsam, *Automatically Building Diagrams for Olympiad Geometry Problems*, arXiv:2012.02590v2 (2021). [著者稿](https://arxiv.org/abs/2012.02590) | 書誌・Abstract | パラメータ化・直接作図・追加loss制約を含むDSLから最適化で図を作る先行研究。323問と同じ課題・許容誤差の成績ではない |

今回得られなかったもの：競技幾何のpについての臨界密度、有限サイズ指数ν、lifting後のp増分を入力だけから数値予告する理論、完成solverの各経路の条件付き成功率q_jを予告する理論。いずれも**未確認**。検索で見つからないことを新規性の証拠にはしていない。

answer.mdの有限サイズスケーリング式は将来の仮説に必要な測定を示す候補形であり、上記論文がこのsolverに証明した式ではない。P1〜P3は経験的再現予想、再出発の式は初等確率であり、深い理論由来の成功予言とは数えない。
