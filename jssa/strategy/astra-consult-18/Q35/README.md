Q35の結論は[answer.md](answer.md)。整数計数は再現したが、自由度による一般的な認証優位は未識別。Aの中心候補としては不可。

**入力と凍結版。** solver/srcのGit treeは `ab7b6ceabc60b205d78bd4fc9d8a08b5f605aae3`、commit `60db4b679b04167175c51c479c87c22fa663fda0` と一致。benchmarks/cases.jsonl、pyproject.toml、uv.lockにも同commitとの差分なし。既存集計・実験データは後に作られた研究成果を使った。共有checkoutのHEADが進んでも、入力はハッシュで監査する。

依頼文のQ35節は、開始時の作業ツリーの `jssa/strategy/codex-tasks-1023.md` にはまだなかったため、取得済みローカルGit参照 `origin/claude/project-thread-9bdbbg` のcommit `2c1efa588fc3d242efdfb6db19a1a3a3573cf934` にある同ファイル末尾を読んだ。fetch/pull/checkoutは行っていない。Q27f/answer.md、H/answer.md、Q11/certify-all/answer.mdと関連原票を参照した。

主な出典：

- [Hの68問分類](../../astra-consult-17/H/classification.csv)：G/L0/R0/GAUGE/AUX。局所分類であり、全実成分の分類ではない。
- [Q11の343問表](../../../difficulty/certify-all/per-case.csv)：開発323問のみを抽出。各resultのSHA-256を照合し、recovery/recovery2の採用先も表に従った。
- [旧msolve/Singular比較](../../astra-consult-17/H/sources/comparison-cases.csv)、[来歴](../../astra-consult-17/H/source-provenance.md)。旧直接消去は600秒、旧恒等式は300秒、Q11は全体60秒＋段階上限で、同じ成功指標ではない。
- [旧成分分解](../../astra-consult-17/H/sources/prior-components.json)。生成元は一部表示が切られているため、この表示だけをQ35の厳密証明には使わず、3例の族を保存された完全なFに代入し直した。
- `minima/raw-323-seed1`：54問の候補集合のみを再抽出。cls/ref/参照解による選別なし。

旧H/sourcesとL/vendorのalgebraize.py、run_exact.pyの相違は末尾の改行1個のみ。ただし、旧比較とQ11全体の実行条件・根選別は同一ではない。

**検算だけを再実行する。** リポジトリルートで以下を実行する。通常1秒程度、1プロセス。元データと予測lockは変更せず、verification.jsonだけを更新する。`--replay-census` はQ35内の一時ディレクトリで集計を再生成して比較し、その一時生成物を片付ける。

```bash
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q35/verify.py --replay-census
```

**小実験の再実行。** 次のコマンドは指定問題のQ35結果を上書きする。現在の数値を保持したい場合は先にQ35を別途保存する。予測と依存ハッシュが変わっていれば実験は停止する。`paired` は1コマンド約39秒以内、`components` と `seed` は今回各1秒未満だった。すべて逐次に実行する。

```bash
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q35/experiment.py components AIME-2009-I-12
```

componentsの残りIDはHMMT-2006-FEB-GEO-01、JMO-2013-PRE-08。pairedの6IDは[prediction.md](prediction.md)と[paired.csv](paired.csv)に固定してある。例：

```bash
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q35/experiment.py paired AIME-2011-II-04
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q35/experiment.py seed
env PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q35/summarize_experiments.py
```

各問の成功予測を変えず再現するコードなので、新しい実行環境でP2/P3の結果が変わればverify.pyの当初結果[3,0,0,7]との一致は失敗する。別計算機の成績を当初結果として上書き採用しない。

`analyze.py` は最初の集計生成器。これを直接実行すると固定済みsummary.jsonの生成時刻も更新されるため、保存版の検算には上記の `verify.py --replay-census` を用いる。予測lockを再生成して過去の予測と称することはしない。

**資源と成果物。** 1worker、BLAS/OMP/MKL各1thread、AS上限2GiB、1ファイル4,500,000bytes上限。計算は18腕・約229秒の記録時間、数値solver新規実行0回。新規ファイルはこのQ35内のみ。5MB超のファイル、依存導入、本担当によるcommit/pushはない。予測2ファイルは別作業のcommit `428223c` に含まれる（commit件名はlock後、実験が始まっていた可能性を明記）。予測固定後の実験コード変更はなく、検算器のHEADメタデータ比較の修正だけを[検算履歴](verification-attempts.md)に残した。

主要成果物はanswer.md、mechanism.md、case-matrix.csv、strata.csv、archived-certificates.csv、summary.json、prediction.md、prediction.lock.json、experiment-summary.json、seed-candidates.json、paired/、components/、certificates/、verification.json。各表の生成コードと入力のSHA-256も同梱している。
