# Q21a Manders audit

最終判定・候補2件の(a)〜(h)・文献・結果は [answer.md](answer.md)。

## 再現

リポジトリのルートから順番に実行する。元データとsrcは読むだけで、出力はこのフォルダ内の同名ファイルを更新する。新しい局所探索は開始しない。既存Python環境を使い、インストールは不要。

```bash
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21a-manders/analyze.py
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21a-manders/semantic_v2.py
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21a-manders/verify.py
```

第一監査41.74秒、第二監査31.23秒、各1プロセス。実行時刻や圧縮ファイルの時刻情報などは再実行で変わるため、出力ファイルのバイト単位一致を再現の条件にはしない。

## 出力

| ファイル | 内容 |
|---|---|
| analysis-plan.md | 第一集計前の固定計画。既読結果のある開発集合の再解析であり外部事前登録ではない。 |
| input-manifest.json | 第一監査の入力587ファイル・src・計画・コードのハッシュ。 |
| endpoint-cross-tab.csv, sensitivity.csv | 実装の等式達成とhard判定の交差、閾値感度。 |
| endpoints.jsonl.gz, per-problem.csv | 第一監査の失敗終点と問題別集計。 |
| constraint-taxonomy.csv, guard-taxonomy.csv | 第一監査の暫定分類。diagramをco-exactと読んではいけない。 |
| summary.json, semantic-cross-tab.csv, hard-tags.csv | 第一監査の集計。exact_contactをmetricとまとめた旧集計も保存する。 |
| semantic-v2-plan.md | Hamamiほか確認後の第二監査計画。探索的な修正である。 |
| two-axis-constraints.csv, two-axis-guards.csv | exact/co-exactと計量/位相の二軸、未分類の注釈。 |
| two-axis-endpoints.csv, two-axis-per-problem.csv, two-axis-summary.json | 第二監査の未達所見。因果の分類ではない。 |
| manual-audit.json | HMMT 2024 GEO4の座標guardの意味、追加した2007 GEO2の個別監査。 |
| verification.json | ハッシュ・集計・元評価との一致検算。 |
| provisional-results.md | 第一監査直後の暫定結果。意味分類は最終answer.mdの訂正を優先する。 |
| *.pdf, *.png | 出典確認に用いた公式解答・著者版と確認ページの画像。 |

CSVの問題別カウント欄の空欄は、該当カウンタが立たなかった0件を表す。human列の空欄は欠測。`p`は保存局所探索のhit率であって完成solverの正答率ではない。

候補2の追加計算は設計のみ。新しい人間実験も行っていない。
