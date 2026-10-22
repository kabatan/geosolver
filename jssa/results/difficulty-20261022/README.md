# 難しさの実験（2026-10-22、凍結版 60db4b6）

## 1. 余分な変数の実験：solver本体の計測（extra-variables-campaign/）
- 入力: branch `claude/project-thread-9bdbbg` commit 9d3c1e8 の `benchmarks/extra-variables/`（15問×k=0..3、60入力）。src/ は 60db4b6 と同一。
- 条件: seed 0・1・2、180秒・1物理コア、4並列（research_runner）。1プロセス4 GiBの上限（ulimit -v）。
- 並行負荷: 同じ時間に、厳密解法の比較（msolve 4並列）が別のプロセスで動いていた。時間はその負荷込みの値。
- 結果: 165/180一致。3seedすべて一致したのは53/60入力。時間切れ12回、engine_error 0。
- k別（kは置き換えた作図の数）: 一致は k=0 42/45、k=1 40/45、k=2 42/45、k=3 41/45。求解コストCの中央値（15問）は 8.6→19.7→28.8→29.8秒。C_k/C_0の中央値は 1.00→1.55→1.80→3.43。
- 表: `dose-response.md`。実行ごとの記録: `per-run.csv`。全体: `report.txt`、`summary.json`、`campaign-manifest.json`。
