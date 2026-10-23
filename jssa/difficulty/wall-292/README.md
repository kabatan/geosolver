# Q1：探索中のhard feasibility罰則、292問

主報告は [answer.md](answer.md)。全292問・55,097保存開始点を完了し、主3条件165,291件と停止条件対照S 3,729件を監査済み。

- [preregistration.md](preregistration.md)：最初の新しいoptimizer呼出しより前に固定した予測・条件・G2設計。SHA256は `f4a72cadf217c76c47b1466cdcaf1adf36696f3449feef7182e3f6b0e05586ac`。
- [manifest.json](manifest.json)：292問・55,097保存開始点のk/F/I、固定診断集合、悪化リスク群R、入力ハッシュ。F36,251、I18,846、F判定例外0。診断3,973開始点のうちLM3,729、Powell244。
- [execution-freeze.json](execution-freeze.json)：本実行開始時刻、環境、src全Pythonファイルと実装・主要入力のSHA256。srcは60db4b6から差分なし。利用者の指示によりcommit/pushなし。
- [g2.py](g2.py)：事前固定した違反量の二乗和平方根。外側の係数10と元のguard行を残す。数値距離を得られない場合のfallbackは回数を保存する。
- [run.py](run.py)：prepare/run。最大4プロセス、1開始・1条件10秒。既存Gの読み取り専用helper（common.py、mechanism.py）を利用する。B/N/G2を同じ保存startで実行し、固定診断集合のLMにSを追加する。
- [preflight.py](preflight.py)、[preflight.json](preflight.json)：optimizerを実行せず、違反量の傾きと等式・guard残差行が変わらないことを確認。人工context不足による準備失敗2回を記録。
- `records/<id>.jsonl`：開始点ごとの全主条件・Sの結果、最終座標、分類、停止status、評価数、時間。診断対象ではnative試行の集計と最後8試行も保存。差分点は試行に含めず、受理は次のjac基点・返却xから推定する。同一座標はunknown。
- `case-summary/<id>.json`：問題単位の完了と異常。`progress.json`は250問で更新が止まったため最終完了の根拠にはしない。`run-complete.json`は全292問の完全記録を直接検査して作成した確認記録で、通常のsupervisor終了マーカーとは区別する。[completion-reconciliation.json](completion-reconciliation.json)に経緯を記録。
- [analyze.py](analyze.py)：主判定・集計。`per-problem.csv`、`summary.json`、`status.csv`、`transitions.csv`、`failures.csv`、`g2-fallbacks.csv`、`mechanism-by-problem.csv`を作成。Sと主3条件の分母を分ける。
- [audit.py](audit.py)、[audit.json](audit.json)：凍結ハッシュ、保存start、条件順、成功判定、旧B、ファイルサイズの監査。
- [final_checks.py](final_checks.py)、[final-checks.json](final-checks.json)：保持行・補完行の由来、控えとの一致、再開コードの不変性を監査。[recovery-sensitivity.json](recovery-sensitivity.json)は初回127問の集計を用いたP1〜P5の感度分析。

実際に使用した初回の起動環境（実行済み。以下のprepareを再実行する必要はない）：

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/wall-292/run.py prepare
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/wall-292/preflight.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/wall-292/run.py run
```

`prepare`は既存manifestを上書きしない。`run`はハッシュを照合し、完了した問題・開始点を再実行せず中断部分を続行する。上書きによる条件変更を防ぐためである。完全な新規反復を行いたい場合は、そのための別登録と別出力先を設ける。ここにある結果を消して作り直さない。

途中の暫定報告の更新（完了時は使わない）：

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/wall-292/analyze.py --update-answer
```

完走後の集計・監査・日本語報告の再生成（新しい局所探索は行わない）：

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/wall-292/analyze.py --final
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/wall-292/audit.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/wall-292/final_checks.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/wall-292/report.py
```

独立φの感度分析は既存 `jssa/strategy/astra-consult-13/phi-independent.csv` のみを読み、新しい開始点の探索はしない。人間難度は `ghost-1023/human_feat.csv` のhuman実測値のみ。主相関は順位を変数数の順位で線形回帰してから残差間Pearson相関を計算する。

最大ファイルサイズはワーカーで16MiBに制限し、core dumpを無効化する。出力は本フォルダ内のみ。依存関係の追加・Python環境の変更・ネットワークアクセス・git fetch/commit/pushは行わない。

## 保存不整合・中断からの再開

初回のappendログにprefixへの巻き戻りが見つかり、実行ツールから終了コード1が返った。原因は未確定。予測・solver関数は変更せず、[recovery-protocol.md](recovery-protocol.md) を再開前に固定した。[resume.py](resume.py) の保存準備失敗後、保存先生成と保存時の再試行を加えた [resume_v2.py](resume_v2.py) で不足分を続行した。1問1プロセス、同時4プロセス、各開始点後のatomic保存、完了ログの別名backupを用いた。再開対象・コードのハッシュは [recovery-plan.json](recovery-plan.json)、[recovery-v2-freeze.json](recovery-v2-freeze.json)。

実際に使用した再開コマンド（実行済み）：

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/wall-292/resume.py prepare
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/wall-292/resume_v2.py run
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/wall-292/finish_recovery.py
```

再開ツールも終了コード143を返したが、その後も既存の計算が継続し、全292問の控えが完成した。追加solver起動は行わず、全記録と未完了state 0を検査して完了を確認した。元サマリー・不足prefixはinitial-summaries/、initial-prefixes/。再開中のworker個別異常終了ログは0件。最終報告はanalyze.py --final、audit.py、final_checks.py、report.pyの順で生成する。結果の統計的な判定は最初のpreregistration.mdのままである。
