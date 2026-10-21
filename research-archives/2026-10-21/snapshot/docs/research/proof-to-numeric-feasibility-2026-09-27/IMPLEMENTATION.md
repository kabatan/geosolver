# 証明の前提から数値教材を自動生成する経路：実装確認

2026-09-27。既存solverを変更せず、CPU上の小実験を実施した。GPU学習・モデル評価は行っていない。既存solverの大規模成功率を再評価する調査ではない。

## 判定

**元の証明問題の前提を一度DSL化すれば、対象の証明・定理・gold rationaleを使わずに、数値条件付きの問題と最終数値ラベルを反復生成する経路は実装可能である。** 三角形を三辺で確定する初段なら、1〜3日で少数の対象に適用したtrialを準備できる見立てである。一方、そのSFTで元の一般証明が解けるようになるかは実験上の未確認事項であり、データ生成の可否とは別である。

現在は、任意の自然言語の証明問題を入力するとDSL・数値化・query選択・文章・labelが一括生成されるpipelineは存在しない。現行56pairもその機能の実証ではない。個別の座標builderから正解を測る既存実装と、**共通の数値化policyを一度DSL化した前提へ適用する**新実装を区別する。

## 既存の接続点

| 役割 | 既存実装 | 使えるもの・不足 |
|---|---|---|
| 問題表現 | `src/geosolver/problem/models.py:GeometryProblem` | variables・named constructions・conditions・単一targetを持つ。命題のpremises/claimを分けるschemaは新規に必要 |
| DSL静的検査 | `src/geosolver/problem/validation.py`、`compiler.py` | AST・関数・参照・型・構成順序の検査。元の自然言語に忠実かの意味検査はない |
| 数値ラベル | `src/geosolver/application/service.py:solve` | 公開APIから高精度検証・厳密descriptor・診断・problem/engine hashを取得できる。targetを交換して再利用可能 |
| 作図演算 | `dsl-spec.json` | Orthocenter、Circumcenter、Midpoint、FootOfPerpendicular、PerpendicularBisector、IntersectLines、CircleThroughPoint、Intersect(...exclude=A)、Orderなど |
| 多枝 | DSL selectorと検証trace | `exclude`、`near`、`far`などを表現できる。自由な選択を元問題にある枝条件へ結びつける責任はgenerator側 |
| 自由度固定 | 通常DSLのPointとscalar条件 | 平行移動・回転のgaugeと形状パラメータを人手DSL化時に決められる。自動DOF検出・充足する数値given集合探索は未実装 |
| 数値問題文 | `english_templates.py:NUMERIC_EN`、`variant_templates.json` | 構図固有の固定templateがある。任意DSLを自然言語化しqueryを変える共通rendererはない |
| sampling・重複排除 | `program-self-training-2026-09-26/numeric_cases.py` | seed、非相似signature、givens hash、退化reject、private witness/public projectionの仕組みを再利用できる。ただし構成builder・queryは構図ごとのif分岐 |
| 既存静的variant | `authoring/gen_variants.py` | H01/H04等に直接作図sampler。DA01/DA15はこのgeneratorではscale-basedであり、全構図共通samplerではない |

公開APIの`solve`は`completeness=unknown`を返す。一件のsolved、一つのanswer、複数seedでの一致だけから、全解・一般一意性を証明したとは扱わない。今回の全形状固定方式では、前提の各作図が単値であることと明示した枝条件を確認し、その**一つの配置**の測定値を教師にする。

## 何を固定すると教材にできるか

| 対象 | 元の数値givenに残る自由度（一般位置の目安） | 最小生成での扱い |
|---|---|---|
| H01 | BC・AMを固定してもAの方向に1自由度が残る | ABC三辺を指定すれば全形状が確定。AP以外の点対距離も測れる。元の2givenに圧縮するには全形状から測ったanswerが同given内で変化しないか別検査が必要 |
| H04 | BCと構成されたBTの固定後も通常1自由度が残る | ABC三辺指定、T,B,Cの順序をguard。ATと他距離を測る |
| DA01 | ABC三辺で鏡映を除いて0自由度 | 接円中心はAを通る接線への垂線とAB/ACの垂直二等分線の交点。二円のA以外の交点を`exclude=A`で選択。三辺givenのまま開始できる |
| DA15/AP01 | AO・AFの2givenに対し三角形は3形状パラメータで、通常1自由度が残る | ABC三辺から元前提のM,D,E,Fを構成。D/Eのhalf-rayとF内部条件を満たす配置だけ採用。OFやAFなどの変動距離を問う |
| EV02 | 証明前提のみではABCの形・scaleが自由 | ABC三辺を指定しH,M,E,F,Tを元定義通り作る。距離queryを採用し、HTとAMが垂直という結論をconditionsへ追加しない |

三辺による数値化は元の前提へ合法な具体条件を追加する処理であり、元の定理を教師へ混ぜる必要はない。derived pointの座標を問題文へ与えると測定の算術だけになり得るため、公開givenはABC三辺などの**元の自由点を確定する量**に限定する。private DSLでの座標gaugeは公開する必要がない。

三角形SSSは共通部品にできる。BC=a、CA=b、AB=cに対してB=(0,0)、C=(a,0)、A=(x,sqrt(c²−x²))、x=(c²+a²−b²)/(2a)を使えばよい。この式は三辺指定を座標へ変換する基本処理であり、対象証明の結論ではない。整数三辺をsampleし三角不等式・鋭角・不等辺を検査する方式なら、scaleだけ異なる例をsignatureで落としやすい。最小trialで任意の制約充足問題へ広げる必要はない。

## CPU小実験の実測

再実行：

```bash
.venv/bin/python docs/research/proof-to-numeric-feasibility-2026-09-27/premises_cpu_trial.py
```

`premises_cpu_trial.py`は証明・正解・定理ファイルを一切読み込まず、A=(0,4)、B=(−2,0)、C=(4,0)の一つの完全形状と、問題文に定義された基本作図を公開APIへ送る。API optionsは180秒・1コア・seed 0。全4件のvalidationを通り、以下を返した。固定点構成なので内部backendは`direct_evaluation`であり、変数付き数値探索の再評価ではない。

| 問題 | target | solver十進値 | elapsed秒 |
|---|---|---:|---:|
| H01 | Distance(A,P) | 1.94028500029066… | 0.9847 |
| H04 | Distance(A,T) | 12.6491106406735… | 1.1728 |
| DA01 | Distance(A,T) | 3.06785995538948… | 0.9839 |
| DA15 | Distance(O,F) | 0.766964988847370… | 0.9721 |

各答えは十進値だけでなく、整数係数minimal polynomial・実根index・隔離区間を含むalgebraic descriptorとして保存された。全problem JSON、診断、API engine hash、script hashは`CPU_RECEIPT.json`。

DA15の最初の試行では`Intersect(PerpendicularBisector(...),Ray(A,M))`経路からNoneを返し、no_answer_foundになった。これはlabelとして採用しない。構成を同値な`IntersectLines(...,Line(A,M))`と`Dot(Vector(A,D),Vector(A,M))>0`（Eも同様）へ書き換えると成功した。最初の失敗receiptを`CPU_FIRST_ATTEMPT.json`に残した。solver本体の原因追究・修正は行っていない。このようにDSLがvalidateしても、実行domainまで必ず通るわけではないため、problem単位のreceiptとreject台帳が必要である。

この小実験は1配置・4queryの配管確認であり、非相似大量生成、元の少ないgivenでの一意性、自然言語自動変換、SFTの証明改善は確認していない。

### 追加：同じ前提DSLからの自動小バッチ

`premises_cpu_batch.py`で、DA15の一度手書きした前提DSLを使い、seed=20260927から整数三辺をsampleし、共通条件だけで鋭角不等辺・非相似の3shapeを採った。それぞれAF・OF・AOの3queryを差し替え、計9件のpublic API求解と公開問題文生成を自動実行した。公開問題文は元前提＋ABC三辺＋queryだけで、derived point座標・結論・解法を含まない。

| ABC三辺（BC,CA,AB） | AF | OF | AO |
|---|---:|---:|---:|
| (8,12,10) | 5.8277151741… | 1.6152908161… | 6.0474315681… |
| (12,11,10) | 6.3721289100… | 0.6493182425… | 6.4051261522… |
| (17,15,14) | 8.9301083668… | 0.6495146396… | 8.9536978233… |

9件すべてsolved、一意の返却descriptorを持ち、各0.94〜1.02秒。samplerが先にrejectした6候補は`not_acute_scalene`として保存した。3採用shapeのhalf-rayとF内部条件は全queryでsolver検証を通った。生成にAFとOFとAOの間の定理関係は使用していない。9件の公開prompt・入力DSL・exact descriptor・診断・shape signature・sampler rejectは`CPU_BATCH_RECEIPT.json`。

これは**一度formalizeした前提を共通policyで数値化し、変動queryとlabelを作る経路**の小さな実証である。自然言語→DSLは依然として手書き1回、query集合はAF/OF/AOへ固定した。任意graphからquery集合を選ぶpolicy・大量の非相似例・学習への有効性はまだ未実装・未評価である。

```bash
.venv/bin/python docs/research/proof-to-numeric-feasibility-2026-09-27/premises_cpu_batch.py
```

## 1〜3日trialで新しく実装する範囲

1. **premises manifest**：source id、原問題文、premises-only DSL、named points、domain/branch条件、public given policyを持つ。claim/proof/answer keyは別ファイルでgeneratorから読めないようにする。元前提の1回のDSL化は現状人手レビューを含む。
2. **共通SSS sampler**：整数三辺とseedから非相似形状を生成。元前提以外の補助点・定理条件は導入しない。退化・domain・branch違反、重複、解答未取得を理由付きrejectとして記録する。
3. **共通query policy**：元問題に名前がある点から、少なくとも一方がconstructed pointの点対距離を列挙し、seedで一定数を選ぶ。三辺の再問・0距離・全例同じlabel等を汎用規則で除外する。結論を既知の角90度等へそのまま変換する方式だけにしない。query選抜にgold証明やbase/finetuned成功は使わない。
4. **label adapter**：構成graphへprimitive targetを差し替えて公開solveを実行し、成功値だけexport。exact descriptor→短い数値表現の変換を用意し、descriptorと変換誤差はprivate keyへ残す。証明・code・思考過程はSFTのassistant targetに含めない。
5. **renderer/export**：元前提の文章＋ABC三辺＋query文を出力。trialでは3前提の文章templateを用意し、数値とqueryを機械差替えする。生成された与条件のキーとDSL入力が一致するか検査。derived coordinatesはprivate receiptへ限定。
6. **freeze**：source、parameter seed、shape signature、query id、prompt/label hash、reject counts、solver hashを保存。train/holdout分割はshape単位で、同じ形の別queryが分割を跨がないようにする。

DA01・EV02・AP01の3題に64非相似shape×4変動query=256pair/題を作る候補は実装範囲として妥当。H01/H04は配管確認に使える。AP01の中点N/Pは元前提にあり、そのconstructed pointsをquery候補に含めてよい。EV02で証明にしか登場しない補助点をpremises graphへ持ち込まない。

上記は3つの前提を既にDSL化できる場合の開発見立てで、実測した作業時間ではない。24〜32pair程度のCPU preflightから始め、3題のsemantic/branch監査が済んでから768pairへ増やす。今回の約1秒/labelを機械換算するとsolver時間は小さいが、難しい別構成・exact識別・大量実行で同じ速度とは保証しない。SFT・証明評価のGPU待ち時間はこの1〜3日の実装見立てとは別。

## このtrialで自動と言える範囲

一度の前提DSL化と文章templateの準備後、shape選択、数値given、query、solver label、promptの差替え、reject、split、exportを共通policyで自動化できる。対象ごとに正解関係式や専用の座標label公式を書く必要はない。

NL→DSLを含む完全自動化は次段である。既存APIにその機能はなく、LLMが出したDSLをsyntax validationだけで採用すると、証明の結論をconditionsへ混ぜたり、元前提にない補助点を追加したりする可能性を捕捉できない。初段で主張できるのは**「前提だけをformalizeした後のデータ自動生成」**。元の難しい証明でbase失敗・SFT成功が出れば、データ生成から証明改善までの一つの実験経路を示せるが、未知の一般定理の自動発見や未解決問題の成功をこの小実験から約束しない。
