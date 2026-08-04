# DSL修正ケースの再ベンチマーク

## 実行条件

`experiment` ブランチで、修正対象だけを次の条件で再実行した。

- 10 cases（9件のDSL不備監査対象 + 同一内容のJMO-2022 MathNet alias 1件）
- seed `7`
- solver budget `180 s`
- `jobs=1`, `taskset -c 0`, `hard_timeout=true`
- 実測CPU affinity `[0]`、`one_core_enforced=true`
- raw Phase C `answer_values` と `exact_truth.jsonl` の厳密集合比較

実行結果は [`benchmark_results_180s_1core_dsl_repairs.json`](benchmark_results_180s_1core_dsl_repairs.json)、機械検証は [`validate_dsl_repairs.py`](validate_dsl_repairs.py) で再現できる。

## 結果

| case | raw Phase C値の要約 | strict exact | strict complete | 所要秒 | 判定 |
|---|---|---:|---:|---:|---|
| AIME-2006-II-09 | `19 - 3*sqrt(5)` | ✓ | ✓ | 71.46 | 修正後正答 |
| AIME-2019-I-06 | `90` | ✓ | ✓ | 73.60 | 修正後正答 |
| AIME-2022-II-07 | `192` | ✓ | ✓ | 49.26 | 修正後正答 |
| HMMT-2007-FEB-GEO-04 | `17`, `7` | ✗ | ✓ | 55.45 | 境界枝のsolver誤採用 |
| HMMT-2022-FEB-GEO-05 | `361/4` | ✓ | ✓ | 18.03 | 修正後正答 |
| HMMT-2024-FEB-GEO-10 | 正答 + 5個のdecimal-only | ✗ | ✗ | 92.62 | 近退化枝のsolver誤採用 |
| JMO-2019-MATHNET-08yk | `9*CRootOf(128*x**3 - 80*x**2 + 7*x - 1, 0)` | ✗ | ✗ | 69.80 | `AB=AC`境界枝のsolver誤採用 |
| JMO-2019-PRE-08 | 同上 | ✗ | ✗ | 69.90 | 同じ境界枝（alias） |
| JMO-2022-MATHNET-08z4 | `2*sqrt(21)` | ✓ | ✓ | 74.35 | interior/acute修正後正答 |
| JMO-2022-PRE-12 | `2*sqrt(21)` | ✓ | ✓ | 75.62 | interior/acute修正後正答 |

集計は **strict exact 6/10、strict complete 7/10**。全10件のプロセス自体は `success` で、`no_solution`、exception、timeout はなかった。

## 不一致4件の意味監査

### HMMT-2007-FEB-GEO-04

上側・下側の接線方向の単位ベクトルをそれぞれ

\[
e_1=(-12/13,5/13),\qquad e_2=(-12/13,-5/13)
\]

とし、`B=A+u e1`, `C=A+v e2` と置くと、`By>0`, `Cy<0` は `u>0`, `v>0` に対応する。`BC=7` と `BC` の接線条件から得られる解は、端点閉包の `(u,v)=(0,7),(7,0)`（答え7）と、非退化枝（`u+v=17`）である。修正DSLの `Distance(A,B)>0`, `Distance(A,C)>0`, `Area(A,B,C)>0` および `O` の反対側条件は、厳密数学上は端点枝を除く。したがってDSLの厳密解集合は `{17}` のままである。

再実行で出た `7` は、`B=A` または `C=A` に数値的に近い点（距離・面積が正だが極小）を、厳密不等式の境界としてsolverが採用したもの。DSLの意味欠落ではなく、strict guard に数値マージンを付けないsolver側の境界処理である。

### HMMT-2024-FEB-GEO-10

修正後は、四辺に対する同符号条件（`P` が各辺の同じ側）と `AssumeNoSelfIntersecting` を使い、unsigned `Area(A,B,P)>0` の誤ったinside表現を除去した。正答枝は

`B=(-3.075,3.9426355…), C=(-5.89512195…,-8.07759476…), D=(2.19512195…,-7.69294739…)`

で、perimeter は `9*sqrt(410)/5`。

一方、solverの候補台帳には

`B=(-5, 8.5e-17), C=(-10, -8.2e-17), D=(-19.38, -1.5e-15)`

（残差 `2.0e-17`）や、同様のほぼ一直線な候補が `guard_ok=true` で入っている。これは `Area(A,B,C,D)>0` が数学上は退化を除く一方、数値上の極小面積を拒否するmarginを持たないためである。余分な5値はいずれもdecimal-onlyで、正答の厳密値自体は同じ実行で得られている。ここもDSLのinside条件の欠落ではなく、solverの近退化候補採用である。

### JMO-2019-MATHNET-08yk / JMO-2019-PRE-08

修正前の `AssumeGt(cx,0)` は、問題文にない座標半平面制限で、正答枝（`C.x<0`）を排除していたため削除した。修正後DSLには問題文の `AB>AC` に対応する `AssumeGt(b,Distance(A,C))` が残っている。

再実行で出た `4.9637440886…` は、独立方程式の境界枝 `AB=AC=4.9637440886…`（三角形の底辺 `DE=1` から `BC=9`）であり、問題文の strict 条件 `AB>AC` を満たさない。正答枝は

\[
AB=(81+9\sqrt{13})/16\approx7.0906225924,
\quad AC=(81-9\sqrt{13})/16,
\quad C.x<0.
\]

したがって、削除した `cx>0` は正しく、残る `AB>AC` も意味上正しい。solverが不等式境界を有限精度で通過させた数値偽陽性であり、2つのJSONは同一問題のaliasなので同じ現象になる。

## 修正内容の要点

- AIME-2006-II-09: 内部接線の各円中心が反対側にある signed-line 条件を追加。
- AIME-2019-I-06: 問題文にない `ly>0` を削除。
- AIME-2022-II-07: 2本目の外接線を1本目のx軸反射として `Line(-m,-1,-b)` に修正。
- HMMT-2007-FEB-GEO-04: 接線ray、非退化、円が三角形外側の条件を追加。
- HMMT-2022-FEB-GEO-05: D interior を3辺の signed cross 条件で表現。
- HMMT-2024-FEB-GEO-10: P inside をunsigned面積から同符号side条件へ修正。
- JMO-2019-MATHNET-08yk / PRE-08: 不要な `cx>0` を削除。
- JMO-2022-MATHNET-08z4 / PRE-12: `AssumeAcute` と3辺の signed cross によるP interiorを追加（同一問題のMathNet aliasも同時修正）。

「答えは `a/b` のため `a+b` を答えよ」のようなpresentation変換は、今回もDSLの `answer` や厳密truthには入れていない。例えば `361/4` を `100a+b` に変換するpost-processは行わず、`presentation_answer` にだけ保持している。
