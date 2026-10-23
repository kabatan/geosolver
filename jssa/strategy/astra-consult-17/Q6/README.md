# Q6 再現手順

結果は [answer.md](answer.md)、固定基準は [preregistration.md](preregistration.md)、入力と解析式の監査は [input-audit.md](input-audit.md)。新しい局所探索は実行していない。保存終点の再評価、固定点の摂動・相似変換、SymPyの恒等式検算、Gの保存済み軌道の抽出だけを行う。

リポジトリのルートから、順番に実行する。

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/Q6/audit_existing.py > jssa/strategy/astra-consult-17/Q6/audit.log 2>&1
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/Q6/check_mechanisms.py > jssa/strategy/astra-consult-17/Q6/mechanism-checks.log 2>&1
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/Q6/verify_delivery.py
```

依存パッケージの追加は不要。1プロセス、BLAS各1スレッド。src/を変更・monkeypatchする必要はなかった。書込み先はこのディレクトリだけ。pip、ネットワーク、作業フォルダ外書込み、commit、pushなし。主監査の実測時間は約3.4秒で、成果物は小さいCSV/JSON/Markdownのみ。

## 成果物

| ファイル | 内容 |
|---|---|
| input-manifest.json | 固定基準・ケース・raw・G集計等のSHA-256、選定問題ID |
| selection.csv | 事前規則で選ばれた12問。元はGの292問表 |
| per-start.csv | 2,350保存開始・終点、元分類、独立再評価、主例の追加指標 |
| per-problem.json / .csv | F/I別内訳、箱を外した副分類、再現不一致数 |
| run-summary.json | 主監査の件数・時間、局所探索0回 |
| deep-audit.json | 深掘り5問のDSL、箱、計数、seed 1の座標欠落記録 |
| mechanism-checks.json | P1–P3の固定判定、解析式検算、GのB/N軌道集計、丸めの救済 |
| jmo-radial-evaluations.csv | JMO予選1の箱外123点×4倍率の半径方向点評価 |
| jmo-transverse-evaluations.csv | JMO予選1のF失敗135点の境界横断点評価 |
| jmo-existing-G-traces.csv | GのF開始40点×B/Nの軌道から抽出した拒否試行等 |
| hmmt-2024-expansion-curve.csv | HMMT 2024幾何2の明示的な非有界近似列の10点評価 |
| jmo-4-reciprocal-curve.csv | JMO予選4の保存点から定めた膨張・退化の5点評価 |
| delivery-check.json | 入力ハッシュ、独立集計との一致、ファイルサイズ、src凍結の確認 |

`per-start.csv`の `no_box_cls` は箱だけを除く副分類で、元の `cls` は保持する。AIMEの `normalized_cls` は相似変換後に元箱を含めて全て再評価したもの。これらは完成solverの最終高精度検証ではない。

## 事前登録と事後検算の区別

preregistration.mdは最初の終点数値監査より前に作成し、その後変更していない。audit_existing.pyが最初にハッシュを記録する。commitは禁止されているため行っていない。再実行時にも、検算器は成果物内の固定ハッシュを照合する。

P1–P3はそこで固定した閾値を使用する。JMOの横断摂動、Gの追加軌道抽出、追加2例の解析的な近似列は主監査後の機構確認であり、独立な事前予測として数えない。Gの軌道は他担当が実行した既存計算で、Q6の新規探索0回に合算しない。

## 残った限界

原文・修正台帳は未取得。seed 1の主例には保存開始・終点座標がなく再採点できない。深掘りしない7問の機構は未確定。未知問題検証・完成solver比較・人間難度の分析は未実施。原文の取得のためにネットワークや承認待ちへ移行せず、確認できた範囲と欠落を明記して完了した。
