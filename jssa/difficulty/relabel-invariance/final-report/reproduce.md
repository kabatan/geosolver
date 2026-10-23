固定計画の実行はbatch 49のrun書出し失敗で停止した。以下は保存記録を読むだけで、solver・採点器の再呼び出しはない。repository rootから実行し、出力先には存在しない新しいディレクトリを指定する。

```sh
/tmp/q38-58e3993-venv/bin/python -B \
  jssa/difficulty/relabel-invariance/amendment-null-diagnostics/aggregate_missing_artifacts.py \
  --campaigns /tmp/q38-null-diagnostics-authorized-resume/aggregation-view-after-stop-049/campaigns \
  --assessment-root /tmp/q38-null-diagnostics-authorized-resume/recovered-campaigns \
  --output /tmp/q38-mode-counts-recheck

/tmp/q38-58e3993-venv/bin/python -B \
  jssa/difficulty/relabel-invariance/report_null_resume.py --stopped \
  --historical-answer jssa/difficulty/relabel-invariance/execution-records/answer-at-amendment-65627f72.md \
  --output /tmp/q38-stopped-report-recheck

/tmp/q38-58e3993-venv/bin/python -B \
  jssa/difficulty/relabel-invariance/audit_final_resume.py \
  --output /tmp/q38-final-audit-recheck.json
```

集計用viewは元のcampaignへのリンクと、batch 49前半の未採点raw 3件へのリンクだけで構成する。[リンク・hash記録](../resume-records/aggregation-view.json)。batch 49のmanifestやassessmentを作ったものではなく、書出し途中の一時ファイルも正式なrunとして読まない。batch 21の回復assessmentは別ディレクトリから参照し、原本を上書きしない。

旧answer.mdも追補lockの対象だったため、公開前のbytesを[履歴ファイル](../execution-records/answer-at-amendment-65627f72.md)に保存した。`--historical-answer` はその1ファイルの保存場所を明示する。追補lockの全40項目のhash・サイズ・manifestを検証し、この履歴ファイルにも元lockのSHA-256を要求する。他の固定ファイル、実行adapter、採点器、lockは変更していない。新answerへの差替え記録は[publication receipt](../resume-records/answer-publication.json)にある。

`report_null_resume.py` の変更は、旧報告の明示的な検証場所、未実行／試行後raw欠落の区別、完備部分の記述件数だけである。A/Tの閾値、正誤判定、既存assessmentは変更していない。集計器 `aggregate_missing_artifacts.py` は追補時のbytesのまま使用した。

全840枠は、採点196＋未採点raw 3＋試行後外側run欠落1＋未実行640。全40問のA/Tは空欄とし、完備8問の観測だけを報告する。原本・停止receipt・一時ファイル・完了済みrawはすべて保持している。
