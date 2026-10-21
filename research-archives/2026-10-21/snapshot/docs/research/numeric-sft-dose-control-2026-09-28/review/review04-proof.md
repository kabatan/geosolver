# 匿名 AP01 証明レビュー（review04）

採点基準: [REVIEW_RUBRIC.md](../../related-numeric-sft-2026-09-28/REVIEW_RUBRIC.md)。匿名3答案を全文と最終段まで確認。完全証明はscore 4のみ。

## proof-00: score 2/4、complete_proof=false

正しい進展: DA=DB, EA=EC から角を追い、F が内部にある枝では ∠BFC=2∠BAC を正しく導いた。円 APN の必要な角条件 ∠PFA=∠PNA=C も特定した。

本質的欠落: ∠PFA=C を与条件から導いていない。最終段は「既知の結果」として F∈(APN) そのものを主張し、∠BFC=2A と中点線 PN∥BC だけで円周条件になると断言する。途中の等脚極限の「反例」は垂直二等分線の傾きを誤っており採用できないが、最終論証の穴は残る。

根拠: L75「Thus, $\angle BFC = 2\angle BAC$.」; L485「(a known result in Euclidean geometry concerning the median and perpendicular bisectors)」; L489「one can show $\angle PFA = \angle PNA = C$」

## proof-01: score 1/4、complete_proof=false

正しい進展: DA=DB, EA=EC、底角の一致、および内部枝で ∠BFC=2∠BAC を正しく計算した。もし F が外心なら P,N が直径 AF の円に乗るという条件付き後半は正しい。

本質的欠落: 結論を支える F=外心という主張は誤り。line 154 と171で F が AM 上にあると扱い、∠BAF=∠BAM としているが、与条件は D,E が AM 上というだけで F は一般にそこにない。したがって FA=FB=FC と FP⊥AB, FN⊥AC は証明されない。

根拠: L142「$\angle BFC = 180^\circ - (180^\circ - \alpha - \alpha) = 2\alpha$.」; L171「$F$ lies on $AM$」; L241「the points $P$ and $N$ both lie on the circle with diameter $FA$.」

## proof-02: score 2/4、complete_proof=false

正しい進展: 内部枝で ∠BFC=2∠A を正しく導き、円周条件 ∠PFN=180°−A の正しい枝を特定した。D,E の等距離性と中点線 PN∥BC も正しい。

本質的欠落: 最後に必要な ∠PFN=180°−A を示していない。さらにその代用となる三角比 sinδ cosβ=sinε cosγ は BM=AB/2、CM=AC/2 という誤った長さから導かれた偽の等式であり、これが円周条件と同値だという説明もない。

根拠: L248「$\angle PFN + \angle PAN = 180$.」; L263「$BM = c/2$.」; L348「the geometric configuration satisfies the necessary and sufficient condition for $F$ to lie on the circumcircle」

境界判断: proof-00とproof-02は正しい∠BFC=2Aと円周条件の特定まで進むためscore 2だが、その条件への橋渡しはない。proof-01のF=外心は一般に偽なのでscore 1。score 3/4はない。

独立検算: `A=(0,0), B=(3,2), C=(4,-2)` は鋭角不等辺で、`D=(13/6,0), E=(5/2,0), F=(16/7,2/7)` は与条件を満たしFは内部。外心 `O=(33/14,-2/7)` はFと異なる。proof-02のBMは正しくは`√17/2`で、提示された三角比の両辺は約`0.453421`と`0.406299`で一致しない。この例は答案の等式検証であり一般証明の代用ではない。

付随的誤り、確信度、読了範囲は[JSON](review04-proof.json)に記録。
