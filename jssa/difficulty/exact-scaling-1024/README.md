# 成果物

- [answer.md](answer.md): 日本語の集計・解釈・定義・限界・段階2の案。
- [real-problems.csv](real-problems.csv): 実問題357問。既存時間のみを使用。
- [degree-vs-depth.png](degree-vs-depth.png): 実問題の次数・深さ・solver時間。
- [degrees.csv](degrees.csv)、[families/](families/README.md): 人工3族×k=1〜8、DSL・問題文・有限性と最小多項式の証明。
- [missing.csv](missing.csv): 次数不明、既存時間・実行記録の欠測の全IDと理由。
- `records/`: 各実問題のSingular入力、出力、結果・制限の記録。`inputs/` は参照答えを含まない入力写し、`depths/` は依存グラフの証跡。
- `depth-distribution.csv`, `regressions.csv`, `msolve-profile.csv`: 群別の集計値。
- `provenance.json`, `real-table-milestone.json`, `progress.jsonl`: 元資料のハッシュ、先行保存、「実問題表完了」の記録。
- [verification.json](verification.json): 整合性検査。`SHA256SUMS` はこのファイル自身を除く成果物の一覧。

`base_*` は無変更の既存変換（fresh、Tなし、Rabinowitsch変数付き）、`strong_*` はT付き強化変換を飽和したイデアル。`degree` は重複度込み、`dimension>0` は解が有限個ではない。次数不明の数値欄は空欄、表示欄は「次数不明」、理由は `status` / `reason` / `detail`。`nvars` / `neqs` は変換後の系（強化版は飽和前の生成等式数）。旧記録のサイズは `msolve_historic_*` に別記。

`solver_correct_seconds_median` は正解seedだけの時間中央値。予定seed数、欠測数、記録済み不正解数を区別する。`*_cas_wall_s` は次数計算の制限管理用で、時間比較に使っていない。

検査だけをやり直す場合（solverやCASは呼ばない）：

```sh
/tmp/q38-58e3993-venv/bin/python -B jssa/difficulty/exact-scaling-1024/verify_artifacts.py
```

既存CSVからの集計・図・本文再生成は `analyze_real.py`、補強の本文追記は `finish_report.py`。`collect_real.py` と `run_families.py` はCAS計算を伴うため、検査用には実行しない。
