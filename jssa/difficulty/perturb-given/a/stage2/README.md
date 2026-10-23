# Q40a 段階2の記録

固定計画は親ディレクトリの `prediction.md` と `prediction.lock.json`。
計測器は凍結 `60db4b6` のコードを `/tmp/q40a-clean/src` から読み、
`python -S -B` によって共有環境の editable-install を読み込まない。
局所探索は最大2 worker、各1 thread。各実行コマンドは外側の `timeout 200s` で区切る。
`run.py` が処理するのは固定予定表の未着手枠だけで、着手済み枠を再試行しない。

| 保存物 | 内容 |
|---|---|
| `receipt.json` | 実行前に記録した承認commit・確認時刻、入力・src hash、環境 |
| `versions/`、`*-review.json` | 計測器の旧版と変更理由。固定計画・探索条件は不変 |
| `instrumentation-checks.json` | 人工関数を用いた計測器の確認。選択問題の追加探索は0回 |
| `per-condition.csv` | 40問×3seed×6版の720行。各行の分母は200 |
| `per-problem.csv` | 40問のseed別Δ、水準別Δ、安定改善、特異値・枝の判定 |
| `subgroups.csv` | 事前指定した群、変数数、探索法、元版pの床・天井の集計 |
| `summary.json` | P1〜P4、区間、失敗内訳、感度確認、相関 |
| `completion-audit.json` | 全枠・始点・入力不変性・分母・実行上限の照合 |
| `raw-index.json` | 外部の生データ全ファイルのパス、サイズ、SHA256 |
| `artifact-manifest.json` | ここに置いた成果物と `answer.md` のSHA256 |

`returned` は終点が返った状態を表し、当たりとは限らない。当たりは固定した
残差・guard・hard条件・箱のすべてを満たす `hits`。時間切れなども分母200に含む。
CSVの空欄とJSONの `null` は欠測であり、0や無限大への補完はしない。
`diagnose.py` は保存終点と固定された元版の始点を評価するだけで、探索・精密化をしない。

生データは `/tmp/q40a-execution/` にある。`trials.sqlite` は予定144,000枠と状態・
終点を保存し、`batches/` は各コマンドの実行証跡、`diagnostics/` は行尺度・
全特異値・クラスタ・欠測理由を保存する。5MB超の生ログはリポジトリに置かない。
外部保存先は一時ディレクトリであり、永続アーカイブではない。
