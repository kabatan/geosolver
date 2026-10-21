# 匿名 AP01 証明レビュー（review07）

採点基準: [REVIEW_RUBRIC.md](../../related-numeric-sft-2026-09-28/REVIEW_RUBRIC.md)。全文592行を確認。

## proof-00: score 2/4、complete_proof=false

正しい進展: D,Eの等距離性とF内部の枝から∠BFC=2∠BACを導く。鋭角ABCで外心Oも内部にあるためB,C,F,Oが同一円上にあること、またAB,ACの中点P,NによりA,P,O,Nが直径AOの円上にあることを正しく把握した。

本質的欠落: これら二つの円の関係からFが直径AOの円に乗るという核心を導いていない。途中の∠OFB=∠OCBは円周角の枝を誤り、正しい構図例でも前者は鈍角、後者は鋭角。最終の「詳細な角追いで∠AFO=90°を確認した」は実際には無証明の断言。さらに∠AFO=90°からOF⊥AOとする記述は誤りで、正しくはOF⊥AF。

根拠: L97「So, $\angle BFC = 2\angle BAC$.」; L184「$\angle OFB = \angle OCB$」; L236「$A, P, O, N$ are concyclic on a circle with diameter $AO$.」; L542「It implies $OF \perp AO$.」; L589「Detailed angle analysis confirms that $F$ also satisfies $\angle AFO = 90^\circ$」

境界判断: B,C,F,OとA,P,O,Nについて別々の円周関係を得た点は有用な一般進展でscore 2。ただしFが後者の円にも乗ることを導く核心は欠けており、単なる代数数行の省略ではない。

独立検算: 鋭角不等辺でF内部の例 `A=(0,0), B=(3,2), C=(4,-2)` では `F=(16/7,2/7), O=(33/14,-2/7)`。B,C,F,Oは共円だが、`(O−F)·(B−F)=−13/14<0` に対し `(O−C)·(B−C)=17/2>0` なのでL184の角の一致は偽。また `(O−F)·(O−A)=65/196≠0` でL542のOF⊥AOも偽。

読了範囲、付随的誤り、確信度を[JSON](review07-proof.json)に記録。
