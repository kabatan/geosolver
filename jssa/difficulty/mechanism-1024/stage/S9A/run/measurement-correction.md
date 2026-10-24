# 初期残差の評価モード修正（探索・精密化の再実行なし）

本計測開始直後の最初の6問で initial-metrics.json の全候補が HighPrecisionContaminationError('high_precision_mode is required at hp_contract:compute_residual_vector_high_precision') となることを確認した。元スクリプトは固定したまま保持し、このファイルと correction.py を次の数値評価前に measurement-correction-hashes.json に固定する。

変更は保存初期候補の evaluate_hp_residual 呼出しを high_precision_mode 内に置く点のみ。x_floatの正確な二進値からの変換、通常evaluator、180dps、L2ノルム、全候補中央値、分母、予測閾値は不変。元initial-metrics.jsonをinitial-metrics.original.jsonとして保持し、修正測定をinitial-metrics.jsonに保存。元工程の開始終了receiptも保持する。修正測定は全候補あり問題につき一度、最大6並列・各1コア・内部1スレッド、90秒外枠。探索・精密化・最終検証は再実行しない。残差修正処理は元campaign完了後に実施し、同時実行上限を守る。全新規ジョブは/tmp空き6GiB以上を確認する。
