**文献確認（2026-10-23）**

書誌を検索し、下記の一次論文本文または著者・arXiv公開ページを開いて確認した。検索で見つけた二次解説の文言は根拠に採用していない。これは網羅的レビューではない。

| 文献 | 確認箇所・今回の意味 | 同一視しない点 |
|---|---|---|
| Peter Cheeseman, Bob Kanefsky, William M. Taylor, *Where the Really Hard Problems Are*, IJCAI 1991. [会議公式PDF](https://ijcai.org/Proceedings/91-1/Papers/052.pdf) | 冒頭、Hamilton circuitとgraph coloringの実験。制約の密度・解の存在・探索費用を分け、サイズに伴う変化も調べる古典的出発点。 | 有限の成功率曲線だけで本研究に同じ転移があるとは言えない。SATの定数を幾何へ移さない。 |
| Florent Krzakala, Lenka Zdeborová, *Hiding Quiet Solutions in Random Constraint Satisfaction Problems*, Physical Review Letters **102**, 238701 (2009), arXiv:0901.2130. [書誌](https://arxiv.org/abs/0901.2130)、[本文 Easy/Hard/Easy pattern](https://arxiv.org/html/0901.2130v2) | 解を埋め込む集団の構造と易難易、特定クラスで元のランダム集団と同じ性質を保つquiet plantingを扱う。 | 「解があるのに難しい」「高密度で易しくなる」だけは新規でない。今回の有理座標・中点の植え込みがquietであることは未確認。 |
| Shiva Prasad Kasiviswanathan, Cristopher Moore, Louis Theran, *The Rigidity Transition in Random Graphs*, SODA 2011, arXiv:1010.3605. [著者の書誌](https://theran.lt/papers/c006-rigiditytransition.html)、[本文](https://arxiv.org/html/1010.3605v2) | Abstract、§1、§2。genericな平面bar-joint系のG(n,c/n)で巨大剛性成分が生じる閾値c≈3.588を示す。 | 巨大成分・全点の固定・大域一意性・局所探索到達は別。固定3点、中点の依存、有理格子を持つ本生成器へ数値3.588を適用していない。 |
| T. Eren, D. K. Goldenberg, W. Whiteley, Y. R. Yang, A. S. Morse, B. D. O. Anderson, P. N. Belhumeur, *Rigidity, Computation, and Randomization in Network Localization*, IEEE INFOCOM 2004. [論文PDF](https://people.cs.rutgers.edu/~rmartin/teaching/spring05/local/readings/eren04.pdf) | Abstract、§IV–VI、Fig.6–9。固定点を持つ距離実現の一意性と計算量、逐次trilateration、ランダム配置でのlocalizabilityの急変が既存研究にある。年・会議は[著者側の後続稿の参考文献](https://www.eng.yale.edu/controls/2006/mtns_localization_summary.pdf)でも確認。 | 図を局所探索で同時に求める本実験と、位置が分かった点から順に伝えるITPは違う。「幾何で相転移を初めて見た」とは書けない。 |
| Ryan Krueger, Jesse Michael Han, Daniel Selsam, *Automatically Building Diagrams for Olympiad Geometry Problems*, arXiv:2012.02590（2021年改訂版）. [著者稿の書誌・要旨](https://arxiv.org/abs/2012.02590) | GMBLが変数化、直接作図、追加制約のlossを指定し、最適化で競技幾何の図を作る構成を確認。 | DSLから多数の幾何制約を同じ最適化機構で解くことも、それだけでは新規でない。 |

**検索範囲と未確認**

主な検索語は `random constraint satisfaction phase transition`、`planted CSP easy hard easy quiet planting`、`random geometric distance constraints rigidity percolation`、`The rigidity transition in random graphs`、`random distance geometry optimization phase transition local minima`、`Rigidity Computation Randomization Network Localization`。SAT/CSP、剛性理論、ネットワーク位置推定、GMBへ順に照合した。

- 「競技幾何入力がランダム作図のアルゴリズム転移のどちら側にあるか」を、このsolverと同じ採点・形式化で検証した先行研究は今回の検索では確認できなかった。**世界初は未確認**。
- ランダム中点作図族の臨界密度・有限サイズ指数、quiet plantingの成立、本solver以外の局所法への普遍性は**未確認**。
- 原論文の巨大剛性成分の定理を全配置一意性やLMの成功保証として使っていない。今回測ったのは別に定義した有限予算のS、埋め込み回復R、数値ランクLである。
