# R1 開発群の全誤予測

中間への着地も外れ。未対応・error・not_run は費用の正誤を判定せず、末尾に別記。全候補R0–R2の外れは `development-errors-all.csv`、保留を含む全323問×3規則は `development-predictions-all.csv`。

|ID|局所予告→観測|厳密側予告→観測|p|厳密側秒|
|---|---|---|---:|---:|
|AIME-2006-II-01|easy → easy|costly → intermediate|1.0|1.4013497860000257|
|AIME-2006-II-09|hard → intermediate|abstain → intermediate|0.21|2.9009188080000285|
|AIME-2007-I-15|abstain → easy|costly → intermediate|0.9|3.3648516169999994|
|AIME-2007-II-15|abstain → intermediate|costly → enumeration_mismatch|0.26||
|AIME-2008-I-10|hard → intermediate|abstain → enumeration_mismatch|0.12||
|AIME-2008-II-05|easy → easy|fast → costly|0.98||
|AIME-2009-I-12|easy → intermediate|fast → enumeration_mismatch|0.125||
|AIME-2009-II-10|easy → intermediate|abstain → fast|0.365|0.4309063449999826|
|AIME-2010-II-15|abstain → easy|costly → intermediate|0.925|1.1472109669999782|
|AIME-2011-I-04|abstain → easy|costly → fast|1.0|0.5584133380000367|
|AIME-2011-II-04|abstain → hard|costly → enumeration_mismatch|0.06||
|AIME-2011-II-10|hard → easy|costly → intermediate|0.945|2.5449734099999546|
|AIME-2012-I-12|hard → intermediate|costly → enumeration_mismatch|0.185||
|AIME-2012-II-15|abstain → easy|costly → fast|0.955|0.8721788880000076|
|AIME-2013-II-08|abstain → easy|costly → intermediate|0.915|1.9161932869999418|
|AIME-2013-II-15|easy → intermediate|out_of_scope → intermediate|0.475|8.283877462999953|
|AIME-2014-I-13|hard → intermediate|costly → enumeration_mismatch|0.12244897959183673||
|AIME-2014-II-03|hard → intermediate|abstain → intermediate|0.195|2.7468800190000024|
|AIME-2014-II-08|easy → intermediate|fast → fast|0.525|0.5814181510000367|
|AIME-2014-II-11|hard → intermediate|abstain → enumeration_mismatch|0.115||
|AIME-2014-II-14|abstain → easy|costly → intermediate|1.0|1.2715709550000724|
|AIME-2015-I-07|hard → hard|costly → enumeration_mismatch|0.0||
|AIME-2015-II-07|abstain → easy|costly → enumeration_mismatch|1.0||
|AIME-2015-II-15|easy → intermediate|out_of_scope → intermediate|0.495|2.453441020000014|
|AIME-2016-I-15|hard → hard|costly → intermediate|0.01694915254237288|5.508927108000023|
|AIME-2019-I-06|hard → intermediate|abstain → intermediate|0.155|4.731732590999854|
|AIME-2019-I-13|hard → intermediate|abstain → intermediate|0.345|4.9488551579997875|
|AIME-2019-I-15|abstain → intermediate|costly → enumeration_mismatch|0.255||
|AIME-2019-II-11|hard → intermediate|abstain → intermediate|0.17901234567901234|4.892719355000054|
|AIME-2019-II-15|hard → hard|costly → enumeration_mismatch|0.0||
|AIME-2020-I-01|hard → hard|costly → enumeration_mismatch|0.07||
|AIME-2020-I-13|abstain → easy|costly → fast|0.99|0.7904091549996792|
|AIME-2020-I-15|hard → intermediate|costly → costly|0.12154696132596685|33.14628373000005|
|AIME-2020-II-15|abstain → hard|costly → intermediate|0.01|2.236033030999806|
|AIME-2021-I-13|hard → hard|costly → enumeration_mismatch|0.0||
|AIME-2021-II-02|easy → intermediate|abstain → intermediate|0.815|7.359964838999986|
|AIME-2022-I-08|easy → intermediate|costly → fast|0.585|0.9482808819998354|
|AIME-2022-I-11|hard → intermediate|abstain → intermediate|0.37|1.399385177000113|
|AIME-2022-II-11|hard → intermediate|enumeration_mismatch → enumeration_mismatch|0.5||
|AIME-2023-I-08|hard → intermediate|abstain → intermediate|0.225|7.773013558999992|
|AIME-2023-I-12|easy → intermediate|abstain → intermediate|0.54|2.4620451440002853|
|AIME-2023-II-09|abstain → easy|costly → intermediate|1.0|1.2135749089998171|
|AIME-2025-I-06|easy → intermediate|abstain → fast|0.265|0.922208822000357|
|AIME-2025-II-05|abstain → easy|costly → intermediate|0.98|4.872628486000394|
|AIME-2025-II-14|hard → intermediate|costly → intermediate|0.36|3.133080343000529|
|HMMT-2006-FEB-GEO-06|easy → hard|fast → intermediate|0.06|1.0028945720000593|
|HMMT-2006-FEB-GEO-07|easy → intermediate|abstain → fast|0.155|0.6332956770002056|
|HMMT-2006-FEB-GEO-10|easy → intermediate|fast → fast|0.56|0.42307803200037597|
|HMMT-2007-FEB-GEO-04|hard → intermediate|costly → intermediate|0.565|1.0624923639998087|
|HMMT-2007-FEB-GEO-06|abstain → intermediate|costly → intermediate|0.59|2.337688194999373|
|HMMT-2007-FEB-GEO-07|easy → intermediate|fast → fast|0.3|0.6484054699999433|
|HMMT-2007-FEB-GEO-08|easy → easy|fast → enumeration_mismatch|1.0||
|HMMT-2007-FEB-GEO-10|hard → intermediate|abstain → intermediate|0.13|1.6529761409997263|
|HMMT-2008-FEB-GEO-02|easy → hard|fast → fast|0.09|0.4550365129994134|
|HMMT-2008-FEB-GEO-03|abstain → intermediate|costly → fast|0.825|0.8743345890006822|
|HMMT-2008-FEB-GEO-07|abstain → easy|costly → intermediate|1.0|1.1350771889997304|
|HMMT-2008-FEB-GEO-09|hard → intermediate|costly → enumeration_mismatch|0.64||
|HMMT-2008-FEB-GEO-10|abstain → easy|costly → intermediate|1.0|1.0374210429999948|
|HMMT-2009-FEB-GEO-04|abstain → easy|costly → intermediate|0.995|1.028837016000125|
|HMMT-2011-equilateral-hexagon|hard → intermediate|costly → unsupported|0.21693121693121692||
|HMMT-2012-FEB-GEO-03|easy → intermediate|out_of_scope → unsupported|0.835||
|HMMT-2013-FEB-GEO-03|hard → intermediate|costly → enumeration_mismatch|0.37209302325581395||
|HMMT-2013-FEB-GEO-04|hard → intermediate|abstain → enumeration_mismatch|0.375||
|HMMT-2015-FEB-GEO-04|abstain → intermediate|costly → intermediate|0.44|1.746105187000012|
|HMMT-2016-FEB-GEO-10|hard → intermediate|out_of_scope → not_run|0.155||
|HMMT-2017-FEB-GEO-01|hard → intermediate|out_of_scope → costly|0.63|11.73355492500059|
|HMMT-2017-FEB-GEO-04|easy → intermediate|abstain → fast|0.83|0.6473141690003104|
|HMMT-2017-FEB-GEO-06|abstain → intermediate|costly → intermediate|0.27|2.5035962550000477|
|HMMT-2018-FEB-GEO-08|abstain → intermediate|costly → intermediate|0.665|1.459086447000118|
|HMMT-2018-FEB-GEO-10|abstain → intermediate|costly → enumeration_mismatch|0.52||
|HMMT-2019-FEB-GEO-05|hard → easy|enumeration_mismatch → enumeration_mismatch|1.0||
|HMMT-2020-FEB-GEO-04|abstain → easy|costly → enumeration_mismatch|1.0||
|HMMT-2020-FEB-GEO-07|hard → easy|costly → fast|1.0|0.6312773360000392|
|HMMT-2020-FEB-GEO-09|hard → easy|costly → intermediate|0.995|9.499742778000837|
|HMMT-2021-FEB-GEO-04|abstain → intermediate|costly → fast|0.84|0.9234187570000358|
|HMMT-2022-FEB-GEO-05|easy → intermediate|abstain → intermediate|0.385|2.189719628000603|
|HMMT-2022-FEB-GEO-06|abstain → intermediate|costly → intermediate|0.745|3.2348889419990883|
|HMMT-2022-FEB-GEO-10|hard → hard|costly → enumeration_mismatch|0.0||
|HMMT-2023-FEB-GEO-05|easy → intermediate|fast → fast|0.225|0.4624251920013194|
|HMMT-2024-FEB-GEO-01|hard → easy|abstain → intermediate|0.945|5.061625600000298|
|HMMT-2024-FEB-GEO-03|easy → hard|abstain → fast|0.055|0.9995859040000141|
|HMMT-2024-FEB-GEO-04|easy → intermediate|fast → fast|0.55|0.7674839549999888|
|HMMT-2024-FEB-GEO-10|hard → intermediate|costly → enumeration_mismatch|0.245||
|HMMT-2025-FEB-GEO-01|hard → hard|costly → intermediate|0.0|7.16150637300052|
|HMMT-2025-FEB-GEO-02|hard → easy|enumeration_mismatch → enumeration_mismatch|0.9852941176470589||
|HMMT-2025-FEB-GEO-04|abstain → intermediate|costly → intermediate|0.665|2.654533566000282|
|HMMT-2025-FEB-GEO-05|easy → intermediate|abstain → intermediate|0.545|3.88941766500011|
|HMMT-2025-FEB-GEO-08|hard → intermediate|abstain → intermediate|0.445|2.6454158699998516|
|JMO-2006-PRE-09|abstain → intermediate|costly → enumeration_mismatch|0.34||
|JMO-2008-PRE-11|hard → intermediate|abstain → intermediate|0.165|4.425324386000284|
|JMO-2014-PRE-09|easy → intermediate|abstain → enumeration_mismatch|0.165||
|JMO-2016-PRE-05|hard → intermediate|abstain → intermediate|0.425|7.321851585999866|
|JMO-2017-PRE-01|easy → intermediate|fast → intermediate|0.19|1.6715302620004877|
|JMO-2017-PRE-08|abstain → intermediate|costly → enumeration_mismatch|0.235||
|JMO-2018-PRE-06|hard → intermediate|abstain → intermediate|0.54|2.552361517999998|
|JMO-2019-PRE-04|hard → easy|costly → error|0.915||
|JMO-2019-PRE-08|hard → intermediate|abstain → costly|0.135|10.524371166000492|
|JMO-2020-PRE-02|easy → intermediate|fast → fast|0.54|0.9255574500002695|
|JMO-2021-PRE-03|abstain → easy|costly → intermediate|0.95|1.0115680720000455|
|JMO-2021-PRE-10|hard → intermediate|costly → enumeration_mismatch|0.136||
|JMO-2022-PRE-02|abstain → intermediate|costly → intermediate|0.4|6.8223587020002014|
|JMO-2022-PRE-04|abstain → easy|costly → intermediate|0.92|1.4852098040000783|
|JMO-2022-PRE-12|abstain → intermediate|costly → intermediate|0.41|5.3569386929993925|
|JMO-2024-PRE-06|hard → hard|costly → intermediate|0.0|4.119071804001578|
|JMO-2025-PRE-09|abstain → easy|costly → intermediate|0.955|6.2556300119995285|
|aime-2000-2-8|easy → intermediate|fast → fast|0.795|0.6566280350000113|
|aime-2001-1-9|hard → hard|costly → enumeration_mismatch|0.01||
|aime-2001-2-6|hard → intermediate|abstain → enumeration_mismatch|0.11||
|aime-2001-2-7|hard → intermediate|abstain → costly|0.59|34.98612111199998|
|aime-2002-2-13|hard → intermediate|abstain → fast|0.505|0.7822408550000262|
|aime-2003-1-15|abstain → easy|costly → fast|0.995|0.43799719300000106|
|aime-2003-1-7|easy → hard|out_of_scope → unsupported|0.04||
|aime-2003-2-11|easy → intermediate|fast → fast|0.51|0.4236380570000051|
|aime-2004-2-13|easy → intermediate|fast → fast|0.85|0.4049098720000188|
|aime-2005-1-15|easy → easy|fast → intermediate|0.945|1.470787131999998|

## 費用分類を出したが、観測側を判定できない全件

|ID|予告|観測側の状態|
|---|---|---|
|AIME-2013-I-12|costly|unsupported|
|AIME-2019-II-13|fast|unsupported|
|AIME-2021-II-14|enumeration_mismatch|error|
|HMMT-2008-FEB-GEO-05|enumeration_mismatch|unsupported|
|HMMT-2011-equilateral-hexagon|costly|unsupported|
|HMMT-2017-FEB-GEO-05|costly|error|
|JMO-2010-PRE-11|costly|error|
|JMO-2018-PRE-09|costly|error|
|JMO-2019-PRE-04|costly|error|
|JMO-2021-PRE-02|fast|error|
|aime-2000-2-10|enumeration_mismatch|unsupported|
|aime-2005-1-14|enumeration_mismatch|not_run|
