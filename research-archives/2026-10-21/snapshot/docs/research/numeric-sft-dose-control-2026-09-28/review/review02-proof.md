# 匿名 AP01 証明レビュー（review02）

採点基準: [REVIEW_RUBRIC.md](../../related-numeric-sft-2026-09-28/REVIEW_RUBRIC.md)。匿名3答案を全文・最終版まで確認。完全証明はscore 4のみ。

## proof-00: score 1/4、complete_proof=false

正しい進展: D,E が各垂直二等分線上にあることから DA=DB, EA=EC と底角の等式を正しく得た。F=O なら P,N が直径 AF の円に乗るという条件付き最終段は正しい。

本質的欠落: 核心の F=ABC の外心 O は誤り。F は一般には AM 上になく、line 65 の ∠FAB=∠MAB は導けない。したがって FA=FB=FC も、そこからの円周結論も成立する推論ではない。

根拠: L65「$\angle FAB = \angle MAB = \alpha_1$」; L120「From these two results, $FB = FA = FC$.」; L198「the circle with diameter $AF$ passes through $P$ and $N$.」

## proof-01: score 2/4、complete_proof=false

正しい進展: A を原点、AM を x 軸とする一般座標化で D,E の位置 d=(u²+h²)/(2u), e=(v²+h²)/(2v) と F の交点 x 座標を導き、円 APN の方程式を立てた。別途、内部枝から ∠BFC=2∠A を正しく導いた。

本質的欠落: F を円方程式へ代入して0と示す核心の計算を行わず、最終段では目標と同値の「known geometric property」に置き換える。∠BFC=2A のみでは F∈(APN) は従わない。さらに line 455 の必要十分条件 ∠PFN=∠PAN=A は円周角の枝が逆で、F が内部で四点が円周上なら両角の和が180°。

根拠: L164「Now we must verify if $F(x_F, y_F)$ satisfies $x_F^2 + y_F^2 + D x_F + E y_F = 0$.」; L455「is that $\angle PFN = \angle PAN = A$」; L500「it is a geometric theorem that for this construction, $F$ lies on the circumcircle of $\triangle APN$.」

## proof-02: score 2/4、complete_proof=false

正しい進展: 冒頭の誤った ∠FBC,∠FCB の取り方を明示的に訂正し、内部枝で ∠BFC=2∠A を導く。また P,N と外心 O が直径 AO の円上にあることを正しく確認した。

本質的欠落: 結論に必要な F が直径 AO の円に乗ることを証明せず、最終版は同じ構図の結論を「known geometric property」として引用する。等脚極限から連続性だけで一般の scalene 構図への円周所属は出ない。途中の ∠PFN=A も正しい円周角枝ではなく、実際は 180°−A。

根拠: L157「$$ \angle BFC = 2\angle BAC $$」; L509「A known geometric property states that for this specific construction」; L510「By continuity and the uniqueness of the intersection for scalene triangles, $F$ must lie on $\omega$.」

境界判断: proof-01 は一般座標と円方程式まで進むが、F の代入検算を明示的に残し、最終論証で目標と同値の特殊定理を無証明引用するためscore 2。proof-02 の ∠BFC=2A も正しい中間式だが目標円への橋渡しがない。両答案の ∠PFN=A は枝が逆で、円周上なら内部点Fにおける角は180°−A。

独立検算: `A=(0,0), B=(3,2), C=(4,-2)` は鋭角不等辺で、`D=(13/6,0), E=(5/2,0), F=(16/7,2/7)` は与条件を満たし、Fの重心座標 `(16/49,20/49,13/49)` は全て正。外心 `O=(33/14,-2/7)` はFと異なる。Fは実際に円APNに乗るが、∠PANは鋭角、∠PFNは鈍角で和が180°。この例は答案中の等式・枝の反証であり、一般証明の代用ではない。

付随的誤り、確信度、読了範囲は[JSON](review02-proof.json)に記録。
