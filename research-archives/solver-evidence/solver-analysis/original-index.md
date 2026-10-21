# GeoSolver 機構分析の資料索引

固定対象は `e703e2d99484793f162f961bc50126ae65e4069f`。製品ソースを変更せず、研究用の別評価器・途中状態からの介入・独立採点で調べた資料である。

## レポート

- [日本語本文・Markdown](report/research-report-ja.md)
- [配布用PDF](report/research-report-ja.pdf)
- [元原稿](report/manuscript.md) と [節ごとの解釈](report/fragments/)
- [図のPNG・SVGと入力hash](report/figures/)
- [最終ページの目視確認記録](report/qa-final-v1/receipt.json)

最終版の有無と採否は本文とmanifestで確認する。`draft` は作成中、`review` は最終査読へ渡した版である。これらを最終版の代わりに引用しない。

## 証拠をたどる

| 読みたい内容 | 入口 |
|---|---|
| 323問・5 seedの全体像 | [集計](analysis/baseline-v1/strata.json)、[問題別](analysis/baseline-v1/problem-results.json)、[全run索引](analysis/baseline-v1/run-index.jsonl) |
| 47問・30 seedと同じseedの反復 | [集計](analysis/detail-v1/summary.json)、[通常生データ](campaigns/detail-30seed-20260911/)、[反復](campaigns/detail-repeat01-20260911/) |
| 同一保持候補への残差介入 | [計画](development/stage-plan-v2.json)、[生データ](development/stage-campaign-v2/)、[元条件を動かさず調べた採点](analysis/stage-v3/) |
| 減衰の引継ぎ・尺度・停止イベント | [計画](development/damping-plan-v1.json)、[対応差](analysis/damping-paired-v2/)、[段階開始からの予測](analysis/lm-events-v1/) |
| 標準多点探索・候補選択・同定 | [共通比較](analysis/development-comparisons-v1/)、[候補選択計画](development/selection-replay-v2/plan.json) |
| 未使用問題での予測 | [個別予測の凍結](unknown-intake/individual-predictions-v1.json)、[途中採点](analysis/prediction-mid-v1/)、[最終採点](analysis/prediction-final-v1/) |
| 将来stepを計算しない有限停止の補足 | [通常pilotからの事前予測](unknown-intake/rootfree-stop-v1/predictions.json)、[全8開始の採点](unknown-intake/rootfree-stop-v1/assessment.json)、[独立数値検査](unknown-intake/rootfree-stop-v1/independent-checks.json) |
| 初期量の十分条件・分母床だけの原因介入 | [15スカラー条件](development/initial-stop-certificates-v1/)、[同一軌道の一対](development/denominator-pair-v1/) |
| 根中心のLMモデル照合 | [途中96条件の全軌道](analysis/finite-lm-mid-v3/)、[最終60条件](analysis/finite-lm-final-v1/) |
| 参照値と探索の分離 | [分離記録](unknown-references/separation-receipt.json)、[公式解答からの参照](unknown-references/assessment-v1/) |
| 原問題、構造、採用・差替えの理由 | [入力と出典](unknown-intake/)、[過去生成例との照合](history/generated-input-audit-v1/) |
| 履歴をどこまで再利用したか | [生データ照合](history/reuse-integrity-v1/)、[過去版との対応比較](analysis/history-comparison-v1/) |
| 実装の段階とソース | [実装対応表](implementation-map.md) |
| 原典と今回との差 | [文献比較表](literature/comparison-v1.md)、[取得した原典](literature/sources/) |
| GPT-Pro監査への回答 | [監査記録](audits/) |
| 全資料のhashとコード | [再現用索引](reproducibility/receipt.json)、[ソース一式](reproducibility/source-and-research-code.tar.gz) |

`completion` があるだけで全実験の成功を意味するわけではない。実行エラー、打切り、未開始、条件の不成立、予測の保留を、それぞれの集計と本文に残している。seed、保持候補、鏡映、同じ軌道の複数目標は独立した自然問題数へ加算しない。

主な到達点は、自然問題の構成・残差・目標と固定実装の精密化・停止を結ぶ限定的な機構説明である。元の未知自然60問への自動因子検出は0/60で、全pipelineの成否予測は全保留だった。人手で構造を解析した自然2問の補足は8開始中6認定が一致、2開始保留であり、一般的な未知成否予測の達成を意味しない。

## 図と本文の再生成

測定用環境と描画用環境は分けている。以下は既存の生データを読むだけで、solverを再実行しない。図・本文の派生ファイルを再生成するため、配布時のhashとの比較が必要な場合は、先にそのファイルを別名で保存する。

```bash
cd /home/kabatan/work/solver
STUDY=/home/kabatan/work/solver-experiment/research-archives/solver-analysis
REPORT_PY="$STUDY/report/.venv/bin/python"
"$REPORT_PY" -B benchmarks/solver_analysis/report_figures.py "$STUDY" "$STUDY/report/figures"
"$REPORT_PY" -B benchmarks/solver_analysis/build_report.py "$STUDY"
"$REPORT_PY" -B benchmarks/solver_analysis/render_report_pdf.py "$STUDY/report/research-report-ja.md" "$STUDY/report/research-report-ja.pdf"
```

描画環境のパッケージは [requirements.txt](report/requirements.txt) に保存した。日本語フォントはIPA明朝・IPAゴシック、数式の補助文字はFreeSerifを使う。実際のフォントファイルとライブラリ版はPDFと図のmanifestに記録される。異なるフォントやライブラリ版では、同じ数値でも改ページやPDFのhashが変わり得る。

## 数値計算を一例だけ再現する

基準実装と `uv.lock` が一致する測定用 `.venv` を使う。以下の `REPLAY` は存在しない新しいディレクトリを指定する。元の保持台帳の先頭点から、残差の表現だけを変えて、100桁・80反復の診断を行う。公式参照値をoptimizerに与えない。

```bash
cd /home/kabatan/work/solver
STUDY=/home/kabatan/work/solver-experiment/research-archives/solver-analysis
REPLAY="$STUDY/replay-example-v1"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir "$REPLAY"
taskset -c 0 .venv/bin/python -B benchmarks/solver_analysis/paired_stages.py run \
  "$STUDY/development/representations-v2/JMO-2013-PRE-05/original.json" \
  benchmarks/dsl/JMO-2013-PRE-05.json "$STUDY/development/jmo-legacy-source-pool.json" 0 \
  "$REPLAY/original.json" --engine native_lm --iterations 80 --dps 100 --seconds 30
taskset -c 0 .venv/bin/python -B benchmarks/solver_analysis/paired_stages.py run \
  "$STUDY/development/representations-v2/JMO-2013-PRE-05/projection.json" \
  benchmarks/dsl/JMO-2013-PRE-05.json "$STUDY/development/jmo-legacy-source-pool.json" 0 \
  "$REPLAY/signed.json" --engine native_lm --iterations 80 --dps 100 --seconds 30
```

出力は二進仮数・指数を保持した `exact_codec` 形式である。`pre_verifier_point` が比較対象の座標、`trace` が実際のLM step・減衰・線探索である。診断には最終verifierによる座標修正を含めていない。同一seedの180秒実行全体を完全に再現したと解釈しない。

通常の全体測定を再実行する場合は、`benchmarks/research_runner.py run` に別の出力先、`--jobs 8 --seeds 0,1,2,3,4` を指定する。既存campaignを上書きしない。研究ファイルのため `--allow-dirty` を使う場合も、固定の製品ソース・入力・依存のhash照合を省略しない。

全介入の条件順・初期点・反復数・精度・CPU割当は各planと実行manifestにある。plan内の出力先は当時の絶対パスであり、そのまま再実行して既存資料へ書き込まない。再実行する条件の出力引数を新しい場所へ変える。過去の外部archiveは、`history` の完全照合記録と元の保存先を参照する。

## 初期量の停止上界を再現する

`finite_stop_test.py powers NEW_DIRECTORY` は15スカラー条件について、初期量の上界を保存してから実測する。`finite_stop_test.py floor NEW_DIRECTORY --archive "$STUDY"` は保存済みのJMO段階入口から分母床だけを変える一対を再実行する。両者とも測定用Pythonを使い、既存の結果ディレクトリを指定しない。

自然2問の補足は `rootfree_stop.py` の `prepare`、`pilot`、`predict`、`measure` をこの順で実行する。全コマンドへ同じ新規ディレクトリを渡し、`prepare` と `measure` には `--archive "$STUDY"` を付ける。`predict` はpilotの保存状態と固定定数から有理上界を計算する。100桁の将来軌道、目標、参照答を入力に含めない。ただし問題専用の式は人手の構造証明から導いており、証明に根の情報が含まれることを本文と同様に区別する。

保存された元の予測は実測前の記録である。再実行は再現確認であり、元の事前成績を新しい結果で置き換えない。図・本文・監査記録・全生データへの索引は本ディレクトリに揃え、再現用tarには固定製品ソース、研究コード、元323問の入力と依存lockを収録する。約12 GBの測定資料は重複圧縮せず、[全ファイルのSHA-256索引](reproducibility/archive-files.jsonl) から辿る。過去版の外部archiveは元の保存先と照合receiptを参照する。
