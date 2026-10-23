# Q32：NOMAD単体とLM単体の比較

結論は [answer.md](answer.md)、実行前の仕様は [prediction.md](prediction.md)。凍結solverは `60db4b679b04167175c51c479c87c22fa663fda0`。対象21問と対照7問について、同じ一様始点16個を11条件で比較した。全4,928枠の原票を分割保存している。

予測固定はUTC `2026-10-23T15:30:17.549434+00:00`。prediction.mdのSHA-256は `a7214b4d992dedc3d265c392a14292be849e2ee0e870a61a6069c64e1a025117`。[prediction.lock.json](prediction.lock.json) に入力・探索・一次集計コードも封印し、「予測固定」を標準出力へ出してから対象問題の探索を始めた。これは自己記録であり第三者の時刻認証ではない。この作業ではGit commitを作成していない。

| ファイル | 内容 |
|---|---|
| answer.md | 日本語の結論、4基準、全条件の結果、仮説判定、限界 |
| prediction.md / prediction.lock.json | 事前予測、判定閾値、ハッシュとUTC時刻 |
| selection.csv / selection.json | 21問と、旧成功率から固定した7対照の選択 |
| inputs/ | 答えを含まないDSL、箱、同一始点 |
| grading/ | 採点だけが使う参照答 |
| source-manifest.json | 凍結srcの全ファイルのハッシュ |
| runs/ | 448個の出発点別JSON、1個あたり11条件 |
| logs/ / receipts/ | workerのログ、コード版、終了状態、コマンド所要時間 |
| per-start.csv | 4,928条件の成功、残差、使用量、200/800評価時点の結果 |
| per-problem.csv / success-matrix.csv | 問題別成功数、率、seed別結果、記述的区間 |
| group-summary.json / paired-effects.csv / summary.json | 群別・seed別率、同一始点の救済と喪失、固定判定 |
| raw-manifest.json | 原票のSHA-256 |
| success-matrix.png / success-matrix.svg | 各問題・各条件の成功数／16 |
| strict-and-coarse.png | 厳密側の主指標と残差1e-4の補助指標 |
| case-study.md / margin-diagnostic.csv / diagnostic-summary.json | 事後のmargin罰則・勾配診断。探索なし |
| endpoint-audit.csv / endpoint-summary.json | 事後の最終点のみ採点と初期許容性別集計 |
| case-formula-check.json / native-epsilon-audit.json | 事後の手計算照合と、NOMAD返却点の数値比較精度の補足 |
| resource-summary.csv / verification.json | 実評価回数、時間上限、同一始点・封印・完全性の監査 |
| delivery-verification.json | 最終成果物のハッシュ、全原票の照合、集計・ローカルリンク・サイズ確認 |
| literature.md / sources/ | 理論の適用範囲、Q31とQ32節の取得時点 |
| amendments/ | 報告処理だけの修正履歴と旧コード |

再集計はこのリポジトリのルートから行う。実行環境はNumPy 2.5.1、SciPy 1.18.0、PyNomadBBO 4.5.1、SymPy 1.14.0。以下は使用したPythonのパスであり、別環境では同じ依存関係を持つPythonへ置き換える。各コマンドは順に実行する。

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/derivative-free/analyze.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/derivative-free/diagnose.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/derivative-free/audit_results.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/derivative-free/check_case_formula.py
env PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/derivative-free-mpl OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -B jssa/difficulty/derivative-free/plot_results.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/derivative-free/verify_delivery.py
```

図の生成だけは、既存のMatplotlibを使えるシステムのpython3を使用した。CSVの読み取りと描画のみで、数値探索環境やパッケージを変更していない。

探索の実行単位は以下。1コマンドは160秒の外枠、workerは85秒、数値workerは最大3。残り85秒になると新たな起動を止める。BLASも1スレッドとする。このコマンドを同時に複数起動しない。全原票が存在する現状態では何も追加探索しない。partialや既存ログがある出発も再実行しない。

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/derivative-free/campaign.py --seconds 160
```

新規再現実験は、この出力を保存した別ディレクトリ／作業ツリーで行う。既存原票や予測固定ファイルを削除して上書きしない。prepare.pyは対象選択と入力の生成、check_harness.pyは合成問題での配線確認、seal.pyは最初の予測固定に使用した。現成果物でseal.pyを再実行すると固定時刻が変わるため、再集計に使わない。

各条件の上限は元の残差ベクトル1,200評価か壁時計6秒の早い方。有限差分とGaussian標本も数える。尺度を求める32評価／出発は別枠で明示する。最大評価回数の上限をそろえた比較であり、早期停止・cache・NOMAD内部上限により実使用量は同一ではない。時間上限の判定にはrawのstatusだけでなくnative_result.stop_reasonも用いる。

20出発終了時、PyNomadが空のx_bestを返す場合の座標変換で報告上の例外が2件発生したため、長さ確認だけを追加した。探索・候補選択・予測は不変で、旧原票を保存し再試行していない。[amendment-01.json](amendments/amendment-01.json) が変更前後のハッシュを記録する。campaignのverify()はこの履歴と全凍結入力を検査する。

各ファイルは5,000,000 bytes未満に保つ。探索workerには4,900,000 bytesのRLIMIT_FSIZEも設定した。参照答はoffline採点のanalyze.pyとaudit_results.pyのみが読む。手計算の解を始点や探索目標へ投入していない。
