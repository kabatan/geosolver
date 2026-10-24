# 参照値評価の型制約の修復

最初の表示変換の修復後の監査で、無理数を含む5問の参照値評価が None となっていることを確認した。凍結された `_eval_exact_to_mpf` を high_precision_mode 内で呼ぶと、SymPy Floatからmpfへの変換が型制約に阻まれて失敗し、関数が None を返すためである。これは参照値の変更ではなく、参照式の読み込み経路の不備である。

worker.py と事前hashは変更しない。repair_references.py は参照式の評価行だけを high_precision_mode の直前に移し、同じ700桁・同じ関数で評価する。以前に修復した表示変換も維持する。該当する保存済み座標の measure 工程のみを1並列で実行する。

探索・精密化・最終検証は再実行せず、座標・参照式・閾値・判定ルールは変えない。旧測定と暫定集計は/tmpに退避する。差分、対象、スクリプトhash、修復開始時刻は修復前に reference-repair-hashes.json に保存する。修復後に元の analyze.py で同じ規則を適用する。
