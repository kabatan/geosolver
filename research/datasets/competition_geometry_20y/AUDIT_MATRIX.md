# 20年手動監査マトリクス

`manual_scope_audit.py`で問題文または公式問題画像を一問ずつ確認した結果。HMMT 2011のtrack再掲は `dedupe_key` でまとめ、JMOの公式年次リンクは問題行に数えていない。

| 年 | contest | source rows | unique in-scope | unique out-of-scope | JSON | runnable | reference_only | pending |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 2006 | AIME | 13 | 6 | 7 | 6 | 6 | 0 | 0 |
| 2006 | HMMT | 10 | 9 | 1 | 9 | 9 | 0 | 0 |
| 2006 | JMO preliminary | 7 | 2 | 3 | 2 | 2 | 0 | 0 |
| 2007 | AIME | 10 | 5 | 5 | 5 | 5 | 0 | 0 |
| 2007 | HMMT | 10 | 8 | 2 | 8 | 8 | 0 | 0 |
| 2007 | JMO preliminary | 4 | 1 | 2 | 1 | 1 | 0 | 0 |
| 2008 | AIME | 10 | 4 | 6 | 4 | 3 | 1 | 0 |
| 2008 | HMMT | 10 | 8 | 2 | 8 | 7 | 1 | 0 |
| 2008 | JMO preliminary | 2 | 2 | 0 | 2 | 2 | 0 | 0 |
| 2009 | AIME | 9 | 4 | 5 | 4 | 4 | 0 | 0 |
| 2009 | HMMT | 10 | 6 | 4 | 6 | 4 | 2 | 0 |
| 2009 | JMO preliminary | 1 | 1 | 0 | 1 | 1 | 0 | 0 |
| 2010 | AIME | 10 | 5 | 5 | 5 | 4 | 1 | 0 |
| 2010 | HMMT | 10 | 5 | 5 | 5 | 4 | 1 | 0 |
| 2010 | JMO preliminary | 2 | 2 | 0 | 2 | 2 | 0 | 0 |
| 2011 | AIME | 12 | 8 | 4 | 8 | 8 | 0 | 0 |
| 2011 | HMMT | 32 | 5 | 10 | 5 | 4 | 1 | 0 |
| 2011 | JMO preliminary | 3 | 3 | 0 | 3 | 3 | 0 | 0 |
| 2012 | AIME | 7 | 3 | 4 | 3 | 3 | 0 | 0 |
| 2012 | HMMT | 10 | 4 | 6 | 4 | 4 | 0 | 0 |
| 2012 | JMO preliminary | 3 | 3 | 0 | 3 | 3 | 0 | 0 |
| 2013 | AIME | 13 | 8 | 5 | 8 | 7 | 1 | 0 |
| 2013 | HMMT | 10 | 8 | 2 | 8 | 7 | 1 | 0 |
| 2013 | JMO preliminary | 6 | 3 | 2 | 3 | 3 | 0 | 0 |
| 2014 | AIME | 14 | 6 | 8 | 6 | 6 | 0 | 0 |
| 2014 | HMMT | 10 | 9 | 1 | 9 | 9 | 0 | 0 |
| 2014 | JMO preliminary | 3 | 3 | 0 | 3 | 3 | 0 | 0 |
| 2015 | AIME | 11 | 6 | 5 | 6 | 6 | 0 | 0 |
| 2015 | HMMT | 10 | 4 | 6 | 4 | 4 | 0 | 0 |
| 2015 | JMO preliminary | 6 | 3 | 1 | 3 | 3 | 0 | 0 |
| 2016 | AIME | 14 | 3 | 11 | 3 | 3 | 0 | 0 |
| 2016 | HMMT | 10 | 6 | 4 | 6 | 5 | 1 | 0 |
| 2016 | JMO preliminary | 3 | 3 | 0 | 3 | 3 | 0 | 0 |
| 2017 | AIME | 10 | 1 | 9 | 1 | 1 | 0 | 0 |
| 2017 | HMMT | 10 | 7 | 3 | 7 | 6 | 1 | 0 |
| 2017 | JMO preliminary | 4 | 4 | 0 | 4 | 4 | 0 | 0 |
| 2018 | AIME | 13 | 6 | 7 | 6 | 4 | 2 | 0 |
| 2018 | HMMT | 10 | 4 | 6 | 4 | 4 | 0 | 0 |
| 2018 | JMO preliminary | 3 | 3 | 0 | 3 | 3 | 0 | 0 |
| 2019 | AIME | 13 | 9 | 4 | 9 | 8 | 1 | 0 |
| 2019 | HMMT | 10 | 5 | 5 | 5 | 5 | 0 | 0 |
| 2019 | JMO preliminary | 10 | 3 | 5 | 3 | 3 | 0 | 0 |
| 2020 | AIME | 11 | 6 | 5 | 6 | 6 | 0 | 0 |
| 2020 | HMMT | 10 | 7 | 3 | 7 | 6 | 1 | 0 |
| 2020 | JMO preliminary | 3 | 3 | 0 | 3 | 2 | 1 | 0 |
| 2021 | AIME | 12 | 7 | 5 | 7 | 7 | 0 | 0 |
| 2021 | HMMT | 10 | 5 | 5 | 5 | 5 | 0 | 0 |
| 2021 | JMO preliminary | 4 | 4 | 0 | 4 | 4 | 0 | 0 |
| 2022 | AIME | 12 | 6 | 6 | 6 | 6 | 0 | 0 |
| 2022 | HMMT | 10 | 6 | 4 | 6 | 5 | 1 | 0 |
| 2022 | JMO preliminary | 7 | 4 | 0 | 4 | 4 | 0 | 0 |
| 2023 | AIME | 14 | 6 | 8 | 6 | 6 | 0 | 0 |
| 2023 | HMMT | 10 | 7 | 3 | 7 | 7 | 0 | 0 |
| 2023 | JMO preliminary | 3 | 3 | 0 | 3 | 3 | 0 | 0 |
| 2024 | AIME | 5 | 2 | 3 | 2 | 2 | 0 | 0 |
| 2024 | HMMT | 10 | 10 | 0 | 10 | 10 | 0 | 0 |
| 2024 | JMO preliminary | 3 | 3 | 0 | 3 | 3 | 0 | 0 |
| 2025 | AIME | 13 | 7 | 6 | 7 | 7 | 0 | 0 |
| 2025 | HMMT | 10 | 9 | 1 | 9 | 9 | 0 | 0 |
| 2025 | JMO preliminary | 3 | 3 | 0 | 3 | 3 | 0 | 0 |

## 問題ID一覧

- **2006 AIME / in_scope (6)**: AIME-2006-I-01, AIME-2006-I-07, AIME-2006-II-01, AIME-2006-II-06, AIME-2006-II-09, AIME-2006-II-12

- **2006 HMMT / in_scope (9)**: HMMT-2006-FEB-GEO-01, HMMT-2006-FEB-GEO-02, HMMT-2006-FEB-GEO-03, HMMT-2006-FEB-GEO-04, HMMT-2006-FEB-GEO-05, HMMT-2006-FEB-GEO-06, HMMT-2006-FEB-GEO-07, HMMT-2006-FEB-GEO-08, HMMT-2006-FEB-GEO-10

- **2006 JMO preliminary / in_scope (2)**: JMO-2006-PRE-02, JMO-2006-PRE-09

- **2007 AIME / in_scope (5)**: AIME-2007-I-09, AIME-2007-I-12, AIME-2007-I-15, AIME-2007-II-09, AIME-2007-II-15

- **2007 HMMT / in_scope (8)**: HMMT-2007-FEB-GEO-02, HMMT-2007-FEB-GEO-03, HMMT-2007-FEB-GEO-04, HMMT-2007-FEB-GEO-06, HMMT-2007-FEB-GEO-07, HMMT-2007-FEB-GEO-08, HMMT-2007-FEB-GEO-09, HMMT-2007-FEB-GEO-10

- **2007 JMO preliminary / in_scope (1)**: JMO-2007-PRE-01

- **2008 AIME / in_scope (4)**: AIME-2008-I-02, AIME-2008-I-10, AIME-2008-II-05, AIME-2008-II-11

- **2008 HMMT / in_scope (8)**: HMMT-2008-FEB-GEO-02, HMMT-2008-FEB-GEO-03, HMMT-2008-FEB-GEO-04, HMMT-2008-FEB-GEO-05, HMMT-2008-FEB-GEO-06, HMMT-2008-FEB-GEO-07, HMMT-2008-FEB-GEO-09, HMMT-2008-FEB-GEO-10

- **2008 JMO preliminary / in_scope (2)**: JMO-2008-PRE-02, JMO-2008-PRE-11

- **2009 AIME / in_scope (4)**: AIME-2009-I-05, AIME-2009-I-12, AIME-2009-II-05, AIME-2009-II-10

- **2009 HMMT / in_scope (6)**: HMMT-2009-FEB-GEO-01, HMMT-2009-FEB-GEO-04, HMMT-2009-FEB-GEO-07, HMMT-2009-FEB-GEO-08, HMMT-2009-FEB-GEO-09, HMMT-2009-FEB-GEO-10

- **2009 JMO preliminary / in_scope (1)**: JMO-2009-PRE-02

- **2010 AIME / in_scope (5)**: AIME-2010-I-13, AIME-2010-I-15, AIME-2010-II-09, AIME-2010-II-14, AIME-2010-II-15

- **2010 HMMT / in_scope (5)**: HMMT-2010-FEB-GEO-01, HMMT-2010-FEB-GEO-02, HMMT-2010-FEB-GEO-06, HMMT-2010-FEB-GEO-09, HMMT-2010-FEB-GEO-10

- **2010 JMO preliminary / in_scope (2)**: JMO-2010-PRE-08, JMO-2010-PRE-11

- **2011 AIME / in_scope (8)**: AIME-2011-I-02, AIME-2011-I-03, AIME-2011-I-04, AIME-2011-I-14, AIME-2011-II-02, AIME-2011-II-04, AIME-2011-II-10, AIME-2011-II-13

- **2011 HMMT / in_scope (5)**: HMMT-2011-collinear-circumcircle, HMMT-2011-equilateral-hexagon, HMMT-2011-regular-hexagon, HMMT-2011-square, HMMT-2011-two-circles-tangent-line

- **2011 JMO preliminary / in_scope (3)**: JMO-2011-PRE-04, JMO-2011-PRE-06, JMO-2011-PRE-11

- **2012 AIME / in_scope (3)**: AIME-2012-I-12, AIME-2012-II-13, AIME-2012-II-15

- **2012 HMMT / in_scope (4)**: HMMT-2012-FEB-GEO-01, HMMT-2012-FEB-GEO-02, HMMT-2012-FEB-GEO-03, HMMT-2012-FEB-GEO-04

- **2012 JMO preliminary / in_scope (3)**: JMO-2012-PRE-01, JMO-2012-PRE-02, JMO-2012-PRE-07

- **2013 AIME / in_scope (8)**: AIME-2013-I-03, AIME-2013-I-09, AIME-2013-I-12, AIME-2013-II-04, AIME-2013-II-05, AIME-2013-II-08, AIME-2013-II-13, AIME-2013-II-15

- **2013 HMMT / in_scope (8)**: HMMT-2013-FEB-GEO-02, HMMT-2013-FEB-GEO-03, HMMT-2013-FEB-GEO-04, HMMT-2013-FEB-GEO-05, HMMT-2013-FEB-GEO-07, HMMT-2013-FEB-GEO-08, HMMT-2013-FEB-GEO-09, HMMT-2013-FEB-GEO-10

- **2013 JMO preliminary / in_scope (3)**: JMO-2013-PRE-03, JMO-2013-PRE-05, JMO-2013-PRE-08

- **2014 AIME / in_scope (6)**: AIME-2014-I-13, AIME-2014-I-15, AIME-2014-II-03, AIME-2014-II-08, AIME-2014-II-11, AIME-2014-II-14

- **2014 HMMT / in_scope (9)**: HMMT-2014-FEB-GEO-01, HMMT-2014-FEB-GEO-02, HMMT-2014-FEB-GEO-03, HMMT-2014-FEB-GEO-04, HMMT-2014-FEB-GEO-06, HMMT-2014-FEB-GEO-07, HMMT-2014-FEB-GEO-08, HMMT-2014-FEB-GEO-09, HMMT-2014-FEB-GEO-10

- **2014 JMO preliminary / in_scope (3)**: JMO-2014-PRE-01, JMO-2014-PRE-04, JMO-2014-PRE-09

- **2015 AIME / in_scope (6)**: AIME-2015-I-04, AIME-2015-I-06, AIME-2015-I-07, AIME-2015-II-07, AIME-2015-II-11, AIME-2015-II-15

- **2015 HMMT / in_scope (4)**: HMMT-2015-FEB-GEO-02, HMMT-2015-FEB-GEO-03, HMMT-2015-FEB-GEO-04, HMMT-2015-FEB-GEO-06

- **2015 JMO preliminary / in_scope (3)**: JMO-2015-PRE-02, JMO-2015-PRE-08, JMO-2015-PRE-11

- **2016 AIME / in_scope (3)**: AIME-2016-I-06, AIME-2016-I-15, AIME-2016-II-10

- **2016 HMMT / in_scope (6)**: HMMT-2016-FEB-GEO-02, HMMT-2016-FEB-GEO-03, HMMT-2016-FEB-GEO-04, HMMT-2016-FEB-GEO-06, HMMT-2016-FEB-GEO-09, HMMT-2016-FEB-GEO-10

- **2016 JMO preliminary / in_scope (3)**: JMO-2016-PRE-03, JMO-2016-PRE-05, JMO-2016-PRE-08

- **2017 AIME / in_scope (1)**: AIME-2017-II-10

- **2017 HMMT / in_scope (7)**: HMMT-2017-FEB-GEO-01, HMMT-2017-FEB-GEO-04, HMMT-2017-FEB-GEO-05, HMMT-2017-FEB-GEO-06, HMMT-2017-FEB-GEO-07, HMMT-2017-FEB-GEO-09, HMMT-2017-FEB-GEO-10

- **2017 JMO preliminary / in_scope (4)**: JMO-2017-PRE-01, JMO-2017-PRE-04, JMO-2017-PRE-08, JMO-2017-PRE-10

- **2018 AIME / in_scope (6)**: AIME-2018-I-04, AIME-2018-I-15, AIME-2018-II-04, AIME-2018-II-09, AIME-2018-II-12, AIME-2018-II-14

- **2018 HMMT / in_scope (4)**: HMMT-2018-FEB-GEO-01, HMMT-2018-FEB-GEO-05, HMMT-2018-FEB-GEO-08, HMMT-2018-FEB-GEO-10

- **2018 JMO preliminary / in_scope (3)**: JMO-2018-PRE-03, JMO-2018-PRE-06, JMO-2018-PRE-09

- **2019 AIME / in_scope (9)**: AIME-2019-I-03, AIME-2019-I-06, AIME-2019-I-13, AIME-2019-I-15, AIME-2019-II-01, AIME-2019-II-07, AIME-2019-II-11, AIME-2019-II-13, AIME-2019-II-15

- **2019 HMMT / in_scope (5)**: HMMT-2019-FEB-GEO-02, HMMT-2019-FEB-GEO-05, HMMT-2019-FEB-GEO-07, HMMT-2019-FEB-GEO-08, HMMT-2019-FEB-GEO-10

- **2019 JMO preliminary / in_scope (3)**: JMO-2019-PRE-04, JMO-2019-PRE-08, JMO-2019-PRE-10

- **2020 AIME / in_scope (6)**: AIME-2020-I-01, AIME-2020-I-13, AIME-2020-I-15, AIME-2020-II-04, AIME-2020-II-13, AIME-2020-II-15

- **2020 HMMT / in_scope (7)**: HMMT-2020-FEB-GEO-02, HMMT-2020-FEB-GEO-04, HMMT-2020-FEB-GEO-05, HMMT-2020-FEB-GEO-06, HMMT-2020-FEB-GEO-07, HMMT-2020-FEB-GEO-08, HMMT-2020-FEB-GEO-09

- **2020 JMO preliminary / in_scope (3)**: JMO-2020-PRE-02, JMO-2020-PRE-06, JMO-2020-PRE-11

- **2021 AIME / in_scope (7)**: AIME-2021-I-02, AIME-2021-I-09, AIME-2021-I-11, AIME-2021-I-13, AIME-2021-II-02, AIME-2021-II-12, AIME-2021-II-14

- **2021 HMMT / in_scope (5)**: HMMT-2021-FEB-GEO-03, HMMT-2021-FEB-GEO-04, HMMT-2021-FEB-GEO-05, HMMT-2021-FEB-GEO-06, HMMT-2021-FEB-GEO-09

- **2021 JMO preliminary / in_scope (4)**: JMO-2021-PRE-02, JMO-2021-PRE-03, JMO-2021-PRE-07, JMO-2021-PRE-10

- **2022 AIME / in_scope (6)**: AIME-2022-I-03, AIME-2022-I-08, AIME-2022-I-11, AIME-2022-II-07, AIME-2022-II-11, AIME-2022-II-15

- **2022 HMMT / in_scope (6)**: HMMT-2022-FEB-GEO-01, HMMT-2022-FEB-GEO-02, HMMT-2022-FEB-GEO-03, HMMT-2022-FEB-GEO-05, HMMT-2022-FEB-GEO-06, HMMT-2022-FEB-GEO-10

- **2022 JMO preliminary / in_scope (4)**: JMO-2022-PRE-02, JMO-2022-PRE-04, JMO-2022-PRE-07, JMO-2022-PRE-12

- **2023 AIME / in_scope (6)**: AIME-2023-I-05, AIME-2023-I-08, AIME-2023-I-12, AIME-2023-II-03, AIME-2023-II-09, AIME-2023-II-12

- **2023 HMMT / in_scope (7)**: HMMT-2023-FEB-GEO-01, HMMT-2023-FEB-GEO-02, HMMT-2023-FEB-GEO-04, HMMT-2023-FEB-GEO-05, HMMT-2023-FEB-GEO-07, HMMT-2023-FEB-GEO-08, HMMT-2023-FEB-GEO-10

- **2023 JMO preliminary / in_scope (3)**: JMO-2023-PRE-03, JMO-2023-PRE-06, JMO-2023-PRE-10

- **2024 AIME / in_scope (2)**: AIME-2024-II-05, AIME-2024-II-10

- **2024 HMMT / in_scope (10)**: HMMT-2024-FEB-GEO-01, HMMT-2024-FEB-GEO-02, HMMT-2024-FEB-GEO-03, HMMT-2024-FEB-GEO-04, HMMT-2024-FEB-GEO-05, HMMT-2024-FEB-GEO-06, HMMT-2024-FEB-GEO-07, HMMT-2024-FEB-GEO-08, HMMT-2024-FEB-GEO-09, HMMT-2024-FEB-GEO-10

- **2024 JMO preliminary / in_scope (3)**: JMO-2024-PRE-03, JMO-2024-PRE-06, JMO-2024-PRE-09

- **2025 AIME / in_scope (7)**: AIME-2025-I-02, AIME-2025-I-06, AIME-2025-II-01, AIME-2025-II-05, AIME-2025-II-06, AIME-2025-II-12, AIME-2025-II-14

- **2025 HMMT / in_scope (9)**: HMMT-2025-FEB-GEO-01, HMMT-2025-FEB-GEO-02, HMMT-2025-FEB-GEO-03, HMMT-2025-FEB-GEO-04, HMMT-2025-FEB-GEO-05, HMMT-2025-FEB-GEO-06, HMMT-2025-FEB-GEO-07, HMMT-2025-FEB-GEO-08, HMMT-2025-FEB-GEO-09

- **2025 JMO preliminary / in_scope (3)**: JMO-2025-PRE-05, JMO-2025-PRE-09, JMO-2025-PRE-12

