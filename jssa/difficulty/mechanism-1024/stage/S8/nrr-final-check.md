# 7b の NO_RESIDUAL_REWRITE と最終検証

結論：7b で実際に使われた final（BASE1）では、NO_RESIDUAL_REWRITE は最終検証の接条件・点と直線の距離0の変換を止めない。精密化側の残差書き換えと、それに依存する解析 Jacobian 計画の採用だけを止める。

`inventory/switches-priority.md` は実装前の提案であり、最終検証も止めるという記述は実装の説明としては不正確。S8 は事前登録15に従い最終検証を凍結版のまま使い、パッチを変更しない。

比較対象 BASE0：`60db4b679b04167175c51c479c87c22fa663fda0`（git show から直接取得）。BASE1：`/tmp/mechanism-7b-lkdjle5l/final/src/geosolver/`。

| ファイル | BASE0 / BASE1 共通 SHA-256 | バイト一致 |
|---|---|---|
| verification_numerics.py | `e781e0e5a0318e0941e596294c51b80ed6e6c2f2f24d6fc3607a039c8390b67f` | yes |
| final_verifier.py | `64351d787c7ffcb2637d95b3e8d6a2e7077e5d9d9a222e965a80be6751366e3a` | yes |

`engine/standard/evaluation/` の全 25 Python ファイルを本文検索し、`ablated` の参照は0件。比較手順と機械可読証拠は `nrr-final-check.json`。

残る変換は verification_numerics.py の `_smooth_zero_equation` 内の IsTangent と Distance(P, Line)=0 分岐（論理式の葉も同じ関数を経由）。final_verifier.py の補正・閾値も同一。精密化側の停止は mpmath_refiner.py:1035,1356、解析微分全体の停止は analytic_jacobian.py:163 を別途参照。
