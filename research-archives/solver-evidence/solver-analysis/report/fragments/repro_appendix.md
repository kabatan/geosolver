測定はPython 3.12.11、NumPy 2.5.1、SciPy 1.18.0、mpmath 1.3.0、SymPy 1.14.0、PyNomad 4.5.1で行った。図とPDFには別の小さな環境を使い、測定のdependency lockを変更していない。使用した版はreport内のrequirementsとbuild manifestに保存する。

### E.1 主要な保存先

| 内容 | 相対パス |
|---|---|
| 固定条件・323問の生データ | `campaigns/baseline-5seed-20260911/` |
| 47問×追加25 seed、同じseedの反復 | `campaigns/detail-30seed-20260911/`、`campaigns/detail-repeat01-20260911/` |
| 旧版と最終snapshotの照合 | `history/final-v4-audit/`、`history/reuse-integrity-v1/` |
| 再利用候補群、同一候補介入 | `development/stage-campaign-v2/`、`development/jmo-legacy-source-pool.json` |
| 減衰・尺度のpaired介入 | `development/damping-campaign-v1/` |
| 初期点・標準探索器・同定の比較 | `development/comparison-batch-v1/`、`development/common-completion-batch-v1/` |
| 未知問題の出典・入力・予測の凍結 | `unknown-intake/` |
| 探索から分離した独立参照 | `unknown-references/` |
| 未知自然問題の生データ | `unknown-results/mid/`、`unknown-results/final/` |
| 局所診断と同じ物理配置の持上げ | `unknown-local-v1/` |
| 採点・元条件検査・trace解析 | `analysis/` |
| 計測・保存・経路のQA | `harness-qa/` |
| 原典PDFと取得hash | `literature/sources/` |
| 監査依頼・指摘・対応 | `audits/` |
| 編集可能な本文・図・PDF | `report/` |

表の基準ディレクトリは `/home/kabatan/work/solver-experiment/research-archives/solver-analysis/`。測定結果は新しい版に保存し、失敗した初期版も残している。`completion`はプロセスの完了を意味する場合があるため、nonzero exit、timeout、未開始の件数と解析の欠落も確認する。

### E.2 コードと再生成

再利用するコードは `/home/kabatan/work/solver/benchmarks/solver_analysis/` にある。`exact_codec.py`はmpmathの二進仮数・指数等を丸めずに保存する。`paired_stages.py`は同じ候補から新しい精密化を開始し、`common_multistart.py`と`common_completion.py`は初期点を揃えた探索と共通後段を担当する。各planは入力hash、条件、順番、反復上限、精度、CPU割当を含む。

図の再生成は、report用環境で次を実行する。これはsolverを再実行しない。

```bash
REPORT_PY=/home/kabatan/work/solver-experiment/research-archives/solver-analysis/report/.venv/bin/python
STUDY=/home/kabatan/work/solver-experiment/research-archives/solver-analysis
cd /home/kabatan/work/solver
"$REPORT_PY" -B benchmarks/solver_analysis/report_figures.py "$STUDY" "$STUDY/report/figures"
"$REPORT_PY" -B benchmarks/solver_analysis/build_report.py "$STUDY"
"$REPORT_PY" -B benchmarks/solver_analysis/render_report_pdf.py "$STUDY/report/research-report-ja.md" "$STUDY/report/research-report-ja.pdf"
```

通常測定を再現する場合は、保存されたcampaign manifestの入力・source hash・dependency lockを照合し、既存結果とは別の出力ディレクトリを指定する。研究用スクリプトがあるためdirtyな作業木を許す場合にも、製品ソースと測定依存を独立に照合する。既存の結果や固定tagへ上書きしない。

固定反復の診断と180秒の通常測定の時間を直接比較しない。再実行は新しいキャッシュとoptimizerを用いる。元の全内部状態を復元する手順ではない。候補群の選択比較は保持済み群に条件付けたものであり、全探索点の均等な標本ではない。

### E.3 保証と再現の範囲

全runについて入力とsource/dependency hash、seed、予算、環境を保存し、未処理・棄却・時間切れを分母から落とさない。通常実行が保存していない全初期点や、最初の正答が発見された時刻を復元したとは主張しない。時間分布の時刻は最終returnである。

最終PDFは全ページをPNGへレンダリングし、文字・式・表・図・改ページを確認する。Markdown、図表入力manifest、PDFのSHA-256を対応させる。検査記録はreportのQA資料へ残す。


有限LM補足予測は `unknown-intake/finite-lm-supplement-v1/predictions.json` に、初期点・入力・計画のhashと共に保存した。再採点には `prospective_lm_model.py analyze ARCHIVE --split mid --output NEW_DIRECTORY` を使い、最終側は `--split final` とする。freezeコマンドは選択対象の実測が存在すると拒否する。凍結後に同じ予測を作り直して成績を置き換えない。
