# Q20a：出典・確認範囲

確認日：2026-10-23。以下の先行研究と、今回の手計算・実験を区別する。文献検索は網羅的レビューではなく、未発見を新規性の証明にはしない。

| 文献 | 確認した範囲・使う内容 | 今回へ持ち込めない主張 |
|---|---|---|
| D. N. Bernstein, “The number of roots of a system of equations” (1975), [書誌](https://www.mathnet.ru/eng/faa2258) | 原論文の書誌・DOIを確認。BKKの定理の内容は次行の著者公開稿で確認 | 原論文の証明を精読したとはしない |
| I. Z. Emiris and J. F. Canny, “Efficient Incremental Algorithms for the Sparse Resultant and the Mixed Volume”, [著者公開稿](https://people.eecs.berkeley.edu/~jfc/papers/95/cejsc95.pdf) | §3、Theorem 3.6–3.7。混合体積と複素トーラス内の孤立解数、一般係数での等号 | 正の実解数、幾何条件での許容率、局所法の吸引域の体積を与える定理ではない |
| T. Duff, C. Hill, A. Jensen, K. Lee, A. Leykin and J. Sommars, “Solving polynomial systems via homotopy continuation and monodromy”, [arXiv:1609.08722v4](https://arxiv.org/html/1609.08722v4) | パラメータ族の解をモノドロミーで発見するアルゴリズムと、置換の確率モデルによる期待追跡数の解析 | 一様な置換等のモデル仮定を、今回の幾何DSL・手選びの円・実数LMの成功確率へ無条件に適用できない |
| C. Beltrán and A. Leykin, “Robust certified numerical homotopy tracking”, [arXiv:1105.5992v2](https://arxiv.org/html/1105.5992v2) | 条件数に沿った経路追跡と認証、ビット計算量に関する本文。経路上の条件の変化と必要精度を区別する根拠 | 今回の64分割Euler/Newtonコードは認証付き追跡器ではない。同論文の保証を付与しない |
| U. Kortenkamp / J. Richter-Gebert, “A dynamic setup for elementary geometry”, [著者公開PDF](https://cermat.org/sites/default/files/KortenkampRichter-Ge-DSEG-2001.pdf) | §5–7を中心に、複素パラメータによる幾何構成の追跡とモノドロミーの利用 | 「複素数を経由する幾何」は新規ではない。ただし特定バージョンのGeoGebraで今回のDSLがそのまま実行できることは未確認 |
| Hanyu Li and Shaoxin Wang, “Partial condition number for the equality constrained linear least squares problem” (2016), [arXiv:1603.08290](https://arxiv.org/abs/1603.08290) | **abstractを確認**。解全体でなく、その線形関数の条件数を扱う先例 | 本文未確認。対象は線形等式制約付き最小二乗であり、今回の非線形幾何系の定理として引用しない |
| J. R. Rice, “A Theory of Condition” (1966), [DOI](https://doi.org/10.1137/0703023) | 書誌のみ。**本文未確認** | 今回の具体的感度式や時間予測を、この論文で確認済みとはしない |

候補1の確率和・再出発の式、候補2の陰関数微分、候補3の二次式の補正誤差は[theory.md](theory.md)で直接導出した。先行研究の新定理として紹介するものではない。一般の数値代数幾何の実装性能や、完成solverとの優劣は今回の文献確認だけでは決まらない。

**内部資料の参照範囲。**

依頼された背景資料の主要結論と該当箇所を読んだ。今回の数値集計に使ったのは下記の3問と限定された保存ログであり、全323問の代数構造を新たに解析したわけではない。

- [Q20と22:05の追加基準](../../codex-tasks-1023.md)、[過去セッションの基準](../../codex-session-01a1171a-summary.md)。今回のA判定は「高速化だけでは不可」「solverが例示や検証の道具に留まる案は不可」を適用した。
- [相談16](../../gpt-pro-consult-16-answer.md)、[相談17](../../gpt-pro-consult-17-answer.md)、[本文v10](../../../draft/report-draft-v10.md)、[補足v10](../../../draft/supplement-v10.md)。既存の問い・基準・完成solverと局所探索の区別を引き継いだ。
- `astra-consult-17/G`〜`L`、`Q6`〜`Q10`の `answer.md`。とくに[J](../../astra-consult-17/J/answer.md)には希少枝の回収の既存議論があり、[Q7](../../astra-consult-17/Q7/answer.md)には動的幾何の複素迂回の先例がある。今回それらを新発見として数えない。
- `astra-consult-17/Q3`〜`Q5` は指定位置になかったため、タスク表の出力先を追った。[Q3の実体](../../../difficulty/wall-diagnostic/answer.md)、[Q4の実体](../../../difficulty/multiplicity/answer.md)を参照。Q5の出力先 `jssa/difficulty/full-solver-nohard/` は再開時に存在せず、結果未確認。
- [basins-323.csv](../../../difficulty/minima/basins-323.csv)、[human_feat.csv](../../../difficulty/ghost-1023/human_feat.csv)、[new2026-predictのREADME](../../../difficulty/new2026-predict/README.md)・[score](../../../difficulty/new2026-predict/score.md)。後者は既存の予測研究の背景として参照し、今回の予測器には使っていない。
- `minima/raw-323/` と `raw-323-seed1/` の AIME-2007-I-15、HMMT-2009-FEB-GEO-07、HMMT-2013-FEB-GEO-04 の計6ファイルを再集計。各200試行。[完成solverの既存stage-profile](../../../results/stage-profile-20261023/per-case.csv)から同3問×3 seedだけを抽出した。

未使用54問の封印結果は開いていない。文献・背景の不足を補うための大規模実行やインストールは行っていない。
