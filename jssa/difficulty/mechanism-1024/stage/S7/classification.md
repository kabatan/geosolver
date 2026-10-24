# 事前登録14・段階(1) 特異値計測

対象323問。状態別: {'ok': 266, 'reference_unavailable': 26, 'excluded_no_variables': 31}。

段階(2)は実行していない。精密化成績との結合・W1/W2/W4の評価は行わない。

## 型別件数

| σ_base / σ_raw / 接する条件 | 件数 |
|---|---:|
| base=不定;raw=不定;tangency=0 | 1 |
| base=特異;raw=特異;tangency=0 | 34 |
| base=特異;raw=特異;tangency=1 | 3 |
| base=非特異;raw=特異;tangency=0 | 5 |
| base=非特異;raw=特異;tangency=1 | 7 |
| base=非特異;raw=非特異;tangency=0 | 190 |
| base=非特異;raw=非特異;tangency=1 | 26 |

## W3対象（raw特異・base非特異・接する条件なし）

5問。

- AIME-2013-II-04
- AIME-2020-II-04
- HMMT-2006-FEB-GEO-01
- HMMT-2009-FEB-GEO-01
- JMO-2021-PRE-07

## 全問題の判定理由

| 問題 | 状態 | 型 | 理由 |
|---|---|---|---|
| AIME-2006-I-01 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2006-I-07 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| AIME-2006-II-01 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2006-II-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2006-II-09 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| AIME-2006-II-12 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2007-I-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2007-I-12 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| AIME-2007-I-15 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2007-II-09 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| AIME-2007-II-15 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| AIME-2008-I-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2008-I-10 | reference_unavailable | 参照解なし | reference: TimeoutError('solve deadline reached') |
| AIME-2008-II-05 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2008-II-11 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| AIME-2009-I-05 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2009-I-12 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| AIME-2009-II-05 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2009-II-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2010-I-13 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2010-I-15 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2010-II-09 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2010-II-14 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2010-II-15 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2011-I-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2011-I-03 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| AIME-2011-I-04 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2011-I-14 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2011-II-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2011-II-04 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| AIME-2011-II-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2011-II-13 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2012-I-12 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| AIME-2012-II-13 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| AIME-2012-II-15 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2013-I-03 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| AIME-2013-I-09 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| AIME-2013-I-12 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| AIME-2013-II-04 | ok | base=非特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2013-II-05 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| AIME-2013-II-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2013-II-13 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2013-II-15 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2014-I-13 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2014-I-15 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2014-II-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2014-II-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2014-II-11 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2014-II-14 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2015-I-04 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| AIME-2015-I-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2015-I-07 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2015-II-07 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| AIME-2015-II-11 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2015-II-15 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| AIME-2016-I-06 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2016-I-15 | reference_unavailable | 参照解なし | 凍結版通常solve(seed 0, 180秒)の1回で最終検証通過図なし |
| AIME-2016-II-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2017-II-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2018-I-04 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2018-I-15 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2018-II-04 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| AIME-2018-II-09 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| AIME-2018-II-12 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2018-II-14 | ok | base=特異;raw=特異;tangency=1 | 両幅で同じ閾値区分; 凍結版の元残差fallbackを保持; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| AIME-2019-I-03 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| AIME-2019-I-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2019-I-13 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2019-I-15 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2019-II-01 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2019-II-07 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| AIME-2019-II-11 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2019-II-13 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2019-II-15 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2020-I-01 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| AIME-2020-I-13 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2020-I-15 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| AIME-2020-II-04 | ok | base=非特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| AIME-2020-II-13 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| AIME-2020-II-15 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2021-I-02 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| AIME-2021-I-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2021-I-11 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2021-I-13 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| AIME-2021-II-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2021-II-12 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2021-II-14 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2022-I-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2022-I-08 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| AIME-2022-I-11 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| AIME-2022-II-07 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| AIME-2022-II-11 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| AIME-2022-II-15 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2023-I-05 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2023-I-08 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| AIME-2023-I-12 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2023-II-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2023-II-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2023-II-12 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2024-II-05 | ok | base=不定;raw=不定;tangency=0 | 両幅で同じ閾値区分; 不定のmodeは閾値間[1e-60,1e-10]または幅間の区分不一致 |
| AIME-2024-II-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2025-I-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2025-I-06 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| AIME-2025-II-01 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2025-II-05 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2025-II-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2025-II-12 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| AIME-2025-II-14 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2006-FEB-GEO-01 | ok | base=非特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2006-FEB-GEO-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2006-FEB-GEO-03 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2006-FEB-GEO-04 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2006-FEB-GEO-05 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| HMMT-2006-FEB-GEO-06 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| HMMT-2006-FEB-GEO-07 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2006-FEB-GEO-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2006-FEB-GEO-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2007-FEB-GEO-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2007-FEB-GEO-03 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2007-FEB-GEO-04 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| HMMT-2007-FEB-GEO-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2007-FEB-GEO-07 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2007-FEB-GEO-08 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| HMMT-2007-FEB-GEO-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2007-FEB-GEO-10 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| HMMT-2008-FEB-GEO-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2008-FEB-GEO-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2008-FEB-GEO-04 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2008-FEB-GEO-05 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2008-FEB-GEO-06 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| HMMT-2008-FEB-GEO-07 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2008-FEB-GEO-09 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| HMMT-2008-FEB-GEO-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2009-FEB-GEO-01 | ok | base=非特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2009-FEB-GEO-04 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2009-FEB-GEO-07 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2009-FEB-GEO-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2009-FEB-GEO-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2009-FEB-GEO-10 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| HMMT-2010-FEB-GEO-01 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2010-FEB-GEO-02 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| HMMT-2010-FEB-GEO-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2010-FEB-GEO-09 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| HMMT-2010-FEB-GEO-10 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2011-FEB-ALGGEO-08 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| HMMT-2011-FEB-ALGGEO-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2011-FEB-ALGGEO-18 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2011-equilateral-hexagon | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2011-two-circles-tangent-line | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2012-FEB-GEO-01 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2012-FEB-GEO-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2012-FEB-GEO-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2012-FEB-GEO-04 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2013-FEB-GEO-02 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2013-FEB-GEO-03 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| HMMT-2013-FEB-GEO-04 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2013-FEB-GEO-05 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2013-FEB-GEO-07 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2013-FEB-GEO-08 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2013-FEB-GEO-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2014-FEB-GEO-01 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2014-FEB-GEO-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2014-FEB-GEO-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2014-FEB-GEO-04 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2014-FEB-GEO-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2014-FEB-GEO-07 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2014-FEB-GEO-08 | ok | base=非特異;raw=特異;tangency=1 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| HMMT-2014-FEB-GEO-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2014-FEB-GEO-10 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| HMMT-2015-FEB-GEO-02 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2015-FEB-GEO-03 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2015-FEB-GEO-04 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2015-FEB-GEO-06 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2016-FEB-GEO-02 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2016-FEB-GEO-03 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2016-FEB-GEO-04 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2016-FEB-GEO-06 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2016-FEB-GEO-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2016-FEB-GEO-10 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| HMMT-2017-FEB-GEO-01 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2017-FEB-GEO-04 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2017-FEB-GEO-05 | ok | base=特異;raw=特異;tangency=1 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| HMMT-2017-FEB-GEO-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2017-FEB-GEO-07 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| HMMT-2017-FEB-GEO-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2017-FEB-GEO-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2018-FEB-GEO-01 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2018-FEB-GEO-05 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| HMMT-2018-FEB-GEO-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2018-FEB-GEO-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2019-FEB-GEO-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2019-FEB-GEO-05 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2019-FEB-GEO-07 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2019-FEB-GEO-08 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| HMMT-2019-FEB-GEO-10 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2020-FEB-GEO-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2020-FEB-GEO-04 | ok | base=非特異;raw=特異;tangency=1 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| HMMT-2020-FEB-GEO-05 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2020-FEB-GEO-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2020-FEB-GEO-07 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| HMMT-2020-FEB-GEO-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2020-FEB-GEO-09 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| HMMT-2021-FEB-GEO-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2021-FEB-GEO-04 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2021-FEB-GEO-05 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2021-FEB-GEO-06 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2021-FEB-GEO-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2022-FEB-GEO-01 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| HMMT-2022-FEB-GEO-02 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| HMMT-2022-FEB-GEO-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2022-FEB-GEO-05 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2022-FEB-GEO-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2022-FEB-GEO-10 | ok | base=非特異;raw=特異;tangency=1 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| HMMT-2023-FEB-GEO-01 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2023-FEB-GEO-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2023-FEB-GEO-04 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2023-FEB-GEO-05 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2023-FEB-GEO-07 | ok | base=非特異;raw=特異;tangency=1 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| HMMT-2023-FEB-GEO-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2023-FEB-GEO-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2024-FEB-GEO-01 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2024-FEB-GEO-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2024-FEB-GEO-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2024-FEB-GEO-04 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2024-FEB-GEO-05 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2024-FEB-GEO-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2024-FEB-GEO-07 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2024-FEB-GEO-08 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| HMMT-2024-FEB-GEO-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2024-FEB-GEO-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2025-FEB-GEO-01 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2025-FEB-GEO-02 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2025-FEB-GEO-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2025-FEB-GEO-04 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| HMMT-2025-FEB-GEO-05 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2025-FEB-GEO-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2025-FEB-GEO-07 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2025-FEB-GEO-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| HMMT-2025-FEB-GEO-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2006-PRE-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2006-PRE-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2007-PRE-01 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2008-PRE-02 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| JMO-2008-PRE-11 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2009-PRE-02 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| JMO-2010-PRE-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2010-PRE-11 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| JMO-2011-PRE-04 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| JMO-2011-PRE-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2011-PRE-11 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| JMO-2012-PRE-01 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2012-PRE-02 | excluded_no_variables | 探索変数なし | 凍結版bundleの探索変数が0個 |
| JMO-2012-PRE-07 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2013-PRE-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2013-PRE-05 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| JMO-2013-PRE-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2014-PRE-01 | ok | base=非特異;raw=特異;tangency=1 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| JMO-2014-PRE-04 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| JMO-2014-PRE-09 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2015-PRE-02 | ok | base=非特異;raw=特異;tangency=1 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| JMO-2015-PRE-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2015-PRE-11 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2016-PRE-03 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| JMO-2016-PRE-05 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2016-PRE-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2017-PRE-01 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2017-PRE-04 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| JMO-2017-PRE-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2017-PRE-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2018-PRE-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2018-PRE-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2018-PRE-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2019-PRE-04 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2019-PRE-08 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2019-PRE-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2020-PRE-02 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2020-PRE-06 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| JMO-2020-PRE-11 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2021-PRE-02 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| JMO-2021-PRE-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2021-PRE-07 | ok | base=非特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| JMO-2021-PRE-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2022-PRE-02 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| JMO-2022-PRE-04 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2022-PRE-07 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2022-PRE-12 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2023-PRE-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2023-PRE-06 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2023-PRE-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2024-PRE-03 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2024-PRE-06 | ok | base=非特異;raw=特異;tangency=1 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| JMO-2024-PRE-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2025-PRE-05 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| JMO-2025-PRE-09 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| JMO-2025-PRE-12 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| aime-2000-1-14 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2000-1-2 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| aime-2000-2-10 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2000-2-11 | reference_unavailable | 参照解なし | 凍結版通常solve(seed 0, 180秒)の1回で最終検証通過図なし |
| aime-2000-2-6 | reference_unavailable | 参照解なし | 凍結版の一度の620桁closureが残差基準に到達せず |
| aime-2000-2-8 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2001-1-13 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2001-1-4 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2001-1-9 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| aime-2001-2-6 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2001-2-7 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| aime-2002-1-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2002-1-13 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2002-2-13 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2002-2-14 | ok | base=特異;raw=特異;tangency=1 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| aime-2002-2-15 | ok | base=非特異;raw=非特異;tangency=1 | 両幅で同じ閾値区分 |
| aime-2003-1-10 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2003-1-12 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2003-1-15 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2003-1-7 | ok | base=特異;raw=特異;tangency=0 | 両幅で同じ閾値区分; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照） |
| aime-2003-2-11 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2003-2-14 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2003-2-6 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2003-2-7 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2004-2-12 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2004-2-13 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2005-1-14 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
| aime-2005-1-15 | ok | base=非特異;raw=非特異;tangency=0 | 両幅で同じ閾値区分 |
