# 文献・データ・未確認事項

確認日：2026-10-23。文献で報告された結果と、この作業で実行した結果を区別する。主報告は[answer.md](answer.md)。

## 確認した一次資料

| 資料 | 確認範囲と用途 | 今回していないこと |
|---|---|---|
| Trinh et al., *Solving olympiad geometry without human demonstrations*, Nature 625, 476–482 (2024), [論文](https://www.nature.com/articles/s41586-023-06747-5) | 論文情報と、[公式リポジトリ](https://github.com/google-deepmind/alphageometry)のREADME・入力・DD+ARコード。書誌と実装の役割を確認 | 学習済みモデルの取得、AG全体の再実行 |
| Sinha et al., *Wu’s Method can Boost Symbolic AI to Rival Silver Medalists and AlphaGeometry to Outperform Gold Medalists at IMO Geometry*, arXiv:2404.06405v2 (2024), [本文](https://arxiv.org/html/2404.06405v2) | §2とFigure 1、Appendix B。保存した図を目視転記し、集計を検算 | JGEXの再実行、全入力の意味同値性の証明、同一ハードウェアでの時間比較 |
| Chervonyi et al., *Gold-medalist Performance in Solving Olympiad Geometry with AlphaGeometry2*, JMLR 26(241):1–39 (2025), [掲載情報](https://jmlr.org/papers/v26/25-1654.html)、[本文v3](https://arxiv.org/html/2502.03544v3) | §2、Table 4、Appendix Gを確認。旧AG1の結果を現行の一般的限界としないために参照 | AG2の実行、各問題の証明探索ログの取得 |
| Janičić, Narboux, Quaresma, *The Area Method: A Recapitulation*, JAR 48:489–532 (2012), [著者所属機関の書誌・要旨](https://research.matf.bg.ac.rs/handle/123456789/510?mode=simple)、[DOI](https://doi.org/10.1007/s10817-010-9209-7) | 書誌・要旨、[公開実装](https://github.com/rocq-archive/area-method)の所在を確認 | 本文全体の精査、導入・実行、IMO-AG-30の測定 |
| Krueger, Han, Selsam, *Automatically Building Diagrams for Olympiad Geometry Problems*, arXiv:2012.02590v2 (2021), [論文](https://arxiv.org/abs/2012.02590v2) | 図生成を目的とするGMBの位置づけ。具体的な今回の数値は下記のローカル記録から取得 | GMBの新規実行 |

面積法とFull-Angle methodは別の手法である。公開表のFull-Angleの数字を面積法の成績として扱わない。古い論文の特定LLMの成績も、現在のLLM一般の成績へ拡張しない。

## 保存した公開資料の来歴

- [upstream/imo_ag_30.txt](upstream/imo_ag_30.txt)および同ディレクトリのコード・定義・規則は、引継ぎ時点で保存済みの公式AlphaGeometry資料。今回それらを編集していない。[ライセンス](upstream/LICENSE)も保持した。
- [summary.json](summary.json)と各DD+ARログに保存ファイルのSHA-256がある。6ログが同じ保存コードを指すことを再集計時に検査している。取得元コミットIDは未確認なので、特定コミットの再現とは記さない。
- [wu-2024-v2.pdf](wu-2024-v2.pdf)と[wu-figure1.png](wu-figure1.png)は引継ぎ資料。[published-imo-ag30.csv](published-imo-ag30.csv)はそのFigure 1を目視転記したもの。値0は「同図で解決に数えられない」であり、時間切れ・翻訳不能・定理が偽を区別する符号ではない。
- DD+ARの依存ライブラリの代替は[deviations.md](deviations.md)を参照。推論の追加規則や問題ごとの補助点は与えていない。

## ローカルな入力・結果

| 入力 | 用途 | 制限 |
|---|---|---|
| [human_feat.csv](../../../difficulty/ghost-1023/human_feat.csv) | 人間成績のある問題集合を確認 | IMOの人間データではない |
| [GMB比較入力](../../../../benchmarks/gmb_comparison/cases)と[比較仕様](../../../../benchmarks/gmb_comparison/README.md) | 元問題IDでの接続、図生成と求値・証明の区別 | ID一致は述語・枝・結論の意味同値性の保証ではない |
| [GMB per-trial.csv](../../../results/gmb-success-definition/per-trial.csv)と[README](../../../results/gmb-success-definition/README.md) | 2008 P1の6行を抽出 | 図を検査した部分集合であり全試行表ではない |
| [草稿v10](../../../draft/report-draft-v10.md)と[補足v10](../../../draft/supplement-v10.md) | GeoSolverの既存集計を理解 | 個別問題の生ログの代わりにはしない |

## 比較を進める場合に必要な具体的データ

以下を今回は未取得・未実行として扱う。欠けた値を推定で埋めていない。

1. **AG1/AG2の問題別の推論過程。** [AG1公式](https://github.com/google-deepmind/alphageometry)、[AG2公式](https://github.com/google-deepmind/alphageometry2)から、入力・結論・補助構成・証明トレース・終了理由・予算を同じIDに揃える。AG2の集計表だけでは、2008 P1のどの改良が効いたかは分からない。
2. **Wu/JGEXの実入力と非退化条件。** 論文が案内する[SimpleGeometryデータ](https://huggingface.co/datasets/bethgelab/simplegeometry)の.gex、26題の翻訳と元入力の対応、未翻訳4題のID・理由、実行設定・消去結果。今回の公開0/1表から失敗機構は復元できない。
3. **面積法の再生可能な条件。** 上記公開実装の版、必要環境、表現できる構成、共通問題の入力・証明・失敗ログ。存在確認と、本ベンチマークで動くことは別である。
4. **GeoSolver/GMBの同一課題ごとの生記録。** 既存の比較キャンペーンから、P・B・Qの翻訳対応、図、探索・精密化・値同定の時間と終了理由、各seedを取得する。保存済みの100/108という集計から作らない。図生成用の目標なし入力に、証明数と同じ成功ラベルを付けない。
5. **単独LLMの固定された回答記録。** モデルと版、プロンプト、図の有無、推論予算、全回答、採点規約。公開表の古いモデルや、AGの内部構成提案器の成績では代用できない。
6. **人間の同一の問いへの記録。** 元問題別得点の確認先は[IMO公式2008大会](https://www.imo-official.com/editions/2008/)。今回は当該得点表を取得していない。a/bや15結論の解答時間・正答率を比較するには、結論別の既存実験データまたは別途の人間実験が必要であり、公開の元問題の平均点だけでは足りない。

必要データが全て揃っても、手法別の勝敗表だけでは候補2の機構的主張は成立しない。先に具体的な逆転の予測が必要である。
