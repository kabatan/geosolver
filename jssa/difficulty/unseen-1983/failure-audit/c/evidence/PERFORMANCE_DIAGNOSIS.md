# 180秒測定の性能低下に関する切り分け

> **最終更新 (2026-08-04)**: 本文中のbaseline診断にあったAIME-2016-I-15の「近さ/分岐guard不足」は、最終DSLで `C=Intersect(omega,omega2,exclude=B)` と `D!=A,C!=B` を明示して解消した。最終測定・不一致分類は [`BENCHMARK_REPORT_180S_1CORE_FINAL.md`](BENCHMARK_REPORT_180S_1CORE_FINAL.md) を正とする。

> **更新 (2026-08-03)**: この文書の本文と表は、自由度圧縮前のbaseline測定を切り分けるための履歴である。その後、experiment branchで高自由度DSLを source-faithful に再構成した。現行302 JSONはすべて0--7変数で、圧縮後39ケースの180秒/1 core結果は [`DOF_COMPRESSION_AUDIT.md`](DOF_COMPRESSION_AUDIT.md) と [`dof_measurement_180s_1core.jsonl`](dof_measurement_180s_1core.jsonl) にある。以下の「44 filesが8変数以上」「17 timeout」は**圧縮前baseline**を指し、現行DSLの状態ではない。

## 結論

`139/206` を、過去の `134/145` と同じ意味のsolver正答率として比較することはできない。両者は問題集合、solverの起動経路、正答の表現、採点規則が違う。

今回の結果には、次の三つが混在している。

1. **比較不能なベンチマーク差**: 旧145件はOMCのsolver向けに整形された別コーパスであり、今回のAIME/HMMT/JMO問題ではない。
2. **DSL/解答メタデータ・採点の不備**: AIMEの最終回答形式を`post_process`に写していない5件、HMMT 2006の誤った公開解答転記1件、accepted候補の先頭だけを代表解にする選択問題がある。
3. **solver側の実障害**: 期待値付き206行のうち、`no_solution=23`、180秒timeout=17、exception=3。例外4件（期待値なしの行も含む）は再現可能なsolver/pipelineバグである。

したがって、今回の低下は「solverだけ」でも「DSLだけ」でもない。公平な再スコアを先に行うと、少なくとも評価上隠れていた正解候補が増える一方、DSLの分岐欠落とsolverのtimeout/exceptionはなお残る。

## 比較対象が同じでないこと

| | 旧 `134/145` | 今回の180秒測定 |
|---|---:|---:|
| 問題集合 | OMC 145件 | 競技幾何302 JSON（AIME/HMMT/JMO） |
| 実行対象 | 145/145 | 285 files（279 unique、17 reference-only） |
| 正答の意味 | minimal polynomial + selected-real-root の**厳密集合一致** | `reported_answer`/`selected_answer`の数値一致（206行に公開解答あり） |
| 代表的な結果 | reference-isolation `134/145`; jobs=7 one-shot `130/145` | representative `139/206` |
| solver起動 | `geotarget solve`, `--time-limit 180 --cores 1 --seed 0` | `geosolver` external pipeline, seed 7, CPU 0固定、外側hard timeout 180秒 |
| 変数数 | 145件すべて0--7変数 | 44 filesが8変数以上（うち17 timeout、3 no_solution） |

旧結果の根拠は[旧reproduction report](/home/kabatan/work/solver-artifacts/experiment-freeze-20260727/product-145-20260727-v4/CHAMPION_PIPELINE_REPRODUCTION.md)、[旧exact score](/home/kabatan/work/solver-artifacts/experiment-freeze-20260727/product-145-20260727-v4/truth-score-input/OFFLINE_SCORE.json)、[reference-isolation audit](/home/kabatan/work/solver-artifacts/experiment-freeze-20260727/product-145-20260727-v4/REFERENCE_ISOLATION_AUDIT.json)にある。旧145件の変数数分布は0--7だけで、今回の高変数・図依存の自然文問題とは難易度分布が異なる。

なお、旧形式の低変数OMCを10件（0--4変数）だけ現行pipelineに、CPU 0固定・180秒で順次通したspot checkでは、10/10が成功し、旧truth targetを含む結果になった。これは全145件の同値性を証明しないが、「現行solverが旧DSL形式を一律に解けなくなった」という説明は支持しない。

## まず採点を直すと何が変わるか

今回の206行（公開解答あり・reference-only除外）の内訳は次の通り。

| 判定 | 件数 |
|---|---:|
| solver status=`success` | 163 |
| `no_solution` | 23 |
| hard timeout (180秒) | 17 |
| exception | 3 |
| 代表解が公開解答に一致（現行集計） | 139 |

`benchmark_child.py`は、`post_process`がある場合でも`phasec.answer_values[0]`だけを変換して代表解にし（同ファイル44行）、`run_benchmark_parallel.py`もその代表解だけを比較する。また、従来のanswer-set判定は生の`accepted_answers`に対して行うため、AIMEの変換後候補を集合判定に入れていない。

### AIMEの明示的な最終回答形式の欠落

次の5件は、問題文の幾何量自体はDSLの`answer`に入っているが、問題文が最後に求める整数への変換が空のままになっている。

| case | solverが返した幾何量 | 問題文の最終形式 | 変換後 |
|---|---|---|---:|
| AIME-2007-I-15 | `231/10 ± 3√989/10` | 2つの値のradicand `r` | `989` |
| AIME-2012-I-12 | `4√3/11` | `m+n+p` | `18` |
| AIME-2014-II-08 | `4√15-14 = √240-14` | `m+n` | `254` |
| AIME-2023-II-12 | accepted候補に `99√37/74 = 99/√148` | `m+n` | `247` |
| AIME-2025-II-14 | `104√3` | 係数 `n` | `104` |

この5件を追加のpresentation transformとして適用すると、少なくとも4件は先頭の代表解も正答になり、AIME-2023-II-12は先頭以外のaccepted候補に正答がある。

既存のtransformを全accepted候補に適用し、先頭以外も含めて「正答候補を少なくとも1つ含む」と数え直すと、現行の146/206になる（代表解は139/206）。上の5件とHMMT 2006の解答転記を補正した場合、候補包含は少なくとも`152/206`、代表解は少なくとも`144/206`になる。ただし候補包含は余分な候補を許す診断値であり、旧145件の厳密集合スコアと同一ではない。

既存transformで先頭以外に正答があった7件は、AIME-2006-II-12、AIME-2016-I-15、AIME-2019-II-07、AIME-2019-II-15、AIME-2020-II-13、HMMT-2013-FEB-GEO-04、HMMT-2024-FEB-GEO-10である。これはsolverが方程式を全く解けなかったのではなく、候補選択・枝選択または採点の問題で落ちた行があることを示す。

### HMMT 2006の公開解答転記ミス

`manual_audit.jsonl`とDSLは公開解答を`20+2√2`としているが、[HMMT 2006公式solutions](https://hmmt-archive.s3.amazonaws.com/tournaments/2006/feb/geo/solutions.pdf)の第1問は`20+√2`と明記し、解答中でも`GH=2`、`AH=4+√2`から同値を導いている。現行solverは`20+√2`（約21.4142）を返しているため、この行はsolver失敗ではなくanswer ledgerの失敗である。ここを直すだけで代表解一致が1件増える。

## DSLの意味が不足していることが確認できる例

### HMMT-2025-FEB-GEO-02（確認済み）

問題文は4つのtipが「**some order**」で正方形の頂点になると言っている。DSLは[`HMMT-2025-FEB-GEO-02.json`](dsl/HMMT-2025-FEB-GEO-02.json)で、`T1,T2`を2本のstalactite、`T3,T4`を2本のstalagmiteとして固定し、その順番だけで正方形を作っている（constraints 18--21）。clause ledgerには「branch」と書かれているが、実際の順列列挙はない。

公式解答は[HMMT 2025 solutions](https://hmmt-archive.s3.amazonaws.com/tournaments/2025/feb/geo/solutions.pdf)第2問で、2本のstalactiteは正方形の**対角の頂点**、2本のstalagmiteも対角の頂点であることから高さ63を導いている。固定順序のDSLはこの対角配置を表せず、現行solverは85を返す。これはsolverの数値誤差ではなく、問題文の「some order」をDSLが一つの順序に潰した意味の欠落である。

### AIME-2016-I-15（分岐guardの不足）

問題文には「common tangent line `AB` is closer to `X` than to `Y`」がある。一方、[`AIME-2016-I-15.json`](dsl/AIME-2016-I-15.json)のguardsは`b,r1,r2,xy`の正値だけで、この近さの不等式を表していない。solverはaccepted候補に正答270を含む一方、先頭は別枝の`AB^2≈1787.689`である。ここは「方程式は解けたが、原文の枝選択がDSLにない」という具体例である。

このほか、図から読み取る内外・点順・交点の選択は、validatorの`source_statement`一致検査だけでは意味の同値性を保証できない。validatorが検査しているのは主にテキスト一致、件数、JSON整合性であり、constraintの意味的完全性ではない。

## 変数数の爆発はDSL encodingの問題を示す

今回の`variables.names`は「独立自由度」ではなく、主に全点の`x,y`座標をsolver変数として数えている。つまり、点が既知の線分上・円周上・交点上にあることを、構成式で消去せず、自由な2座標と後付けの残差制約で表している。

このため、runnable filesの比較は次のようになる。

| 変数数 | files | success | timeout | no_solution |
|---|---:|---:|---:|---:|
| 0--7 | 241 | 194 (80.5%) | 8 (3.3%) | 35 |
| 8以上 | 44 | 24 (54.5%) | 17 (38.6%) | 3 |

14変数を超える6件は全件timeoutである。これは旧145件が最大7変数だったこととも整合し、今回の低下のかなりの部分が「問題の自由度」ではなく「DSLが作った探索空間の次元」による可能性を示す。

特に次のケースは、変数爆発が明瞭である。

| case | 現在の変数数/status | 過剰な表現 |
|---|---:|---|
| HMMT-2019-FEB-GEO-10 | 38 / timeout | 辺長13,14,15で三角形の形は固定なのに、9個の正方形の頂点をほぼ全て自由な座標にし、各正方形を等長・垂直制約で再発見している。正方形は辺ベクトルの90度回転で構成できる。 |
| AIME-2015-I-07 | 17 / timeout | F,G,H,J,K,L,M,Nを全て自由な2座標にし、既知の線分上と2つの正方形を残差で表現している。線分パラメータと正方形構成を使えば大幅に減る。 |
| AIME-2015-I-06 | 20 / timeout | 2つの円弧上の等間隔点を10点の自由座標で表し、等弦条件を後から課している。中心・半径・角度刻みで表すべき構造である。 |
| AIME-2025-II-12 | 20 / timeout | A2--A11を全て自由座標にし、同じ面積・同じcos条件を10組の残差にしている。A1からの半径と角度の再帰を使う構造化余地がある。 |
| HMMT-2020-FEB-GEO-09 | 20 / timeout | 3中心、3接点、共通接線の2点、4つ目の円の中心を自由にし、平行移動・回転ゲージまで探索している。接点は中心線上の構成、接線は法線距離で表せる。 |
| AIME-2019-I-15 | 21 / timeout | chord上のA,P,B、3つの円の中心、交点Q,X,Yを全て自由座標にしている。chord gaugeと円の接点・交点構成で消去できる変数が多い。 |

したがって、「普通に幾何問題をDSL化すれば7変数以内」という感覚は、少なくとも正方形・中点・交点・線分上の点・等間隔円弧を構成演算として持つDSLなら妥当である。ただし、11点非凸多角形のように点列自体が問題の本質であるものまで一律に7以下になるとは限らない。現状は、その判定をせず全てを座標残差系に落としている点が問題である。

## solver側に残る確定的な障害

180秒実行の全285 runnable filesでは、`success=218 / no_solution=38 / timeout=25 / exception=4`だった。公開解答のある206行に限ると上表の`no_solution=23 / timeout=17 / exception=3`である。

例外は次の2種類で、DSLの正誤とは独立したpipeline実装問題である。

- AIME-2007-II-09、AIME-2015-I-04: `UnboundLocalError: phasec_result`。現行runtimeの`run_external_pipeline.py`では、変数なし・guard不成立の経路で`phasec_result`を生成しないまま806行で参照している。
- JMO-2013-PRE-08、JMO-2024-PRE-09: mpmathのfindroot中に`TypeError: '>=' not supported between instances of 'NoneType' and 'int'`。JMO-2013-PRE-08では`mpmath_refiner.py`のclosure polishから再現し、Jacobian/行列の`None`がインデックス比較まで流れている。

timeoutは高変数ほど偏っている。今回のrunnable filesでは、8変数以上44件中17件がtimeout、14変数超の6件は全件timeoutだった。これは旧145件（最大7変数）には存在しない負荷であり、solver探索能力・時間配分の実問題である。ただし、timeoutしたDSLが原文と意味的に正しいかは別途確認が必要で、timeoutだけからsolver回帰と断定してはいけない。

## 判定

- **主因（比較上）**: 旧134/145との比較が同一条件でない。旧OMC145と今回の自然文競技問題は難易度・変数数・分岐性が違う。
- **確定した評価/DSLメタデータ要因**: AIME 5件の最終形式未記述、HMMT 2006のanswer ledger誤り、accepted候補の先頭選択。
- **確定したDSL意味要因**: HMMT-2025-FEB-GEO-02の順序/対角枝、AIME-2016-I-15の近さguard欠落。
- **確定したsolver要因**: 4例外、17期待行timeout、その他23期待行no_solution。特に例外は修正対象である。

したがって、現時点で「solverの性能が134/145から同じ尺度で大幅退化した」とは結論できない。まずanswer projectionとanswer ledgerを修正し、branch/inside/order clauseを列挙可能なDSLに直してから、同じ問題集合・同じ厳密集合規則で再計測する必要がある。その再計測後にも残る`no_solution`/timeout/exceptionがsolver本体の比較可能な性能低下である。
