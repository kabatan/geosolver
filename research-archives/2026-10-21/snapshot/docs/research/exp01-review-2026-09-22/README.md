# exp01再評価の保存資料

モデル名を伏せて全80件の判定を固定した後、対応表と結合した記録。
過去の一部答案を見ているため、完全独立の盲検とはいえない。基準と限界は[完了報告](../exp01-repair-completion-2026-09-22.md)を参照。

- [数値再採点の集計](numeric_rescore_summary.json)
- [証明の集計](proof_review_summary.json)
- [80件の判定と原回答hash](proof_grades_unblinded.jsonl)
- [判定固定時のhash](proof_grades_freeze.json)
- [旧成果物のhash](historical_source_manifest.json)

## 証明の判定根拠

completeだけを完全正解に集計。local_errorは明記した局所修正を要するため別扱い。core_gapは核心の欠落、special_caseは数値例だけの議論。

| 問題 | モデル | sample | review ID | 判定 | 根拠 |
|---|---|---:|---|---|---|
| AP01 | baseline | 0 | [P014](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:13) | core_gap | 円の一般式は書くがFの座標と円への代入を実行せず、結論を反復する。 |
| AP01 | baseline | 1 | [P009](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:14) | special_case | A=(0,0),B=(2,0),C=(1,2)の例だけから一般化。Fの数値座標にも誤りがあり、一般証明ではない。 |
| AP01 | baseline | 2 | [P045](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:15) | core_gap | D,Eは一般座標で求めるが、核心のFの座標と共円条件の検証が欠落する。 |
| AP01 | baseline | 3 | [P057](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:16) | special_case | 一つの三角形での確認を提案するだけで、その計算も一般証明も提示していない。 |
| AP01 | trained | 0 | [P059](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:13) | special_case | 一例から一般化。Dのx座標1.5はABの垂直二等分線x=1にすら乗らない。 |
| AP01 | trained | 1 | [P011](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:14) | core_gap | ∠ANP=∠ABCと∠AFB=∠ABCを根拠なく用い、FBとFPも混同している。 |
| AP01 | trained | 2 | [P075](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:15) | core_gap | D,Eの一般座標まで正しく進むが、Fの座標と円への代入が丸ごと欠けている。 |
| AP01 | trained | 3 | [P050](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:16) | core_gap | ∠ANPの取り違えに加え∠AFB=∠ABCを断言。F,B,Pの共線性もなく結論を導けない。 |
| AP01_hint | baseline | 0 | [P015](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:37) | core_gap | 一般座標の実計算がなく、最後は∠AFP=∠ANPの断言。 |
| AP01_hint | baseline | 1 | [P078](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:38) | core_gap | ALの中点Qの共円性には触れるがF=Qを導かず、∠AFP=∠ANPを示していない。 |
| AP01_hint | baseline | 2 | [P042](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:39) | core_gap | 円ANPを直径APの円と誤認。AF⊥FPも未証明で一般には偽。 |
| AP01_hint | baseline | 3 | [P052](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:40) | core_gap | 等角共役線ALを角二等分線と誤認し、QとFを結ぶ論証がない。 |
| AP01_hint | trained | 0 | [P007](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:37) | core_gap | ∠AFP=∠ABCを未証明で使用。ALの中点への言及も可能性の説明のみ。 |
| AP01_hint | trained | 1 | [P061](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:38) | core_gap | 具体的座標で検証したと述べるだけで座標も計算もなく、核心は断言。 |
| AP01_hint | trained | 2 | [P049](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:39) | special_case | 特定の数値例だけから一般化。一般の共円条件は導いていない。 |
| AP01_hint | trained | 3 | [P073](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:40) | core_gap | 一般座標の途中に特定例のCE:y=7x−10を挿入し、一般のFの座標を求めていない。 |
| DU01 | baseline | 0 | [P017](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:5) | core_gap | symmedianへの言及と特定数値例のみ。一般のUVとAKの方向の関係を証明していない。 |
| DU01 | baseline | 1 | [P026](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:6) | core_gap | 一般座標の方針を述べるだけでU,V,Kを計算していない。Kを垂直二等分線の交点とする誤認もある。 |
| DU01 | baseline | 2 | [P001](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:7) | core_gap | UVとAKの方向が補角だから垂直、という核心の角関係に根拠がない。 |
| DU01 | baseline | 3 | [P072](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:8) | core_gap | U,Vの座標とUVの傾きは導出するが、AKの傾きは負の逆数となるように置くだけでKの接線条件から導いていない。 |
| DU01 | trained | 0 | [P064](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:5) | core_gap | symmedianへの言及と一つの座標例はあるが、一般的な直交の導出がない。 |
| DU01 | trained | 1 | [P065](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:6) | core_gap | UVの方向とsymmedianの角の対応を未証明のまま用いる。 |
| DU01 | trained | 2 | [P048](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:7) | core_gap | 核心の角関係は未証明で、座標による検証も手順の予告のみ。 |
| DU01 | trained | 3 | [P033](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:8) | core_gap | AKを対称軸と呼び、UVとの直交を角度関係の断言で済ませる。 |
| DU01_hint | baseline | 0 | [P043](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:29) | core_gap | 接弦定理の角対応に誤りがあり、D∈AKの核心も断言。 |
| DU01_hint | baseline | 1 | [P079](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:30) | core_gap | D∈AKをそのまま仮定した循環論証。 |
| DU01_hint | baseline | 2 | [P006](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:31) | core_gap | 未定義のc,d,eでAKとADの同じ傾きを断言し、Kの接線条件から導かない。 |
| DU01_hint | baseline | 3 | [P020](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:32) | complete | 一般のU,V、外心Oを正しく導き、接線交点KからのAK傾きを明示。連立一次式の計算は通常の省略として許容。 |
| DU01_hint | trained | 0 | [P044](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:29) | core_gap | AKがsymmedianであることだけから、根拠なくD∈AKを結論する。 |
| DU01_hint | trained | 1 | [P016](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:30) | core_gap | AKを対称軸と誤認し、AD=AKは未証明。座標例の実計算もない。 |
| DU01_hint | trained | 2 | [P013](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:31) | core_gap | ADがsymmedianである核心を一つの座標例への言及で済ませる。 |
| DU01_hint | trained | 3 | [P012](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:32) | core_gap | D∈AKを対称性や根軸から導出可能と述べるだけ。 |
| EV02 | baseline | 0 | [P035](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:1) | complete | 一般の高線からHを導き、E,Fを経た交点T=ac/(a−c)を明示。内積の直接代入で0となる。 |
| EV02 | baseline | 1 | [P030](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:2) | core_gap | Tの式もH=(a/2,3b/4)も一般には誤りで、内積0も計算されていない。 |
| EV02 | baseline | 2 | [P080](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:3) | complete | 一般の座標と傾きの積−1を正しく示す。末尾のFinal Answerが763回反復しており、数学的正しさと別の出力品質問題として記録。 |
| EV02 | baseline | 3 | [P023](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:4) | complete | 一般のE,F,H,Tの座標を明示し、内積を0へ計算する。高線の説明中の括弧の誤記は計算に影響しない。 |
| EV02 | trained | 0 | [P027](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:1) | local_error | ACの切片bを2b/(2−a)へ、内積末尾−a+aを−a(2−a)+a(2−a)へ直せば完成。提示したE,F,H,Tは正しい。 |
| EV02 | trained | 1 | [P077](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:2) | complete | 一般の各点の座標と内積の相殺を正しく示す。 |
| EV02 | trained | 2 | [P070](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:3) | local_error | 内積第一項を+a(2c−a)から−a(2c−a)へ直せば、前段の正しい座標から証明が完成する。 |
| EV02 | trained | 3 | [P029](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:4) | complete | 一般座標でE,F,T,Hを明示し、内積の式から直交を確認する。 |
| EV02_hint | baseline | 0 | [P039](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:25) | core_gap | Hの座標とAMの傾きまでで、T∈HPは未計算の断言。 |
| EV02_hint | baseline | 1 | [P063](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:26) | core_gap | T∈HPを幾何的対称性からと断言。P=Tという誤記もある。 |
| EV02_hint | baseline | 2 | [P003](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:27) | core_gap | 九点円がE,F,Mを通ることからT∈HDへ、核心の推論が飛んでいる。 |
| EV02_hint | baseline | 3 | [P076](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:28) | core_gap | Tのx座標が一般に−1と誤って仮定し、傾きの式も同値でない。 |
| EV02_hint | trained | 0 | [P036](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:25) | complete | 一般のE,F,H,Tの座標を正しく示し、傾きの積−1を確認。Pは証明後に付加される。 |
| EV02_hint | trained | 1 | [P032](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:26) | core_gap | T∈HGを垂足三角形の性質と数値例への言及だけで済ませる。 |
| EV02_hint | trained | 2 | [P068](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:27) | complete | 一般のH,P,T=(1/a,0)を明示し、HPへの代入でT∈HPを示す。補助点Pは実際に論証に使うが、方法は座標。 |
| EV02_hint | trained | 3 | [P025](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:28) | complete | 一般座標でHとT=cd/(d−c)を明示し、方向ベクトルの内積で証明。Pは最後の言い換えで、幾何的補助関係は新たに使っていない。 |
| N01 | baseline | 0 | [P069](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:17) | complete | 一般座標でH=(a,(1−a²)/b)、P=(a,b)/(a²+b²)、円の係数を正しく明示。代入は直ちに0となる。末尾の余分な角度説明は用いない。 |
| N01 | baseline | 1 | [P040](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:18) | core_gap | ∠BPC=∠BHCを配置の性質と断言するだけ。 |
| N01 | baseline | 2 | [P041](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:19) | core_gap | P∈AMから∠BPC=∠BACを未証明で主張する。 |
| N01 | baseline | 3 | [P066](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:20) | core_gap | Pの座標を与えず円への代入も実行せず、角の一致を断言する。 |
| N01 | trained | 0 | [P074](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:17) | core_gap | 一般座標で確認したと主張するが実計算がなく、数値例への言及だけ。 |
| N01 | trained | 1 | [P002](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:18) | core_gap | 一般座標を置くだけでH,P、円の式の計算がない。 |
| N01 | trained | 2 | [P024](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:19) | core_gap | 核心の∠BPC=180°−∠BACを「証明可能」と述べ、数値例への言及で済ませる。 |
| N01 | trained | 3 | [P010](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:20) | core_gap | Hの座標を示すがPと円の式を計算しない。AMの式にも符号誤り。 |
| N02 | baseline | 0 | [P067](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:21) | local_error | 冒頭のABをx軸・B=(d,0),C=(c,e)を、ACをx軸・B=(d,e),C=(c,0)へ統一すると、以後の中心・T・距離式は成立する。 |
| N02 | baseline | 1 | [P034](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:22) | core_gap | 接弦定理の角を補角と取り違え、最後も正弦定理を組み合わせれば導けるとの断言で止まる。 |
| N02 | baseline | 2 | [P058](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:23) | core_gap | 円の中心は与えるが、Tの座標と距離計算が未実行で、根軸のmも未定義。 |
| N02 | baseline | 3 | [P004](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:24) | complete | 一般の二円からTの座標を明示し、AT²とBT·CTを同じ有理式へ計算する。 |
| N02 | trained | 0 | [P018](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:21) | core_gap | 円の中心・根軸までで、TとBT·CTの一般式を計算せず結論を述べる。 |
| N02 | trained | 1 | [P028](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:22) | local_error | BT²の表示b²(d²+e²)/Dをb⁴/Dに直すと、示されたTの座標、BT=b²/√D、CT=(d²+e²)/√Dと整合し証明が完成する。 |
| N02 | trained | 2 | [P008](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:23) | special_case | A=(0,0),B=(1,2),C=(2,0)の一例のみで一般化する。 |
| N02 | trained | 3 | [P060](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:24) | core_gap | 特定例から一般化し、B,C,Tが共線でないのにCA²=CT·CBなどの誤った方べきを用いる。 |
| OB01 | baseline | 0 | [P038](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:9) | special_case | A=(0,0),B=(2,0),C=(1,2)だけの確認。 |
| OB01 | baseline | 1 | [P062](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:10) | complete | 一般座標でE,F、二円の中心、Xを明示し、正しい倍率D/(2bc)でNを得る。 |
| OB01 | baseline | 2 | [P019](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:11) | core_gap | O1O2⊥ANという結論に相当する関係を「図形的関係から」と断言する。 |
| OB01 | baseline | 3 | [P055](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:12) | complete | 一般の円の中心と第二交点の正しい座標を明示し、Nとの比例関係で結ぶ。二円を解く部分は通常の代数省略。 |
| OB01 | trained | 0 | [P021](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:9) | special_case | 一つの三角形で正しく確認するが、円と垂線を保たない一般アフィン変換で一般化する。 |
| OB01 | trained | 1 | [P053](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:10) | special_case | 一つの三角形で共線性を確認しただけで一般化する。 |
| OB01 | trained | 2 | [P054](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:11) | complete | 一般の二円の方程式を導き、根軸をx=(b+c)y/dと明示して中点との共線性を示す。 |
| OB01 | trained | 3 | [P046](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:12) | complete | 一般座標で垂足・円の中心・根軸を求め、XとNの方向比を一致させる。 |
| OB01_hint | baseline | 0 | [P031](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:33) | special_case | 数値例のX,Pだけで一般化。垂心を垂直二等分線の交点とする誤りもある。 |
| OB01_hint | baseline | 1 | [P051](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:34) | core_gap | AN⊥O1O2とX=Mの両方が、計算可能という予告のみで未証明。 |
| OB01_hint | baseline | 2 | [P037](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:35) | core_gap | Nの二円への方べきが等しいという核心を数値例への言及で済ませる。 |
| OB01_hint | baseline | 3 | [P047](/home/kabatan/work/solver/qwen/.runtime/exp01/baseline_proof.jsonl:36) | core_gap | APの中点が両円に属する理由を対称性と断言するだけ。 |
| OB01_hint | trained | 0 | [P056](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:33) | special_case | X=Mという数値例への言及から一般化し、一般の関係を導かない。 |
| OB01_hint | trained | 1 | [P005](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:34) | core_gap | 根軸の式は正しい形だが座標b,c,dを定義せず、二円の中心・方程式も提示しない。核心の差し引きが追えない。 |
| OB01_hint | trained | 2 | [P071](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:35) | core_gap | 方べきが等しいことを示す必要を述べるだけで計算せず、X=Mも例への言及のみ。 |
| OB01_hint | trained | 3 | [P022](/home/kabatan/work/solver/qwen/.runtime/exp01/trained_proof.jsonl:36) | core_gap | X=Mを具体例で確認したと述べるだけで、一般の円への所属を示していない。 |
