# Q9 の再現と成果物

結論は [answer.md](answer.md)。事前登録した向きの多様性による多点出発は、固定したP1〜P4を全て満たさず、中心成果には採用しない。

## 実行条件

Python `/home/kabatan/work/solver/.venv/bin/python`、`PYTHONPATH=src`、bytecode出力なし、BLAS/OMP各1スレッド、4worker。環境の追加・変更、srcの変更、git commit/pushは行っていない。

自然問題の実行順：`preregistration.md`作成 → 合成問題のselftest → 入力選定 → `freeze.json`作成 → 新しい局所探索 → 公式解で採点 → 保存値の再評価。予測・実験コード・採点コード・入力の固定後の修正は0。予備実験は48問×3seed×3方式×8点、3,456呼出し、実測165.45秒。入力準備・合成検査・集計・検算はこの165.45秒の外。

## コマンド

repoルートから、指定Pythonで実行する。いずれも追加ファイルはQ9内だけ。

```bash
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/Q9/analyze.py
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/Q9/verify.py
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/Q9/example_analysis.py
```

数値探索の初回は同じ環境変数で `experiment.py prepare`、`experiment.py selftest`、`experiment.py freeze`、`experiment.py run --jobs 4` の順。今回はselftestをprepareより先に実行したが、合成入力のみの検査なので対象選定には影響しない。`prepare`と`freeze`は既存freezeがあれば上書きを拒否する。`run`は既存rawをスキップする再開用の動作なので、今あるフォルダで実行しても再計測にならない。保存したrawを維持したまま、全く同じ入力・ソースの別チェックアウトで初回手順を実行すれば、新しい計時が得られる。壁時計時間が完全一致することは要求しない。

## ファイル

| ファイル | 内容 |
|---|---|
| preregistration.md / freeze.json | 予測・基準・手順／実行前ハッシュとUTC時刻 |
| manifest.json / inputs/ | 323問の適格性・除外理由、適格219問からの固定48問、idとdslだけの入力 |
| experiment.py | 初期点生成、層を一致させる選点、凍結LMの呼出し。公式解は読まないworker |
| raw/ | 144問題×seed組。各方式の準備時間、選択点、符号列、8終点と目標候補 |
| analyze.py / summary.json | 全実行終了後の独立採点、固定P1〜P4、問題単位bootstrap |
| per-start.csv / per-run.csv / per-problem.csv | 3,456出発／432方式実行／48問題の表 |
| verify.py / verification.json | 初期点・符号列・候補の再評価、別経路の座標照合、ハッシュ照合 |
| diagnostics.json / repeated-start-audit.json | 最初の候補の誤り、問題別得失、同一出発点の再現 |
| example_analysis.py / example-analysis.json | AIME 2011 II-4の事後説明。新しい局所探索なし |
| human-coverage.csv | Easy2Hardが得られる16問の対応。相関探索には使用していない |
| literature.md | 一次資料のリンクと確認範囲・未確認事項 |
| selftest.json / execution.json / progress.jsonl | 合成検査、実行時間と設定、進捗記録 |

## 計時上の境界

各方式の`prep_sec`は入力コンパイル、探索箱、初期点、必要な全256点の層診断、Gの幾何特徴と選択を含む。`solve_sec`は凍結局所探索とその候補構築、`check_sec`は追加の終点分類と目標値計算。モジュールimport・プロセス起動・結果のディスク書込み・事後の公式解照合は含めない。SciPyの遅延importが最初の局所探索に入る場合の費用は、実測値のまま残している。三方式をseedと出発番号で循環させ、特定の方式だけ常に最初にはしていない。

`C16`は成功を知って最初の当たりで止めた場合の費用を後から数え、当たりなしを16秒とする指標。全8点を走らせた実時間、完成solverの実時間、未知の問題で実装可能な停止時間とは別物である。実時間の全8点平均と、参照解を使わない最初の候補の成績も併記している。

`verify.py`と`example_analysis.py`は計測後の検算・記述用で、freeze対象の実験・採点コードを変更していない。元の判定を事後説明で置き換えない。
