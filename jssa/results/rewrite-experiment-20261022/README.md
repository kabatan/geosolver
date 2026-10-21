# 書き換え実験（凍結版solver、2026-10-22 05:06〜05:5x）

- 入力: branch `claude/project-thread-t5cuwm` commit fc34fc8 の `benchmarks/rewrite-experiment/`（PROTOCOL.mdどおり）。src/は60db4b6と同一。
- 実行: `run-order.tsv`、続けて `derivation/run-order.tsv` の順に厳密に1件ずつ。1件ごとに独立したrunner campaignとし（`--case-id`、`--seeds`、`--jobs 1`）、論理CPU 20（1物理コア）に固定した。180秒、1コア。
- 並行負荷: 同じ時間帯にアブレーションを別コアで実行していた。05:06〜05:29はjobs 5（NO_ANALYTIC_JAC）、05:29以降はjobs 6（NO_RESCUE, NO_SCALE_CHART）。CPU 4のGMB比較は05:04に終了。書き換え実験と合わせた同時実行は6〜7ジョブ。
- 実行記録: `rewrite-per-run.csv`（84行）。列は一致、C、実時間、段階別時間、評価回数、経路、入力時の変数・等式数など。前処理後の変数・条件数は成果物に記録がないため含めていない。代数前処理を通った場合は、その枝数を `algebraic_branch_count` 列に入れた。
- 集計: `summary.md`。C = 3seed平均（一致ならmin(t,180)、不一致・時間切れは180）。

## 要点
- 実験1（A：凍結版、B：冗長な等式の追加、C：構成の展開）。6問とも、C/C_A は B で1.0〜3.1倍、C で2.3〜26倍。
  - Cで成功率が下がった問題: AIME-2016-I-06（3/3→1/3）、HMMT-2017-FEB-GEO-10（3/3→0/3）。
  - AIME-2014-II-14は、Aでは代数前処理（変数2）で1.8秒だったが、Bでは数値探索（5.5秒）、C（変数14）では46.8秒になった。冗長な等式を足しただけで代数前処理の経路から外れた。
- 実験2（A：凍結版、R：手で行った導出を外した版）。
  - AIME-2013-I-12は3/3→2/3でC_Aの11.6倍。HMMT-2010-FEB-GEO-10は変数0→6で7.8倍。HMMT-2016-FEB-GEO-03は2.4倍。HMMT-2006-FEB-GEO-04はほぼ同じ（1.08倍、Rは代数前処理）。
  - AIME-2015-II-07はRの方が速い（0.22倍、Rは代数前処理）。
