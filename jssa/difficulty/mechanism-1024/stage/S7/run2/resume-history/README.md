# 事前登録14・段階(2)

対象は固定済みS7/classification.csvのstatus=okの266問のみ。分類・参照解は読み取り専用。seed 0の主探索候補をS1と同じ178秒budget・180秒外枠で一度だけ保存し、同じ候補集合から各90秒のBASE/raw精密化を一度ずつ行う。再探索・再精密化・別seed・追加除外・最終検証・commit/pushは行わない。

S1のprepare.py / driver.py / worker.py / analyze.pyの手順を流用する。BASEは `/tmp/mechanism-7b-lkdjle5l/final/src` (BASE1) のコピーを無変更で使う。S7 READMEに記録されたとおり、既存のNO_RESIDUAL_REWRITEとS3_TANGENCY_MODE=T1の併用ではT1も迂回する。そのためrawは `GEOSOLVER_ABLATE_NO_RESIDUAL_REWRITE=1` と新しい `GEOSOLVER_S7_RAW_T1=1` を設定し、raw_switch.pyをプロセス内で適用する。S7段階(1)のsigma-details.jsonに固定済みの接する条件・円円分枝を使い、元残差のその行だけを同じT1式に置換する。距離0の座標差・接点式・半径補助式は適用しない。T1の評価精度は各精密化段階のdpsに従う。T1行があるraw問題では不一致な既存解析ヤコビ行列を使わず、既存の数値微分を使う。他の問題とBASEの解析微分方針は変更しない。元ソースは変更しない。

目標値は元IRの評価器で700桁評価し、段階(1)のreference.jsonの `answer`（保存参照座標で700桁再評価した値）への絶対誤差からD=min(600,-log10(error))を測定する。数学的独立正答へのすり替えは行わない。通過状態で選別せず、返却候補中で絶対誤差が最小のものを使う。未返却候補・評価不能候補は理由付き欠測。残差はS1の元IRと保存した全初期候補から作る固定除数で評価する。

W1/W2の母集団は固定分類のbase非特異/特異全問とし、D_base欠測を成功に数えない。W2はこの固定分母で非特異成功率−特異成功率>=0.20。W3/W4の対象は段階(1)で固定した接する条件なしのW3_target=Trueの5問。W4は符号付きD_base−D_raw>=40が固定5問の半数以上（3問以上）。欠測を除いた参考率と欠測がすべて成功の場合の範囲も併記し、欠測による判定の感度を明示する。閾値・分類は変更しない。

最大10 worker、各工程CPU affinity 1コア、OMP/BLAS等1スレッド。工程は各問題内で逐次、開始receiptによって再試行を禁止する。生ログ・候補・座標・ソースコピーはリポジトリ外の/tmp、各ファイル3,000,000bytes未満。workerはRLIMIT_FSIZE=2,999,999、監督側はログのサイズ上限とprocess group timeoutを監視する。progress.mdは追記。

実行: `/home/kabatan/work/solver/.venv/bin/python -B prepare.py` → `driver.py` → `analyze.py`。実行前hash、全生データhash、終了後hashとauditを保存する。
