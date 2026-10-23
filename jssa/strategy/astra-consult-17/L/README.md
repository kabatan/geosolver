# astra-L 成立確認の成果物

結論は [answer.md](answer.md)。入力DSLから始める試作を固定した開発標本で測り、候補4の続行条件は未達と判定した。ネットワーク・導入・src変更は不要。

## ディレクトリ

- `inputs/`: id,dsl だけの323入力。公式解は含まない。実行対象は `cohorts.json` の19問。
- `vendor/`: 取得済みリモート追跡ブランチの algebraize.py / run_exact.py。原本のまま。
- `audit_source/`: 旧証明器と旧Pの監査用。experiment.py はここを読まない。
- `runs/<ID>__<C1|C2|C3>__<seed>/`: 85実行。元の多項式系、試行、実数根区間、証明書、時間を保存。
- `debug_runs/`: 実装不具合を修正する前の記録。集計から分離した理由は implementation-log.md。
- `source.git/`: 再投入前から存在したもの。今回の作業では使用・変更していない。

## 検算

リポジトリのルートから、指定済みPythonで実行する。PYTHONHASHSEEDは補助変数の生成順の再現に必要。

```bash
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/L/validate.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/L/evaluate_reference.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/L/summarize.py
```

`validate.py` は新しい探索を行わない。保存済み恒等式と元の入力の対応を確かめ、独立の Fraction 多項式演算で検算し、負例を確かめる。

`evaluate_reference.py` **だけ**が独立評価のため公式解を読む。計測・候補生成へのフィードバックはない。

単独の恒等式の検算は、SymPyを使わない次のコマンドでも行える。

```bash
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/L/verify_certificate.py jssa/strategy/astra-consult-17/L/runs/HMMT-2013-FEB-GEO-02__C2__4301/certificate-9.json
```

## 計測コード

```bash
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/L/run_batch.py positive_first
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/L/run_batch.py positive_repeat
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/L/run_batch.py zero
```

実行済みの結果がある場合はスキップし、上書きしない。順序はコードに固定され、同時に1 workerだけが動く。比較のための入力・数値seed・上限は preregistration.md を参照。

- C1/C2: 凍結版の局所探索部（完成solver全体ではない）。C2は明示的な許容条件だけを探索時に外す。
- C1/C2証明: grevlexの拡張Gröbner基底でP、または候補からだけ作る反射積のmembershipを証明。
- C3: 拡張lex基底から目標だけの多項式を得る。既存のPを必要としない。同じ係数検算と根の選別を行う。
- 原入力から認められる非零条件だけを使う。候補のための自由変数固定は最終証明に入れない。
- 不成功も per-run.csv に残す。C180は集計用に失敗を180秒とした補助指標で、実際の証明段階上限は45秒。

Singular/msolveは未導入。今回のSymPyによるC3はmsolve -eの実測代替にはならない。
