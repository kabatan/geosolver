# H14 blind grading — secondary

P001–P008の完成答案だけを読み、条件名、実験出力、他の採点者の結果は参照せずに採点した。採点基準と問題文は答案を読む前に確認し、下記の関係も独立に導出済み。数値正答だけでは完全証明としない。

`mapping_claim` は「RがHからAMへの垂足」という主張の有無を厳密に記録する。AMR共線とAR⊥HRを併記した場合も含むが、Rで直角という単独の帰結は別記する。`mapping_proof` はこの同定、または面積を決める同等の正しい関係を作図から自己完結で証明したか。正しい別解も受け入れる。`downstream_proof` は正しい投影関係／Rで直角という前提を認めた後段の論証のみを判定する。誤った「Aで直角」からの計算は、算術が正しくても合格としない。`exact_value` は最終的に採用した値を評価する。`branch_valid` はMD・MEの指定rayと、M以外の円の交点を正しく確認したかを表す。

| ID | mapping_claim | mapping_proof | downstream_proof | exact_value | complete | branch_valid |
|---|---|---|---|---|---|---|
| P001 | false | false | true | true | false | false |
| P002 | false | false | false | false | false | false |
| P003 | false | false | false | false | false | false |
| P004 | false | false | false | false | false | false |
| P005 | false | false | false | false | false | false |
| P006 | true | false | true | true | false | false |
| P007 | false | false | false | false | false | false |
| P008 | false | false | false | false | false | false |

## 独立照合に用いた一般関係

M=(0,0), B=(-1,0), C=(1,0), A=(u,v), v>0 と正規化し、k=u²+v²と置く。鋭角条件からk>1。

- Ωの式は x²+y²−((k−1)/v)y−1=0。
- ΩをBCで反射した円Ω′の式は x²+y²+((k−1)/v)y−1=0。
- AB上を X=B+t(A−B) とし、L²=(u+1)²+v²=k+2u+1 と置く。C中心・半径CAの円との交点方程式は L²(t−1)(t−δ)=0、δ=(3+2u−k)/L²。したがってDはt=δ。Ω′への代入は t[L²t−(3+2u−k)]=0 なのでD∈Ω′。B,Cを交換してE∈Ω′も得られる。
- M中心・単位半径の反転 X↦X/|X|² はΩ′をΩに写す。反転像D*,E*は正の倍率でそれぞれray MD,ME上にあり、MはΩ内部なので各ray上のΩとの交点は一意。よってP=D*, Q=E*。
- この反転により(BPM),(CQM)はそれぞれ直線BD=AB, CE=ACに写る。M以外の共通点Rの像はAなので、R=A/k。
- H=(u,(1−u²)/v)よりA·H=1。したがってR=(A·H/|A|²)AはHのAMへの正射影。0<1/k<1なのでRはAMの内部にある。

従って∠ARH=90°であり、正の長さHR=√(AH²−AR²)、面積=(1/2)AR√(AH²−AR²)。

- AH=13/4, AR=39/20：HR=13/5、面積=507/200。
- AH=17/3, AR=34√13/39：HR=17/√13、面積=289/39。

この導出は採点者の照合用であり、答案に存在しない手順を補って採点するためのものではない。

## P001

Rで直角という正しい関係を述べているが、R∈AMという主張はないため厳密なmapping_claimはfalse。証明は “a known theorem” と “The algebraic verification ... yields exactly the equation of this circle” に依存し、実際の座標や円の式を示していない。等腰三角形への極限と曖昧な回転対称性から一般の鋭角不等辺三角形の結論は導けず、指定された交点も確認していない。

一方、Rで直角を前提にしたHR=13/5の正の平方根の選択と面積507/200は正しい。よって後段と最終値のみ合格。

## P002

採用している “A, H, R, M are concyclic” は誤り。実際にはA,R,Mが異なる3点として一直線上に並ぶ。答案は “R is not on AM” とまで述べる。座標計算のH=(u,−k(u+k)/v)も誤りで、正しくはH=(u,(k²−u²)/v)。Dの式ではBA方向の符号も逆になっている。

最終的には “Assumption: The construction implies AH perpendicular to AR” を、答えの一意性から推測して採用している。最終値289√13/117は誤りで、正答は289/39。誤ったA直角の前提からの積の算術は正しいが、求める後段の証明ではない。交点の枝も未確認。

## P003

最終的なAR∥BC、すなわちAで直角という主張が誤り。核心は “it can be shown ... y_R = v” と “Detailed expansion ... confirms” という宣言だけで、対応する代入や交点計算がない。M=(0,0), B=(-a,0), C=(a,0), A=(u,v)なら、実際のy_Rはa²v/(u²+v²)であり、鋭角条件の下ではvより小さい。

y=vについて全体を反射しても元の作図を保存しない。最終値507/160は誤ったA直角を仮定した積であり、正答507/200ではない。途中で検討したR直角は最終解として採用されていない。交点の枝の検証もない。

## P004

Mを原点、B=(-a,0), C=(a,0)としたままA=(0,h_A)を置き、AB=ACを強制している。これは与えられた不等辺三角形を扱う座標設定ではない。冒頭の「RはHのBCについての反射像」は後で明示的に撤回されるため、その主張自体を最終的に保持された誤りとしては数えない。ただし代わりの作図証明は提示されていない。

最終的な “The existence of a unique answer implies the relation AH perpendicular to AR” は論証にならず、相似の核心も “triangle ADM similar to triangle ???” のまま。最終値289√13/117は誤り。正しい関係からの後段と枝の確認はない。

## P005

最終主張AH⊥ARは誤りで、証明は “Coordinate geometry showing dot product vanishes” という予告だけ。作図の途中ではBE=BAを “Distance AE = AB = c” に取り違え、Dも同様に扱っているため、問題の点を導出していない。

答案自身が等腰の場合の考察からAH⊥ARは一般には成り立たないと述べた後、“Let's trust the numbers and the likely orthogonal relationship” として未解決のまま採用する。13/4=6.5という小数の誤りは末尾で明示的に訂正されるので、それ自体は独立した不合格理由にしない。最終値507/160と採用した直角の位置は依然として誤り。枝の確認もない。

## P006

冒頭にA,R,Mの共線とR∈segment AMを明記し、最終要約にAR⊥RHを保持している。両者を合わせると垂足同定の主張になるのでmapping_claim=true。ただし作図からの証明はない。長い座標計算で確かめている「HのMについての反射像がΩ上にある」はそれ自体正しいが、その点が作図上のRだという同定にはならない。反射像による同定は途中で疑われ、最後は “Based on the Miquel point properties ... R lies on the circle with diameter AH” と結論を宣言するだけ。

未解消の誤主張として “the quadrilateral PBRC is cyclic”、Rが直径AHの円とΩの交点だという説明を含む。実際のRはΩの内部にあり、冒頭のR∈segment AMとも矛盾する。またArea=|u×v|とした直後の “4 Area² = |u cross v|²” は自己矛盾した係数である。これらは完全証明としての一貫性を満たさない。

しかし最後のR直角を認めた後のHR=13/5と面積507/200は正しい。小数の取り違えも明示的に修正されている。後段と最終値を合格、構成証明と枝の確認を不合格とする。

## P007

誤ったA,H,R,Mの共円性を保持し、最後は誤ったA直角を採用する。Hの座標は途中で訂正し、Dの正しい二次方程式も書くが、“Let's skip the heavy algebraic derivation” として作図の核心を放棄する。“One is D. What is the other?” と述べ、t=1がAであることも利用しない。

二円(BPM),(CQM)に対する “Radical axis PQ” は誤りで、共通弦の直線MRが根軸。R直角を試した数値計算も289/9=50222/1521と誤変換する（正しくは48841/1521）ため、正しい可能性を複雑な根号として放棄している。最終値289√13/117は正答289/39ではない。枝の検証なし。

## P008

R∈ΩとAH⊥ARという二つの誤った一般主張を採用する。証明中の “Let's use the property that AR perpendicular to AH” が結論の先取りで、“Does this R lie on (BPM)? In this symmetric case, yes” も一般の不等辺配置でどちらの定義円も確認していない。Hの反射像がΩに乗るという既知事実はRの同定にならない。

答えが有理数になるはずという後段の推測も論証を修復しない。最終採用値289√13/117は誤りで、正答は289/39。誤ったA直角からの掛け算は合っているが、正しい関係からの後段ではない。枝の検証なし。

## 集計

完全証明0/8、作図からの決定的関係の証明0/8、枝の検証0/8。正しい関係を仮定した後段と最終数値の一致はともにP001・P006の2/8。厳密な垂足同定の主張はP006のみ。ただし、いずれも条件別の解釈は行っていない。
