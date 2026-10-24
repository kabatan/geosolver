HMMT-2023-FEB-GEO-07 の環境欠測補完を完了。D_base=484.53438515817004、D_raw=160.89844175205795。

W判定の旧→新: W1: 当たり→当たり、W2: 外れ→外れ、W3: 当たり→当たり、W4: 当たり→当たり。変更した判定: なし。

元のErrno 122は interrupted_env_quota として interrupted-env-quota/ に元ログ・receipt・0バイトinitial.pkl・SHA-256を保存。旧answer.mdは answer-before-quota-rerun.md に保存。ユーザーの明示指示によりこの1問のみ、seed 0の主探索1回→候補保存→固定scales→BASE精密化90秒→RAW精密化90秒→保存refined.pklから両measureを実行した。1枠、taskset -c 31、内部OMP/BLAS等1スレッド、全工程foregroundでwait。各runtime開始終了receiptはThreads=1・affinity=[31]。ただし実行中のsearchとrefine.BASEではOS Threads=2を観測した。新規補完の実行条件監査もviolationsとし、内部1スレッド条件の完全充足は主張しない。追加threadの役割は観測receiptのみでは不明。再探索・再精密化は追加しない。他265問の生ファイル・集計行、solverソース、driver.py、worker.py、analyze.py、入力・参照値・分類・分母・閾値・構成は不変。元events.jsonlは変更せず、新工程は対象run内の専用receiptに記録した。旧resume-started.jsonは保存し、completed_files内の当該5原本の参照先だけをscratchの事故退避先に移し、hash値と他フィールドは不変。analyze.pyを無変更で実行し、旧報告と同じannotate_failures.pyで既存例外詳細を追記して再集計した。下記の「測定修正」「再実行なし」「no_retries」および元イベント由来の工程数は先行campaign/measure修正時点の履歴を述べる。今回の1問の例外は本補完記録とquota-rerun-audit.jsonが示す。元の2件のthread逸脱は保持。

