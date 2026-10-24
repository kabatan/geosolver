# S7/run2 measure工程の修正

旧結果は「測定不具合による全欠測」（266問のD_base・D_raw、計532問題×構成）。精密化性能を測定した結果ではない。旧answer.mdはanswer-measure-failed.mdに無変更で保存した。変更前worker/analyze/manifest/集計結果はresume-history/measure-failed/に保存する。

## 原因と比較

保存済み全measure JSONを調べると、answer_errorは `float(mpf) in HP mode` 型のHighPrecisionContaminationErrorが6,445候補、nonfinite/unavailable answerが58候補であり、residual_errorは0件だった。今回のS7/run2では `high_precision_mode is required at hp_contract:...` 型ではない。AIME-2006-I-01 BASEの例外も `float(mpf) in HP mode` である。目標値計算は成功しても、同じtry節内の `error_digits=float(digits)` が失敗するため、row.update全体が実行されずanswer/absolute_error/Dが保存されなかった。

S1/worker.pyのmeasureも、700dpsとhigh_precision_modeで候補ループ全体を囲み、内側でfloat(digits)を実行する同じ境界問題を持つ。S7/run2の差は主に参照値を保存reference_answerから読み込む点、固定scale欠測時の扱い、error_digits_exact追加と指数表記・receiptであり、この原因を解消していない。

一方S9A/run/measurement-correction.mdとcorrection.pyは、evaluate_hp_residualをhigh_precision_mode外で呼んでいたためhp_contractに拒否された事例である。その修正は評価呼出しをモード内に置くもの。S7/run2では既に目標・残差呼出しがモード内なので、単にモードを追加してもfloat変換例外は解消しない。共通する正しい境界は「高精度評価をモード内、JSON用float変換をモード外」に置くこと。

修正workerはmeasureの外側をmp.workdps(700)のみにし、evaluate_hp_residualとevaluate_answer_hpの各呼出しを明示的なhigh_precision_modeで囲む。error/digits計算は同じ700dpsのまま、float(digits)はモード外の出力境界で実行する。solverソース・guardの無効化や変更はしない。measureのruntime receiptだけはmeasure-corrected.*名で新規保存し、元receiptを上書きしない。search/scales/refineのコードと動作は不変。

## 固定条件と手順

探索・精密化は一切再実行しない。入力、分類、参照値、初期候補、scales、refined.pkl、判定式、W1〜W4の閾値と分母を変更しない。refine終了receiptが正常(returncode=0かつreasonなし)で保存refined.pklがある構成のみmeasureする。失敗refineおよび探索失敗は欠測のまま。元*.measure.jsonは*.measure.original.jsonにrenameして保持し、同じ元パスに新測定を出す。元ログ・開始終了receipt・events.jsonlを保持する。

measure_correction.pyは測定専用でworkerをmeasureモードでしか呼ばない。実行前に全元ファイルのSHA-256 inventoryをscratch内へ保存し、終了後は旧measureの.original.jsonへの移動を対応付けて照合する。保存座標のhash不変、全子プロセスwait、各出力の存在と正常終了を直接確認する。analyze.pyの変更は修正測定の監査・原本照合・説明だけであり、W判定コードは変更しない。scratch/manifest.jsonは元のまま、現行pre-run-hashes.jsonは変更コードのhashを更新し、旧新hashと補助スクリプト・本noteのhashを数値評価前にhash-update-history.jsonへ追記する。

3問は入力順の先頭 AIME-2006-I-01、AIME-2006-II-01、AIME-2006-II-06（各BASE/RAW）。桁数が有限かつ上限600以下であり、HP汚染例外が解消することだけ確認する。W値・判定はこの段階で見ない。その後全266問×2構成を走査し、3問の完了measureは再実行しない。最大8並列、CPU22〜29に固定、各1コア、元のOMP/BLAS等の内部1スレッド設定を適用。新測定は開始・終了receiptと実行中/proc監視でThreads/affinityを確認する。各開始前・実行中に/tmp空き6GiB以上を検査し、未満なら停止。新出力はすべて既存scratchまたは本workspace（いずれも/tmp）に限定する。

## 旧OS Threads=2の監査

HMMT-2011-equilateral-hexagonとHMMT-2018-FEB-GEO-10のrefine.BASE.runtime-end.jsonでThreads=2。元receiptとviolations判定をそのまま保持する。双方のrefine.BASE.logは空で、thread ID/名前/stackの記録はないため原因は確定できず、不明。

凍結ソースruntime/symbolic.pyは外部symbolic workerのstdoutを読むdaemon threadを作り、close時のjoin待ちは0.2秒である。runtime/deadline.pyのruntime_session終了後でもreaderが残る可能性はコード上ある。ただし当該2件がこのthreadだったという証拠はなく、仮説にとどまる。環境変数でBLAS等を1に設定するだけでは、このPython threadの不存在を保証しない。元の内部1スレッド条件を充足したとは扱わず、再精密化で置換もしない。今回のmeasureはruntime_sessionやSymbolicClientを起動せず、新たな実測監査を別に報告する。
