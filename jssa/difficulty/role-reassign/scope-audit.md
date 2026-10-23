# 既存の接条件変換と今回の介入範囲

凍結署名は `sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5`。以下はソースと全323入力を読み取った監査である。

| 段階 | 凍結版での扱い | 今回のR |
|---|---|---|
| 入力の読込み | construction contract、incidence、logical equalityをlowering | 同一 |
| NOMAD、その他の大域探索 | 元の評価器、hard判定 | 同一 |
| scipyの局所LM/Powell/有界TRFの拡大残差 | 元等式行＋guard行＋hard行。非許容のhard行は10,000 | hard行だけ0。対象の接条件行を既存の接触式へ変更 |
| 局所探索の候補受入れ | 元の残差、箱、guard、hardによる判定 | 同一 |
| 高精度精密化の通常stage | `_residual_vector_for_stage(...smooth_zero_constraints=True)` から既存変換 | 元関数へそのまま委譲。呼出数のみ記録 |
| 高精度Newton closure | 通常closure、warm Newtonでも既存変換。整数closureがあると優先され、接条件平滑化を通らない経路もある | 同一 |
| 最終数値検証 | `verification_numerics._smooth_zero_equation` にも `_SignedTangency` 等の処理がある。元の条件・定義域を使う既定の検証手順 | 全て同一 |

既存実装の根拠は `src/geosolver/engine/standard/search/scipy_multistart_backend.py` の `_evaluate_augmented_residual_vector`、`refinement/mpmath_refiner.py` の `_zero_constraint_plans`、`_smooth_zero_constraint_residuals`、`_residual_vector_for_stage` と各呼出箇所、および `evaluation/verification_numerics.py` の `_smooth_zero_equation`。ソースはいずれも編集していない。

「凍結版は接条件を全く符号付きにしていない」ではない。今回追加したのは、既存の高精度用規則の一部を、別の局所探索段階へ適用することだけである。

入力規則に該当するのは26/323問。うち24問は変数あり、2問（HMMT-2011-two-circles-tangent-line、HMMT-2019-FEB-GEO-07）は変数なし。行番号と変換式は[manifest.json](manifest.json)に全保存した。共有接点を使う10問を含むが、AIME-2015-II-15のように該当式が探索変数に依存しない例もあり、適用可能というだけで改善を予告したことにはならない。

一般のIsTangentの近い枝を選ぶ処理は大域的に滑らかとは限らない。直線–円の二乗距離差は尺度も変える。共有接点の式は他の入射等式が成立する集合上での必要式／同値式であり、入射を満たさない探索途中で元の残差値と同値ではない。Q4で区別された重複度・非平滑性・尺度の効果を一つの原因へまとめない。

最終判定を緩和した数値合格は数えない。B/Rで同じcanonical answer keyの**答え集合一致**を採点し、元評価器・hard関数群の同一性、実行契約、実際のhardバイパス・接条件適用を各子プロセスの監査ログで確認する。使用経路がなければ0回として残す。
