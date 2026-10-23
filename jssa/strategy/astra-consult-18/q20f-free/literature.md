# Q20f 文献確認記録

確認日：2026-10-23。書誌の確認、本文の確認、このsolverへの適用可能性を区別する。「未確認」は存在しないという意味ではない。今回の検索は網羅的な先行研究調査ではなく、同一の幾何solver研究を見つけなかったことを新規性の証明には使わない。

| 文献 | 確認できた資料 | この課題での位置づけ |
|---|---|---|
| Michael Luby, Alistair Sinclair, David Zuckerman (1993), *Optimal speedup of Las Vegas algorithms*, Information Processing Letters 47(4), 173–180, DOI: 10.1016/0020-0190(93)90029-9 | [出版社の書誌・抄録](https://www.sciencedirect.com/science/article/pii/0020019093900299)を確認。著者サイトのPDFは取得できず、本文の精読は未確認 | 第一成功までの再出発理論の出発点。今回の6候補から選ぶ固定打切りはLuby系列の実験ではない |
| Sergey Belan (2018), *Restart Could Optimize the Probability of Success in a Bernoulli Trial*, Physical Review Letters 120, 080601, DOI: 10.1103/PhysRevLett.120.080601 | [出版版の情報](https://doi.org/10.1103/PhysRevLett.120.080601)、[MITの出版記録](https://dspace.mit.edu/entities/publication/8272ba69-bf32-43e5-a113-24746b4f941b)、[著者プレプリント本文](https://arxiv.org/pdf/1703.01486)を確認。本文は2017年版 | 再出発で到達先の確率が変わるという一般論は既知。今回の新規性を削る、最も重要な先行研究 |
| Alon Orlitsky, Ananda Theertha Suresh, Yihong Wu (2016), *Optimal prediction of the number of unseen species*, PNAS 113(47), 13283–13288, DOI: 10.1073/pnas.1607774113 | [公開出版記録](https://pmc.ncbi.nlm.nih.gov/articles/PMC5127330/)の検索表示で書誌を確認。直接閲覧は検証画面となった。[著者プレプリント](https://arxiv.org/pdf/1511.07428)の本文・導入を確認 | 新たに観測する種類数の有限期間予測。真の総種類数や全値回収の証明とは異なる |
| Efraim Fischbein (1993), *The theory of figural concepts*, Educational Studies in Mathematics 24, 139–162, DOI: 10.1007/BF01273689 | [出版社の書誌・抄録](https://link.springer.com/article/10.1007/BF01273689)を確認。購読対象の本文は未確認 | 概念と図像の二重性。人間の図に対する選好を考える動機にはなるが、数値探索の出力頻度を予言しない |
| Efraim Fischbein, Talli Nachlieli (1998), *Concepts and figures in geometrical reasoning*, International Journal of Science Education 20(10), 1193–1211, DOI: 10.1080/0950069980201003 | [出版社ページ](https://www.tandfonline.com/doi/abs/10.1080/0950069980201003)の書誌・抄録を検索で確認。直接取得は403。本文・個々の実験条件は未確認 | 図形認知案の関連研究。オンライン掲載日の2006年を出版年として扱わない |
| Carlos Beltrán, Anton Leykin (2012), *Certified Numerical Homotopy Tracking*, Experimental Mathematics 21(1), 69–83, DOI: 10.1080/10586458.2011.606184 | [出版社の書誌・抄録](https://www.tandfonline.com/doi/full/10.1080/10586458.2011.606184)と[著者公開本文](https://personales.unican.es/beltranc/archivos/certified_homotopy_tracking.pdf)の導入を確認。著者原稿の日付は2011-06-17 | 正則な多項式系の解経路を追う理論。現在のLM記録へそのまま転用できない |

**再出発に関する確認。** Belanの式(3)は、再出発前に終わった試行のうち特定の結果となる割合を与える。完了時間と出力ラベルが依存すれば、打切りは出力分布を変える。本課題の「複数の参照値を全部集める」目的そのものが同論文で扱われたとは確認していないが、目的の違いだけで新規な一般原理を得たとは言えない。[Belan本文、式(2)–(4)](https://arxiv.org/pdf/1703.01486)

**種数推定に関する確認。** Orlitskyらのプレプリント名は *Estimating the number of unseen species: A bird in the hand is worth log n in the bush* で、出版版と異なる。対象は、同じ分布から得たn標本の後、追加tn標本で初めて見る種類数。所定の平均二乗誤差の意味で、予測可能なtの範囲がlog n程度まで伸びるという結果である。数値解の同一性判定、探索中に変化する分布、確率が極小の未観測解、全解の不存在証明は、この定理だけでは扱えない。[プレプリント、導入・主結果](https://arxiv.org/pdf/1511.07428)

**図形認知に関する確認。** Fischbeinの理論から「人間は退化図を除外する」「人間に自然な図はsolverに希少である」「競技数学の難易度を説明できる」とは導けない。後二者は今回提案側が付け加えた未検証の仮説であり、引用文献の結論ではない。[Fischbeinの抄録](https://link.springer.com/article/10.1007/BF01273689)

**ホモトピー案を選ばなかった理由。** 条件長は、多項式系とその解がたどる経路全体について定義される量である。最終解のヤコビアン条件数を測ってLMの難しさと相関させる案に置き換えると、理論の前提も、今回の求める新しさも失う。経路を新設して追跡する研究は可能だが、この小検証には経路データも同じ前提の表現もない。既存の厳密追跡法との区別も未確認であり、第四の有望候補とは数えない。[Beltrán–Leykin、導入](https://personales.unican.es/beltranc/archivos/certified_homotopy_tracking.pdf)
