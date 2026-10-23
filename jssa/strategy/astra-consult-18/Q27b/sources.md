# 確認した一次文献と適用範囲

2026-10-23の検索・公開原文の確認による。過去回答の書誌をそのまま事実として引用せず、以下のページを開いて確認した。

1. Bogdan I. Epureanu, Henry S. Greenside, *Fractal Basins of Attraction Associated with a Damped Newton's Method*, SIAM Review 40(1), 102–109 (1998), DOI [10.1137/S0036144596310033](https://epubs.siam.org/doi/abs/10.1137/S0036144596310033)。[1996年著者版の本文](https://arxiv.org/html/chao-dyn/9612010v1)も確認。非最近接根への到達・減衰Newtonの複雑な盆は既知。ここでの過剰決定LMやPowellの境界次元を与える定理としては使わない。

2. Alvar Daza, Alexandre Wagemakers, Bertrand Georgeot, David Guéry-Odelin, Miguel A. F. Sanjuán, *Basin entropy: a new tool to analyze uncertainty in dynamical systems*, [著者版 arXiv:1605.02342](https://arxiv.org/html/1605.02342v1)（2016年投稿）。§Iの不確実性指数 `α=D−d`、§IIの箱サイズ・境界サイズ・行き先数の区別を確認。今回のランダム開始200点を多尺度の箱標本と見なすことはしない。basin entropy・フラクタル次元は未測定。文書のHTML表示には2026年の日付もあるが、版の投稿年と取り違えない。

3. Martin Golubitsky, Ian Stewart, *Recent advances in symmetric and network dynamics*, Chaos 25, 097612 (2015), DOI 10.1063/1.4918595。[著者公開PDF](https://www.asc.ohio-state.edu/golubitsky.4/reprintweb-0.5/output/papers/recent_advances.pdf)。§III、Proposition 3.2の同変写像と固定部分空間の不変性を確認。対応する盆の等測度という今回の条件付き説明は、写像の同変性と開始測度の不変性からの直接の変数変換であり、同論文が本solverについて証明した主張ではない。

本solverのDSLと内部状態を含むLM/Powell反復から、複数競技問題の境界次元や盆の体積を事前計算できる既知理論の適用は**未確認**。不存在・世界初とも主張しない。連続解の167位置クラスタについて深い理論を必要とする文献は提示しない。順序統計の期待値は本文で直接導いた初等式であり、書誌を作って補わない。

# ローカル証拠の区別

- 方針：`jssa/strategy/codex-tasks-1023.md`末尾の本人方針とQ27、`codex-session-01a1171a-summary.md`。
- 過去の棄却理由：`astra-consult-18/q20a*`〜`q20f*`、`q21a*`〜`q21f*`のanswer.md。特にq20bの失敗した対称統合検証とtheory.md。
- 一次測定：`difficulty/minima/raw-323/`、`raw-323-seed1/`。原始ログにない軌道・seed 1終点を推測で追加しない。
- 完成solver：`results/stage-profile-20261023/per-case.csv`の969行。`stage-taxonomy/per-run.csv`は全969行の代用にしていない。
- 許容性：`difficulty/start-feasibility-1023/per-problem.csv`と`per-problem-seed1.csv`。JMOの細分だけ実装評価器で再評価し、全体152/145、48/0と整合を確認。
- 代数系：`astra-consult-17/H/sources/comparison-cases.csv`。real_solutionsは複素次数と同一視しない。
- 精度：`astra-consult-18/q21b-number-theory/problem-summary.csv`、`precision-summary.csv`、`difficulty/multiplicity/precision-sensitivity.csv`、`precision-regressions.csv`。別実験の必要精度と完成solverの時系列を区別。
- 作図展開：`benchmarks/extra-variables/PROTOCOL.md`と既存common-start・near-start・holdoutの表。元60入力の完全なdose-response rawは未入手。
- GMB：`benchmarks/gmb_comparison/`の比較資料、`results/gmb-success-definition/summary.json`とper-trial.csv。開始点地図の共有がなく、盆の比較の因果対照としては未使用。
