# 2026年新規問題の一回限りの評価（凍結版solver）

- 入力: branch `claude/project-thread-kyag6v` commit eeec693 の `benchmarks/new-2026/`（HMMT Feb 2026 17問、JMO 2026予選 3問）。src/は60db4b6と同一。
- 条件: seed 0・1・2（実行前に固定）、180秒・1物理コア／job、6並列（taskset、CPU 4はGMB比較が使用）。結果を見た後のDSL修正はしていない。
- 結果: seed0 18/20、seed1 19/20、seed2 18/20、合計55/60。3seedすべて一致18問、全seed不一致1問。実時間中央値9.9秒。時間切れ2回、engine_error 0。
- 不一致:
  - HMMT-2026-FEB-GEO-05: 3seedとも答え 8√6 を出せず。いずれも約163秒で探索を終え、候補はガード違反（domain_violation, guard returned False）で棄却。
  - HMMT-2026-FEB-GEO-09: s0・s2で時間切れ（3+√11を検証できず、domain_boundary_unresolved）。s1は152.8秒で一致。
- 問題ごとの表は `per-problem.md`、実行ごとの記録は `per-run.csv`。
