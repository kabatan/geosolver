# 圧縮前（全点を自由な x,y で書いた）competition_geometry_20y の DSL

## 結論

**DSL ファイルそのものは、このスーパーPCには残っていません。** 置けるのは、圧縮前の測定結果と、44件・17件の根拠となる記述だけです。

## 探した場所と結果

| 探した場所 | 結果 |
|---|---|
| `~/work/solver-experiment`（experiment ブランチ）の `research/datasets/competition_geometry_20y/dsl/` の git 履歴（全ブランチ） | 最初の版は 94aa68c4e（2026-08-04 18:30）で、この版が既に 0〜7変数です（0:43, 1:39, 2:62, 3:55, 4:52, 5:23, 6:17, 7:11、8以上は0件）。それ以前の版はこのrepoに無し。`-S` 検索でも最古は同コミット |
| 同repoの dangling object（49,973個の未到達blob） | DSL形式のJSONは0件 |
| `~/work/solver`、`solver-research-assets/workspace-before-research-root-20260830`、`research-archives/*`、`solver-artifacts/experiment-freeze-20260727/*.tar.zst`、`/tmp`、`/var/tmp`、`~` 以下の全 json | `source_statement` と `variables` を持つ DSL は圧縮後の302件の1か所のみ。8変数以上のものは0件 |
| 測定時の実行環境 `~/work/solver-experiment-runtime`（結果JSONの `runtime_root`） | 存在しない |

## 日付の根拠

- `DOF_COMPRESSION_AUDIT.md` の初出コミットは 15370d2f8（2026-08-05 04:53）。ただし DSL の最古の版（2026-08-04）が既に圧縮後で、`PERFORMANCE_DIAGNOSIS.md` の冒頭に「更新 (2026-08-03)」とあります。圧縮は 2026-08-03〜04 に行われ、圧縮前のDSLは git にコミットされる前に置き換わったと考えられます（推測）。
- 圧縮前の測定結果 `benchmark_results_180s_1core.json` は、94aa68c4e でコミットされています。ファイルの更新時刻は 2026-09-08（アーカイブ時にコピー）。

## ここに置いたもの

- `baseline-pre-compression-results.csv`: 圧縮前の302件の180秒/1coreの結果（case_id, status, wall_sec, answer_match, expected_answer）。success 218、no_solution 38、timeout 25、reference_only 17、exception 4。
- `diagnosis-excerpt.md`: `PERFORMANCE_DIAGNOSIS.md` の「変数数の爆発」節の原文。8変数以上44件の内訳（success 24、timeout 17、no_solution 3）、14変数超6件は全件timeout、変数数の多い6件（HMMT-2019-FEB-GEO-10: 38変数 ほか）の変数数と、その過剰な表現の説明。

## 分からないこと

- 44件の case_id の一覧は、どの文書にもありません（変数数の多い6件だけ原文にあります）。
- 17件のtimeoutのうち、`timeout` の25件はCSVで分かりますが、どれが8変数以上かは特定できません。

## 代わりに使えそうな方法（提案）

圧縮後の DSL には `source_statement` と `clause_ledger` が全件残っています。圧縮前の形（全点を自由な x,y と残差制約で表す）は、この元の条件から機械的に作り直せます。ただし、作り直した版は「当時の入力そのもの」ではなく、再現であることを明記する必要があります。必要なら、この再現の作成を依頼してください。
