# 匿名 AP01 証明レビュー（review08）

採点基準: [REVIEW_RUBRIC.md](../../related-numeric-sft-2026-09-28/REVIEW_RUBRIC.md)。全文414行を確認。

## proof-00: score 2/4、complete_proof=false

正しい進展: D,Eの垂直二等分線からDA=DB,EA=ECと底角の等式を導き、Fが内部という枝で∠BFC=2∠BACを正しく示した。PN∥BCにより円APNで必要な∠PFA=∠PNA=Cも特定した。

本質的欠落: 核心の∠PFA=Cを与条件から導かない。最終のFormal Proofは「この構図ではFが円APN上にある」という結論同値の特殊定理を無証明で述べ、Sine Ruleを使えば導けるとだけ書く。∠BFC=2Aから目標円周条件への橋がない。

根拠: L391「\angle BFC = 180^\circ - (180^\circ - A) + A = 2A」; L397「it suffices to show that $\angle PFA = \angle PNA = C$.」; L400「A known theorem states that for the configuration described, the point $F$ lies on the circle」; L402「one can derive that $\angle PFA = C$.」

境界判断: 正しい∠BFC=2Aと必要な円周角の特定はscore2の有用な一般進展だが、目標と同値の特殊定理への置換はscore3の局所的書き落としではない。

付随的誤り、確信度、読了範囲は[JSON](review08-proof.json)に記録。
