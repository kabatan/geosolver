BASE未解決15問中、10問は3seed中2回以上がFSIZE切断であり、観測された失敗の主因は保存上限。別の1問にも1seedのFSIZE切断がある。  
残る5問はartifact_missingのみ3問、artifact_missing 2seed＋FSIZE切断1seedが1問、solver_no_answer_foundのみ1問。artifact_missingのworker終了原因は記録なし。  
過去成功→今回未解決は14/15問で確認。全構成のnonzero_exit 320枠はFSIZE切断231枠＋artifact_missing 89枠で、上限撤廃後の正解数は現記録から確定できない。

# S8 superPC BASE失敗レビュー

既存記録の読み取り分析のみ。対象は現行の `run-superpc/` の53問×3seed（601–603）×7構成＝1113枠。旧 `run-superpc-aborted-attempt1/`、smoke、WinPC、後続stageの結果は混ぜない。solver・実験・採点器の再実行、外部ネットワーク取得、git commit/pushは行っていない。

## 判定と根拠

「解けた」は3seed中2回以上の `exact_whole_set_match`。[per-problem.csv](run-superpc/per-problem.csv) のBASEは38/53問、未解決15問であり、[per-run.csv](run-superpc/per-run.csv) と全1113組の開始・終了receiptの問題ID・seed・構成・入力hash・終了状態を照合した。各raw `result.json` の現存サイズも全1113件で終了receiptの `files.result.json.size_bytes` と一致した。各問題・構成の正解seed数と多数決をCSVから再集計し、per-problem.csvと一致した。

「主因」は、当該問題の3seed中2回以上に同じ観測上の失敗があることを指す。FSIZE切断のある11問すべてをFSIZE単独の失敗とは数えない。切断された出力から独立参照集合との完全一致は確定できず、上限を外せば解けるという反実仮想はここでは判定しない。

- **exit1 / FSIZE切断（231枠）**：reason=`nonzero_exit`、終了receiptの `exit_code=1`、rawとreceiptのサイズがともに **2,900,000 bytes**、CSVの `descriptor_error` が全件 `JSONDecodeError`。さらに全231枠の保存済みstderrに `OSError: [Errno 27] File too large` を確認した。[measurement_launch.py](measurement_launch.py) は `resource.setrlimit(resource.RLIMIT_FSIZE, (2_900_000, 2_900_000))` を設定している。例：[0152.end.json](run-superpc/receipts/0152.end.json) と `/tmp/mechanism-S8-superpc-raw-2_b72k5n/0152/stderr.log.0000`。サイズ一致だけで原因を推定した分類ではない。
- **exit2 / artifact_missing（89枠）**：reason=`nonzero_exit`、終了receiptの `exit_code=2`。全89件のrawは有効JSONで `status=engine_error`、`error.code=artifact_missing`、`error.message="worker exited with code 1 without an artifact"`、`diagnostics=null`。保存stderrは全89件で内容なし。これは **result.json自体の欠落ではなくworker artifactの欠落**。worker終了の詳細原因は記録なし。FSIZE切断とは別に数える。例：[0578.end.json](run-superpc/receipts/0578.end.json) と `/tmp/mechanism-S8-superpc-raw-2_b72k5n/0578/result.json`。
- **solver_no_answer_found**：正常終了コード0の公開結果が `no_answer_found`。外側のtimeoutとは区別する。AIME-2014-II-10のBASE 3件は内部 `termination_reason=time_limit_reached` を記録している。
- **時間切れ列**：S8 per-runの外側timeout状態・reasonの枠数。現行1113枠のstateは全て `completed` で、timeout枠は0。内部の `time_limit_reached` は元のreasonどおり `solver_no_answer_found` に数え、二重計上しない。
- **answer_set_mismatch / 成功**：それぞれ元CSVの同名reason / `exact_whole_set_match`。分類の優先順位は既存の [measurement_grade.py](measurement_grade.py) の記録に従う。

## BASE未解決15問：3seedとresult.jsonサイズ

各セルはreason、result.jsonのバイト数、終了receiptのqueue_index。全セルのreason原文・exit_code・サイズ・rawパス・hash・開始/終了receiptは [全1113枠の照合CSV](base-failure-review-slots.csv) に収録した。

| 問題 | seed 601 | seed 602 | seed 603 |
| --- | --- | --- | --- |
| HMMT-2015-FEB-GUTS-24 | nonzero_exit(exit2：artifact_missing)<br>930 bytes<br>[q0583](run-superpc/receipts/0583.end.json) | nonzero_exit(exit2：artifact_missing)<br>930 bytes<br>[q0594](run-superpc/receipts/0594.end.json) | nonzero_exit(exit2：artifact_missing)<br>930 bytes<br>[q0605](run-superpc/receipts/0605.end.json) |
| HMMT-2019-FEB-GUTS-17 | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q0875](run-superpc/receipts/0875.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q0886](run-superpc/receipts/0886.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q0897](run-superpc/receipts/0897.end.json) |
| AIME-2018-I-15 | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q1015](run-superpc/receipts/1015.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q1026](run-superpc/receipts/1026.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q1037](run-superpc/receipts/1037.end.json) |
| AIME-2001-II-13 | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q1085](run-superpc/receipts/1085.end.json) | exact_whole_set_match<br>1,914,698 bytes<br>[q1096](run-superpc/receipts/1096.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q1107](run-superpc/receipts/1107.end.json) |
| HMMT-2024-FEB-GEO-10 | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q1225](run-superpc/receipts/1225.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q1236](run-superpc/receipts/1236.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q1259](run-superpc/receipts/1259.end.json) |
| AIME-2015-II-11 | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q1587](run-superpc/receipts/1587.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q1598](run-superpc/receipts/1598.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q1609](run-superpc/receipts/1609.end.json) |
| AIME-2007-II-15 | nonzero_exit(exit2：artifact_missing)<br>929 bytes<br>[q1739](run-superpc/receipts/1739.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q1750](run-superpc/receipts/1750.end.json) | nonzero_exit(exit2：artifact_missing)<br>928 bytes<br>[q1761](run-superpc/receipts/1761.end.json) |
| HMMT-2021-FEB-GEO-09 | nonzero_exit(exit2：artifact_missing)<br>929 bytes<br>[q2451](run-superpc/receipts/2451.end.json) | nonzero_exit(exit2：artifact_missing)<br>929 bytes<br>[q2462](run-superpc/receipts/2462.end.json) | nonzero_exit(exit2：artifact_missing)<br>929 bytes<br>[q2473](run-superpc/receipts/2473.end.json) |
| JMO-2020-PRE-11 | nonzero_exit(exit2：artifact_missing)<br>929 bytes<br>[q2521](run-superpc/receipts/2521.end.json) | nonzero_exit(exit2：artifact_missing)<br>930 bytes<br>[q2532](run-superpc/receipts/2532.end.json) | nonzero_exit(exit2：artifact_missing)<br>929 bytes<br>[q2555](run-superpc/receipts/2555.end.json) |
| HMMT-2021-FEB-GEO-06 | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q2743](run-superpc/receipts/2743.end.json) | exact_whole_set_match<br>2,399,045 bytes<br>[q2754](run-superpc/receipts/2754.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q2765](run-superpc/receipts/2765.end.json) |
| AIME-2014-II-10 | solver_no_answer_found<br>1,806,173 bytes<br>[q2813](run-superpc/receipts/2813.end.json) | solver_no_answer_found<br>1,891,942 bytes<br>[q2824](run-superpc/receipts/2824.end.json) | solver_no_answer_found<br>1,808,386 bytes<br>[q2835](run-superpc/receipts/2835.end.json) |
| JMO-2023-PRE-06 | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q3385](run-superpc/receipts/3385.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q3396](run-superpc/receipts/3396.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q3419](run-superpc/receipts/3419.end.json) |
| HMMT-2017-FEB-GUTS-02 | exact_whole_set_match<br>1,831,716 bytes<br>[q3467](run-superpc/receipts/3467.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q3478](run-superpc/receipts/3478.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q3489](run-superpc/receipts/3489.end.json) |
| JMO-2016-PRE-05 | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q3537](run-superpc/receipts/3537.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q3548](run-superpc/receipts/3548.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q3559](run-superpc/receipts/3559.end.json) |
| HMMT-2023-FEB-GUTS-03 | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q3607](run-superpc/receipts/3607.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q3618](run-superpc/receipts/3618.end.json) | nonzero_exit(exit1：FSIZE切断)<br>2,900,000 bytes<br>[q3629](run-superpc/receipts/3629.end.json) |

15問45枠の内訳は **FSIZE切断28、artifact_missing 11、solver_no_answer_found 3、成功3**。成功3枠はAIME-2001-II-13（602）、HMMT-2021-FEB-GEO-06（602）、HMMT-2017-FEB-GUTS-02（601）で、各1/3のため問題単位では未解決。これら15問にはanswer_set_mismatch・外側timeoutはない。

BASE全53問159枠ではFSIZE切断28、artifact_missing 12、solver_no_answer_found 4、成功115。未解決15問以外にもAIME-2016-I-15の601がartifact_missing、AIME-2005-I-01の602がsolver_no_answer_foundだが、それぞれ残る2seedは成功し、問題単位では解決している。

## 同じ問題の過去記録との照合

参照元は以下。問題IDで対応づけ、該当する7b 9問、unseen-2/a 2問、unseen-2/b 4問、S6 1問について、保存済みの過去入力SHA-256とS8の `input_sha256` が **全て一致** した。S1/S3はそれぞれ全12問を確認し、今回の未解決15問に該当する問題はなく、表は「記録なし」とした。空欄を成功・失敗として補完していない。

- **7b**：[per-problem.csv](../../run-7b/per-problem.csv)、[per-run.csv](../../run-7b/per-run.csv)、[answer.md](../../run-7b/answer.md)、[pre-run-hashes.json](../../run-7b/pre-run-hashes.json)。BASEは全体69/72問、205/216枠完全一致、seed 401–403。今回の15問との共通9問は全て3/3完全一致。S8と7bは同じsource_hash `sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3`。
- **開発外34問**：unseen-2/aの [per-problem.csv](../../../unseen-2/a/per-problem.csv)、[per-run.csv](../../../unseen-2/a/per-run.csv)、[answer.md](../../../unseen-2/a/answer.md) と、unseen-2/bの [per-problem.csv](../../../unseen-2/b/per-problem.csv)、[answer.md](../../../unseen-2/b/answer.md)。入力hashは各 `execution/campaign-manifest.json` の `dsl_file_hash` で照合。seed 301–305、a=80正解・5失敗、b=81正解・3不正答・1保存欠測で、合計 **161/170正解、8観測失敗、1保存欠測**。161/170を「残り9枠すべてsolver失敗」とは解釈しない。
- **S1 / S3**：[S1 per-problem.csv](../S1/per-problem.csv)、[S1 answer.md](../S1/answer.md)、[S3 per-problem.csv](../S3/run/per-problem.csv)、[S3 answer.md](../S3/run/answer.md)。S1のBASE、S3のT2は候補精密化・数値検証の記録であり、完成solverの厳密答え集合の成功件数とは別の指標。今回の15問との共通問題は0問。
- **S6**：[per-problem.csv](../S6/run/per-problem.csv)、[per-run.csv](../S6/run/per-run.csv)、[answer.md](../S6/run/answer.md)、[README](../S6/README.md)。BASE相当の比較は未設定モードT2、seed 501–503。source_hashは `sha256:add5afaf829806ca3cbd11fb07b69d956102752e1c6738b0630581a3ceb121eb`（切替実装）。今回の共通問題はAIME-2007-II-15のみで3/3完全一致。T1の結果をBASEとして代用していない。

unseen-2の凍結元は60db4b6、source_hashは `sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5`。S8/7bのスイッチ実装とソース全体が同一バイトという意味ではない。凍結元から既存patch・new-switches.patchを適用した履歴は [reconstruction.json](patches/reconstruction.json)、スイッチOFF経路の既存比較記録は [switches/README.md](../../switches/README.md) にある。過去と今回ではseed、実行経路（7bはEngineRunner直接、S8はCLI）、並列数、保存制限等の条件が異なる。ここでは過去成功と今回の観測原因を対応づけ、これらの差の因果効果を割り当てない。

| 問題 | 7b BASE（401–403） | 開発外34問（301–305） | S1 BASE | S3 T2 | S6 T2（501–503） | 過去との対応 | 今回BASEの観測原因 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HMMT-2015-FEB-GUTS-24 | 記録なし | b：4/5正解、欠測1（301欠測、302–305正解） | 記録なし | 記録なし | 記録なし | 以前成功→今回未解決 | artifact_missing 3/3（worker終了原因：記録なし） |
| HMMT-2019-FEB-GUTS-17 | 記録なし | b：5/5正解、欠測0（301–305全正解） | 記録なし | 記録なし | 記録なし | 以前成功→今回未解決 | FSIZE切断3/3 |
| AIME-2018-I-15 | 401/402/403：全3回完全一致（3/3）、solved=True | 記録なし | 記録なし | 記録なし | 記録なし | 以前成功→今回未解決 | FSIZE切断3/3 |
| AIME-2001-II-13 | 記録なし | a：5/5正解、欠測0（301–305全正解） | 記録なし | 記録なし | 記録なし | 以前成功→今回未解決 | FSIZE切断2/3、成功1/3 |
| HMMT-2024-FEB-GEO-10 | 401/402/403：全3回完全一致（3/3）、solved=True | 記録なし | 記録なし | 記録なし | 記録なし | 以前成功→今回未解決 | FSIZE切断3/3 |
| AIME-2015-II-11 | 401/402/403：全3回完全一致（3/3）、solved=True | 記録なし | 記録なし | 記録なし | 記録なし | 以前成功→今回未解決 | FSIZE切断3/3 |
| AIME-2007-II-15 | 401/402/403：全3回完全一致（3/3）、solved=True | 記録なし | 記録なし | 記録なし | T2：501/502/503 全3回完全一致（3/3）、solved=True | 以前成功→今回未解決 | artifact_missing 2/3＋FSIZE切断1/3（混在） |
| HMMT-2021-FEB-GEO-09 | 401/402/403：全3回完全一致（3/3）、solved=True | 記録なし | 記録なし | 記録なし | 記録なし | 以前成功→今回未解決 | artifact_missing 3/3（worker終了原因：記録なし） |
| JMO-2020-PRE-11 | 401/402/403：全3回完全一致（3/3）、solved=True | 記録なし | 記録なし | 記録なし | 記録なし | 以前成功→今回未解決 | artifact_missing 3/3（worker終了原因：記録なし） |
| HMMT-2021-FEB-GEO-06 | 401/402/403：全3回完全一致（3/3）、solved=True | 記録なし | 記録なし | 記録なし | 記録なし | 以前成功→今回未解決 | FSIZE切断2/3、成功1/3 |
| AIME-2014-II-10 | 記録なし | a：0/5正解、欠測0（301–305全失敗、厳密同定） | 記録なし | 記録なし | 記録なし | 過去も0/5、今回も0/3 | solver_no_answer_found 3/3（内部終了理由time_limit_reached） |
| JMO-2023-PRE-06 | 401/402/403：全3回完全一致（3/3）、solved=True | 記録なし | 記録なし | 記録なし | 記録なし | 以前成功→今回未解決 | FSIZE切断3/3 |
| HMMT-2017-FEB-GUTS-02 | 記録なし | b：5/5正解、欠測0（301–305全正解） | 記録なし | 記録なし | 記録なし | 以前成功→今回未解決 | FSIZE切断2/3、成功1/3 |
| JMO-2016-PRE-05 | 401/402/403：全3回完全一致（3/3）、solved=True | 記録なし | 記録なし | 記録なし | 記録なし | 以前成功→今回未解決 | FSIZE切断3/3 |
| HMMT-2023-FEB-GUTS-03 | 記録なし | b：5/5正解、欠測0（301–305全正解） | 記録なし | 記録なし | 記録なし | 以前成功→今回未解決 | FSIZE切断3/3 |

「以前は解けていたのに今回落ちた問題」は表の **14問**（7bで9問、開発外で5問、S6の1問は7bと重複）。唯一その分類に入らないAIME-2014-II-10は、unseen-2/aでも0/5、今回も0/3。過去のanswer.mdは厳密同定段階での期限到達を報告し、今回のrawも `no_answer_found / time_limit_reached` を記録している。今回の詳細な内部原因を過去の診断だけで補完していない。

## 構成×原因の枠数

単位は問題数ではなくseed実行枠。各構成53問×3seed＝159枠。成功は厳密答え集合の完全一致。

| 構成 | exit1 FSIZE切断 | exit2 artifact_missing | 時間切れ（外側） | solver_no_answer_found | answer_set_mismatch | 成功 | 合計 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| N | 44 | 14 | 0 | 6 | 0 | 95 | 159 |
| C1 | 29 | 12 | 0 | 31 | 6 | 81 | 159 |
| C2 | 44 | 15 | 0 | 7 | 6 | 87 | 159 |
| C3 | 29 | 12 | 0 | 7 | 0 | 111 | 159 |
| C4 | 29 | 12 | 0 | 4 | 0 | 114 | 159 |
| C5 | 28 | 12 | 0 | 4 | 0 | 115 | 159 |
| BASE | 28 | 12 | 0 | 4 | 0 | 115 | 159 |
| 合計 | 231 | 89 | 0 | 63 | 12 | 718 | 1113 |

## nonzero_exit 320枠の問題別集中

**25/53問**にnonzero_exitがあり、残る28問は0枠。下表は0以外の全25問。BASE未解決15問のうち14問に **271/320枠（84.69%）** が集中し、AIME-2014-II-10はnonzero_exit 0枠。全7構成・全3seedでnonzero_exitだった問題は8問、計168/320枠（52.50%）。BASEが解決した問題にも計49枠のnonzero_exitがあり、BASE未解決だけで320枠を説明していない。

| 問題 | BASE判定 | N | C1 | C2 | C3 | C4 | C5 | BASE | exit1 | exit2 | nonzero合計 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AIME-2015-II-11 | 未解決 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 21 | 0 | 21 |
| AIME-2018-I-15 | 未解決 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 21 | 0 | 21 |
| HMMT-2015-FEB-GUTS-24 | 未解決 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 21 | 21 |
| HMMT-2019-FEB-GUTS-17 | 未解決 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 14 | 7 | 21 |
| HMMT-2021-FEB-GEO-09 | 未解決 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 21 | 21 |
| HMMT-2023-FEB-GUTS-03 | 未解決 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 21 | 0 | 21 |
| JMO-2016-PRE-05 | 未解決 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 21 | 0 | 21 |
| JMO-2020-PRE-11 | 未解決 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 18 | 21 |
| AIME-2007-II-15 | 未解決 | 3 | 1 | 3 | 3 | 3 | 3 | 3 | 11 | 8 | 19 |
| HMMT-2024-FEB-GEO-10 | 未解決 | 3 | 2 | 2 | 3 | 3 | 3 | 3 | 19 | 0 | 19 |
| JMO-2023-PRE-06 | 未解決 | 3 | 0 | 3 | 3 | 3 | 3 | 3 | 18 | 0 | 18 |
| HMMT-2021-FEB-GEO-06 | 未解決 | 3 | 3 | 3 | 2 | 2 | 2 | 2 | 17 | 0 | 17 |
| AIME-2001-II-13 | 未解決 | 3 | 2 | 3 | 2 | 2 | 2 | 2 | 16 | 0 | 16 |
| HMMT-2017-FEB-GUTS-02 | 未解決 | 3 | 0 | 3 | 2 | 2 | 2 | 2 | 9 | 5 | 14 |
| HMMT-2025-FEB-GEO-08 | 解決 | 3 | 3 | 3 | 1 | 1 | 0 | 0 | 11 | 0 | 11 |
| AIME-2016-I-15 | 解決 | 1 | 0 | 2 | 1 | 1 | 1 | 1 | 3 | 4 | 7 |
| HMMT-2017-FEB-GEO-01 | 解決 | 3 | 2 | 2 | 0 | 0 | 0 | 0 | 7 | 0 | 7 |
| AIME-2012-I-12 | 解決 | 3 | 1 | 1 | 0 | 0 | 0 | 0 | 5 | 0 | 5 |
| HMMT-2017-FEB-GEO-10 | 解決 | 3 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 5 | 5 |
| JMO-2018-PRE-06 | 解決 | 3 | 1 | 1 | 0 | 0 | 0 | 0 | 5 | 0 | 5 |
| HMMT-2023-FEB-GEO-04 | 解決 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 3 | 0 | 3 |
| HMMT-2020-FEB-GUTS-13 | 解決 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 2 | 0 | 2 |
| HMMT-2023-FEB-GEO-02 | 解決 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 2 |
| AIME-2022-I-11 | 解決 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| HMMT-2025-FEB-GEO-04 | 解決 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |

| 合計 | N | C1 | C2 | C3 | C4 | C5 | BASE | exit1 | exit2 | nonzero合計 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 全25問 | 58 | 41 | 59 | 41 | 41 | 40 | 40 | 231 | 89 | 320 |

## 読み取り範囲と記録の限界

今回の作業は既存CSV、JSON、receipts、過去のanswer.md・manifest、計測コードの静的参照、rawのサイズ取得、nonzero_exitの保存stderrおよび小さいexit2 JSONの読取りのみ。AIME-2014-II-10のBASE 3件はrawのstatus・termination_reasonも参照した。231個の大きい切断JSONを修復・再採点しておらず、不正JSONの証拠は既存CSVのJSONDecodeErrorと実サイズ・stderrの一致による。solverをimportしていない。

artifact_missing 89枠のworker側の詳細原因は記録なし。FSIZE切断231枠は保存失敗を直接確認できるが、保存失敗がなかった場合の独立採点結果は記録なし。今回の原因表は観測された終了・保存・採点結果の分類であり、未観測のsolver性能や回復問題数を推測していない。

新規出力は本Markdownと [base-failure-review-slots.csv](base-failure-review-slots.csv) のみ。CSVは全1113枠を含み、`BASE_unsolved_problem=True` かつ `configuration=BASE` が冒頭の15問45枠。rawや既存成果物は変更していない。
