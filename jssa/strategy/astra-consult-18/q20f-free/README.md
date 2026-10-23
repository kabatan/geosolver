# Q20f 成果物

最終判断・候補3案・小検証の結果は[answer.md](answer.md)。Aの核としては不可。一次の固定続行目安R1は0/5、R2は該当例なし。新しい局所探索は行っていない。

| ファイル | 内容・継承状況 |
|---|---|
| [answer.md](answer.md) | 再開後の最終報告。各候補(a)〜(h)、全8問、限界を記載 |
| [answer-interim.md](answer-interim.md) | 最終稿に置き換える直前の暫定報告を保存 |
| [literature.md](literature.md) | 書誌・一次資料のリンク・確認範囲・未確認事項 |
| [theory.md](theory.md) | 経験分布モデル、回収費用の式、一般例、理論の適用限界 |
| [analysis-plan.md](analysis-plan.md)、[analyze_restarts.py](analyze_restarts.py) | 継承した一次手順と集計コード。変更なし |
| [summary.json](summary.json)、[all-problems.csv](all-problems.csv) | 継承した一次集計。292問×固定費2条件、584行 |
| [multi-value.csv](multi-value.csv)、[cutoff-curves.csv](cutoff-curves.csv) | 多値8問×固定費2条件の16行、各seed・6打切りの192行 |
| [provenance.json](provenance.json) | 継承した入力584ファイル・計画・コードのSHA256 |
| [theory-exact.json](theory-exact.json) | 継承した一般確率モデル2例の厳密有理数。幾何実験ではない |
| [posthoc-check-plan.md](posthoc-check-plan.md)、[posthoc_check.py](posthoc_check.py) | 継承した一次結果後の追加検算の手順とコード |
| [posthoc-bootstrap.json](posthoc-bootstrap.json)、[posthoc-bootstrap.csv](posthoc-bootstrap.csv) | 継承した4,000回の事後再標本化。全5問掲載、確認的検定ではない |
| [verify_resume.py](verify_resume.py)、[resume-verification.json](resume-verification.json) | 再開後の整合性・算術監査。一次計算や局所探索を再実行しない |

継承した12ファイルのハッシュは`resume-verification.json`に記録した。表の∞は経験分布の未観測であり、真の不可能性ではない。元データは問題全体の時間制限で打ち切られるため、保存完了試行の選択による偏りがある。

再開監査を意図的に再実行する場合のコマンド（現在の監査は完了しているので再実行不要）：

```bash
env PYTHONPATH=src OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q20f-free/verify_resume.py
```

このコマンドは`resume-verification.json`だけを更新する。一次集計や事後ブートストラップの再実行は、継承結果を上書きするため推奨しない。
