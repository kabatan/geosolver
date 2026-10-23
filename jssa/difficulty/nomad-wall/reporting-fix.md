# 集計時の読み取り補正

本実験の途中（121/144実行までの記録がある時点）、凍結した aggregate.py が呼ぶ既存 `benchmarks.research_runner.read_run_outcome` は、engine_error の `diagnostics: null` で AttributeError になった。

事前登録と元の集計コード、実験コードは変更しない。追加した `aggregate_robust.py` は、読み取り時だけ `diagnostics: null` を空辞書としたコピーを既存関数に渡す。raw JSON は書き換えず、status=engine_error・normal_completion=False を保つ。対象、seed、正答の集合一致、エラーを失敗とする扱い、bootstrap、P1/P2 の基準に変更はない。

ラッパー内の合成 engine_error 記録で、失敗扱いになることと元の raw 辞書が変わらないことを確認してから、元の aggregate.py 全体を実行する。この修正後の正式な再集計コマンドは `aggregate_robust.py` とする。キャンペーンの事前ハッシュは元の aggregate.py を保持しており、実行中の solver には影響しない。

その後、起動前失敗・最終結果欠測の記録を分母に残すため、実測されていない時間を null とした。参考時間の中央値だけは null を除いて計算するラッパーを追加した。正答の分母・欠測を失敗とする扱いは変更していない。
