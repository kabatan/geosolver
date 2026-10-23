# Q21c 再現手順と成果物

判定は **Aの核として不可**。結論・測定結果・候補3件の(a)〜(h)と未実行の1.5日設計は [answer.md](answer.md)。2026-10-23の既存323問の再解析と小さい理論照合である。

## 入力と来歴

| 用途 | 作業ツリー内の入力 |
|---|---|
| 母集団と既存局所探索集計 | `jssa/difficulty/minima/basins-323.csv` |
| 保存試行の照合 | `jssa/difficulty/minima/raw-323/{id}.json`、323ファイル |
| 人間難度 | `jssa/difficulty/ghost-1023/human_feat.csv` |
| DSL変数数と作図数 | `benchmarks/cases.jsonl` のうち母集団323 ID |
| 既存msolve比較と完成solver3seed | `jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv` |
| 別の代数化 | `jssa/difficulty/certify-all/per-case.csv` の `development323` 群のみ |

元のmsolve比較の結果ディレクトリはこの作業コピーには無く、Hが既に保存したCSVを使った。Hの `sources/provenance.json` によれば、出典は別ブランチのcommit `c0bd76dba24b808866ca6f8b96bffda742d08320`、`jssa/results/exact-comparison-pc-20261022/aggregate/cases.csv`。本作業ではfetch・checkout・追加取得をしていない。

[provenance.json](provenance.json) に入力328ファイルのSHA-256・サイズ、Pythonの版、集計コードと固定手順のSHA-256を保存した。ハッシュは集計に使ったバイト列のもの。比較表自体の古い測定条件と、現在の集計コードの実行条件を混同しない。

## 再実行

リポジトリのルートで、次の2コマンドを順番に実行する。既存の指定PythonとSymPy 1.14.0を使用し、インストールは不要。出力はこのディレクトリ内の対応CSV/JSONを上書きする。経過秒数は再実行で変わる。

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21c-complexity/analyze.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21c-complexity/theory_check.py
```

`analyze.py` は標準ライブラリのみ。全323問を結合し、rawのhitを数え、CSVと照合する。`theory_check.py` はSymPyを使用し、CPU時間60秒・仮想メモリ1 GiBを自分に設定して小さい厳密計算だけを行う。実測はそれぞれ約0.43秒、1.39秒だった。solverや新規の局所探索は呼ばない。

## 読む順番

| ファイル | 内容 |
|---|---|
| [answer.md](answer.md) | 主報告。結論と根拠、候補3件、限界 |
| [analysis-plan.md](analysis-plan.md) | 結合集計を見る前に固定した群・閾値・最低条件。結果に応じた変更なし |
| [literature.md](literature.md) | 文献本文の確認箇所、確認していない原著、適用範囲 |
| [theory-notes.md](theory-notes.md) | 二次式によるSAT符号化、存在保証を加えた反例、Chebyshevの証明 |
| [per-problem.csv](per-problem.csv) | 323問の全対応表 |
| [human-hard.csv](human-hard.csv) | 大会別上位1/4の33問 |
| [small-d-large-explicit.csv](small-d-large-explicit.csv) | d≤2かつ(N≥10またはD≥8)の43問 |
| [local-hard-exact-fast.csv](local-hard-exact-fast.csv) | p≤0.1、代数法集合一致、記録3段階合計≤1秒の4問 |
| [summary.json](summary.json) | 群別統計・照合結果・選択閾値 |
| [chebyshev-check.csv](chebyshev-check.csv) | k=1〜8の厳密計算結果 |
| [theory-check.json](theory-check.json) | 理論照合の全結果とコードハッシュ |
| [provenance.json](provenance.json) | 入力328ファイルと集計の来歴 |
| [verification.json](verification.json) | 最終QA結果。コード構文、入力ハッシュ、CSVのID・主要数値、ローカルリンクを確認 |
| [artifact-manifest.json](artifact-manifest.json) | 成果物のサイズとSHA-256。manifest自体を除く |

## 列の注意

- `d` は現在のDSLの変数数。多項式化後の `N,m,D` と、別の変換の `cert_N,cert_D` を混ぜない。
- `p` は問題ごとの保存局所探索のhit割合。空欄は主にd=0。空欄を0成功に置き換えない。
- `human_top_quartile` は大会内で固定した上位群。人間難度が空欄なら対象外。AIMEの閾値は約0.630339、HMMTは約0.845754。
- `small_explicit_proxy` 等のTrueは記述用閾値を満たすというだけで、Pに属する証明ではない。空欄はN,Dの不足。
- `msolve_class=answer_set_matches` は既存の数値検査を経た集合一致。数理的な全解証明と読まない。
- `exact_total_recorded_s` は変換・msolve・filterの全3値がある場合だけ合計。欠けた値を0秒とみなさない。
- `geo_all_matched` は既存比較の3seed全てでの集合一致。局所探索pや保証された成功確率とは別。
- `bezout_product_recorded` と `real_solutions_recorded` は出典の記録を残した列。主報告ではBézout上界を実際の解数・困難性の代用にしていない。

成果物はこのディレクトリに限定。既存入力・`src/`・Python環境を変更せず、commit・pushは行っていない。未使用問題の封印結果は読んでいない。最終QA後に再実行した場合、経過時間等が変わるためmanifestとverificationはその再実行結果を保証しない。
