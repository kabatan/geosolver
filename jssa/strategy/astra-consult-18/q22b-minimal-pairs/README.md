# Q22b 成果物

結論は[answer.md](answer.md)。Aの核としては不可。20組の事前予言、全6,400開始、外れたS04・S05、人間側の未確認、代替手段を含めて報告した。

| ファイル | 内容 |
|---|---|
| [preregistration.md](preregistration.md)、[registration-lock.json](registration-lock.json) | 実行前に固定した設計・判定・入力とコードのハッシュ |
| [stimuli.json](stimuli.json)、[preflight.json](preflight.json) | 20組・60入力、解析参照、実行前の60入力確認 |
| [prepare.py](prepare.py)、[experiment.py](experiment.py) | 固定済み入力作成と局所探索。実行済みデータの上書き用ではない |
| [execution.json](execution.json)、[raw/](raw/) | 実行時刻・環境・全20組の開始と終点、残差、成否、終了情報 |
| [analyze.py](analyze.py)、[summary.json](summary.json) | 全件集計。新しい最適化なし |
| [S-all-pairs.csv](S-all-pairs.csv)、[H-all-pairs.csv](H-all-pairs.csv) | 全対の観測件数と事前予言の当否 |
| [per-mode.csv](per-mode.csv)、[contrasts.csv](contrasts.csv) | Wilson区間、対応bootstrap区間、符号検定、主10比較のHolm補正 |
| [power-far-stationarity.csv](power-far-stationarity.csv) | 遠側の失敗283終点と登録済み極小の照合 |
| [stopping-status.json](stopping-status.json)、[failed-H-starts.json](failed-H-starts.json) | 終了理由の集計とHの失敗を両入力とも保存 |
| [theory.md](theory.md)、[human-evidence.md](human-evidence.md)、[sources.md](sources.md) | 導出、人間側の根拠の強弱、文献確認範囲 |
| [posthoc-plan.md](posthoc-plan.md)、[posthoc-audit.py](posthoc-audit.py)、[length-near-posthoc.csv](length-near-posthoc.csv) | 結果を見た後の説明用解析。登録を変えず新しい最適化もなし |
| [static-dispatch.py](static-dispatch.py)、[static-dispatch.json](static-dispatch.json) | 棄却した候補2のコンパイルのみの確認。登録した試行ではない |
| [verify.py](verify.py)、[verification.json](verification.json) | 独立な残差式で6,400記録を再採点、単一変更・共通開始・ハッシュ・リンク・容量を検査 |
| [background.md](background.md) | 指定資料の参照範囲、既存回答との重複、Q5資料の欠落 |

作業ツリーのルートから、保存データの検算だけを行うコマンド：

~~~bash
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/q22b-minimal-pairs/verify.py
~~~

集計の再作成（rawを読み、同じディレクトリの派生CSV・JSONを更新）：

~~~bash
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/q22b-minimal-pairs/analyze.py
~~~

実験コードは既存execution.jsonがあると再実行を拒否する。再計測するなら、登録ファイル一式とsrcが同じ状態の別の作業コピーを用意する。本成果物のrawや登録を消す手順にはしない。固定時刻は当初の実行前固定を示すので、再現実行の登録時刻として流用しない。

実行環境はPython 3.12.11、NumPy 2.5.1、SciPy 1.18.0。srcを編集せず、pip install・fetch・commit・pushを行っていない。今回作成・変更したファイルはこのディレクトリ内のみ。局所探索の結果であり、完成solverや人間の難度測定の代用ではない。
