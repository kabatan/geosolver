# 修正版DSL r1（4問）の評価

- 入力: branch `claude/project-thread-t5cuwm` commit ff7cd31 の `benchmarks/dsl-revisions/`（HMMT-2015-FEB-GEO-04、HMMT-2016-FEB-GEO-03、AIME-2015-II-07、AIME-2013-II-15）。src/は60db4b6と同一。
- 条件: seed 0・1・2、180秒・1コア／job、6並列。323問の結果とは別のcampaignとして記録し、まとめていない。
- 結果: 12/12実行で一致（各seed 4/4）。実時間の中央値4.8秒、最大15.6秒。
