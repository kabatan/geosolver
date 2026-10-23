Q20b：参照した一次文献と、そこから言えること

いずれも2026-10-23に公開原文または著者版を確認した。下記の内容をこのsolverでの新規発見とは扱わない。

| 文献 | 確認した内容 | 今回の使い方と制約 |
|---|---|---|
| Daza, Wagemakers, Sanjuán (2018), *Ascertaining when a basin is Wada: the merging method*, Scientific Reports 8, 9954, DOI 10.1038/s41598-018-28119-0。[原文](https://arxiv.org/html/1803.03480) | 非自明な盆の統合に対して共通境界が保存される性質を使うWada検出。有限解像度の制約もある。 | 色をまとめる操作自体は既知。完全Wadaなら鏡映統合だけで共通境界を消せない。今回のFを真の盆と仮定しない。 |
| Daza, Wagemakers, Georgeot, Guéry-Odelin, Sanjuán (2016), *Basin entropy: a new tool to analyze uncertainty in dynamical systems*, Scientific Reports 6, 31416, DOI 10.1038/srep31416。[著者版](https://arxiv.org/abs/1605.02342) | 盆の体積だけでなく、局所的な混ざり方を測る枠組み。不確実性と境界次元の関係には尺度に関する前提がある。 | 当たり率だけでは境界の形が決まらないという土台。今回はbasin entropyを計算していない。4尺度の傾きを確定した不確実性指数と呼ばない。 |
| Epureanu, Greenside (1998), *Fractal Basins of Attraction Associated with a Damped Newton's Method*, SIAM Review 40, 102–109, DOI 10.1137/S0036144596310033。[著者版](https://arxiv.org/abs/chao-dyn/9612010) | 減衰付きNewton法にもフラクタルな盆が残る例を示している。 | 「減衰があるから境界は単純」とは言えない。ただし対象アルゴリズムは今回の過剰決定LMと同一ではない。Newton法一般の複雑な盆を見つけるだけでは新規性がない。 |
| Golubitsky, Stewart (2015), *Recent advances in symmetric and network dynamics*, Chaos 25, 097612, DOI 10.1063/1.4918595。[著者版PDF](https://www.asc.ohio-state.edu/golubitsky.4/reprintweb-0.5/output/papers/recent_advances.pdf) | Proposition 3.2：同変写像は対称群の固定部分空間を保つ。 | 候補3の不変性は既知。LMで条件を確認するだけではAの核にならない。 |

**未確認の部分。** このGeoSolverの作図DSLから反復写像の逆像構造を共通に取り出し、複数の競技幾何問題について境界の生成規則を予測した既存研究は、今回の範囲では確認していない。「存在しない」「世界初」とは主張しない。幾何対称性で合同類を作った後の有限予算分類図に、この問題群特有の尺度則があるかも未確認であり、今回の予備仮説は支持されなかった。

文献由来の性質、ここでの条件付き導出、実測結果は [theory.md](theory.md) と [answer.md](answer.md) で分けている。
