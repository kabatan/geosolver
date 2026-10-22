# per-case.csv（問題 × seed 単位の段階別プロファイル、再実行なし）

元データは stage-profile（66d481b）と同じ本計測 `jssa-main-j6-20261022`（凍結版 60db4b6、323問 × seed 0〜2 = 969行）です。solver は動かしていません。作成手順は `mechanism-attribution/` の集計と同じです。

| 列 | 中身（元の記録の場所） |
|---|---|
| candidates_sent_to_refinement | 精密化に送った候補数（`pipeline_summary.refinement.attempted_count`） |
| candidates_converged | 収束した候補数（`refinement.converged_count`） |
| candidates_rejected_as_false | 偽の候補として棄却した数（`exact_assembly.rejected_false_positive_count`） |
| candidates_accepted | 採用した数（`exact_assembly.accepted_count`） |
| refinement_time_s | 精密化の時間（`phase_timings.refinement`） |
| identification_verification_time_s | 同定・検証の時間（`phase_timings.exact_assembly`） |
| final_answer_source | 最終的な答えを出した段階（`answer_source_candidate_id` の `candidate_uid` から判定） |
| search_time_s、rescue_time_s、initial_probe_time_s、wall_time_s | 参考の時間 |

## 全体の数（969行）

- 精密化に送った候補の合計は12,499、収束は8,873、偽として棄却は4,194、採用は8,460です。
- 偽の候補を1つ以上棄却した行は353行（うち正解は338行）です。
- 3つの数（収束・棄却・採用）は同じ候補を重複して数えている可能性があります。互いに足し合わせず、それぞれを別の指標として読んでください。

## 答えの出どころ別（1行あたりの平均）

| 出どころ | 行数 | 精密化に送った候補 | 精密化(秒) | 同定・検証(秒) |
|---|---:|---:|---:|---:|
| Phase A の探索（search/nomad） | 476 | 19.6 | 13.46 | 6.78 |
| 代数的前処理 | 292 | 3.8 | 0.54 | 0.69 |
| 変数0の経路 | 93 | 1.0 | 0.00 | 0.65 |
| LM法の多点出発（scipy） | 74 | 8.0 | 8.06 | 6.09 |
| rescue | 25 | 47.5 | 64.27 | 37.72 |

## 注意

- `candidates_sent_to_refinement` などは、変数0の経路や代数的前処理でも1以上になります（候補を1つ作って確認するため）。
- 6並列で測った時間のため、別の計測と秒数を直接比べるときは条件の違いに注意してください。
- 因果ではなく観察です。
