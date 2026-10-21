# exp02の検証資料

[完了報告](../exp02-technical-results-2026-09-22.md) の数値を再確認できるよう、軽い成果物を保存した。
各コピーの元パスとSHA-256は [manifest.json](manifest.json) に記録する。

| 確認対象 | ファイル |
|---|---|
| 全体の通過条件・実行コードhash | [readiness.json](readiness.json) |
| CPUの44勾配比較 | [loss_equivalence.json](loss_equivalence.json) |
| exp01 adapterの精度比較 | [exp01_forward.json](exp01_forward.json)、[exp01_actor.json](exp01_actor.json) |
| 固定回答3更新、注意計算変更後の再検証 | [fixed_update.json](fixed_update.json)、[fixed_update_attention_recheck.json](fixed_update_attention_recheck.json) |
| 注意計算の参照一致と最大長の実負荷 | [attention.json](attention.json)、[capacity.json](capacity.json) |
| 自然生成16回答・1更新 | [natural_generation.json](natural_generation.json)、[natural_update.json](natural_update.json) |
| 更新の復元・生成側への反映 | [checkpoint_reload.json](checkpoint_reload.json)、[natural_actor.json](natural_actor.json)、[resume_smoke.json](resume_smoke.json) |
| 正解報酬11件の数学的確認 | [positive_answer_review.json](positive_answer_review.json) |
| OOM前後のソース・入力の由来 | [original_execution_manifest.json](original_execution_manifest.json)、[update_recovery_manifest.json](update_recovery_manifest.json)、[update_recovery_attempt.json](update_recovery_attempt.json) |
| 本学習の入力・評価・206依存の固定確認 | [long_run_preflight_manifest.json](long_run_preflight_manifest.json) |
| 元実験の保持・テスト結果 | [exp01_preservation.json](exp01_preservation.json)、[verification_tests.log](verification_tests.log) |

全token列・回答本文・old/new logprob・モデル状態・失敗ログは `qwen/.runtime/exp02_tech/` に残している。
元の失敗した実行記録は保持し、修正後の完了記録は `live/RECOVERED_COMPLETE.json` とした。
この資料は技術的較正の結果であり、数値監督から証明への転移を示す評価結果ではない。
