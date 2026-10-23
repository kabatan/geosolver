# Q8 成果物と再実行

結論と根拠は [answer.md](answer.md)、結果を見る前に固定した予測は [preregistration.md](preregistration.md)。主線としての判定は中止。検算済み18/43問で、事前基準22問に届かなかった。

## 保存内容

- `inputs/`・`manifest.json`：変数がちょうど1個の全43問。workerへ渡す内容はid,dslのみ。入力と事前登録のSHA-256を保存。
- `pilot-v1/`・`versions/v1/`：初回結果と当時の実装。角の二等分線に関する認証主張の撤回を含むため、最終成績には使わない。
- `pilot-v2/`・`verification-v2/`：修正版の全43問と、complete 19問の検算。18問成功、1問検算時間切れ。
- `contradiction-inputs/`・`contradiction-manifest.json`・`existence-checks/`・`existence-verification/`：事前指定の最初5問から作った矛盾入力と、空集合の生成・検算。
- `per-problem.csv`・`all-cases.md`・`summary.json`：全43問の成績、参照集合との照合、既存結果との比較、費用。
- `method.md`・`implementation-log.md`：保証の論理、信頼する部分、修正と撤回の履歴。
- `unit_checks.py`・`unit-checks.json`：重根、極、根号の符号、空集合、複数値、定義域、未対応構文を含む小さい数学的検査15件。

## 再実行

リポジトリのルートから、指定Pythonを使う。インストールは不要。以下は各行を順に実行する。runnerは最大4 worker、各workerは1 thread、処理120秒、メモリ2 GiB、個別ファイル16 MiB上限。出力先が存在すれば停止するので、保存済みの実験を上書きしない。

```bash
q8_python=/home/kabatan/work/solver/.venv/bin/python
q8_dir=jssa/strategy/astra-consult-17/Q8
export PYTHONPATH=src
export PYTHONDONTWRITEBYTECODE=1

# 保存済み証拠の検算と負例検査のみ
"$q8_python" "$q8_dir/run_pilot.py" --verify pilot-v2 --output reproduce-saved-verification

# 凍結入力43問から新たに生成し、その結果を検算
"$q8_python" "$q8_dir/run_pilot.py" --output reproduce-pilot
"$q8_python" "$q8_dir/run_pilot.py" --verify reproduce-pilot --output reproduce-verification

# 凍結した矛盾入力5問を生成・検算
"$q8_python" "$q8_dir/run_pilot.py" --inputs contradiction-inputs --output reproduce-existence
"$q8_python" "$q8_dir/run_pilot.py" --inputs contradiction-inputs --verify reproduce-existence --output reproduce-existence-verification
```

時間切れの有無は実行時の負荷で変わりうる。今回の判定は保存済みの結果に対するものであり、後日の再実行で置き換えない。`prepare.py`と`prepare_existence_checks.py`は初回の入力固定用で、既存ディレクトリがあれば停止する。

`summarize.py`は保存済みの所定ディレクトリを集計し、`summary.json`・`per-problem.csv`・`all-cases.md`を再生成する。この評価器だけが参照値と旧結果を読む。`reproduce-*`の結果は自動で主成績に混ぜない。

DSL翻訳・代数的符号判定は生成器と検算器で共有する。独立なのはFractionによるSturm根数・区間被覆の検算部分で、形式証明器による保証ではない。
