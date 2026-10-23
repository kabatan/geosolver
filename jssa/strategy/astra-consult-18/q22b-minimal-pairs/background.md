# 背景の確認と重複の扱い

指定資料は読み取り専用で参照した。今回の新規計測は人工20組であり、他担当の計測を本検証の試行数に足していない。

| 資料 | 参照した範囲・今回への反映 |
|---|---|
| [codex-tasks-1023.md](../../codex-tasks-1023.md)末尾 | 方針転換、Q20、追加基準、Q21、Q22を最初に確認。「数値予言が当たる」だけでは採用せず、紙上の自明性・代替手段・汎用solverが主役かも判定する |
| [session要約](../../codex-session-01a1171a-summary.md) | 本人の採用基準と過去の却下理由。記号的に作った個別例の数値検算を主成果にしない |
| [相談16](../../gpt-pro-consult-16-answer.md)、[相談17](../../gpt-pro-consult-17-answer.md) | 結論・提案・中止条件を参照。旧来の壁、許容条件、証明書等を核として再提案しない |
| [report-draft-v10](../../../draft/report-draft-v10.md)、[supplement-v10](../../../draft/supplement-v10.md) | 主要節、定義、表と難度に関する議論を参照。全補遺の数式・全生ログを独立再検証したという意味ではない |
| astra-consult-17のG〜L | 各answerの結論・根拠・限界を参照。Lの既存answerも確認し、現在の正誤・枝の定義を人工例へ無条件に転用しない |
| Q3・Q4 | 指定ディレクトリ直下にはなく、[wall-diagnostic](../../../difficulty/wall-diagnostic/answer.md)、[multiplicity](../../../difficulty/multiplicity/answer.md)の回答を参照 |
| Q5 | task文にあるfull-solver-nohardを含め、該当answerが作業ツリー内に見つからなかった。未参照。取得や他フォルダへの書き込みはしていない |
| Q6〜Q10・Q12 | astra-consult-17の各answerの結論と関連する検証節を参照 |
| Q11 | [certify-all/answer.md](../../../difficulty/certify-all/answer.md)を参照。保存局所終点と完成solverの返答を区別する必要を反映 |
| astra-consult-18のQ20a〜f、Q21a〜f | 既存answerの結論と関係節を参照。更新中の内容を変更していない。特にQ20eの目標不変性、Q21eのm<dでのPowell分岐との重複を明示した |
| Q22a | 作成中のanswerを参照。隠れた一致、人間難度の相関予測、GeoGebraとの比較を本担当の候補へ重ねていない |

[basins-323.csv](../../../difficulty/minima/basins-323.csv)は323行。[raw-323](../../../difficulty/minima/raw-323/)の323ファイルのメタデータを確認し、自由変数ありは292問、保存されたnative制約件数でm<nは20問だった。個々のrawの形式と終点の保存項目も確認した。全旧終点の再採点はしていない。

[human_feat.csv](../../../difficulty/ghost-1023/human_feat.csv)は323行中、有限なhuman値が131問（AIME 52、HMMT 79）。今回の人工対には対応する人間値がない。相関係数による選別・予測は行わず、旧pを新しい箱や開始分布でのpとして使わなかった。

「局所探索で同じ座標を得る」ことは完成solverの全処理の不変性ではない。今回測っていないNOMAD、精密化、PSLQ、答え集合の網羅性について、旧回答の成績を根拠に補完していない。
