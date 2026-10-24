# S6：S3スイッチの適用範囲（静的監査のみ）

対象は `/tmp/s3-impl/src/geosolver`。実ファイルから `runtime/integrity.py` と同じ規則で計算した source_hash は
`sha256:add5afaf829806ca3cbd11fb07b69d956102752e1c6738b0630581a3ceb121eb`。
全ファイルのSHA-256は `source-hashes.json`、下記関数の原文・行番号・呼出箇所は `switch-scope-evidence.json` に保存した。
solver本体、探索、精密化、最終検証、同定は一切実行していない。環境変数を渡したフルプロセスの挙動を**コードから**追跡した監査であり、実行検証ではない。

## 結論

**同じ入力座標・同じ残り時間を与えた最終検証の数式・アルゴリズムは、T1/T2で切り替わらない。**
最終検証内から `refinement/mpmath_refiner.py` を呼ぶ経路はあるが、呼ばれるのは `_select_rank_revealing_subsystem` のみで、この関数はスイッチを読まず、残差書き換え・Newton closure・解析ヤコビ行列へも進まない。
`mpmath_refiner` のモジュールimportに伴い `analytic_jacobian` もimportされるが、import時にモードを評価せず、最終検証から `derivative_plan` / `compile_jacobian` / `evaluate_jacobian` を実行する経路はない。
したがって「refinementのファイルを参照しているから最終検証もT1になる」とは言えない。最終検証が独自に行う局所補正は凍結版のままである。

ただし、次の二点は区別が必要である。

1. **探索・候補選択の実際の結果まで不変という強い前提は成立しない。** 精密化で得た座標、残差、成功数、消費時間が変わると、最終検証に渡す候補・順序、同定の値と誤差、rescue、第二探索の実行有無や残り時間が変わり得る。これはスイッチの直接参照ではなく、完成したsolverの既存のフィードバックである。事前登録13を完成したsolverの最終性能比較と読む場合は、この間接効果を含む。
2. **「接点を使う残差だけを替える」という介入の前提は、現実装のままでは厳密には成立しない。** T1は接点を証明できない `Distance(中心,直線)=半径` にまで二乗式の書き換えを追加する。さらに解析ヤコビ行列計画の可否も変える。この点は最終検証への漏出とは別の問題である。後述の最小変更案は設計のみで、適用していない。

## プロセス境界とスイッチ読取

`application/service.py:solve` → `engine/runner.py:EngineRunner` → worker → standard pipeline。
`engine/runner.py:113–138` は `os.environ.copy()` を子プロセスに渡す。`runtime/symbolic.py:40–52` も環境をコピーして記号処理workerを作る。したがってフルプロセスへ設定した `GEOSOLVER_S3_TANGENCY_MODE=T1` は内部でも有効である。環境を消す隔離は存在しない。

読取元は `refinement/s3_tangency.py:8–12` の `tangency_mode()`。
未設定はT2、T1は文字列T1、他の有効値はT0。T0は今回の比較対象外。
この関数の実際の呼出元は次の三箇所である。

| 呼出元 | 効果 |
|---|---|
| `mpmath_refiner.py:576` `_smooth_zero_constraint_residuals` | T2の接点式／T1の符号付き残差・二乗式を選ぶ |
| `mpmath_refiner.py:1047` `_run_findroot_closure` | T0で解析微分の平滑化計画を採用しないゲート。T1とT2ではこの真偽自体は同じ |
| `analytic_jacobian.py:183` `derivative_plan` | T1を計画キャッシュ・worker payloadに含める。`compile_jacobian` はpayloadのmodeを使用 |

## 呼出グラフ

矢印は関数呼出、`[import]` はモジュールを読み込むだけの関係である。

```text
run_external_pipeline._run_pipeline_stage
  ├─ run_initial_probe / run_search                 [元の評価器・候補選択]
  ├─ run_refinement → MpmathRefiner.refine_candidates
  │    └─ _refine_single_candidate
  │         ├─ _run_stage
  │         │    └─ _residual_vector_for_stage(smooth_zero_constraints=True)
  │         │         └─ _smooth_zero_constraint_residuals → tangency_mode  ★
  │         └─ warm Newton / _apply_post_lm_closure_polish
  │              └─ _run_findroot_closure
  │                   ├─ 平滑残差 → 同じ書き換え ★
  │                   └─ derivative_plan → tangency_mode ★
  │                        └─ request('refinement_jacobian', payload)
  │                             → symbolic_operations.dispatch
  │                             → compile_jacobian(payload.mode)
  └─ assemble_exact_results
       ├─ refined_candidatesを原残差norm順に並べる
       ├─ _verify_revision → verify_final_candidate
       │    ├─ evaluator.verification_equations → prepare_equations
       │    │    ├─ request('normalize') → exact_constants [微分計画ではない]
       │    │    └─ _smooth_zero_equation → _SignedTangency [モード非依存]
       │    ├─ linearization → differentiate / VerificationSystem.sample
       │    │    └─ 元のHP評価、分岐追跡、局所有限差分
       │    ├─ correction
       │    │    └─ mpmath_refiner._select_rank_revealing_subsystem
       │    │         └─ 完全ピボット消去のみ [スイッチ・微分計画を呼ばない]
       │    ├─ sample_equations [補正試行の評価]
       │    └─ DomainVerifier.verify / answer、hard feasibility
       ├─ 必要な高精度confirmation → _verify_revision [同じ経路]
       └─ identify_answer → request('identify') → 同定・誤差内一致確認

verification_numerics.correction
  └─ [import] mpmath_refiner
       └─ [import] analytic_jacobian → [import] s3_tangency
            [ここではtangency_modeを呼ばない]
```

最終検証の `linearization` は `verification_numerics.py:313–362`、`correction` は同365行以降、ランク選択への唯一の呼出は393行付近。
`_select_rank_revealing_subsystem` は `mpmath_refiner.py:723` から始まる独立関数で、環境変数・モード・evaluatorを受け取らず、入力行列と精度・許容値のみで消去する。
`verify_final_candidate` は `final_verifier.py:85` 以降で独自の9回以下の補正と精度段階を持つが、`MpmathRefiner` の精密化を再度呼ばない。
`_smooth_zero_equation` は独自の `_SignedTangency` を使い、`geometry/mp/signed_tangency.py` とHPコンテキストの実装にもS3環境変数の参照はない。

探索側の `square_difference.py` / `integer_targets.py`、`problem/analysis_plan.py` にも `mpmath_refiner` の参照がある。整数条件の構文抽出・評価、bounds変換はモード非依存。integer completion中の `MpmathRefiner` の利用は精密化であり、最終検証の内部呼出ではない。

## 同定・探索・候補選択への間接効果

`assemble_exact_results.py:159` の候補順は精密化後の `residual_norm_hp` に依存する。候補の状態・座標・誤差も同定の入力になる。最終検証自体のコードが同じでも、入力候補や残り時間の差によって出力が違うことはある。
`run_external_pipeline.py:_complete_pipeline_stage` は受理候補の不足と残り時間でrescueを決める。
`_run_ordered_search_attempts` は受理候補、代数的枝の未完了、残り時間でfallbackを決める。
`_should_select_fallback_attempt` は受理数、精密化後の最良残差などで採用側を決める。
初回探索の数式と精密化前の候補選択規則にはスイッチの直接作用はないが、完成したフルプロセスの全探索履歴・採用候補が同じとは保証できない。共有のwall-clock deadlineや記号workerの処理時間差も間接経路に含む。

## 接点式なしでもT1が式を変える箇所

`_smooth_zero_constraint_residuals` は、T2では `distance_contact_sources` が返す「接点を証明できる行」だけを書き換える。
ところがT1では同じ辞書を `distance_radius_sources` 全体で置き換える（576–588行）。この関数は接点証明を要求しない。
このため、T2が原式 `Distance(center,line)-r` を使う行でも、T1は `(a*x+b*y+c)**2-r**2` を使う。
`analytic_jacobian.compile_jacobian` も、T1でその形式が一つでもあると計画を返さず、有限差分へ移る（30–36行）。

該当は、指定の「T2に接点式なし」というOR条件で同式群に入った15問。
全IDと行ごとの両側の式は `grouping-evidence.json:syntax_formula_discrepancies` および `groups.json` に記録した。
群を恣意的に移動していない。同式群33問は**指定判定による名称**であり、うち15問は実装上の式一致の証明には使えない。
S3の6問は保存された先頭候補の残差バイト・使用式一致、残る構文判定12問は両側のDistance書き換え辞書も空で式一致を証明できる。

## 前提を厳密に成立させる最小変更案（未適用・未実行）

最終検証のT1漏出を止める変更は不要。より明確な依存関係にしたければ、モード非依存のランク選択だけを共通モジュールへ移し、両方から参照する整理が可能だが、今回変更していない。

「接点を使う残差だけを替える」には、次の二箇所を変更する。

1. T2の `distance_contact_sources` をまず固定し、T1の `distance_radius_sources` を**そのキーに限定**する。接点式のないDistance行はT1でも原式のまま残す。T2が接点式を持つ行はT1の対応する非接点式へ替える。
2. 解析ヤコビ行列のT1用Distanceゲートも、T2が接点式を持つ行に限定する。T2が書き換えない行だけの問題で、T1だけ計画を無効にしない。IsTangentに対するT1用微分は現行どおり非接点式と整合させる。

変更すればsource_hashは変わるため、新しいhash、介入の説明、群の根拠を本計測前に固定し直す必要がある。登録文書・ソース・群判定は今回修正していない。

もし「追加探索の発動や最終採用候補も完全に同じ」を要求するなら、環境変数のスコープ変更だけでは足りない。精密化前候補・探索列・段階別予算を外側で固定・再生する別実験が必要になる。これは完成したsolverの最終性能比較から実験の問いを変えるため、今回のdriver案には混ぜない。
