# Q43c：記録の読み方と再解析

本件は仮説なしの探索。既存の20問・5種類（原問、長さ、面積、角、比）・2 seed（43101、43102）、各180秒を引き継いだ。問題選択は `selection.json`、順序は `schedule.json`。開発群10問、unseen_a/b各5問で、結果による除外・置換はない。unseen_a/b は他の実験でも使われており、独立した確認群ではない。

問題と点は事前のハッシュ順で選んでいる。点3個の非共線性や、交換した量の一意性による選別はない。そのため面積0や角0・πとなる問合せも含む。種類ごとの集計は、この選択規則に対する記述値である。

`resume-manifest.json` に従い、実行元は `/tmp/q43c-clean`、commit は `60db4b679b04167175c51c479c87c22fa663fda0`、source hash は `sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5`。既存の2並列・各1 core（CPU 14/15）を維持した。最初の選択記録にある3並列は履歴であり、隔離後の実行設定はこの manifest が定めている。

再開時にホストのプロセスを確認し、動いていたドライバと子をそのまま採用した（`continuation.json`）。この継続では solver の起動を追加していない。共有 worktree で行われた先行1試行は `/tmp/q43c-swap-target-20261024/runs/000` に保存済みで、既存の隔離方針どおり集計に混ぜない。採用する200試行の生記録は `/tmp/q43c-swap-target-clean-20261024`。5 MBを超える生ログをリポジトリに複製しない。

## 指標と限界

- `public_solved`：公開APIが厳密な形式の答えを返したこと。交換した量について独立した正答集合を用意したわけではなく、正答率や全解列挙の保証ではない。APIの完全性も `unknown`。
- `numeric_feasible`：凍結版の最終数値検証を通った候補があること。独自の残差閾値では採点しない。検証には問う量の評価・定義域も関わるため、純粋な「図を見つけたか」だけの指標ではない。
- 原問の正答：凍結版 `benchmarks/research_runner.py` の答えの正規化、集合キー、正常終了判定を使い、保存済みの参照値と集合が一致した場合。採点器の bytes が同 commit と一致することも検証する。
- 時間：公開APIが返るまでの壁時計時間。最初の図を見つけるまでの時間は計測されていない。共有機の負荷と締切の影響があり、時間差から処理の因果効果を分離できない。CPU時間と段階別時間も保存する。
- seed再現：同じ20問で外部seed 43101/43102を比べる。別の問題での追試ではなく、seedは2つだけ。凍結版の追加探索は外部seedから連続5個を派生するので、両実行の内部seedは4/5が重なる。再現を完全に独立な追試とは扱わない。探索後の所見に有意差検定や確認済みのラベルを付けない。
- `selected_search_evaluations` は最終的に選ばれた探索段階の記録で、全段階を通した総評価数ではない。

`analyze.py` は100入力のハッシュ、target以外のDSL一致、コンパイル後の条件一致、実行元、資源、スケジュール、採点器を検査する。候補座標の距離は保存された検証済み座標をfloatにして比べた記述的な補助値で、0でも厳密な図の一致を証明しない。

APIの時間切れは `diagnostics=null` を返す。凍結済みの読み取り関数は辞書を想定するため、その読み取り時だけ空辞書として渡す（元の生記録・status・採点器は変更しない）。時間切れを正常終了にはせず、欠けた段階や数値候補を推測しない。中断扱いで置換したり再試行したりもしない。

`explain_saved.py` は原問で保存された最初の検証済み図へ5種類の問う量を代入するだけで、探索・精密化・再同定・再採点は行わない。100桁での代入値は `saved-figure-targets.json`。AIME-2019-I-12 と AIME-2014-II-10 の明示式から係数を求めた計算は `coefficient-examples.json`。AIME-2012-I-14 と HMMT-2011-FEB-GUTS-01 の交換後の量が一意でないことは、明示的な解の族として `nonunique-targets.json` に残す。他18問すべての一意性を証明したものではない。

`analysis-summary.json` の `paired_comparisons_all` は全20問の対応比較、`paired_comparisons_excluding_two_known_nonunique_problems` は上記2問を除いた事後的な感度分析。元の200試行は残し、除外版を主要な成功率に置き換えない。`answer_sets_agree_when_both_solved` は両seedで答えが返った場合だけの集合一致であり、独立な正答確認ではない。

## 凍結コードから確認した仕組み

下記は上記commitのコードを読んだ結果で、solver本体は変更していない。

- `src/geosolver/problem/adapter.py`：条件と問う量を別々に変換する。
- `src/geosolver/engine/standard/evaluation/ir_evaluator.py`：最終検証の定義域に答えの式も含める。
- `src/geosolver/engine/standard/orchestration/assemble_exact_results.py`：数値候補の検証後、答えを同定する。
- `src/geosolver/engine/standard/exact_assembly/identify_answer.py`：多項式探索には次数・係数上限があり、最も広い設定でも次数8、係数の絶対値10^8まで。別の同定経路もあるため、上限だけから失敗が必然とは言わない。
- `src/geosolver/problem/models.py`：公開答えは代数的数または代数的係数によるπの一次式。一般の逆三角関数の式をそのまま返す形式はない。
- `src/geosolver/engine/standard/orchestration/run_external_pipeline.py` と `search/completion/rescue.py`：厳密な答えを得たかが、追加探索や別探索段階へ進む条件に関わる。答えの同定失敗と探索の終了条件は分離していない。

## 再解析

既存の生記録を使い、実験を追加せずに集計する。

```bash
env PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/sweep/c-swap-target/analyze.py
env PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/sweep/c-swap-target/explain_saved.py
```

最終集計は200件の受領記録がなければ停止する。`--partial` は未完了と明示した途中集計を生記録側の `analysis-preview/` にだけ出す。`prepare.py` や `isolate.py` をやり直して選択や過去の実行を置き換えない。
