# 全答案の採点理由
## 証明48答案
| ID | 問題 | モデル | 区分 | 根拠 |
|---|---|---|---|---|
| R0001 | N01 | base | core_gap | H・Pの一般座標や円の式を一つも示さず「代入して確認」と述べるだけで、共円性の核心が未証明。 |
| R0002 | AP01 | trained | core_gap | 「Fの座標を計算し…円の方程式を満たす」とする手順だけで、Fの一般式も角の核心関係も示さない。 |
| R0003 | AP01 | base | special_case | A=(0,0),B=(3,0),C=(1,2),F=(1.2,0.9)という具体例だけを確認し一般化。一般の共円性の導出はない。 |
| R0004 | N02 | trained | mathematical_error | CA²=CB·CTとBA²=BT·BCはB,C,Tが非共線なので方べきとして使用不能。接弦角の向きも誤る。 |
| R0005 | AP01 | trained | special_case | A=(0,0),B=(2,0),C=(1,2),F=(14/13,8/13)の確認のみ。一般の三角形でも同様との断言では証明にならない。 |
| R0006 | EV02 | trained | complete | E,Fの一般座標からt=a/(a−1)を得て、H=(a,a(2−a)/b)とAMの内積を0に整理。非退化条件も問題から満たす。 |
| R0007 | N02 | base | mathematical_error | ∠ATB=∠ATC=∠Aは誤り。また△BTCの正弦定理に∠TCA,∠TBCを使っている。最後の核心等式も導出なし。 |
| R0008 | DU01 | trained | special_case | U,V,Kの具体例の傾きだけを確認。一般のKの式はなく、V=(1,−a/b)はc=2への特殊化。 |
| R0009 | DU01 | trained | core_gap | 一般のU,VとmUVは正しいが、mAKは具体例のみ。AKを「対称軸」と呼ぶだけでは一般の核心関係を論証していない。 |
| R0010 | OB01 | trained | local_error | E,F,両円の中心,Xの一般式と共線性は正しい。ただしEを「AFに垂直な条件から」導くという説明はBE⊥ACとの取り違え。 |
| R0011 | OB01 | trained | complete | 両円の方程式の差からy=d x/(b+c)を導きANと一致させる正しい一般証明。「共通接線」は根軸の誤訳だが計算と結論に影響しない。 |
| R0012 | DU01 | trained | complete | B=(c,0),C=(b cosα,b sinα)に対してU,V,mUV,mAKの一般式を正しく明示。接線の連立計算は省略されているがmAK=c sinα/(b+c cosα)はその計算結果と一致し、積−1を証明する。計算省略の許容について要人手確認。 |
| R0013 | N02 | base | special_case | 円の中心の一般式まではあるが、Tの座標とAT²=BT·CTの確認は具体例のみ。「Tが両円に属するため」は一般の論証にならない。 |
| R0014 | N01 | base | special_case | A=(1.5,1),B=(0,0),C=(2,0)の一例は計算できているが、一般のPと円の関係がない。 |
| R0015 | EV02 | trained | special_case | A=(0.5,1),B=(0,0),C=(2,0)の一例のみ。Hの座標は正しいがAMを高線とする記述も誤る。 |
| R0016 | N02 | trained | mathematical_error | 途中でb,cを再定義し、AT²=c²/Dという次元も不整合な式を使用。ATが角の二等分線という終結も一般には偽。 |
| R0017 | N01 | trained | complete | H=(e,(d²−e²)/f), P=(d²e/(e²+f²),d²f/(e²+f²)), k=(d²−e²−f²)/(2f)を明示。Pの円への代入は一般に恒等的に成立する。 |
| R0018 | AP01 | trained | mathematical_error | 相似の対応角を逆にして∠ANP=∠ABCとする。さらに∠AFN=∠APNを「対称性」で断言し核心を示さない。 |
| R0019 | AP01 | base | core_gap | DA=DB,EA=ECと二等辺三角形の角関係までは正しいが、∠AFP=∠ACBを導出せず具体例の確認に置き換える。 |
| R0020 | OB01 | base | complete | 両円の一般式の差−2cx+2c(b+c)y/d=0がANと一致。Xの一般座標による確認も正しい。 |
| R0021 | DU01 | trained | special_case | 一般のUVの傾きは正しいがAKの傾きは一例だけで、一般のKに対する式または推論がない。 |
| R0022 | N01 | trained | mathematical_error | Pのy座標がx座標と同じ式で誤り。B=(0,0),C=(2c,0)なのに円のx係数−2、未定義hも混在する。 |
| R0023 | AP01 | base | core_gap | AD=BD,AE=CEからFが円ANP上と断言するだけで、必要な角関係または一般座標計算がない。 |
| R0024 | OB01 | trained | core_gap | Nの両円への方べきが等しいという核心を、中点であることから断言するのみ。根軸の性質の適用自体は正しいが前提が未証明。 |
| R0025 | EV02 | base | complete | E,F,T,Hの一般式が正しく、mHT=−(a−1)/b, mAM=b/(a−1)から直交を証明。 |
| R0026 | DU01 | base | mathematical_error | AKはsymmedianという言及はあるが「角の二等分線と垂直」という誤った性質と、同じ線に垂直な2線が互いに垂直という誤推論を用いる。 |
| R0027 | DU01 | base | core_gap | U,Vの座標と結論に必要なAK傾きは正しいが、核心であるsymmedianの傾きの公式を根拠なく「一般に」と引用。垂線を−tanθとする誤記も残る。 |
| R0028 | AP01 | trained | mathematical_error | ∠ANP=∠ABCが誤りで、∠AFP=∠ANPも「円周角の性質や対称性」で仮定している。 |
| R0029 | OB01 | trained | core_gap | 「中心をそれぞれ求めると…値は等しい」とするのみで中心の式やNの方べきの値を示さず、核心が未証明。 |
| R0030 | AP01 | base | mathematical_error | A,N,Pが同一円上だから∠ANP=∠APNという誤用があり、求める∠AFP=∠ACBも明示的に仮定する。 |
| R0031 | N01 | trained | local_error | H・P・円の一般式は正しく共円性を検算できる。ただし「HはAMとBCの垂直線の交点」は誤りで、高線の説明の局所修正が必要。 |
| R0032 | N02 | base | complete | 両円の中心、共通弦の直線、一般のT座標とAT²を明示しており、BT²CT²=(AT²)²を通常の代入で確認できる。具体例だけに依存していない。radical axisの訳「共通接線」は誤訳だが式は正しい。 |
| R0033 | DU01 | base | special_case | A=(0,0),B=(2,0),C=(1,2)での確認のみ。一般のU,V,Kまたは核心の幾何関係を計算・論証していない。 |
| R0034 | OB01 | base | complete | 垂足、中心、Xの一般式が正しく、AXとANの傾きe/(b+d)が一致する。 |
| R0035 | N01 | trained | local_error | H,P,円の一般式は正しく代入で結論を得る。ただし「BCの傾きは0…BHは垂直」とする説明はACへの垂線との取り違え。表示したBHの式自体は正しい。 |
| R0036 | N01 | base | local_error | H,P,kと円への代入は正しい一般式。一方「高線BHは y=(b²−p²)/q」は直線の式でなくHのy座標。ここを修正すれば完答。 |
| R0037 | N02 | trained | mathematical_error | ∠BAT=∠CAT=∠BACは内部のTに対して不可能。さらに∠ABT=∠ACTを仮定しており、辺の関係の論証にならない。 |
| R0038 | OB01 | base | complete | 方法1は正しい一般のE,F,中心,X座標と傾きの一致による完答。方法2の「NがAとXに挟まれ」は一般には誤りだが、独立に完結する方法1では使わない。 |
| R0039 | EV02 | trained | special_case | A=(0.5,2),B=(0,0),C=(2,0)だけの確認。「一般の三角形でも…推測される」として未証明の一般化をする。 |
| R0040 | EV02 | base | mathematical_error | Tのy=0をHのyと同じとしてHTを水平線と断定し、AB≠ACにもかかわらずAMを高線とする。Eのx座標も誤る。 |
| R0041 | DU01 | base | core_gap | AKのsymmedianという語はあるが、UVとの直交を「対称性と構造から」と断言しており、その関係の根拠がない。 |
| R0042 | N02 | trained | mathematical_error | CT·CA=CA²からCT=CAとする方べき適用が無効。B側も同じ誤用でBT=BAと結論する。 |
| R0043 | EV02 | base | special_case | 一般のE,F,Tの式を示さず、A=(0.5,2)の内積0だけで一般の命題を結論する。 |
| R0044 | N02 | base | mathematical_error | 内角∠ATB=∠ATC=αは誤り（正しくは180°−α）。β+α=π−γという未成立の等式を用いて核心の正弦積を等置している。 |
| R0045 | OB01 | base | local_error | 一般のE,F,中心,Xの座標と傾きは正しいが、Eを「AFに垂直な条件から」導くという説明はBE⊥ACとの取り違え。 |
| R0046 | EV02 | base | complete | 垂足の連立直線を明示してT_x=ac/(a−c)、H=(a,a(2c−a)/b)を求め、傾きの積−1で結論する。 |
| R0047 | N01 | base | mathematical_error | AB=ACの例を選び、さらにH,AM,Pと円の式が誤る。示した円x²+y²−3x+y=0はC=(2,0)も通らない。 |
| R0048 | EV02 | trained | core_gap | E,Fの座標は正しいが、T_x=ac/(a−c)をEFとの交点からでなく「HTとAMが垂直である条件から」求めており循環。正しい式の提示だけでは当該方向の推論を補えない。 |

## 学習48答案
| 配置・回答 | 数値正答 | V | G有用性 | 根拠 |
|---|---|---|---|---|
| DA07 / 0 | False | no | no | AM⊥AN、AY=36を対称性だけから仮定し45とする。 |
| DA07 / 1 | False | no | no | XY=AX+MNを撤回した後、XY=MX+MNを根拠なく採用。 |
| DA07 / 2 | False | no | no | Hを円BHCの中心としてAH²−R²を方べきとする誤用と、XY=MX+MNの仮定。 |
| DA07 / 3 | False | no | no | AN·AY=432cos²Aに根拠がなく、最後はXY=MX+MNと仮定。 |
| DB16 / 0 | False | no | no | NA=NPまでは正しいがNを特定する核心を解けず、AN=24/5を断言。 |
| DB16 / 1 | False | no | no | AOとAO1を同時にx軸上と仮定。さらにその設定でも交点x=4なのに24/5とする。 |
| DB16 / 2 | False | no | no | AOをx軸とした後O1=(4,0)を無根拠に追加しN=O1とする。 |
| DB16 / 3 | False | no | no | AO1をx軸に置いた後、根拠なくAOもx軸と置いてAN=4とする。 |
| DB12 / 0 | False | no | no | B=(13,0),C=(13,13)という形を固定しBX+CX=17に合わせて相似拡大するためBC=13が保たれない。 |
| DB12 / 1 | False | no | no | AB=AC=sに限定し、BCとBX+CXの両条件を満たすことを示さない。 |
| DB12 / 2 | False | no | no | X=(c/2,b/2)をACの中点と誤認し、最後は13を根拠なく断言。 |
| DB12 / 3 | False | no | no | 円1のy係数が誤りで、最後の13は直前の根号式とも一致しない。 |
| H04 / 0 | False | no | no | T,B,Cの順序に反してT=(2,0)とする（正しくは−2）。 |
| H04 / 1 | False | no | no | TをB,Cの間に置いて条件違反。高線の傾きの説明も誤る。 |
| H04 / 2 | False | no | no | T,B,Cの順序を復唱しながらT=(2,0)とする。最後は鋭角条件の不整合も解消しない。 |
| H04 / 3 | False | no | no | T=(2,0)が順序条件違反。 |
| DA04 / 0 | False | no | no | PX,PY=12,2は正しいが、QをXまたはYに同一視してPQ=12とする。 |
| DA04 / 1 | False | no | no | QをΩとの他の交点と誤認してPQ=12とする。 |
| DA04 / 2 | False | no | no | QはX,Yと異なると認めつつPQ=大きい方のPX,PYと無根拠に推定。 |
| DA04 / 3 | False | no | no | QAはΩの接線でないのにQX·QY=QA²とし、QA=QBも仮定する。 |
| DA01 / 0 | False | no | no | O2=(0,1323√5/80)が誤りで、Tと距離の計算も整合しない。 |
| DA01 / 1 | True | no | no | 最終数値9/2は正しいが円2の半径をAC=9と誤認し距離=9という誤った方程式から中心を導出している。表示された中心・最終計算は正しいため局所誤りの扱いは人手確認対象。 |
| DA01 / 2 | True | yes | no | B=(11/3,8√5/3)、2中心、根軸、T=(369/98,54√5/49)と距離9/2の計算は正しい。 |
| DA01 / 3 | True | yes | no | 2中心を等距離条件から求め、根軸と交点の座標を計算し9/2を得る。 |
| HX01 / 0 | False | no | no | Jの位置関係を導かず「symmetry」からAJ=AC=6と断言。 |
| HX01 / 1 | False | no | no | AL=9を満たさない特定の三角形を採用しJ=Lと誤認。自身のAL=6と与条件が矛盾。 |
| HX01 / 2 | False | no | no | AXがsymmedianという言及からAJ=ACに飛躍し、必要な関係を証明していない。 |
| HX01 / 3 | False | no | no | Jを円AEP上と読み替え、対称性からAJ=ACと断言。 |
| H03 / 0 | False | no | no | Pa,Pb,Pcが九点円上と無根拠に同一視しOZ=OH/2とする。 |
| H03 / 1 | False | no | no | この構成は九点円とconsistentとするだけでPa等がその円上との論証がない。 |
| H03 / 2 | False | no | no | 角二等分線による構成が九点円上の点を生むという誤った既知性質を引用。 |
| H03 / 3 | False | no | no | 九点円との同一視に根拠がなく、その半径をOH/2とも誤認。 |
| H02 / 0 | False | no | no | 表示した中心・距離の根号式を17に「simplifies」とする誤計算。 |
| H02 / 1 | True | yes | no | A=(14,8)、U1,V1,U2,V2、Z1=(6,47/4),Z2=(9,19/2)の数値座標を検算でき、距離15/4は正しい。 |
| H02 / 2 | None | no_final | uncertain | 最終説明なし。打ち切りを不正な説明とは区別する。 |
| H02 / 3 | False | no | no | √72833/68を近似が近いという理由で3√7/2と等置。 |
| H01 / 0 | True | uncertain | uncertain | H,Pと最終数値は正しいが、中間式の右辺36を36pと誤記し、続く除算も整合しない。局所的な転記ミスとしてVを許容するか未確定。 |
| H01 / 1 | True | yes | yes | 一般A=(p,q)についてHと投影P=(9p/25,9q/25)を求めてAP=(16/25)AMとする。残る自由なA座標を消去する説明としてG=0.5。 |
| H01 / 2 | True | yes | yes | 一般A=(p,q)、P=((9p+96)/25,9q/25)を導きAP=(16/25)AMとして未知の形状依存を消す。G=0.5。 |
| H01 / 3 | True | yes | yes | 一般A=(a,b)についてP=36A/(a²+b²)を導いてAP=(AM²−36)/AMを数値化する。G=0.5。 |
| DB15 / 0 | True | yes | no | DE,DF,EFから三角形を正しく特定し、S,L,Q,Tを順に正しく計算。 |
| DB15 / 1 | True | yes | no | 2つの距離方程式、外接円とASの式、L,Q,T、距離がすべて整合。 |
| DB15 / 2 | True | yes | no | 距離条件からA=(10,4√6)、S,L,Q,Tを正しく計算してDT=2√7。 |
| DB15 / 3 | True | yes | no | 外接円式とASの交点L、Q,TからDT=2√7を正しく計算。 |
| DA15 / 0 | False | no | no | FがAO上という根拠のない仮定からOF=1とする。 |
| DA15 / 1 | False | no | no | 特定例の相似拡大でAO=13とAF=12を同時に満たすことを示さず、O,Fの座標も誤る。 |
| DA15 / 2 | True | no | no | AF²+OF²=AO²という核心関係を「specific coordinate setup」から一般化しただけで、論証せず5を得る。 |
| DA15 / 3 | True | no | no | FがAM上という誤った主張が残り、1を撤回した後も5の導出を提示していない。 |
