# 学習主体の適合性診断（2026-09-23）

Qwen3-4BとQwen3-4B-Thinking-2507の56答案、追加Qwen3-8Bの6答案を生成・監査済み。学習更新0。全答案は診断用で、学習候補へ流用しない。約1.16時間のGPU worker実時間（読み込み・終了・失敗した起動を含む）。

- [結論と実験結果](REPORT.md) / [次の実験の具体案](NEXT_PLAN.md)
- [事前固定した診断計画](PROTOCOL.md) / [実行設定とモデルrevision](protocol.json)
- [問題文](jobs.json)
- [原モデルの答案](original_4b-answers.md) / [Thinking-2507の答案](thinking_2507-answers.md)
- [追加8Bの答案](original_8b-answers.md) / [追加診断設定](8b-protocol.json)
- [個別採点](grades.json) / [ユーザーの裁定](adjudications.json) / [統合集計](combined-summary.json)
- [旧モデルの基本証明での失敗例](BASIC_COUNTEREXAMPLE.md)
- [先行研究の整理](RESEARCH_NOTES.md)
- [次の学習実験の判断基準](DECISION_FRAMEWORK.md)

`summary.json` は4B同士の事前固定比較、`combined-summary.json` は追加8Bを含む集計。8Bは共通3題だけで比較し、4配置全体の率と混ぜない。元の採点は上書きせず、`adjudications.json` の裁定を派生集計に適用している。
