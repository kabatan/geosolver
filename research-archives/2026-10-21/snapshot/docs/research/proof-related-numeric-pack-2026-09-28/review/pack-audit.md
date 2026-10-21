# AP01 周辺の求値パック：独立監査

2026-09-28。最終10問は DA01, DA02, DA03, DA04, DA06, DA07, DA08, DA11, DB02, DB12 と確認した。公開問題文 PN01–PN10 はこの順の選定に対応し、各問は固定した構図・固定した求値 query を持つ。作図から givens と target を照合する witness 監査は [`witness-audit.json`](witness-audit.json) に保存した。DA verifier と DB verifier は成功し、DB verifier は全12件の原作図 witness と7件の一般記号恒等式を検査した。`verify_additional_relations.py` も成功し、DA04、DA11、DB02、DB12を含む該当 identity 行を記録した。個別 witness の一致を一般命題の証明とは扱わない。

## 問題設計と AP01 との距離

10問は単なる数値や点名の差し替えではない。二接円、120度の点と重心から引く割線、接円と外心の交点、中円弦の接円配置、外心・垂心と直径円、対蹠点と平行四辺形、中点接円、反射角条件と倍長、平行線で作る二円族と、それぞれ構図・求値量が異なる。求値は順に AT, TK, AK, PQ, OE, XY, OT, 円 ABT の半径, BX, AX で固定されている。

どの問題文にも「A,N,F,P が共円」や AP01 の結論を条件として与える記述はない。10問とも証明評価ではなく数値求値であり、AP01 の垂直二等分線・中線・交点 F の結論をそのまま入力に埋め込んだ問題もない。一方、関係の独立性は限定的である。DA01 は A で接する二円の第2交点で、既存監査はそれを A-Dumpty 点として DA15 の中線・垂直二等分線構図に現れる同一点へ結び付けている。DB12 は平行線から作る二円族の固定点で、同じ既存記号検証に含まれる。DB02 も反射角で作る点の円周上性と辺比を共有する。よって「AP01 の結論を漏らした」問題群ではないが、「AP01 と幾何的に無関係な10構図」の比較群でもない。既知関係の再利用を測る関係近接パックとして扱うのが妥当である。

| Pack ID | Source | 固定した query | 構図の要点 |
|---|---|---|---|
| PN01 | DA01 | AT | Aで接する二円の第2交点 |
| PN02 | DA02 | TK | 120度の点、重心、円の割線 |
| PN03 | DA03 | AK | 接円、円BOC、外心を通る直線 |
| PN04 | DA04 | PQ | 大円に内接する二円と共通弦 |
| PN05 | DA06 | OE | 二接円と中線、外心 |
| PN06 | DA07 | XY | 外心・垂心側の二組の直径円 |
| PN07 | DA08 | OT | 対蹠点と平行四辺形 |
| PN08 | DA11 | 円 ABT の半径 | 辺の中点で接する二円 |
| PN09 | DB02 | BX | 角条件、反射する二本の線、倍長点 |
| PN10 | DB12 | AX | 平行線で作る二円族の共通点 |

## 生成器の範囲

`benchmarks/humpty_configurations_v2/authoring/gen_variants.py` の generator 登録は H01, H02, H03, H04, H07, H08, H12, H13, H14, H15, HX01 に限られる。今回の DA/DB 10 ID は非相似形状 generator を持たず、`sample_shape` は「no non-similarity generator」で停止する。10 ID 全てに `variant_templates.json` の固定 query テンプレートはあるため、明示的な similarity augmentation は可能だが、相似倍率の変更だけで形状分布が広がるわけではない。別の生成ロジックが非相似形状を作る場合は、その builder・固定 query・branch/domain 条件・各ラベルの witness 検査を別途記録する必要がある。ここでは、その存在や正しさを `gen_variants.py` から推定していない。

## 過去の数値SFTとの重複

この10問を今後の教師や訓練例に使った後、過去の評価結果を独立した heldout 成績として再利用しないこと。

| ID | 以前の位置 | 過去結果・影響 |
|---|---|---|
| DA01 | 旧数値SFTの7学習構図の一つ（8 pair） | 現在の選定にも再利用。新規 heldout ではない。DA15に現れるA-Dumpty点との一般的な接続は記録済みだが、DA01の教師 target は AT だった。 |
| DA03 | 旧12構図の評価対象 | base 2/2、数値SFT 2/2。既に見た評価構図で、今回の訓練後は heldout にできない。 |
| DA06 | 旧12構図の評価対象 | base 1/2 から数値SFT 2/2。以前に改善が記録された構図で、今回の訓練後の独立確認にはならない。 |
| DA07 | 旧12構図の評価対象 | base 2/2、数値SFT 2/2。既存評価の重複。 |
| DA11 | 旧12構図の評価対象 | base 0/2 から数値SFT 1/2。以前に部分改善が記録された構図で、今回の訓練後の独立確認にはならない。 |
| DA02, DA04, DA08, DB02, DB12 | 旧 numeric-SFT の学習7構図・評価12構図とは別の、同じ既存benchmark内の18候補の一部 | 以前の研究で使った題材で、研究者にとって新規 benchmark ではない。少なくとも current pilot の12 heldout と同一ではないが、今回教師に含めた後は再評価に使わない。 |

上表の過去結果は [`transfer-reanalysis-2026-09-26/FOLLOWUP_REPORT.md`](../../transfer-reanalysis-2026-09-26/FOLLOWUP_REPORT.md)、旧学習構図・候補群は [`numeric-sft-research-plan-2026-09-27/PROPOSAL.md`](../../numeric-sft-research-plan-2026-09-27/PROPOSAL.md) と [`CASE_STUDY.md`](../../numeric-sft-research-plan-2026-09-27/CASE_STUDY.md) を参照した。以前の差は当時の問題、生成条件、推論 seed に対する結果であり、現在のデータで再現する保証ではない。

## 判定

問題文の AP01 結論リークは見当たらない。10問は異なる作図・query を含むが、A-Dumpty／接円・中点関係を共有し、旧数値SFTの訓練または評価履歴とも重なるため、独立した10系統の新規汎化評価と称さない。証明すべき次の問いは、固定 query のまま非相似形状を作れる独立 builder の有無と、各形状の domain/branch を含む witness 検査が保たれているかである。
