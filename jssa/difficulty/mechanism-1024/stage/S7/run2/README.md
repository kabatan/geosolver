# 事前登録14・段階(2)

対象は固定済みS7/classification.csvのstatus=okの266問のみ。分類・参照解は読み取り専用。seed 0の主探索候補をS1と同じ178秒budget・180秒外枠で一度だけ保存し、同じ候補集合から各90秒のBASE/raw精密化を一度ずつ行う。再探索・再精密化・別seed・追加除外・最終検証・commit/pushは行わない。

S1のprepare.py / driver.py / worker.py / analyze.pyの手順を流用する。BASEは `/tmp/mechanism-7b-lkdjle5l/final/src` (BASE1) のコピーを無変更で使う。S7 READMEに記録されたとおり、既存のNO_RESIDUAL_REWRITEとS3_TANGENCY_MODE=T1の併用ではT1も迂回する。そのためrawは `GEOSOLVER_ABLATE_NO_RESIDUAL_REWRITE=1` と新しい `GEOSOLVER_S7_RAW_T1=1` を設定し、raw_switch.pyをプロセス内で適用する。S7段階(1)のsigma-details.jsonに固定済みの接する条件・円円分枝を使い、元残差のその行だけを同じT1式に置換する。距離0の座標差・接点式・半径補助式は適用しない。T1の評価精度は各精密化段階のdpsに従う。T1行があるraw問題では不一致な既存解析ヤコビ行列を使わず、既存の数値微分を使う。他の問題とBASEの解析微分方針は変更しない。元ソースは変更しない。

目標値は元IRの評価器で700桁評価し、段階(1)のreference.jsonの `answer`（保存参照座標で700桁再評価した値）への絶対誤差からD=min(600,-log10(error))を測定する。数学的独立正答へのすり替えは行わない。通過状態で選別せず、返却候補中で絶対誤差が最小のものを使う。未返却候補・評価不能候補は理由付き欠測。残差はS1の元IRと保存した全初期候補から作る固定除数で評価する。

W1/W2の母集団は固定分類のbase非特異/特異全問とし、D_base欠測を成功に数えない。W2はこの固定分母で非特異成功率−特異成功率>=0.20。W3/W4の対象は段階(1)で固定した接する条件なしのW3_target=Trueの5問。W4は符号付きD_base−D_raw>=40が固定5問の半数以上（3問以上）。欠測を除いた参考率と欠測がすべて成功の場合の範囲も併記し、欠測による判定の感度を明示する。閾値・分類は変更しない。

最大10 worker、各工程CPU affinity 1コア、OMP/BLAS等1スレッド。工程は各問題内で逐次、開始receiptによって再試行を禁止する。生ログ・候補・座標・ソースコピーはリポジトリ外の/tmp、各ファイル3,000,000bytes未満。workerはRLIMIT_FSIZE=2,999,999、監督側はログのサイズ上限とprocess group timeoutを監視する。progress.mdは追記。

実行: `/home/kabatan/work/solver/.venv/bin/python -B prepare.py` → `driver.py` → `analyze.py`。実行前hash、全生データhash、終了後hashとauditを保存する。

## 2026-10-24 環境事故からの再開

2026-10-24T07:28:46.777718Z時点でproblem_doneは163/266問。/tmp容量超過とsandbox障害によりdriverが中断した。完了済み163問は結果・全生ファイルを保持し、再実行しない。実行ディレクトリがあるがproblem_doneのない8問は AIME-2025-II-06, AIME-2025-II-14, HMMT-2009-FEB-GEO-01, HMMT-2009-FEB-GEO-09, HMMT-2013-FEB-GEO-04, HMMT-2024-FEB-GEO-09, JMO-2015-PRE-02, JMO-2017-PRE-10。残り95問は未着手。

この8問は「中断=結果に数えず記録」とし、生ファイルをscratchのinterrupted/attempt-0/へ無変更で退避し、問題の最初から各1回だけ実行する。これは失敗の再試行ではなく中断の再開である。記録済みの失敗(returncode≠0)や外枠タイムアウト工程は再試行禁止。元の失敗3工程（AIME-2008-II-11 RAW精密化、HMMT-2023-FEB-GEO-07 主探索、JMO-2011-PRE-11 RAW精密化）はすべて完了済み問題内にあり、そのまま欠測として保持する。90秒の精密化budgetで正常返却した結果は元の設計どおり扱う。

最小変更: driver.pyに--resume、完了skip、中断原本退避とhash inventory、二重起動lock、1回限りの再開receipt、各工程開始前の空き6 GiB条件を追加。元の10 streamを完了問題だけ除いて使い、CPU 22〜31への割当を維持する。6 GiB未満なら新規工程を開始せず記録・停止する。analyze.pyは中断旧attemptを集計から除き、完了163問・退避8問・元イベントprefixのhash一致と有効attemptの工程重複なしを監査し、再開事情をanswer.mdに記載する。worker.py/raw_switch.py、ソース、探索178秒/外枠180秒、各精密化90秒/外枠98秒、固定分類・参照値・閾値・W1〜W4判定式は変更しない。結果を見た設計変更は行わない。

再開コマンド: `/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/mechanism-1024/stage/S7/run2/driver.py --resume`。完了後に同じPythonでanalyze.pyと報告用annotate_failures.pyを実行する。元pre-run-hashes.jsonと変更前3ファイルはresume-history/に保存し、現行pre-run-hashes.jsonの更新履歴・旧新SHA-256はhash-update-history.jsonに保存する。scratch/manifest.jsonは初回のまま保持する。scratch/resume-started.jsonに完了・中断の全ファイルhashと元イベントprefix hashを記録する。git commit/pushは行わない。

### 完了後の報告修正（計測の再実行なし）

2026-10-24T07:50:29.942627Zに266問がproblem_doneとなった。最初のanalyze.pyは保存済みの長い例外全文の反復によりper-problem.csvの3 MB制約で停止した。analyze.pyの報告表示だけを修正し、全例外の原文は各measure.jsonに保持したまま、問題表には例外型・件数・生データ参照先・SHA-256、候補表には例外型とcase_id基準のerror_detailsを載せる。再集計は保存済みJSONの読み取りだけであり、候補評価・探索・精密化を再実行しない。元のCSV上限エラーは実験工程の失敗ではない。

終了receiptでOS Threads=2を2件観測した（HMMT-2011-equilateral-hexagonとHMMT-2018-FEB-GEO-10のBASE精密化終了時）。CPU affinityはいずれも固定CPU31の1コア、OMP/BLAS等の環境設定は1のまま。追加スレッドの役割はreceiptからは不明。analyze.pyは逸脱をassertで報告生成ごと止める代わりに、thread_violationsを保持しexecution_contract_status=violationsと明示して報告を生成する。条件を満たした扱いにはせず、再実行しない。判定式・分母・欠測扱いは変えない。

目標評価のHighPrecisionContaminationError等によりD_base/D_rawは全266問で欠測。W1/W2/W4の形式的な外れ判定から精密化性能の実証結論は出さない。評価器やworkerの修正・再評価はしない。報告修正前のanalyze.py/README/manifest/hash履歴はresume-history/reporting-v1/、更新履歴はhash-update-history.jsonに追記する。
