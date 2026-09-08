# 共通検査で未成功だった試行

主閾値 `1e-6`。各問題のseed 0/1/2をすべて含む。条件名は共通検査のsource pathに対応し、詳細は元の採点JSONを参照する。

| 手法 | 問題 | seed | 区分 | 棄却理由 |
|---|---|---:|---|---|
| gmb | IMO_2000_P1 | 0 | no_output | native受理済み出力なし |
| geosolver | IMO_2000_P1 | 0 | no_valid_output | commands/5:unresolved:no_real_intersection |
| gmb | IMO_2000_P1 | 1 | no_output | native受理済み出力なし |
| geosolver | IMO_2000_P1 | 1 | no_valid_output | commands/5:unresolved:no_real_intersection |
| gmb | IMO_2000_P1 | 2 | no_output | native受理済み出力なし |
| geosolver | IMO_2000_P1 | 2 | no_valid_output | commands/5:unresolved:no_real_intersection |
| gmb | IMO_2000_P6 | 0 | no_valid_output | commands/6:failed:invalid_intersection_witness |
| gmb | IMO_2000_P6 | 2 | no_valid_output | commands/4:failed:invalid_intersection_witness; commands/5:failed:invalid_intersection_witness; commands/6:failed:invalid_intersection_witness |
| gmb | IMO_2001_P1 | 2 | no_output | native受理済み出力なし |
| gmb | IMO_2001_P5 | 0 | no_valid_output | commands/3:failed:=; commands/4:failed:= |
| gmb | IMO_2001_P5 | 1 | no_valid_output | commands/3:failed:=; commands/4:failed:= |
| gmb | IMO_2001_P5 | 2 | no_valid_output | commands/3:failed:=; commands/4:failed:= |
| gmb | IMO_2003_P3 | 0 | no_valid_output | commands/1:failed:=; commands/2:failed:=; commands/3:failed:= |
| geosolver | IMO_2003_P3 | 0 | no_output | native受理済み出力なし |
| gmb | IMO_2003_P3 | 1 | no_valid_output | commands/1:failed:=; commands/2:failed:=; commands/3:failed:= |
| geosolver | IMO_2003_P3 | 1 | no_output | native受理済み出力なし |
| gmb | IMO_2003_P3 | 2 | no_valid_output | commands/1:failed:=; commands/2:failed:=; commands/3:failed:= |
| geosolver | IMO_2003_P3 | 2 | no_output | native受理済み出力なし |
| gmb | IMO_2003_P4 | 0 | no_valid_output | commands/1:failed:cycl/3; commands/5:failed:cong |
| gmb | IMO_2003_P4 | 1 | no_valid_output | commands/1:failed:cycl/3; commands/5:failed:cong |
| gmb | IMO_2003_P4 | 2 | no_valid_output | commands/1:failed:cycl/3; commands/5:failed:cong |
| gmb | IMO_2004_P5 | 0 | no_output | native受理済み出力なし |
| gmb | IMO_2004_P5 | 1 | no_output | native受理済み出力なし |
| gmb | IMO_2004_P5 | 2 | no_output | native受理済み出力なし |
| gmb | IMO_2005_P1 | 0 | no_valid_output | commands/10:failed:cong; commands/11:failed:cong; commands/7:failed:cong; commands/8:failed:cong; commands/9:failed:cong |
| gmb | IMO_2005_P1 | 1 | no_valid_output | commands/10:failed:cong; commands/11:failed:cong; commands/7:failed:cong; commands/8:failed:cong; commands/9:failed:cong |
| gmb | IMO_2005_P1 | 2 | no_valid_output | commands/10:failed:cong; commands/11:failed:cong; commands/7:failed:cong; commands/8:failed:cong; commands/9:failed:cong |
| gmb | IMO_2005_P5 | 0 | no_valid_output | commands/1:failed:cong; commands/5:failed:cong |
| gmb | IMO_2005_P5 | 1 | no_valid_output | commands/1:failed:cong; commands/5:failed:cong |
| gmb | IMO_2005_P5 | 2 | no_valid_output | commands/1:failed:cong; commands/5:failed:cong |
| gmb | IMO_2006_P1 | 0 | no_valid_output | commands/3:failed:= |
| gmb | IMO_2006_P1 | 1 | no_valid_output | commands/3:failed:= |
| gmb | IMO_2006_P1 | 2 | no_valid_output | commands/3:failed:= |
| gmb | IMO_2007_P2 | 0 | no_output | native受理済み出力なし |
| gmb | IMO_2007_P2 | 1 | no_valid_output | commands/7:failed:cong |
| gmb | IMO_2007_P2 | 2 | no_output | native受理済み出力なし |
| gmb | IMO_2008_P6 | 0 | no_output | native受理済み出力なし |
| gmb | IMO_2008_P6 | 1 | no_output | native受理済み出力なし |
| gmb | IMO_2008_P6 | 2 | no_output | native受理済み出力なし |
| gmb | IMO_2009_P2 | 0 | no_valid_output | commands/8:failed:tangent-lc |
| gmb | IMO_2009_P2 | 1 | no_valid_output | commands/8:failed:tangent-lc |
| gmb | IMO_2009_P2 | 2 | no_valid_output | commands/8:failed:tangent-lc |
| gmb | IMO_2009_P4 | 0 | no_valid_output | commands/1:failed:cong; commands/5:failed:= |
| gmb | IMO_2009_P4 | 1 | no_valid_output | commands/1:failed:cong; commands/5:failed:= |
| gmb | IMO_2009_P4 | 2 | no_valid_output | commands/1:failed:cong; commands/5:failed:= |
| gmb | IMO_2010_P2 | 0 | no_valid_output | commands/7:failed:= |
| gmb | IMO_2010_P2 | 1 | no_valid_output | commands/7:failed:= |
| gmb | IMO_2010_P2 | 2 | no_valid_output | commands/5:failed:same-side; commands/7:failed:= |
| gmb | IMO_2010_P4 | 0 | no_valid_output | commands/7:failed:cong |
| gmb | IMO_2010_P4 | 1 | no_valid_output | commands/7:failed:cong |
| gmb | IMO_2010_P4 | 2 | no_valid_output | commands/7:failed:cong |
| gmb | IMO_2012_P5 | 0 | no_valid_output | commands/4:failed:cong; commands/6:failed:cong |
| gmb | IMO_2012_P5 | 1 | no_valid_output | commands/4:failed:cong; commands/6:failed:cong |
| gmb | IMO_2012_P5 | 2 | no_valid_output | commands/4:failed:cong; commands/6:failed:cong |
| gmb | IMO_2013_P3 | 0 | no_valid_output | commands/4:failed:on-circ |
| gmb | IMO_2013_P3 | 1 | no_valid_output | commands/4:failed:on-circ |
| gmb | IMO_2013_P3 | 2 | no_valid_output | commands/4:failed:on-circ |
| gmb | IMO_2014_P3 | 0 | no_valid_output | commands/1:failed:right; commands/2:failed:right; commands/7:failed:=; commands/8:failed:= |
| gmb | IMO_2014_P3 | 1 | no_valid_output | commands/1:failed:right; commands/2:failed:right; commands/7:failed:=; commands/8:failed:= |
| gmb | IMO_2014_P3 | 2 | no_valid_output | commands/1:failed:right; commands/2:failed:right; commands/7:failed:=; commands/8:failed:= |
| gmb | IMO_2014_P4 | 0 | no_valid_output | commands/3:failed:=; commands/4:failed:= |
| gmb | IMO_2014_P4 | 1 | no_valid_output | commands/3:failed:=; commands/4:failed:= |
| gmb | IMO_2014_P4 | 2 | no_valid_output | commands/3:failed:=; commands/4:failed:= |
| gmb | IMO_2015_P3 | 0 | no_valid_output | commands/7:failed:right; commands/9:failed:right |
| gmb | IMO_2015_P3 | 1 | no_valid_output | commands/7:failed:right; commands/9:failed:right |
| gmb | IMO_2015_P3 | 2 | no_valid_output | commands/7:failed:right; commands/9:failed:right |
| gmb | IMO_2015_P4 | 2 | no_output | native受理済み出力なし |
| gmb | IMO_2016_P1 | 0 | no_valid_output | commands/3:failed:cong; commands/4:failed:i-bisector; commands/6:failed:cong; commands/7:failed:i-bisector |
| geosolver | IMO_2016_P1 | 0 | no_output | native受理済み出力なし |
| gmb | IMO_2016_P1 | 1 | no_valid_output | commands/3:failed:cong; commands/4:failed:i-bisector; commands/6:failed:cong; commands/7:failed:i-bisector |
| geosolver | IMO_2016_P1 | 1 | no_output | native受理済み出力なし |
| gmb | IMO_2016_P1 | 2 | no_valid_output | commands/3:failed:cong; commands/4:failed:i-bisector; commands/6:failed:cong; commands/7:failed:i-bisector |
| geosolver | IMO_2016_P1 | 2 | no_output | native受理済み出力なし |
| gmb | IMO_2018_P1 | 0 | no_valid_output | commands/4:failed:cong |
| gmb | IMO_2018_P1 | 1 | no_valid_output | commands/4:failed:cong |
| gmb | IMO_2018_P1 | 2 | no_valid_output | commands/4:failed:cong |
| gmb | IMO_2018_P6 | 0 | no_valid_output | commands/1:failed:eq-ratio; commands/3:failed:=; commands/4:failed:= |
| gmb | IMO_2018_P6 | 1 | no_valid_output | commands/1:failed:eq-ratio; commands/3:failed:=; commands/4:failed:= |
| gmb | IMO_2018_P6 | 2 | no_valid_output | commands/1:failed:eq-ratio; commands/3:failed:=; commands/4:failed:= |
| gmb | IMO_2019_P2 | 0 | no_valid_output | commands/6:failed:=; commands/8:failed:= |
| gmb | IMO_2019_P2 | 1 | no_valid_output | commands/6:failed:=; commands/8:failed:= |
| gmb | IMO_2019_P2 | 2 | no_valid_output | commands/6:failed:=; commands/8:failed:= |
| gmb | IMO_2019_P6 | 0 | no_valid_output | commands/5:failed:invalid_intersection_witness |
| gmb | IMO_2019_P6 | 2 | no_valid_output | commands/4:failed:invalid_intersection_witness; commands/7:failed:ambiguous_exclusion |
| gmb | IMO_2020_P1 | 0 | no_valid_output | commands/2:failed:=; commands/3:failed:=; commands/4:failed:=; commands/5:failed:= |
| gmb | IMO_2020_P1 | 1 | no_valid_output | commands/2:failed:=; commands/3:failed:=; commands/4:failed:=; commands/5:failed:= |
| gmb | IMO_2020_P1 | 2 | no_valid_output | commands/2:failed:=; commands/3:failed:=; commands/4:failed:=; commands/5:failed:= |
