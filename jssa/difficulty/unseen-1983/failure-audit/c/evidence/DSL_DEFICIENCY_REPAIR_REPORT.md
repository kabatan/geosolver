# 残存DSL不備の修正監査

## 対象

残り35件の失敗監査で、問題文の条件そのものが現行JSONに欠けていた3つの幾何を修正した。
既に `a705bb14` で修正済みの HMMT-2024-FEB-GEO-10（Pの内部条件）、JMO-2019-MATHNET-08yk / JMO-2019-PRE-08（問題文にない `cx>0` の過制約）は変更していない。

## 修正内容

### HMMT-2007-FEB-GEO-04

旧DSLは `IsTangent(Line(A,B),omega)` と `IsTangent(Line(A,C),omega)` だけで、接線上の無限直線を表していた。そのため、問題文の「Aから出る二本の接線上（各一本）」というray条件を表せず、`omega` が三角形の外側であることも座標符号に依存していた。

固定ゲージ `O=(0,0), A=(13,0)` では、上・下の接線rayの単位方向は厳密に

\[
e_+=(-12/13,5/13),\qquad e_-=(-12/13,-5/13).
\]

そこで

\[
B=A+u e_+,\qquad C=A+v e_-,\qquad u>0, v>0
\]

と構成した。これは接線ray条件と同値で、自由変数を `(Bx,By,Cx,Cy)` の4個から `(u,v)` の2個へ減らすだけである。さらに `BC` に対して `A` と `O` が反対側にあることを
`cross(BC,BO)*cross(BC,BA)<0` として明示し、円が三角形の外側という条件を保持した。

### HMMT-2021-FEB-GEO-05

旧DSLの `Area(A,E,C)>0` などはruntimeの `Area` が shoelace の絶対値を返すため、Cが三角形の外側でも正になっていた。
`A=(0,0), E=(10,√341), F=(-10,√341)` は反時計回りなので、Cが三角形 `AEF` の内部であることを、次の3つの符号付き条件へ置換した。

```text
Vector(A,E).cross(Vector(A,C)) > 0
Vector(E,F).cross(Vector(E,C)) > 0
Vector(F,A).cross(Vector(F,C)) > 0
```

独立検算で得られた旧DSLの外側枝 `C≈(1.015267,0.267830)` は第一crossが負となり除外され、内部枝 `C≈(0.566913,7.328104)` は3条件すべて正となる。

### HMMT-2013-FEB-GEO-04

旧DSLには、直線 `O1O2` と `omega2` の交点 B が中心 `O1` と一致しないという非退化条件がなかった。実際、

```text
r1=r2=1, O1=(0,0), O2=(1,0),
A=(1/2,√3/2), B=O1
```

は旧DSLの全等式と `AB=O1A` を満たし、比 `r1/r2=1` を生成する。公式の厳密解集合が黄金比の2値だけであることに合わせ、異なる名前の点は一致しないという通常の非退化解釈を `AssumeNe(Distance(B,O1),0)` として明示した。座標半平面など問題文にない枝制限は追加していない。

## 検証

JSON/IR・source provenance・変数上限の全体監査はエラーなしだった。

```text
verify_dsl_integrity.py:
  dsl_files=302, runnable_files=285, reference_only_files=17,
  truth_rows=302, truth_verified=205, errors=0
validate_dataset.py:
  all_records=548, unique_scope=296,
  current_solver_scope_unique=279, benchmark_runs=302
```

修正3件は seed=7、`180 s` hard timeout、`jobs=1`、CPU affinity `[0]` で再実行した。raw Phase C と厳密truthの結果は次の通り。

| case | strict truth | raw Phase C | strict exact | 備考 |
|---|---|---|---:|---|
| HMMT-2007-FEB-GEO-04 | `{17}` | `{17, 7}` | no | `7` は `u=0`/`v=0` 開条件の数値境界漏れ。正しい `17` は取得済み。 |
| HMMT-2013-FEB-GEO-04 | `{(√5−1)/2, (√5+1)/2}` | `{(√5−1)/2, 1, (√5+1)/2}` | no | `1` は `B=O1` の不許可境界をsolverが数値的に通した枝。 |
| HMMT-2021-FEB-GEO-05 | `{49/400}` | `{49/400}` | yes | 旧外側枝 `1/400` はDSLから除去。 |

raw結果のJSONは [`benchmark_results_180s_1core_remaining_dsl_fixes.json`](benchmark_results_180s_1core_remaining_dsl_fixes.json) に保存した。

HMMT-2007の `7` とHMMT-2013の `1` を除くために `u>ε` や `Distance(B,O1)>ε` のような任意の数値marginをDSLへ追加することは、問題文の厳密な開条件を別の問題へ変えるため行っていない。したがって、今回残った2件のstrict不一致はDSL定義ではなくsolverの境界候補受理である。
