# Q10 再現とファイル案内

結論は [answer.md](answer.md)、全実数枝の議論は [root-audit.md](root-audit.md)。主比較は [comparison.csv](comparison.csv) / [comparison.md](comparison.md)。

## 再現

Pythonは `/home/kabatan/work/solver/.venv/bin/python`、PYTHONPATHはリポジトリのsrc。pip等の導入は不要。現在のrunsを保護するため、run_batch.pyは既存実行先があれば停止する。再計測はこのQ10一式を新しい出力場所へコピーし、そのコピー内でrunsを新規ディレクトリへ向けること。保存済み試行を削除・上書きして再計測しない。

```
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/Q10/run_batch.py
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/Q10/summarize.py
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/Q10/audit.py
```

`prepare.py`は初回に取得済みGitオブジェクトとLのコードをコピーし、id,dslだけのinputsを作った。既存のprovenance/registration-lockを上書きするため、保存結果の検算時には再実行不要。Lのコードはvendor/l_*.pyへ凍結し、実行時に進行中のLをimportしない。

## 保証と出力

- runs/：32実行の入力変換、数値候補、PSLQ、結果、係数付き証明書。失敗も残す。
- certificate-validation.json：15件のfresh恒等式のFraction検算と、Qへ1を足した誤証明書の棄却。15件には唯一値に閉じないHMMT-2023のA/Bも含む。
- audit/charts/：15問の手製実数枝の証明書。H由来4件を含む。fresh自動成功数とは別。
- audit/legacy/：取得済みulho54ブランチの旧6証明書のスナップショット。legacy-verification.jsonで独立再検算。
- audit/JMO-2014-PRE-09-counterexample.json：厳密な連続反例の成分式と2配置の検査。
- diagnostic/：事後の、係数追跡なしの通常lex消去16件。主比較と混ぜない。
- preregistration.md / registration-lock.json：事前固定。deviations.mdは補足と事後診断の区別。

## 導入が必要なもの（今回導入・実行していない）

Singularおよびmsolveの実行ファイルがPATHに存在しない。SymPyは1.14.0、SciPyは1.18.0、mpmathは1.3.0。必要なのはPythonのpipパッケージではなく、外部CAS本体である。

1. **Singular**：有理係数の`std`、`eliminate`、`lift`を使える本体。旧証明書の環境は4.3.2。成分分解も行うなら標準の`primdec.lib`が必要。今回の入力は[cas-inputs/](cas-inputs/)に全16問用意した。`Singular -q input.sing`で消去Eと係数の内部検算を行える。新しい計測ではプロセスの120秒/2 GiB/出力サイズ制限と、今回同様の独立係数検算を別途付ける必要がある。
2. **msolve**：ブロック消去の`-e k -g 2`を備える版。Hの取得済み資料にこのオプションが記載されているが、ここでは本体ヘルプの確認も実測もできていない。`input.ms`は有理係数を整数化済み、x0,…,xkの最後xkが目標。kは各mapping.jsonのcoordinate_variables_to_eliminate。想定する実行形は `msolve -t 1 -e k -g 2 -f input.ms -o output.ms`。利用する版のヘルプ・出力仕様を確認し、座標列挙モードと取り違えないこと。

Singularの出力から係数証明書を取り出すパーサーは旧certify.pyにあるが、今回のSingular出力形式へ合わせる調整は未実行。msolveのブロック消去から今回の証明書形式へ結ぶ処理も未実装。この2点まで含めて用意して初めて、同保証のCAS比較を完遂したと言える。

ネットワーク・インストール・承認要求を行っていない。これらの未実行部分を、SymPyの成績から推測で埋めない。
