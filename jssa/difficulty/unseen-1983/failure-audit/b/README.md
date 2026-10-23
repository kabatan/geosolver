# Q29b 再現手順

入口は[answer.md](answer.md)、問題別表は[summary.csv](summary.csv)。
手計算の根拠・条件確認方法は[witness-derivations.md](witness-derivations.md)。
凍結版の成績は **85/130** のまま。DSL修正版の実行はしていない。

Python 3.12の既存環境を利用した。srcはcommit `60db4b6`と完全一致を確認する。
`prepare`が差分を検出したら中止するため、再現時も凍結版srcを使うこと。
並列計算は最大4。下のコマンドはいずれも1ジョブであり、直列でも実行できる。

```bash
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/b/audit.py prepare
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/b/audit.py compare
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/b/audit.py floor
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/b/audit.py local-all --cpu 4
```

各IDについて次を実行する（CPU番号は利用可能な1コアを選ぶ）。

```bash
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/b/audit.py natural --id AIME-1996-13 --cpu 4 --budget 900
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/b/audit.py near --id AIME-1996-13 --cpu 4 --budget 180
```

HMMT-2022-GEO-07の追加診断：

```bash
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/b/audit.py near --id HMMT-2022-FEB-GEO-07 --cpu 4 --budget 180 --expanded
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/b/audit.py exact --id HMMT-2022-FEB-GEO-07 --cpu 4
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/b/audit.py memory-worker --id HMMT-2022-FEB-GEO-07 --cpu 4 --budget 900
```

`memory-worker`は凍結版`runtime.worker.execute`をそのまま呼び、結果をメモリから要約する。探索・精密化・検証・厳密化・seed・予算は変更しない。公開APIのartifact書出し／読戻しは省くので別行に記録する。
通常APIで結果が欠落した試行と、監査用JSONが大き過ぎて保存を中止した試行も残し、後の結果で上書きしない。最新版ハーネスでは大きい公開結果の診断欄だけを要約するが、worker内部のartifact書出しにはファイル上限が適用される。

出力はファイル単位4,900,000 bytes未満。`RLIMIT_FSIZE`で途中生成物も制限し、core dumpは無効にする。
全ての最終データが揃った後、表と整合性検査を再生成する。

```bash
python3 jssa/difficulty/unseen-1983/failure-audit/b/report.py
```

`runs.csv`は元の25実行と追加診断を`group`列・`part_of_original_85_of_130`列で区別する。
`witness-conditions.csv`は80桁・160桁の全128条件行。
`development-features.csv`は開発323問、`target-features.csv`は担当5問の同一尺度の静的集計。
初回の内部API診断は周囲の精度が公開workerと異なったため`exploratory-ambient15/`へ隔離し、主表から除いた。主表の内部API診断は全て180桁に統一した。

封印tarの読み出し、元DSL・srcの編集、既存の採点結果の変更は行わない。
