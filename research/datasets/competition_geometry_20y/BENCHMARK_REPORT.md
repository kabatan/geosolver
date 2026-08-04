# DSL solver性能（frozen runtime）

実行条件: `/home/kabatan/work/solver-experiment-runtime` の固定 geosolver、production baseline pipeline、seed `7`、各 run の total budget 3秒、ケースごとに fresh subprocess、最大8並列。公式解答値は監査台帳の `published_answer` を使用し、DSLから解答値を逆算して期待値にはしていない。`reference_only` は明示的に未実行として記録し、無制約探索の偽陽性を除外した。

| 区分 | 件数 / run | 結果 |
|---|---:|---:|
| 全 JSON | 302 cases / 302 runs | 296 unique scope + 補助別名6 |
| 現行 IR で実行 | 285 files（279 unique） | `success` 188、`no_solution` 85、例外・timeoutを含む |
| `reference_only` | 17 files（17 unique） | 未実行として明示 |
| 正答一致 | — | 136 runs |
| 解答集合が完全一致 | — | 112 runs |
| 例外 | — | 4 runs |
| timeout（30秒上限） | — | 8 runs |

公開解答値が存在するのは全体212 runs（実行可能分206 runs）です。そのうち `success` かつ公開解答値ありは149 runsで、`correct_runs=136` はその solver の `selected_answer`（または許容解答集合）と監査台帳の値を数値比較した結果です。未解答・例外・timeoutを正答扱いにはしていません。`complete_answer_set_runs=112` は、複数解を持つケースも含めてsolverが報告した許容解答集合全体が期待集合と一致した run 数です。

全 raw 値、phase-c の accepted values、seed、wall time、各ケースの status、比較結果は [`benchmark_results.json`](./benchmark_results.json) に保存しています。13件の明示的な解答不一致、4件の例外、8件の timeout も個別行で保持し、公開解答に合わせるため問題定義や DSL を後から変更していません。追加した HMMT-2010-FEB-GEO-09 は公開解答集合 `70;160` に対して `160` のみを3秒 runで報告したため、`answer_match=true`（片方の値）ですが `answer_set_complete=false` として記録されています。

この測定は既存145件の再測定ではなく、今回の20年分コーパス302 JSONの追加測定です。296件は幾何問題としてsource-faithfulにDSL化し、そのうち現行IRで原文の全条項を安全に表現できる279 unique（別名込み285 files）だけを実行しました。円弧・図依存の斜線境界・折り返し後の領域・図が定める順序分岐など現行IRに一意に写せない17件は、定義を推測せず `reference_only` として保持しています。
