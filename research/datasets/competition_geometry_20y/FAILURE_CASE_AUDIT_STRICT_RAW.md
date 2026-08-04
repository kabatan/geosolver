# 厳密解集合で失敗した66ケースの証拠付き監査

このレポートは `benchmark_results_180s_1core_strict_raw.json` の raw Phase C 出力を、`exact_truth.jsonl` の厳密解集合、手作業監査 (`manual_audit.jsonl`)、各DSLと突合したものです。数値近似による正誤判定はしていません。全フィールドと生の長い数値列は`FAILURE_CASE_AUDIT_STRICT_RAW.jsonl` に保存しています。独立計算の再現結果は `FAILURE_CASE_INDEPENDENT_CHECKS.json`、その生成コードは `verify_failure_case_independent.py` です。

## 監査対象と集計

- benchmark: `benchmark_results_180s_1core_strict_raw.json`; hard timeout 180 s, jobs=1, CPU=[0], seed=7
- verifiedかつrunnableな205件のうち、strict exact set failureは **66件 (32.2%)**、strict exact successは139件 (67.8%)。
- strict scoringは、答えの表示形式ではなくDSLのraw targetの厳密解集合を比較する。decimal-only出力は厳密解とは認めない。
- 因果の強さ: `confirmed` は生ログとDSL/ランタイムまたは独立検算で機構まで再現、`high` は生ログと制約から機構を強く特定、`medium` は失敗機構は確定するがDSL意味不備までは立証していない。

| category | 件数 | 主な帰属 |
|---|---:|---|
| `decimal_only_near_exact` | 34 | solver |
| `decimal_only_refinement_error` | 1 | solver |
| `hard_timeout` | 2 | solver |
| `no_solution` | 7 | dsl, solver |
| `runtime_exception` | 1 | solver |
| `target_exact_plus_decimal_extra` | 5 | solver |
| `target_plus_extra_exact` | 9 | dsl, solver |
| `wrong_decimal_branch` | 2 | solver |
| `wrong_exact_branch` | 5 | dsl, dsl+solver, solver |

## 証拠コード

- **E1**: benchmarkの当該row（status, wall_sec, raw `phasec.answer_values`, rejection tags, error）。
- **E2**: Phase C実装。`run_phasec_assembly.py:135-144` は exact identification失敗時にdecimal `candidate.answer_hp`へフォールバックする。
- **E3**: DSLのconstruction/constraints/guardsとsource statementの逐条比較。
- **E4**: DSLとは独立な代入・数値解・代数証明による実行可能性/不可能性の検算。
- **E5**: runtime tracebackの直接再現。
- **E6**: runtime semantics（特に `Area` は `Abs(shoelace)/2`）を確認した証拠。

## ケース別判定

### `decimal_only_near_exact` (34件)

| case | status | expected | raw Phase C (excerpt) | owner / confidence | cause |
|---|---|---|---|---|---|
| `AIME-2006-I-07` | success | `["408"]` | `["407.999999999996965094339884689179658081137451973794131155950026727059252267478010722694139073718698603370008214568948531431647829309677069453903461898"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `AIME-2009-I-05` | success | `["72"]` | `["71.999999999999999999999999999999999999999999999999999999999999999999999999999999999999999148320685140076024224056123646876301130960353060742"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `AIME-2009-II-10` | success | `["60*sqrt(13)/23"]` | `["9.40578593599301568650113521902637752237814307582097506076728492842346886284739028801243099928773073684892923719742442536976405755697760320587813855391"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `AIME-2011-I-14` | success | `["5 - 4*sqrt(2)"]` | `["-0.65685424949238019520675489683879231427868750150779229270671895196292991384842815504824291862190122950498804268697848795718145964589450379149"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `AIME-2013-II-04` | success | `["25*sqrt(3)/12"]` | `["3.60843918243516102818217987813723409779751049652020569832775757092814811855401739243902618197526959935014673896337639215435008924247345774048281404743", "3.60843918243516239857641237961817645115045616798419821173580417442150469753414654…` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `AIME-2013-II-08` | success | `["5 + sqrt(267)"]` | `["21.340134638368191854670580675730483476051844100068456914844598376288677754979128321034470649626170939270895580796084494724039114926126842845"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `AIME-2015-II-11` | success | `["18/5"]` | `["3.59999999999999999999999999999999999999999999999999999999999999999999999999996449939824629161778579717037819231158386063813855486746892427285452732387", "3.60000000000000000169312258426417740906319999277931730510510125699756310924067350…` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `AIME-2015-II-15` | success | `["64/65"]` | `["0.984615384615384545865317188127255682147878930752865224511553889595110582785896741272487070355813430406117437428676086029994952496491334537454440313694", "0.9846153846153846153846153846153846153846153846153846153846153846153846153846153…` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `AIME-2016-I-06` | success | `["10/3"]` | `["3.3333333333333333333333333333333333333333333333333333333333333333333333333333333333340540832672128772980184291380536483851483034719144321671"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `AIME-2022-I-03` | success | `["242"]` | `["241.99999999999999999999999999999999999999999999999999999999999999999999999999999999999999994680352035224451886903906036045470090309763779908"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `AIME-2022-II-11` | success | `["180"]` | `["179.99999999999999999999999999999999999999575130009377572960449167903971519638805758269222637043497651981035474719923452873004135555400898184"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `AIME-2023-II-09` | success | `["18*sqrt(15)"]` | `["69.713700231733503933226777196083192994992590695248634878576327790042695654865622603347082578492877963705688353359754078501851701372483284456"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `AIME-2025-II-12` | success | `["(-1 + 9*sqrt(5))/4"]` | `["4.7811529493745268169206407546453715297413913091259328796095188021736720826850610236824324217618201482292651367342199219587007038598085219558"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2006-FEB-GEO-01` | success | `["20+√2"]` | `["21.41421356237309492343001693370752036571502685546875", "21.4142135623730950488016887242096980785696737537559067253502998429019438868449062679733884992722687159906009712048782199480632468826127794165988584204"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2006-FEB-GEO-03` | success | `["31"]` | `["31.000000000000000000000000000000000000000000000000000000000000000000000000000000000000001198289154314740168515488187919852039148960278661426"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2006-FEB-GEO-04` | success | `["27π/40"]` | `["2.1205750411731104359622842837136644468330893445781964291580875998077760742431910740739235071059290208879499583964655569862423102644583616291"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2006-FEB-GEO-06` | success | `["(2+√2)/4"]` | `["0.853553390593273671549036172214436236281095902023723125261852875967226928130761633626737272785974185696024859277166400519003613014485142107524399633384"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2006-FEB-GEO-07` | success | `["3/7"]` | `["0.42857142857142857142857142857142857142857142857142857142857142857142857142857142985501392952795648266875376402230783215513298042228302947527"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2007-FEB-GEO-02` | success | `["2"]` | `["1.9999999999999999999999999999999999999999999999999999999999999999999999999999999999304044232259482373915813124059039258174905703412478544779"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2008-FEB-GEO-02` | success | `["3"]` | `["3.0000000000000003330669073875469991049444326621785777913711992435727750473616608021004745056782072710171444727364232793066483723330573112372"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2008-FEB-GEO-03` | success | `["π-2"]` | `["1.1415926535897932384626433832795028841971693993751058209749445923078164062862089986280348253421170679821480865132823066470307366124278118586"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2008-FEB-GEO-07` | success | `["8"]` | `["7.9999999999999999999999999999999999999999999999999999999999999999999999999999999999999532393621073339757325474886199464663363209352227049777"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2010-FEB-GEO-01` | success | `["3π/7"]` | `["1.3463968515384828164839900214055012360845011711607596375606905395604927455512324279834434965751930291352063227914067028485891516940815865725"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2012-FEB-GEO-01` | success | `["√17/3"]` | `["1.37436854187255396538819529730877873328369495082592978914996455126040963009745721712456680522431739467266090617161765476160479452165995239555442796767"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2013-FEB-GEO-05` | success | `["-1/8"]` | `["-0.12500000000000000000000000000000000000000000000000000000000000000000000000000000000002783902252874847274858488151789751127609988432707453476"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2016-FEB-GEO-04` | success | `["7√3/3"]` | `["4.0414518843273803515640414635137021895332122588908881321302162853878437061205334198560076525596244888239909422115284367303810269754051075516"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2020-FEB-GEO-02` | success | `["40/21"]` | `["1.904761904761904656169235749985091388225555419921875", "1.9047619047619047619047619047619047619047619047514236279466027575649293791564864765164694422143215325671957690775024435876030755454971856051"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2023-FEB-GEO-01` | success | `["189"]` | `["188.9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999541732420873542144233577105761891061930934169903"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2024-FEB-GEO-05` | success | `["4√5-√7"]` | `["6.2985205989345681951350789212858445160522142553636527167152545224410148793209359698972640760882542698613527668121541324269735636296864810391"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2024-FEB-GEO-07` | success | `["8√11"]` | `["26.532998322843198792919461893365493471416708364714828776469457168931877140872350773261272461002118252318641763153529418832011326021056522641"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `HMMT-2025-FEB-GEO-08` | success | `["√6"]` | `["2.4494897427831785416912729484095619477842120473726075340701154436738253332544734699025810048759710493232515759248233985256524952606486034324183597379"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `JMO-2019-MATHNET-08ya` | success | `["(-3 + sqrt(33))/6"]` | `["0.45742710775633810997510191136982155303671074299713206128331291176098345357623410450452089697424214576474752182282278610071236618151659037653"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `JMO-2019-PRE-10` | success | `["(-3 + sqrt(33))/6"]` | `["0.45742710775633810997510191136982155303671074299713206128331291176098345357623410450452089697424214576474752182282278610071236618151659037653"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |
| `JMO-2022-PRE-04` | success | `["245/6"]` | `["40.83333333333333596219084206854995440219407348470358066401552678270636675961213768459856510162353515625"]` | solver / confirmed | exact-identification/serialization failure (decimal fallback) |

### `decimal_only_refinement_error` (1件)

| case | status | expected | raw Phase C (excerpt) | owner / confidence | cause |
|---|---|---|---|---|---|
| `HMMT-2014-FEB-GEO-08` | success | `["600/73"]` | `["8.219178012772207608804819756187498569488525390625", "8.21917808359780099891622739960439503192901611328125"]` | solver / confirmed | numerical refinement stopped before exact root (relative error is not serialization noise) |

### `hard_timeout` (2件)

| case | status | expected | raw Phase C (excerpt) | owner / confidence | cause |
|---|---|---|---|---|---|
| `AIME-2020-II-13` | timeout | `["60"]` | `[]` | solver / confirmed | hard 180-second/one-core budget expired before a Phase C result |
| `JMO-2015-PRE-11` | timeout | `["288/35"]` | `[]` | solver / confirmed | hard 180-second/one-core budget expired before a Phase C result |

### `no_solution` (7件)

| case | status | expected | raw Phase C (excerpt) | owner / confidence | cause |
|---|---|---|---|---|---|
| `AIME-2018-II-12` | no_solution | `["112"]` | `[]` | solver / confirmed | feasible DSL instance was missed by search/refinement |
| `AIME-2019-I-06` | no_solution | `["90"]` | `[]` | dsl / confirmed | ly>0 guard excludes the actual convex source branch |
| `AIME-2020-II-15` | no_solution | `["717"]` | `[]` | solver / confirmed | feasible acute/scalene instance was missed by search/refinement |
| `AIME-2021-I-13` | no_solution | `["672"]` | `[]` | solver / confirmed | feasible externally-tangent-circle branch was missed |
| `AIME-2022-II-07` | no_solution | `["192"]` | `[]` | dsl / confirmed | symmetric l1/l2 intercept construction is algebraically infeasible |
| `JMO-2019-MATHNET-08yk` | no_solution | `["(81 + 9*sqrt(13))/16"]` | `[]` | dsl / confirmed | cx>0 guard excludes the valid AB>AC branch |
| `JMO-2019-PRE-08` | no_solution | `["(81 + 9*sqrt(13))/16"]` | `[]` | dsl / confirmed | cx>0 guard excludes the valid AB>AC branch |

### `runtime_exception` (1件)

| case | status | expected | raw Phase C (excerpt) | owner / confidence | cause |
|---|---|---|---|---|---|
| `JMO-2013-PRE-08` | exception | `["12"]` | `[]` | solver / confirmed | uncaught mpmath findroot/LU TypeError in Phase B closure |

### `target_exact_plus_decimal_extra` (5件)

| case | status | expected | raw Phase C (excerpt) | owner / confidence | cause |
|---|---|---|---|---|---|
| `AIME-2011-II-02` | success | `["810"]` | `["450.000000000000000000000000000000000000006502501542699925300535145583333724136707469690922661058972902847613320229202434003850417610266799009606587734", "810", "810.00000000000002190467411482356836875515218859747521506445983030531010626…` | solver / confirmed | square-side endpoint branch leaked through strict segment guards |
| `AIME-2020-I-01` | success | `["540/7"]` | `["540/7", "60.0000000000000000000000000000000000000000000000000000000000000000000000000000000000048069958700913702053735064057479302440210225311144777397068723986", "77.1428571428571329560045885667814210964832658534518942771366957401195767…` | solver / medium | target branch found, but a degenerate/invalid numerical branch was also accepted |
| `HMMT-2013-FEB-GEO-04` | success | `["(-1+√5)/2", "(1+√5)/2"]` | `["-1/2 + sqrt(5)/2", "0.61803398874989477099494205945660003260474194525884989211093641979690837996401934732268927123389248181080352573066170526081693548917003783072", "0.618033988749894780648256181961544673406378381679638137438761451964582…` | solver / high | branch enumeration and exact identification produced many duplicate decimal branches and an extra exact 1 |
| `HMMT-2021-FEB-GEO-05` | success | `["49/400"]` | `["0.00250000000000000148314954425004531685500728672741510017970301955537333392112335464037107496298165952226505283977981099444291014333149749811531334907669", "49/400"]` | solver / high | wrong numerical branch accepted alongside the exact target |
| `JMO-2022-MATHNET-08z4` | success | `["2\\sqrt{21}"]` | `["2*sqrt(21)", "6.0000000000000000000000000000000000000000000000004094527553536657209404442480563564700309131117365120052649167872121345471341842316332323017"]` | solver / high | invalid numerical branch accepted after line-search/max-iteration failures |

### `target_plus_extra_exact` (9件)

| case | status | expected | raw Phase C (excerpt) | owner / confidence | cause |
|---|---|---|---|---|---|
| `AIME-2006-II-09` | success | `["19 - 3*sqrt(5)"]` | `["19 - 3*sqrt(5)", "35/9 - sqrt(5005)/9", "7 - sqrt(21)", "83/5 - sqrt(429)/5"]` | dsl / confirmed | DSL omits the internal-tangent side-of-line condition |
| `AIME-2014-II-08` | success | `["-14 + 4*sqrt(15)"]` | `["-14 + 4*sqrt(15)", "0", "0.000000000000000655537018356183619241480948831138938874552035684928341652266681194305419921875", "1.491933384829667474935632753840764053165912628173828125"]` | solver / confirmed | strict-radius boundary branch leaked through numerical guard handling |
| `AIME-2018-I-04` | success | `["250/39"]` | `["10", "250/39"]` | solver / confirmed | endpoint branch leaked through strict OnSegment/coordinate guards |
| `HMMT-2007-FEB-GEO-04` | success | `["17"]` | `["17", "7"]` | dsl / confirmed | DSL omits tangent-ray and circle-outside-triangle branch conditions |
| `HMMT-2010-FEB-GEO-09` | success | `["70", "160"]` | `["160", "180", "70"]` | solver / high | near-degenerate convex branch was promoted to exact 180 |
| `HMMT-2014-FEB-GEO-09` | success | `["92/61"]` | `["0", "92/61"]` | solver / confirmed | positive-radius boundary branch leaked through r4>0 |
| `HMMT-2018-FEB-GEO-05` | success | `["8√2/9"]` | `["0", "8*sqrt(2)/9"]` | solver / confirmed | positive-area boundary branch leaked through Area>0 |
| `HMMT-2024-FEB-GEO-03` | success | `["42"]` | `["246", "42"]` | solver / confirmed | diameter boundary branch leaked through the non-diameter guard |
| `JMO-2022-PRE-12` | success | `["2\\sqrt{21}"]` | `["2*sqrt(21)", "6"]` | dsl / confirmed | DSL omits the source's acute-triangle and true-inside conditions |

### `wrong_decimal_branch` (2件)

| case | status | expected | raw Phase C (excerpt) | owner / confidence | cause |
|---|---|---|---|---|---|
| `HMMT-2006-FEB-GEO-10` | success | `["24"]` | `["1.64824247662973274323213468247230719322799981194878295596595446619286526866983391453916766241594516149227745459013084984719587791733150065196810624583e-57"]` | solver / confirmed | r→0 degenerate circle boundary leaked through r>0 |
| `HMMT-2015-FEB-GEO-04` | success | `["37/76"]` | `["0.49539253647378378778494527107712869477496028613372888138229090740233544306182447158967757853970975354243849829646017182983041248069760623469", "0.50064624775714715255707695440187861438633203874012161368479984728753826125872538870284104…` | solver / medium | no exact target branch was reached/identified; multiple approximate branches remained |

### `wrong_exact_branch` (5件)

| case | status | expected | raw Phase C (excerpt) | owner / confidence | cause |
|---|---|---|---|---|---|
| `HMMT-2014-FEB-GEO-10` | success | `["1235/108"]` | `["11.435185185185185185185185185185185185185185185185185185185185185185185185185185185185185185185185185030236118259399775284624129544017617966", "2*sqrt(65)"]` | solver / confirmed | r1,t→0 degenerate boundary branch leaked through r1>0,t>0 |
| `HMMT-2022-FEB-GEO-05` | success | `["361/4"]` | `["1396.557204175636917142140592970639442901431984038086307926829210401820091647095978260040283203125", "1565/2 - 33*sqrt(1385)/2", "33*sqrt(1385)/2 + 1565/2", "90.2500000000000020781282725523602703473631458094021650970348487341698984209870…` | dsl / confirmed | Area guards are unsigned and do not encode D inside triangle ABC |
| `HMMT-2023-FEB-GEO-02` | success | `["2√13"]` | `["0", "7.211102550927979137895817984826862812042236328125"]` | solver / confirmed | A=B endpoint branch leaked through u>0/OnSegment |
| `HMMT-2023-FEB-GEO-04` | success | `["√5"]` | `["1", "2.2360679774997896964091736687312762354406183596115257242708972454105209256378048994142868372136329732277723252083852688840523253321523246773"]` | solver / confirmed | q=p coincident-point branch leaked through q>p |
| `HMMT-2024-FEB-GEO-10` | success | `["9√410/5"]` | `["30", "36.4472221163698570577477757472693498486308726678863892305936039936511547884182837049849368728729605031541754211797579576836226186445796653181294044453", "41.3749570067196046352364652756446940447180237135723260056014499986844024381…` | dsl+solver / confirmed | inside-P is not represented by unsigned Area guards; near-degenerate branches are then accepted |

## 重要な再現証拠（断定の根拠）

1. `AIME-2018-II-12`: DSLに対し `C=(8/5,56/5), D=(-8,14)` を代入すると、4辺残差は約1e-15、面積等式残差は約7e-15、凸性の各turnは `[112,84,112,140]`、面積は112となる。no_solutionはDSL不可能性ではない。
2. `AIME-2019-I-06`: source条件を満たす `K=(0,0), M=(98,0), N=(98,65), L≈(20.5874,-18.9779)` があり `MO=90`。DSLの `AssumeGt(ly,0)` だけがこの凸branchを排除する。hard_infeasibleはDSL過制約。
3. `AIME-2020-II-15`: 独立解 `A≈(3.92145,25.04529)` で `BT=CT≈16`, `TX²+TY²+XY²≈1143`, `XY²≈717`、三角形はacute/scalene。residual_too_largeはsolverの探索/精密化失敗。
4. `AIME-2021-I-13`: `d=672`, `r=1000`, `A≈(732.5,622.0649)`, `O≈(1232.5,1525.2753)` が外接接条件と120°弦条件を満たす。no_solutionはsolver側。
5. `AIME-2022-II-07`: 同じbを使う `l1:y=mx+b`, `l2:y=-mx+b` を半径24円に接する条件から `mb=0`、m>0ならb=0、半径6円への接線条件と矛盾。DSL自体がsourceの三角形を表現できていない。
6. `JMO-2019-MATHNET-08yk` / `JMO-2019-PRE-08`: 独立解で `AB=(81+9√13)/16≈7.0906225924`, `AC≈3.03437741`, angle A=2π/3, `DE=DI=EI=1`。このsource-faithful branchでは座標Cの `cx<0` だが、両DSLが `AssumeGt(cx,0)` を追加しているため、no_solutionはDSL過制約。
7. `HMMT-2022-FEB-GEO-05`, `HMMT-2024-FEB-GEO-10`: runtime `Area` は符号を捨てるため、`Area>0` はinside条件ではない。outside/near-degenerate候補が `guard_ok=true` で再現し、wrong exact/extra branchesを説明する。
8. `JMO-2013-PRE-08`: tracebackは Phase B `_run_findroot_closure` → `mp.findroot` → mpmath `LU_decomp` → `matrices.__getitem__` の None index。DSLの解集合問題ではなく未捕捉runtime bug。

## 限界と結論

timeout 2件 (`AIME-2020-II-13`, `JMO-2015-PRE-11`) は、180.106秒でchildが停止しPhase Cが存在しないことまでは完全に証明できるが、内部のどの探索段階が時間を使ったかはこのbenchmark artifactからは特定できない。`HMMT-2015-FEB-GEO-04` も、近似候補しか得られなかったことは確定するが、DSL意味欠落を示す独立反例は得ていない。この3件は不必要にDSLの欠陥と断定していない。

監査JSONLには各ケースのDSL hash、source hash、全constraints/guards、raw値、tags、error、cause/evidence codeを保存した。独立検算JSONはsolver本体を呼ばずに、no_solutionの実行可能性・DSL代数矛盾・unsigned Area semanticsを再現する。
