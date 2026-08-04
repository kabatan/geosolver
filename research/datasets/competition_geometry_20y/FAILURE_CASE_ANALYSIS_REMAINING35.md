# 残り35件の失敗原因分析

## 対象と判定方法

対象は、`benchmark_results_180s_1core_after_refiner_fix_failed66.json` のうち
`answer_set_exact=false` だった35件である。判定は表示用のAIME/HMMT/JMO回答や
post-processではなく、Phase Cの `answer_values` と `exact_truth.jsonl` の厳密解集合を
比較した。

根拠は次の4層を突合した。

1. 今回の再実行JSON（status、raw Phase C、rejection tags、wall time）。
2. 旧監査のDSL/source clause ledgerと独立検算。
3. 各DSLのconstruction/constraint/guard。
4. runtimeの実装。

runtime上、Phase Cは `residual < 1e-15`、`hard_feasible`、validity margin、statusを
通過した候補だけを採用する。一方、exact identificationに失敗した候補は
`str(candidate.answer_hp)` にフォールバックするため、厳密式ではなくdecimalが
`answer_values` に入る（`run_phasec_assembly.py:135-144`）。厳密採点はdecimal-onlyを
解とは認めない。さらにguard比較にはdps依存の数値許容幅があり、厳密な開条件の境界へ
収束した候補を数値的に通してしまうことがある。`Area` はshoelaceの絶対値
（`Abs(s)/2`）なので、`Area>0` はinsideや向きを表さない。

## 全体像

| 分類 | 件数 | 主因 |
|---|---:|---|
| decimal-only exactification failure | 10 | solverのexact identification/serialization |
| strict境界・退化枝の混入 | 12 | solverのguard margin/branch filtering |
| DSL/source条件の欠落または過制約 | 5 underlying geometries（6 files） | DSL（うちsolver結果も汚染したものあり） |
| feasibleなのにno_solution | 3 | solverの探索・精密化 |
| timeout | 4 | solverの探索・closure（1件はDSL欠落も併存） |
| exact target未到達の数値枝 | 1 | solverの探索・精密化 |

分類が重なるケース（HMMT-2007-FEB-GEO-04、HMMT-2024-FEB-GEO-10、JMO-2019の2別名）は、
DSLとsolverを別々に記載した。

## 1. decimal-only exactification failure（10件、solver）

いずれもraw値は正解の高精度近似だが、symbolic exact valueが一つも出ていない。
DSLは旧監査でsource-faithfulと確認され、余計な枝も採用されていない。したがって
失敗は「幾何方程式を解けなかった」のではなく、exactifierが式を同定できずdecimal
fallbackしたことが原因である。

| case | 厳密正解 | 今回のraw値の状態 | 証拠 |
|---|---|---|---|
| `AIME-2009-I-05` | `72` | `71.999…` のみ、`residual_too_large` | `Distance(L,P)` は正解近傍だがexact式なし |
| `AIME-2015-II-11` | `18/5` | `3.599…` のみ | sourceの幾何量は `BP=18/5`。`m+n` ではなくraw幾何量を採点している |
| `AIME-2016-I-06` | `10/3` | `3.333…` のみ | `Distance(I,C)` が正解近傍、exact式なし |
| `AIME-2022-II-11` | `180` | `179.999…` のみ、`residual_too_large` | `Area(A,B,C,D)**2` の整数解をdecimalで出力 |
| `HMMT-2006-FEB-GEO-03` | `31` | `31.000…001` のみ | exact targetに対応する数値だがsymbolic化なし |
| `HMMT-2006-FEB-GEO-04` | `27*pi/40` | `2.120575…` のみ | `pi`を含む正解でも数値fallback |
| `HMMT-2008-FEB-GEO-03` | `pi-2` | `1.141592…` のみ、`branch_instability` | 余計な枝ではなく、π式のexactification失敗 |
| `HMMT-2010-FEB-GEO-01` | `3*pi/7` | `1.346396…` のみ | 固定star角の数値化後に式を復元できていない |
| `HMMT-2013-FEB-GEO-05` | `-1/8` | `-0.125…` のみ | `cos(Angle(A,O,D))` が有理数になった後もdecimal |
| `HMMT-2023-FEB-GEO-01` | `189` | `188.999…` のみ、`residual_too_large` | 正六角形面積の整数解をdecimal fallback |

共通する直接原因は、PSLQ/SymPy exactificationが `selected_exact_value` を返さず、
Phase Cが数値文字列へfallbackすること。近いから整数/分数へ丸めてよい、という問題ではない。

## 2. strict境界・退化枝の混入（solver中心）

### `AIME-2011-II-02` — 450枝とsourceの非退化解釈

- 出力: exact `810` と、`450.000…` のdecimal。
- 旧診断では余分な450枝は `E=D`, `F=B` のendpoint枝。
- 現行DSLは `0<t<s`, `0<u<s` を要求しているため、意図された「内部点」解では450は不許可。
- しかし公式source本文は「E lies on side AD」「F lies on side BC」で、`strictly between`とは書かれていない。
  文字通りendpointを許すなら、`s=15*sqrt(2)`, `E=D`, `F=B` で
  `BE=EF=FD=30`、面積450が成立する。

したがって、現在のDSLの意味ではsolverのstrict-guard leakageだが、sourceを完全に
字義通りに扱うなら、450を除外している `exact_truth`/strict-interior解釈にも問題がある。
ここはsolverだけのバグと断定せず、非退化点をsource clauseとして明示するかを決める必要がある。

### `AIME-2014-II-08` — `e -> 0` の半径退化

- 出力: exact `-14+4*sqrt(15)` と `1.15e-42` 程度のdecimal。
- DSLは `e>0`, `3e<2`。
- 余分な値は `e=0`（D/Eの半径が0になる境界）の数値近似で、exact zeroがdecimal化したもの。
- sourceの円は正の半径なので退化枝は不許可。

DSL/sourceの条件は存在するため、主因はsolverのguard marginと境界候補のPhase C採用。

### `AIME-2018-I-04` — D/E endpoint枝

- 出力: exact `250/39` と `9.999…`。
- sourceはD,Eが明示的に「strictly between」なのでendpointは不許可。
- `AD=DE=EC=10` の枝は `D=B`, `E=A` で成立するendpoint退化。
- DSLにも `0<dx<10`, `0<ey<48/5` と `OnSegment` がある。

したがってDSLの意味欠落ではなく、solverが開区間の境界を採用したもの。

### `AIME-2020-I-01` — target枝と60枝の混在

- 出力: exact `540/7` と、60に非常に近いdecimal。
- sourceはD,Eをstrictly interiorに置く。
- 旧独立診断では全変数がほぼ0へ寄る候補が `guard_ok=true` と記録され、正規枝とは別の
  numerical boundary/branch contaminationが再現された。
- 子プロセスartifactには候補と60の完全な対応が残らないため、60がどの一候補かまでは断定しない。

target枝は見つかっているので、DSL全体の不可能性ではなく、無効枝のcandidate validity filteringが主因。

### `HMMT-2006-FEB-GEO-10` — 半径0枝

- 出力: `1.65e-57` 程度、正解24なし。
- DSLは `0<r<33`。
- 独立runtime診断で `r≈3.3e-9`, residual≈`1.2e-9` の候補がguard_okとして残り、
  Phase Cでは半径0の値へ収束した。

円の正半径条件はsourceにもDSLにもあるため、solverの境界受理が原因。

### `HMMT-2010-FEB-GEO-09` — 凸四角形の180度境界

- 出力集合: `{70,160,180}`、正解集合 `{70,160}`。
- source/DSLともconvex quadrilateralを要求する。
- 180は凸四角形の厳密な内角ではなく、ほぼ一直線の退化枝。
- 数値候補がexact `180`へ昇格され、strict convexityで落とされなかった。

### `HMMT-2014-FEB-GEO-09` — `r4=0` 境界

- 出力: exact `92/61` と `0`に極めて近いdecimal。
- DSLは `r4>0`, `y4>0`。
- 余分な0は第四円の半径0境界で、正半径の円というsource条件に反する。

### `HMMT-2014-FEB-GEO-10` — `r1,t -> 0` の二重退化

- 出力: `11.4351807…` と `16.124515…`。正解 `1235/108=11.435185…` は厳密式でない。
- 旧診断では `r1≈0`, `t≈0` の候補がguard_okで、余分な `2*sqrt(65)` 枝を再現。
- DSLは `r1>0`, `r2>0`, `t>0`。sourceでも円の正半径とTの非退化が必要。

主因は、正解枝の精密化不足と、二つの開条件へ同時に近づく枝の採用。

### `HMMT-2018-FEB-GEO-05` — 面積0境界

- 出力: exact `8*sqrt(2)/9` と `0`に近いdecimal。
- DSLは `0<theta<pi` と `Area(M,A,R,E)>0`。
- 余分な0はR/Eが退化して四辺形面積が0に近づく枝。
- sourceは四点からなるinscribed quadrilateralなので退化は不許可。

### `HMMT-2023-FEB-GEO-02` — A=B (`u=0`) endpoint

- 出力: `0` と `2*sqrt(13)`。
- DSLは `u>0` とA,BのOnSegment。
- 0枝はA=Bとなるsegment endpoint/一致点で、ABを正の長さとして求めるsourceの意図に反する。
- current DSLのstrict guardをsolverが数値的に通した枝である。

source本文は「A,B lie on segment XY」とのみ書かれているため、A=Bを文字通り許すかは
AIME-2011-II-02と同じ非退化点の暗黙性を含む。ただし公式正解が正の値であることから、
現行truth ledgerは非退化解釈を採用している。

### `HMMT-2023-FEB-GEO-04` — P=Q (`q=p`) endpoint

- 出力: exact `1` と `sqrt(5)`。
- sourceに `AP<AQ` が明記され、DSLにも `q>p` がある。
- exact 1はP=Qの一致点で、`AP=AQ` となり明示的に不許可。

これはsourceの曖昧性ではなく、solverのstrict inequality境界漏れ。

### `HMMT-2024-FEB-GEO-03` — 直径枝 (`h=0`)

- 出力: exact `42` と `246`。
- sourceはchordがdiameterではないと明記し、DSLも `AssumeNe(h,0)` を持つ。
- 246はh=0の直径長 `2*123`。明示的な非直径条件を数値境界で通した枝である。

## 3. DSL/source条件の欠落・過制約

### `HMMT-2007-FEB-GEO-04` — tangent rayとcircle-outside条件の欠落 + timeout

sourceは、(i) B,CがAからの二本の**接線ray**上、(ii) `omega`がtriangle ABCの外側、を要求する。
DSLは `IsTangent(Line(A,B),omega)` 等の「直線接線」しか置かず、
`By>0`, `Cy<0`, unsigned `Area(A,B,C)>0` だけである。
従って、B/Cが実際のray上にない接線直線配置と、円が三角形内にある配置を排除できない。

修正後の再実行はPhase Cなしの180秒timeoutになった。つまり今回の直接のstatusは探索時間切れだが、
元のDSLが過少制約で枝を増やしており、`17`と`7`の余分枝を生んだ根本原因はDSLである。

### `HMMT-2013-FEB-GEO-04` — ratio 1はDSL/strict truthの非退化問題

sourceは `O2` が `omega1` 上、Aが二円の交点、Bが直線 `O1O2` と `omega2` の交点、
`AB=O1A` とする。DSLには `B != O1` がない。

具体的に `r1=r2=1`, `O1=(0,0)`, `O2=(1,0)`,
`A=(1/2,sqrt(3)/2)`, `B=O1=(0,0)` と置くと、
`O2` はomega1上、Bはomega2と直線O1O2の交点、`AB=O1A=1` が成立し、
`r1/r2=1` となる。DSLの `Distance(A,B)!=0` も満たす。

したがって、現在のstrict truth `{(sqrt(5)-1)/2,(sqrt(5)+1)/2}` が1を除くには、
「BはO1とは異なる交点」などの非退化 clauseをDSL/sourceに明記する必要がある。これは
solverだけの誤枝と断定できず、DSL/target ledgerの不備またはsourceの暗黙的distinctnessである。

### `HMMT-2021-FEB-GEO-05` — C inside条件がunsigned Areaで失われている

sourceはCがtriangle AEFのinteriorにあると明記する。DSLは
`Area(A,E,C)>0`, `Area(E,F,C)>0`, `Area(F,A,C)>0` を置いているが、runtimeのAreaは
`Abs(shoelace)/2` なので、非共線なら外側のCでも全て正になる。

独立数値解で次の二枝を再現した。

- target枝: `t≈0.30868935`, `C≈(0.566913,7.328104)`, Cはtriangle AEF内、面積比 `49/400`。
- extra枝: `t≈0.17236846`, `C≈(1.015267,0.267830)`, barycentric coordinates
  `(0.058015,-0.043511)` でCは外側、面積比 `1/400`。

よって今回の余分な `1/400` はsolverが勝手に作った解ではなく、inside条件を表現していないDSLが
許した枝である。solver側はそのDSL解集合を忠実に列挙しただけで、strict truthとDSLが不一致。

### `HMMT-2024-FEB-GEO-10` — P inside条件がunsigned Areaで失われている（DSL+solver）

sourceはPがquadrilateral ABCDの内部にあることを要求する。DSLは各三角形の
`Area(A,B,P)>0` 等と `AssumeNoSelfIntersecting` を置くが、Areaがunsignedなので
同符号のside-of-edge条件になっていない。self-intersectionを禁止しても、Pが外側の
単純四辺形は残る。

再実行出力は `30`に極めて近いdecimal、target近傍を含む他のdecimal枝、target
`9*sqrt(410)/5` の混在（旧監査ではこの30枝がexactとして出た）。
旧独立診断でも、outside/near-collinear候補が `guard_ok=true` と再現されている。
従って、DSLのinside表現欠落が枝を作り、solverのnear-degenerate candidate filtering不足が
それをPhase Cへ通している。

### `JMO-2019-MATHNET-08yk` / `JMO-2019-PRE-08` — cx>0過制約 + 別枝採用

sourceの `AB>AC` を満たす正しい構成は
`AB=(81+9*sqrt(13))/16≈7.0906225924`, `AC≈3.03437741`,
`angle A=2*pi/3`, `DE=DI=EI=1` である。この座標ゲージでは
`C_x=(-81+9*sqrt(13))/32<0`。

両DSLが `AssumeGt(cx,0)` を追加しているため、source-faithfulな正解枝を最初から除外している。
今回のsolverはno_solutionではなく、両aliasで同じ
`9*CRootOf(128*x**3-80*x**2+7*x-1,0)≈4.9637440886` を返したが、これはtruthの
`7.0906225924` ではない。したがって主因はDSL過制約であり、solverはその残った枝を
選んでしまった二次的問題である。

## 4. DSLは実行可能だが探索が解を拾えない（3件）

### `AIME-2018-II-12`

20候補が全て `residual_too_large` で棄却された。しかし独立witness
`C=(1.6,11.2)`, `D=(-8,14)`, `P=(1,7)` は、4辺長残差0、面積等式残差0、
凸性turn `[112,84,112,140]`、面積112を満たす。DSLは実行可能で、solverの探索/精密化失敗。

### `AIME-2020-II-15`

独立witness `A≈(3.92145098,25.04529231)`、`T`、`X`、`Y` で
`BT=CT≈16`, `XY^2≈717`, 与式の和≈1143、三角形のacute/scalene dot productsは
`521.64,328.27,155.73>0`。DSLはsource条件を満たす。今回statusはno_solution、
候補は `residual_too_large` で棄却され、solverの探索/精密化が原因。

### `AIME-2021-I-13`

独立witnessは `d=672`, `r=1000`, `A≈(732.5,622.0649)`,
`O≈(1232.5,1525.2753)`。外接接線距離は1961/1625、AB上の弦の中心角は120°。
DSLは実行可能だが、今回 `answer_missing`/`residual_non_finite` でno_solution。
solverの枝探索または非有限候補処理の失敗であり、DSL不可能性ではない。

## 5. timeout（4件）

### `AIME-2020-II-13`

5変数（半径と5接触角）の接線pentagonで、180.106秒でhard timeout、Phase Cなし。
DSLの変数・constructionから探索空間が大きく、artifactだけでは内部のどのsubstageが時間を
消費したか特定できない。少なくとも「解なし」とは言えず、solverの探索予算不足/収束失敗である。

### `HMMT-2007-FEB-GEO-04`

DSL過少制約による枝増加も併存する。上記のray/outside条件欠落が探索空間を広げ、今回の
再実行ではPhase Cに到達する前に180秒を使い切った。

### `JMO-2013-PRE-08`

修正前はPhase Bのmpmath `findroot -> LU_decomp` で `TypeError("'>=' not supported ... NoneType ...")`
が発生した。修正後は例外が漏れずに済んだが、同じcaseは180.105秒でtimeoutとなり、
Phase Cは空。つまり「クラッシュ」は直った一方、closureが失敗した候補を早期に切り上げて
別の探索へ移る仕組みがなく、solverは時間だけを消費している。DSLの解集合欠落ではない。

### `JMO-2015-PRE-11`

3変数とcircumcircle上の3 arc-midpoint、3面積制約で、180.106秒、Phase Cなし。
source/DSLの対応に既知の意味欠落はなく、独立artifactにも実行不能証拠はない。
今回の証拠から断定できるのは、solverの探索/arc midpoint評価/精密化のいずれかが
180秒内に候補を返せなかったことまでで、内部substageは未確定である。

## 6. exact target枝に到達しない数値探索（1件）

### `HMMT-2015-FEB-GEO-04`

raw Phase Cは `0.4953925…` から `0.7296142…` まで9個のdecimalだけで、
正解 `37/76≈0.4868421053` のsymbolic valueはない。tagsは
`residual_too_large` と `answer_missing`。

DSLが実行可能であることは独立witnessで確認できる。

`B=(0,0)`, `C=(2,0)`, `A=(-3/4,3*sqrt(15)/4)`,
`D=(49/16,7*sqrt(15)/16)` は、AB=3, BC=2, CD=2, DA=4、cyclicを満たし、
足から作る面積比は厳密に `37/76` になる。

従って「DSLが解を持たない」のではなく、solverが正解 basinを拾えず、近似枝だけを
返したケースである。ただしartifactからは、初期値探索・cyclic制約の精密化・exactificationの
どれが最初の失敗点かまでは分離できない。

## 結論

残り35件は一種類の問題ではない。

- 10件は、正解近傍まで解けているのにexactifierがdecimal fallbackするsolver問題。
- 退化・strict boundary枝は、solverのguard margin/候補受理が主因だが、AIME-2011-II-02と
  HMMT-2013-FEB-GEO-04はsourceの暗黙的distinctnessをDSL/truthに明記すべきである。
- HMMT-2007-FEB-GEO-04、HMMT-2021-FEB-GEO-05、HMMT-2024-FEB-GEO-10、JMO-2019の2別名は、
  問題文のinside/ray/向き条件をDSLが表現していないことが主因。
- AIME-2018-II-12、AIME-2020-II-15、AIME-2021-I-13、HMMT-2015-FEB-GEO-04は、
  独立witnessがあるためsolver探索/精密化の失敗と断定できる。
- 4 timeoutは、今回のartifactだけでは内部substageを完全に特定できない。JMO-2013は
  例外からtimeoutへ変わっただけで、closure失敗後の早期フォールバックが未解決である。

生の再実行結果は `benchmark_results_180s_1core_after_refiner_fix_failed66.json`、旧監査の
証拠は `FAILURE_CASE_AUDIT_STRICT_RAW.jsonl/.md`、追加した独立witnessの数値は
`REMAINING35_INDEPENDENT_WITNESSES.json` に保存されている。
