# Q39 コード対応（静的監査）

対象は `60db4b679b04167175c51c479c87c22fa663fda0`。作業ツリーの tracked `src` と `benchmarks/research_runner.py` は同版と一致。数値評価・solver import・探索・精密化・smoke test は行っていない。

指定資料には版の不足がある。手元の `codex-tasks-1023.md` は310行・Q36まで、`gpt-pro-consult-18-answer.md` は468行で「上位候補①」はない。後者の候補1は答え集合の回収の案で、今回の段間表現の案ではない。ローカルの他2参照にも指定パスはなかった。未読の設計を読んだとは扱わず、今回の依頼文をQ39の仕様とする。4基準はタスク文書の共通基準を使用する。ネットワーク利用なし。

**Aは入力文字列そのものではなく、共通のlowering後の残差ベクトル。Bは精密化の最適化ステップへ渡す書き換え。最終検証はAのまま。**

以下、`d=|P-Q|`、正規化済み直線の符号付き距離を`s`、正半径を`r`、接点を`P`、直線の単位方向を`u`とする。「全域」は、元の作図・残差Aが有限に評価できる実領域Dを指す。無効な作図まで実数全体へ延長する意味ではない。

| 命令・条件 | 前段A | 後段B／コード上の優先順位 | 全域・比較上の注意 |
|---|---|---|---|
| `Distance(P,Q)=0`（2点） | `sqrt(dx²+dy²)`、1行 | `(dx,dy)`、2行 | D全域。二乗和は同じ。重根の除去ではなくノルムの尖点・残差ベクトルの変更。点–直線には適用されない |
| `IsTangent(line,circle)=0`、接点証明なし | `abs(abs(s)-r)` | `s²-r²` | D全域、同じ零点。`B²=A²*(abs(s)+r)²`。**単なる符号除去ではない**。単位と点依存の重みも変わる |
| `IsTangent(circle,circle)=0`、共通接点証明なし | `min(abs(d-r1-r2),abs(d-abs(r1-r2)))` | 絶対値が小さい方の符号付きgap。tieは外接 | D全域だが枝境界で滑らかではない。同心・非正半径等は元predicateに戻す。共通接点版とは区別。二乗和は同じ |
| 接点が作図または別等式から証明できる `IsTangent` | 上記の距離gap | 先に接点式へ置換：線–円は `(O-P)·u`、円–円は `cross(O1-P,O2-P)/r1` | 分母の線長・半径は元作図で非零。別等式がまだ満たされない探索点でも式は評価できるが、その点でAと同値ではない。円–円版は同一円でも0になり得るため、Aの検証が必須 |
| `Distance(center,line)=radius`（接点証明あり） | 左辺−右辺 | 同じ接点内積へ置換。**zero-testより優先** | D全域。新しい独立命令族には数えない。接点で二次に消える式を一次へ戻す例 |
| 正半径を持つ特定の内接円配置 | 元の全行 | `r*g=0`から`g=0`を**追加**。元の全行を保持 | 正半径の作図域で必要条件。`g`に`1/r`は残さない。零半径の除外・単純な因子除去の対照層 |
| `OnSegment(...)=0` | 三角不等式のgap＋必要な有向面積行 | Aと同じ | 面積行はbundle作成時に追加済み。後段だけのBと数えない |
| 点–直線の`Distance(...)=0`、`OnLine`、`OnCircle`、一般角条件 | 元の各残差 | 対象helperでは変更なし | 無変更対照。Angleの片側差分は微分の方針であり別の残差Bではない |
| `IsInteger(x)=0` / `IsPrime(x)=0` | 例：整数条件は`sin(pi*x)²` | 候補近傍で選んだ整数`n`に対する`x-n` | 固定nでは全整数の零点集合を保てない。全域Bの主比較から除外。`n(x)`へ勝手に変更しない |

ソースの根拠（行番号は凍結版と同一）：

- [float_expressions.py:17](../../../src/geosolver/engine/standard/evaluation/float_expressions.py)：53bitでAを評価。[high_precision_expressions.py:84](../../../src/geosolver/engine/standard/evaluation/high_precision_expressions.py)：高精度の元残差もA。
- [mpmath_refiner.py:529](../../../src/geosolver/engine/standard/refinement/mpmath_refiner.py)：zero-test認識。[同:548](../../../src/geosolver/engine/standard/refinement/mpmath_refiner.py)：Bの全分岐。接点距離→点距離→接点接線→円間gap→線円二乗→半径補助行、の順。例外時にAへ戻る実装も記録対象。
- [tangency_contacts.py:20](../../../src/geosolver/engine/standard/problem/tangency_contacts.py)：接点の構文的証明と内積／外積式。同216行から距離＝半径の認識。
- [positive_radius_contacts.py:50](../../../src/geosolver/engine/standard/problem/positive_radius_contacts.py)：正半径の因子除去。
- [signed_tangency.py:4](../../../src/geosolver/geometry/mp/signed_tangency.py)、[mp_api.py:223](../../../src/geosolver/geometry/mp/mp_api.py)：符号付きgapと元predicateの一致・同心時の例外。[mp_core_types.py:64](../../../src/geosolver/geometry/mp/mp_core_types.py)：直線の正規化、半径の正値制約。
- [load_problem_bundle.py:49](../../../src/geosolver/engine/standard/problem/load_problem_bundle.py)、[incidence_residuals.py:53](../../../src/geosolver/problem/incidence_residuals.py)：OnSegment補助行は両段共通。
- [mpmath_refiner.py:1335](../../../src/geosolver/engine/standard/refinement/mpmath_refiner.py)：Bの呼出し。通常LM:1409、warm Newton:2007、後続closure:1726にもBが入る。LMだけを差し替える実験にはしない。
- [analytic_jacobian.py:66](../../../src/geosolver/engine/standard/refinement/analytic_jacobian.py)：接線B用の解析微分がある。Aの残差にBのJacobianを混ぜない。
- [nomad_blackbox_adapter.py:126](../../../src/geosolver/engine/standard/search/nomad_blackbox_adapter.py)：NOMAD目的値は残差ノルムの二乗＋不許容時`1e6`。hard条件のextreme barrierではない。

したがって、点距離ゼロと一般円間gapでは、同じ二乗和を同じNOMADに渡す限り、実数の厳密演算で前段の優劣は生じない。浮動小数の経路差や時間切れを、この恒等式の反例とは呼ばない。接点式・半径補助式だけの改善なら、初等的な正則化の説明が先に立つ。
