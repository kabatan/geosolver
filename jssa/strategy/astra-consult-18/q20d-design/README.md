Q20dの成果物は[answer.md](answer.md)から読む。結論はAの核として不可。候補1の機構上の予言は支持されたが、古典的な体論・既存の同定制限を越える新規性は得られていない。

**記録の順序。**

1. `build_inputs.py`が10入力と、solverへ渡さない独立参照値を生成。入力・参照値・初回runner・予言を`registration-lock.json`に固定した。
2. `run_experiment.py`が局所探索128回を実行。完成solverへの初回20要求は60秒設定が公開CLIの下限180秒を下回って全件入力検査で失敗した。`runs/`はこの設定エラーの記録であり、数学的な失敗20件ではない。
3. 完成solverの結果が0件の時点で`execution-correction.md`と`rerun_public.py`を`correction-lock.json`に固定。局所結果は既知だった。180秒・外側188秒へ共通訂正し、元の記録を残した。
4. 訂正後の20実行を`runs-180/`、保存した同一数値の同定対照2回を`identification-180/`に保存。完成solverの正答は18/20、R4だけ0/2で、R4にも数値検証済み候補はある。
5. `score.py`は保存済みJSONだけを読み、`summary.json`、`per-run.csv`、`scored-runs.json`、`local-summary.json`を作る。新しい局所探索は行わない。

**読み直すとき。** リポジトリのルートから、指定環境で保存結果の採点だけを再生成できる。

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/q20d-design/score.py
```

この操作は上記4集計ファイルを上書きする。元の入力、固定記録、生の実行結果は変えない。採点器は入力・初回固定ファイル・srcのハッシュ一致を必要とする。計算の再実行は今回の作業に不要であり、測定済みの`runs-180/`を上書きするrunner呼び出しは拒否される。

同定対照の根号式は設計者が導いた参照式であり、自動的な問題解法の改善ではない。2 seedは独立した問題数ではなく、局所128回も共通16開始点×8目標である。時間・次数の一般的な相関や自然問題への外挿には用いない。

元の60秒CLI要求、訂正後の180秒求解、30秒の同定単体対照を混同しない。予言の支持とAの採否も分けて読む。
