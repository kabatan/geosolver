**Q21e 小規模検証の記録**

最終判定と3候補の(a)〜(h)は[answer.md](answer.md)。主検証は300入力×3開始、2workerで完了した。追加の大規模実験は実施していない。

| ファイル | 内容 |
|---|---|
| preregistration.md / freeze.json | 探索前に固定した生成規則・格子・採点・予言と、入力・コードのSHA-256 |
| experiment.py / cases.jsonl | 生成・native局所探索・登録済集計のコードと300入力 |
| preflight.json | 新規探索0回での生成・DSL評価の事前検査 |
| raw/*.json / per-start.csv | 900開始の座標、終点、時間、評価回数、残差、S/Rと状態 |
| per-case.csv / cell-summary.csv / summary.json | 基底・セル別集計、区間、P1〜P3の判定 |
| run.log / run-status.json | 開始数・完了数と時間上限の記録 |
| census.py / competition-census.csv / competition-summary.json | 既存競技群の再解析。solverは起動しない |
| input-hashes.json | 再解析した既存データのハッシュ |
| verify.py / verification.json | 全開始の採点再計算、共有開始点、独立残差、解析Jacobianの検算。新規探索0回 |
| condition-count-audit.json | n_eqと明示等式・predicateの件数の事後監査 |
| environment.json | Pythonと主要依存の版、凍結backendとの一致 |
| sources.md / background.md | 一次文献と指定背景の確認内容・未確認事項 |
| generated88-* | 取得済みGitオブジェクトの88入力の仕組み・来歴の確認 |
| deviations.md | 探索前のAPI修正、集計後に見つかった注意点。登録基準の変更なし |

**環境・実行経路**

Python `/home/kabatan/work/solver/.venv/bin/python`、3.12.11。NumPy 2.5.1、SciPy 1.18.0、SymPy 1.14.0。`PYTHONPATH=src`、`-B`、BLAS/OpenMP等は1thread。既存GeometryProblem→load_problem_bundle→build_ir_evaluator→`_collect_local_start_record`の経路を使用。局所backendはGit `60db4b6`の同ファイルとバイト単位で一致した。srcに差分はない。

初回の実行順は次だった。既存のfreeze.jsonがある状態で`run`を再度指定すると、上書きを避けるため停止する。再解析には後ろの3コマンドだけを使う。手元の結果を消して再実行する必要はない。

```bash
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21e-phase-transition/experiment.py prepare
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21e-phase-transition/experiment.py run
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21e-phase-transition/experiment.py analyze
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21e-phase-transition/census.py
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21e-phase-transition/verify.py
```

`run`内で入力順をseed210528でシャッフルして時間順の偏りを避けた。解析の採否条件とは独立の実行順であり、コードとともに探索前に固定されている。1入力30秒のwatchdog、1開始5秒、全体45分の上限。実際は213秒で完了した。全点が候補を返し、wall上限による未観測はない。

結果で予測・生成規則・格子・seed・成功閾値を変更していない。全成果物はこのディレクトリ内で、最大ファイルは約1.5MB。既存ファイル、src、venvに変更せず、pip install・git fetch・commit・pushは行っていない。
