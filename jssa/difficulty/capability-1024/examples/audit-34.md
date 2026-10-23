# 34問のDSL監査（事後）

対象はa,b各17問。cases.jsonlと、aの保存AoPS HTML、bの保存HMMT原文抜粋を照合した。34問すべて手元原文を確認できた（原文未確認0問）。図依存のHMMT 2018は元PDFの既存PNGも確認した。原文の参照先・抜粋は[source-excerpts.md](source-excerpts.md)、入力と出典ハッシュは[evidence/audit-inputs.json](evidence/audit-inputs.json)。

「混入あり」は、答えの漏洩に限らず、原文から導いた解法の関係式や面積分解をDSL作者が先に与えた場合も含めた。この広い意味で5問。答えから逆算した定数の入力は確認できなかった。これら5問が不正である、あるいは答えから作られた、という判定ではない。
座標の移動・回転・尺度固定、定義通りの中点・接線・反射、指定測定量の直接展開は「原文のみ」。それでも原文で無名の補助点・中間値は該当箇所に記した。「要確認」3問は凸性や点の順序を入力側で追加選択したもの。正解したことを根拠に妥当とはしない。

多くのAIMEは元のm+n等ではなく、その手前の幾何量をtargetにしている。整数への後処理は既存採点側で別に行う。answer欄・カード・採点キーに正解があることと、solverに渡すDSLに正解を入れることは区別した。

集計: 原文のみ 26問, 要確認 3問, 混入あり 5問。

| ID | 原文の条件との対応(要約) | 使った作図(DSL命令) | 該当箇所 | 判定 |
|---|---|---|---|---|---|
| AIME-2001-I-05 | 楕円・指定頂点・正三角形・縦の高度。左右対称座標で表現。 | Distance, Point | なし | 原文のみ |
| AIME-2001-I-07 | 三辺21,22,20。DEはBCと平行で内心を通る。 | Distance, Incenter, Point, PointOnSegment | Iは原文の「内接円の中心」に付けた名前。未知のt,uでD,Eを配置。 | 原文のみ |
| AIME-2001-II-04 | P,Qは指定2直線上、R=(8,6)が中点。 | Distance, Midpoint, Point | M=Midpoint(P,Q)は原文の中点条件を表す補助名。傾き15/8,3/10は与式の書換え。 | 原文のみ |
| AIME-2001-II-13 | 辺8,6、対角線10、二組の角相等。 | Angle, ConvexPolygon, Distance, Point | ConvexPolygonとay>0,cy<0は凸・対角線の両側という配置を選ぶ。保存本文にconvexの明記はない。答え64/5の埋込みはない。 | 要確認 |
| AIME-2002-I-02 | 図の7+6+7個の同円・隣接接触・長方形への内接。半径1で尺度固定。 | Distance, Point | W=2+6*s,H=w+1と列間隔共通化は図の配置の座標化。u,v,w,sは未知。図のAsymptoteにsqrt(3)があるがDSLにはその値を転記していない。 | 原文のみ |
| AIME-2003-I-02 | 半径1〜100の同心円、赤緑交互。面積比を計測。 | Area, Circle, Point | Oは無名の共通中心への補助名。targetは偶数番の環の面積差50項の和。交互着色の直接展開であり比101/200は未入力。 | 原文のみ |
| AIME-2004-II-07 | AE=8,BE=17,CF=3。折り目EFでBを反射しAD上へ。 | Distance, Line, Point, Reflect | 幅8+17、F.x=8+17-3は与長の加減。原図コード内の高さ70/3をDSLは使用しない。 | 原文のみ |
| AIME-2005-I-01 | 半径30の円内に6個の等円の環、隣同士外接。 | Area, Circle, ConvexPolygon, Distance, Point | O,P0〜P5は原文で無名の中心。rは未知。中心の凸順序と非隣接中心距離>2*rで重複配置を除外。半径10や面積300*piは未入力。 | 原文のみ |
| AIME-2005-I-07 | BC=8,CD=12,AD=10、角A,B=60度。 | ConvexPolygon, Distance, Point, cos, sin | ConvexPolygonとC,DをABの同側に置く座標は凸配置を選ぶ。保存本文にconvexの明記はない。p,sqrt(q)の値は未入力。 | 要確認 |
| AIME-2005-II-08 | 半径4,10の接円、大円内部接触、中心共線、共通外接線の弦。 | Distance, Line, Point, sqrt | Lの無名の支持点Point(0,b),Point(1,a+b)も補助点。Lを傾きa切片bで表し、target=2*sqrt(R**2-Distance(O3,L)**2)。原文にない弦長計算式を人が入力。垂直線はこの表現では除くが、異径の共通外接線は垂直にならない。 | 混入あり |
| AIME-2005-II-12 | 辺900の正方形、中点O、EF=400、角EOF=45度、AE<BF。 | Angle, Distance, Midpoint, Point | O=Midpoint(A,C)は原文の正方形中心。e,fは未知で中間値BF=250+50*sqrt(7)は未入力。 | 原文のみ |
| AIME-2005-II-14 | 三辺13,15,14、CD=6、指定角相等。 | Angle, Distance, Point, PointOnSegment | D.x=15-6は与条件の加減。補助の解法点やBEの解値はなし。 | 原文のみ |
| AIME-2012-I-14 | 三次式の根3個、絶対値二乗和250、直角三角形。 | Distance, Point | 根の和0をVietaから導き2*x+u=0,2*y+v=0に置換。q,rと多項式をDSLから除去。直角頂点と二辺を座標軸に選ぶ。375は未入力。 | 混入あり |
| AIME-2014-I-01 | 50×80の長方形、各長辺に4穴、指定の交差経路と両端200。 | Distance, Point | 無名の穴にL0〜L3,R0〜R3と命名。間隔80/3とtargetの距離7本+2*200は原文経路の展開。最終長790は未入力。 | 原文のみ |
| AIME-2014-I-10 | 半径1の円が半径5の円外を転がり、元の半径が一回転。 | Angle, Point, cos, sin | 滑りなしから(5+1)*theta=2*pi*1を人が入力。B=(D.x-1,D.y)は回転完了を既に使う。theta=pi/3や答え27/31そのものは未入力。 | 混入あり |
| AIME-2014-II-10 | \|z\|=2014、1/(z+w)=1/z+1/w、全頂点の面積。 | Area, Point | 分母を払ったw^2+z*w+z^2=0を実虚部に分解し、W1,W2の上下で二根を指定。原文からの代数変形・根の列挙を人が済ませた。3042147や147は未入力。 | 混入あり |
| AIME-2019-I-12 | f(z)=z^2-19z、虚部11、f(z)で直角。 | Distance, Dot, Point, Vector | F=f(z),G=f(f(z))の実虚部を展開。原文にある中間値に名前を付けたもの。Dot=0、非零辺、x>0は指定の正の実部に対応。m=9,n=221は未入力。 | 原文のみ |
| HMMT-2010-FEB-GUTS-13 | 3方向への射影の最小最大値が指定の端点。 | Area, Point, max, min | (x+y)/2はy=xへの正射影座標の展開。補助点を増やさずmin/maxで端点を指定。 | 原文のみ |
| HMMT-2011-FEB-GUTS-01 | 面積1の三角形、辺上D,E、平行、比1/3、AをDEで反射したF。 | Area, Distance, Line, Parallel, Point, PointOnSegment, Reflect | なし | 原文のみ |
| HMMT-2012-FEB-GUTS-06 | 20×12の長方形、CZ=18、Eと2辺の距離6、EZの交点X,Y。 | Area, Distance, IntersectLines, Line, Point | Z.y=12+18は与長の加算。Eの座標6,6を固定せず探索する。 | 原文のみ |
| HMMT-2013-FEB-GUTS-01 | 直線y=kx上、横差4の距離31。7と19の点間距離。 | Distance, Point | 原文の無名の2点を(1,k),(5,5*k)に選ぶ。横差だけで距離が決まる直線上の平行移動。kの解値はなし。 | 原文のみ |
| HMMT-2014-FEB-GUTS-03 | 正六角形、BDFの内接円、ABDEの面積との比。 | Area, Incircle, Point, Radius, cos, sin | 外接半径1を比の尺度として選ぶ。pi*Radius(P)**2は円面積の定義。 | 原文のみ |
| HMMT-2015-FEB-GUTS-24 | 4辺10,8,25,12の円内接四角形、3辺の線分に接する円。 | Center, Circumcircle, ConvexPolygon, Distance, FootOfPerpendicular, Line, Point, Radius | Wは接円の無名の中心、Gammaは共通円への補助名。T0,T1,T2=FootOfPerpendicularは原文にない接点の明示で、中心から辺への距離と線分内を表す。値を固定した解法点ではない。 | 原文のみ |
| HMMT-2016-FEB-GUTS-14 | 三辺13,14,15、高度の足E,F、その外接円の接線3本で囲む面積。 | Area, Center, Circumcircle, Distance, FootOfPerpendicular, IntersectLines, Line, PerpendicularLine, Point | lA,lE,lFは原文の無名接線、U,V,Wは求める三角形の無名頂点。PerpendicularLineで接線を定義。 | 原文のみ |
| HMMT-2017-FEB-GUTS-02 | 円上6点の順序、交点X,Y,Z、指定6距離とXYZの周長。 | Center, Circumcircle, ConvexPolygon, Distance, Point, Radius | X,Y,Zを先に未知座標で置き、単位方向ベクトルでA〜Fを逆に構成。EをZより先、FをZより先とする符号選択は本文の明示的な位置条件より強く、円上の順序からの対応を要確認。解いた長さは未入力。 | 要確認 |
| HMMT-2018-FEB-GUTS-01 | 図の正方形を合同な4領域に分割、各面積1。 | Area, Midpoint, Point | O,M,N,P,Qは原図の分割線交点に付けた補助名。元PDFの十字の中線図をPNGで確認した。面積4の固定はなし。 | 原文のみ |
| HMMT-2019-FEB-GUTS-17 | 三辺3,4,5、各辺上の2点と共通Pを頂点とする合同正三角形、凸六角形。 | Area, ConvexPolygon, Distance, Point, PointOnSegment | sは原文で無名の共通辺長への中間変数。ax,ayも未知のまま。Pの解座標・面積定数は未入力。 | 原文のみ |
| HMMT-2020-FEB-GUTS-13 | 三辺7,1,4*sqrt(3)、Cの三等分線、外接円との第二交点X,Y。 | Angle, Center, Circumcircle, Distance, Point, PointOnSegment, Radius, sqrt | tx,ty!=0は原文のagain（C以外）の表現。D,Eの順序はラベル交換を除く。sqrt(3)は与条件そのもの。 | 原文のみ |
| HMMT-2021-FEB-GUTS-14 | 角A=2角C、AC=6,BC=8。ABを測る。 | Angle, Distance, Point | bは未知のABへの名前で原文の整数bとは別。sqrt(73)-3を制約に入れていない。 | 原文のみ |
| HMMT-2022-FEB-GUTS-11 | 単位円の正十二角形、交点X,Y、指定の曲線領域の面積。 | Angle, Area, IntersectLines, Line, Point, cos, sin | target=Angle(P2,O,P4)/2-Area(O,X,Y)は原文にない扇形から三角形を引く分解を人が入力。pi/6-sqrt(3)/12やfloor後45の埋込みはない。 | 混入あり |
| HMMT-2023-FEB-GUTS-03 | 凸四角形、角ABD=角BCD=90度、BDの中点M、CM=2,AM=3。 | Angle, ConvexPolygon, Distance, Midpoint, Point | なし | 原文のみ |
| HMMT-2024-FEB-GUTS-04 | 正五角形の外側に正三角形ABF,BCG、角FEG。 | Angle, Point, Rotate, cos, sin | 外接半径1は角の尺度固定。頂点をcos,sinで直接構成し、F,Gを-60度のRotateで外側に置く。48度や4*pi/15は未入力。 | 原文のみ |
| HMMT-2025-FEB-GUTS-06 | 正三角形、BD=1,DC=4、AC,ABの半直線上E,F、DはEF中点。 | Distance, Point | C.x=1+4は与長の和。未知t,u>=0で半直線。EF=2*sqrt(13)は未入力。 | 原文のみ |
| HMMT-2010-FEB-TEAM1-07 | 凸五角形内部のP、FPDQが平行四辺形、10度と15度の角。 | Angle, ConvexPolygon, Point | P=(fx+dx-1,fy+dy)は平行四辺形の定義の座標化。AQ=1は角の尺度固定。内部判定の各辺との外積を展開。15度の答えの固定はなし。 | 原文のみ |
