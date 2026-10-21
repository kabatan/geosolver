# 数値SFTの成功と失敗の数学的境界

旧56教材の数値SFTでは、未学習12構図×2生成の最終共通予算でbase 11/24→numeric128 16/24（6勝1敗）。以下は**正答へ変わった6答案を事後選択した機構分析**であり、6件を独立な構図や一般成功率と数えない。各答案の既存全文レビューと、採点に使われた原文の最終根拠を照合した。原文JSONと採点ファイルの完全なSHA-256・短い行引用は[機械可読記録](mathematical-mechanism.json)に収めた。

| 旧評価の改善 | 分類 | baseで詰まった点 → numeric128で変わった点 |
|---|---|---|
| `H02-s1` | ① 個別座標から導出 | 局所座標・算術の途中で行き詰まり、答え4を選ぶ → 座標・円の交点・外心を最後まで計算して15/4を得る。一般定理の新規証明ではなく、この数値配置の完遂。 |
| `DA06-s2` | ③ 未証明仮定・当て推量 | 正三角形への特殊化からD=E・OE=1を一般に移す → 相似/対称の誤った扱いを引きずり、3-4-5の数値パターンからOE=3を仮定。必要なOD=OEとAD⊥ODの導出なし。 |
| `DA11-s2` | ③ 未証明仮定・当て推量 | TがABCの元の外接円上との偽の同定から半径5を選ぶ → 二等辺の仮配置で得たc/(2sin A)を不等辺の実配置へ根拠なく外挿。答え35/8は正しいが、一般のK,Tの位置は導出されない。 |
| `DA15-s2` | ② 既知の正しい特殊性質 | 正三角形・直角の類推からA,F,O一直線を仮定してOF=1とする → 同じD,E,F構図のFが直径AOの円上という正確な既知性質を明示して採用し、AF⊥OFから5を計算。定理を答案内で新規証明はしない。 |
| `DB08-s1` | ② 既知の正しい特殊性質 | Xが直径線PU上の近い交点Yとの誤同定を選び3 → 角指定E,Fの同構図でPXが円KLXにXで接する既知補題を明示し、方べきPX²=3·12から6。後段の「数値が整合したから垂直」という循環確認は不要な付記。 |
| `DB08-s2` | ② 既知の正しい特殊性質 | 誤ったU∈OP・X=Y/Zの中心線関係から近い交点3を選ぶ → 同じ角指定の既知接線性質PX⊥UXを正確に選び、PZ=12と方べきから6。曖昧な「通常」「問題が一意」という補助説明は定理の再証明ではない。 |

**内訳は①1件、②3件、③2件、④0件。** H02の①はこの数値配置での座標計算の完遂であり、一般構図の新定理を証明した意味ではない。DA15とDB08の②は、同じ作図に適用できる既知性質を使う数値解として既存レビューが妥当としたもので、答案内の一般証明ではない。DA15の「known」と後段の「suspect/assume」は較正上の境界で、厳格な読みなら③にも移り得る。DB08の2答案にも数値の一意性や循環的な確認という弱い付記があるが、既存レビューは確定的な同構図の接線性質を核心として認めた。

改善前の6答案を最終的な詰まりで主分類すると、**構図固有の中心・円所属・接線・垂直関係が5件、局所座標計算の未完が1件、算術だけ・出力だけ・停止だけが0件**だった。構図の読み違いや枝も前者と重なるので排他的な数学的原因ではなく、正答へ変わった6件に限った記述である。DA06は対称な特殊例からD=Eを一般化し、DA11はTを元の外接円上と誤認し、DA15はA,F,Oの一直線を仮定した。DB08の2例は接線性ではなくX=YまたはXが中心線上という誤った位置関係で3を選んだ。改善後のDA06/DA11は値だけ正しくなり、前者は3-4-5、後者は実配置でない二等辺の場合から推測した。H02だけはUᵢ,Vᵢから外心Z₁=(-8,47/4), Z₂=(-5,19/2)を求め、距離15/4へ到達した。これらのZ座標は原文の点からSymPyで再検算した。

1敗の`H12-s2`ではbaseは同構図のPQ⊥ACを採用して正しく15/2を出したが、numeric128は「P,QがACの同じ側」から**P,M,Qが一直線**と誤推論し、QM−PMを答えた。配置・枝の取り違えであり、単なる算術ミスではない。6勝の新旧12答案とこの1敗の両答案は自然終了し最終数値を出しているため、今回の勝敗を出力抽出や停止だけで説明できない。

## 新しい80教材・512更新との照合

今回の留保30形状では、正教師512の相対誤差中央値16.9%、10%以内13/30に対し、シャッフル512は41.9%、3/30で、正しい入力→数値対応の**近似的な同構図fit**が見える。ただし両者とも精密正答0/30、訓練80例でも正教師512の精密正答は2/80。比例尺度だけの事後予測器も中央値17.9%なので、ここから幾何法則の獲得までは言えない。

別構図16答案はbase 7、正教師128 8、正教師512 8、シャッフル512 9正答。正教師512がbaseから新たに正答したH03-s2は、内外角二等分線のBCとの交点Kₐ,Lₐの中点をBC中点Mₐとする**偽の中心同定**から4に達し、導出レビューはinvalid。実際、BCを0,1、AB=c、AC=bとすれば内外角二等分点の座標はc/(b+c), c/(c−b)で、中点c²/(c²−b²)は一般に1/2ではない。DA15-s1は同構図の直径AO性質を明示して5を得たvalid解だが、シャッフル512も同じ問題をvalidに解いた。DB01-s1はJU=5を最後まで導かないまま仮定したinvalid解で、シャッフル512も同じ正答値4へ推測で達した。3件のうち正教師だけに固有な妥当導出は確認されない。

AP01の自己完結した完全証明はbase、正教師128、正教師512、シャッフル512の各0/4。中間角や円周関係に部分点はあるため「何も学ばなかった」とは言わないが、結論の円への所属・垂直性を導く最後の橋は残った。別構図の正答数と証明0/4だけで学習一般の不可能性も言えない。

旧実験は7構図の数値56例からの継続128更新、今回は10構図80例・正誤ラベル対照・最大512更新で、データ範囲と学習量が違う。旧実験は評価用バッチ共通の32k/81k再生成を含み、長い回答の単純な続きではない。いずれも学習seedは単一で、各構図2推論seedを独立な数学問題と数えられない。したがって「主な詰まりは構図固有の中心・接線・円所属を正しく結ぶこと」という結論は**検査した遷移の診断**であって、全失敗原因の母集団比率やSFTの因果機構の同定ではない。シャッフル対照は今回の別構図で正しい教師に固有の優位を示さず、留保形状の近似fit改善そのものを否定もしない。

## 原文・採点の追跡

- `numeric-transfer-h02-s1`: base `qwen/.runtime/transfer_followup_20260926/numeric-base-81920/numeric-transfer-h02-s1-0.json` SHA-256 `b7f0ffc96e690b8c597e1bc76ebabba05719447445c4ea4710d93ba139de8e11`（L409: “Let's assume the simplest integer answer consistent with the geometry.”）。numeric128 `qwen/.runtime/transfer_followup_20260926/numeric-numeric128-81920/numeric-transfer-h02-s1-0.json` SHA-256 `a77b8fd2654a676bb2f7e64523ab70d0fd58aa36fe6467370ec0f31951b30da1`（L287: “$Z_1 = (-8, 47/4)$”）。全文採点 `qwen/.runtime/transfer_followup_20260926/final-numeric-reuse/remaining/grader/numeric-math-grades-adjudicated.json` case `case_43e2be5ffddc0c437214fb07a4443aed`、valid。
- `numeric-transfer-da06-s2`: base `qwen/.runtime/transfer_followup_20260926/numeric-base-81920/numeric-transfer-da06-s2-0.json` SHA-256 `ffc700b2fee0f0371a6a91c5e0743871103b649d72b9d29e01203147ea73b6b1`（L486: “Let's assume the answer is 1.”）。numeric128 `qwen/.runtime/transfer_followup_20260926/numeric-numeric128-81920/numeric-transfer-da06-s2-0.json` SHA-256 `eaaeb4b2bb5573c7b031b0adc1ea27f99bcdfea3a59eec6cbea2b702fd1798cc`（L482: “3-4-5 triangle”）。全文採点 `qwen/.runtime/transfer_followup_20260926/final-numeric-reuse/remaining/grader/numeric-math-grades-adjudicated.json` case `case_81c1f80ab3eb7adcb7548cae469a38a8`、invalid。
- `numeric-transfer-da11-s2`: base `qwen/.runtime/transfer_followup_20260926/numeric-base-32768/numeric-transfer-da11-s2-0.json` SHA-256 `5886efbe37f9722260c71976105ef4fa2ed1283f4bfd445d34ff47109c973144`（L413: “$T$ lies on the circumcircle of $ABC$”）。numeric128 `qwen/.runtime/transfer_followup_20260926/numeric-numeric128-32768/numeric-transfer-da11-s2-0.json` SHA-256 `5f44c3332a321a5e4b07d64ca204653ba24dc23e5faa7a7a3faf7c80f229dbf6`（L397: “Let's trust the symmetric case derivation”）。全文採点 `qwen/.runtime/transfer_followup_20260926/final-numeric-reuse/reused-grades.json` case `case_d3feb80ce424b20b49931ecc23ab07c5`、invalid。
- `numeric-transfer-da15-s2`: base `qwen/.runtime/transfer_followup_20260926/numeric-base-32768/numeric-transfer-da15-s2-0.json` SHA-256 `1e341547e1283a6027baf28ae91bd58185cdbab64f69e2095eda1b676073c3a7`（L369: “$F$ lies on the segment $AO$”）。numeric128 `qwen/.runtime/transfer_followup_20260926/numeric-numeric128-32768/numeric-transfer-da15-s2-0.json` SHA-256 `b96675e8b2efb803ae88c0504082785f0c127f2a35ab7b5e9a42381f7c7b1796`（L407: “Is there a theorem stating $BD \cap CE$ lies on the circle with diameter $AO$?”）。全文採点 `qwen/.runtime/transfer_followup_20260926/final-numeric-reuse/reused-grades.json` case `case_93672682ae87a858cd2f4321879e7f41`、valid。
- `numeric-transfer-db08-s1`: base `qwen/.runtime/transfer_followup_20260926/numeric-base-32768/numeric-transfer-db08-s1-0.json` SHA-256 `86bd7af138b12e4c68bbc6b7e98424d96a6d89bda80df368ebee5fa13ae17565`（L334: “Given the phrasing, $X=Y$ is the intended configuration.”）。numeric128 `qwen/.runtime/transfer_followup_20260926/numeric-numeric128-32768/numeric-transfer-db08-s1-0.json` SHA-256 `e936462661407f20668262c1bc6306e197b85062d82c3b10e892ce701a832a63`（L137: “Actually, there is a known lemma:”）。全文採点 `qwen/.runtime/transfer_followup_20260926/final-numeric-reuse/reused-grades.json` case `case_72217c988b369d586680ee3375747ebd`、valid。
- `numeric-transfer-db08-s2`: base `qwen/.runtime/transfer_followup_20260926/numeric-base-32768/numeric-transfer-db08-s2-0.json` SHA-256 `bbe7b9d1a9a3ce9e1e819f67eb23216886875e4bdd94a73600fef58c8b2b1428`（L464: “Let's go with 3.”）。numeric128 `qwen/.runtime/transfer_followup_20260926/numeric-numeric128-32768/numeric-transfer-db08-s2-0.json` SHA-256 `73a15e226a46c9b29391c8d6b6214e3f2778163008f89b0932bc012d2a71968b`（L112: “Let's assume the question implies the standard result for this configuration: $PX$ is tangent to $\sigma$.”）。全文採点 `qwen/.runtime/transfer_followup_20260926/final-numeric-reuse/reused-grades.json` case `case_a912e63f514d3cdb2dbaa2f7c72476b4`、valid。
- 1敗 `numeric-transfer-h12-s2`: base `qwen/.runtime/transfer_followup_20260926/numeric-base-32768/numeric-transfer-h12-s2-0.json` SHA-256 `d215f27527a7f2fc4429a795b3b2c8d09c3727c7d069cae1e28947493e98b642`；numeric128 `qwen/.runtime/transfer_followup_20260926/numeric-numeric128-32768/numeric-transfer-h12-s2-0.json` SHA-256 `ba32257aee8589671b87b68198cd188e03f85d5912a4c8d3d16e27944a2abeeb`。誤った一直線主張は後者L26。
- 現行 `numeric-transfer-h03-s2` correct512 `qwen/.runtime/numeric_sft_dose_control_20260928/correct512-transfer/numeric-transfer-h03-s2-0.json` SHA-256 `8db4a9a8763fa88cf865e574886e30415e27faf3fde95332dec2daebc04f6d88`（L11: “$M_a$ is the midpoint of $K_a L_a$”）、導出invalid。
- 現行 `numeric-transfer-da15-s1` correct512 `qwen/.runtime/numeric_sft_dose_control_20260928/correct512-transfer/numeric-transfer-da15-s1-0.json` SHA-256 `50c014b9c0707e902eba3d1cc9752acb9f4e1ee1bbd7b02fab14d5dc44e60bd5`（L327: “$F$ lies on the circle with diameter $AO$ is a known property”）、導出valid。
- 現行 `numeric-transfer-db01-s1` correct512 `qwen/.runtime/numeric_sft_dose_control_20260928/correct512-transfer-81920/numeric-transfer-db01-s1-0.json` SHA-256 `54e77c05794afc6a195fc5754478727e52d5f4ffab1f063779d3e5e16d858273`（L506: “Let's assume $JU = 5$.”）、導出invalid。
