
# GeoTarget solver 研究全体像

この文書は、この repository で開発してきた solver（GeoTarget）の研究内容を、数値計算・幾何・リポジトリの前提知識がない読者にも追えるようにまとめたものである。単なる使い方の README ではなく、

- 何を解くためのソフトウェアなのか
- 問題をどのような JSON/DSL にしたのか
- 数値探索から厳密値の出力まで、どんなアルゴリズムを実装したのか
- どの仮説をどの実験で調べ、何を採用・棄却したのか
- 最終的にどの範囲で、どの程度の結果を得たのか
- 現在の main に何が製品として残り、研究履歴がどこにあるのか

を一つの流れで説明することを目的とする。

## 0. 先に結論

GeoTarget は、**有限個の答えを持つ2次元ユークリッド幾何の問題を、数値探索と高精度・代数的な検証によって、厳密な答えの記述へ変換するローカル solver** である。

入力は、例えば「点を円周上に置く」「この点はこの線分上」「二つの長さが等しい」「角度を求める」といった作図・条件・求める量を、V15 JSON DSL と呼ぶ形式で記述する。solver は次のように動く。

1. 入力の意味・構文・作図順序を検証する。
2. 自由な少数の実数を変えながら、条件をよく満たす配置（configuration）を多く探す。
3. 見つかった近似配置を、元の DSL をそのまま評価する独立 replay で再確認する。
4. 倍精度だけでは判定しにくい候補を、512/768/1024-bit 級の高精度計算で精密化する。
5. 求める scalar が代数的数なら、整数係数多項式・実根番号・隔離区間を用いた ExactAnswer として返す。

最終的に main に入った実装は、2026-07-22 に選定した champion-v2-poc-preloaded を唯一の数値アルゴリズムとする。完全に固定した reference engine と、それと同じ数値的判断を保ったまま高速化・並列化した optimized engine の二つがある。2026-07-30 の最終 qualification では、145 問を全て処理でき、失敗 0、reference が返した descriptor の取りこぼし 0、optimized の中央値は 55.66 秒（reference は 136.28 秒）、p95 は 177.38 秒（reference は 178.17 秒）だった。

ただし、これは「どんな幾何問題にも解があることを証明する solver」ではない。no_answer_found は、**決められた有限時間・有限スタート数の探索で採用できる答えが見つからなかった**という意味だけであり、元問題に解がないという証明ではない。

## 1. この文書が扱う範囲と証拠の読み方

現在のブランチ構成には、意図的に二つの層がある。

| 層 | 場所 | 役割 |
|---|---|---|
| 製品の現在形 | main、特に src/geotarget/、frontend/ | 実行可能な API、CLI、HTTP サービス、UI、固定済み solver とその検証テスト |
| 研究の履歴 | experiment ブランチ、experiment-freeze/20260727/、タグ champion-v2-poc-preloaded-20260722 | 初期設計、失敗実験、比較実験、選定根拠、巨大な raw artifact の索引 |

大きな実験結果（145 問の全ケース別ログなど）は Git の外に checksummed archive として保管されている。したがって、この文書では次のように表記を分ける。

- **現在の製品結果**：src/geotarget/qualification.json と README.md に記録された最終 qualification。
- **選定時の結果**：experiment-freeze/20260727/ に記録された凍結 champion の結果。
- **研究上の signal**：development split、pilot、事前登録した候補比較。製品の正しさを直接保証するものではない。
- **棄却結果**：その実験で測った特定実装・特定設定を棄却したのであって、同じ名前のアルゴリズム分野全体を否定したものではない。

この区別は重要である。例えば、初期 Julia lab の「Trust Region が強かった」という結果は有用な仮説生成だったが、そのまま現在の製品の正しさや全問題での優越性を意味しない。

## 2. solver とは何か：初めて読む人向けの説明

### 2.1 普通のプログラムとの違い

普通のプログラムは、入力に対して手順を実行すると一つの出力を返す。solver は、入力された条件を満たす未知の値を自分で探すプログラムである。

例えば次のような問題を考える。

> 点 A と B を固定し、点 P を円の上に置く。さらに P から作った二つの長さが等しくなる配置を探し、そのときの別の距離を求める。

ここで未知なのは「点 P の位置」である。候補位置を一つ選び、条件がどれだけ外れているかを数値で測る。その外れ具合が 0 に近づくように候補を動かす。この「条件を満たす未知量を探す」のが solver の基本である。

### 2.2 幾何問題を数値問題へ変換する

GeoTarget では、図を直接画像として認識するのではなく、作図を少数の自由 scalar と式で表す。

概念的には次の三つの関数を作る。

~~~text
configuration u  ──作図を実行──>  点・線・円などの幾何オブジェクト
configuration u  ──条件を評価──>  residual（条件の外れ具合）
configuration u  ──answerを評価──> target scalar（求める量）
~~~

例えば「二つの距離が等しい」は、

~~~text
Distance(P, A) - Distance(P, B) = 0
~~~

という residual になる。solver は residual の絶対値が小さく、同時に点の順序や非退化条件などの guard も満たす configuration u を探す。最後に、その u で answer 式を評価して target を得る。

### 2.3 なぜ「答え」ではなく「答えの descriptor」なのか

浮動小数点で 0.465477516175... と表示するだけでは、丸め誤差によって本当に同じ値なのかを区別できない。そこで GeoTarget は、代数的数を次の組で返す。

| フィールド | 意味 |
|---|---|
| minimal_polynomial_high_to_low | その数が根になる、既約な最小多項式の係数（高次から低次） |
| selected_real_root_index | 多項式の実根を昇順に並べたときの番号 |
| isolating_interval | その根だけを含む区間 |
| decimal | 人間が読みやすい近似小数 |

例えば最終 qualification の補正テストには、

~~~text
7 x^2 - 14 x + 5 = 0 の root 0
~~~

という descriptor が現れる。小数表示は補助情報であり、同一性の主キーは「最小多項式＋選択した実根番号」である。これが異なる target を、単に小数が近いという理由で一つにまとめないための仕組みである。

## 3. 何を解く問題として受け入れたか

### 3.1 V15 の問題クラス

V15 DSL の対象は、次を満たす **有限解・単一 scalar target の2次元ユークリッド幾何** に限定される。

- 点、直線、線分、半直線、円、円弧、多角形を使う。
- 距離、長さ、角、面積、半径、周長、所属、交点、接線、平行、垂直、順序、凸性などを条件にできる。
- 平行移動と回転という座標の自由度だけを gauge として除いた後、label を保った配置が有限個になる。
- 鏡映、二つの交点、左右の接線など、有限個の branch は残っていてよい。
- 求めるものは一つの scalar 式である。配置ごとに複数の distinct target 値が出てもよい。

逆に、次は対象外である。

- 最大化・最小化などの最適化問題。
- 連続無限個の配置を持つ locus 問題や、任意点のまま残る問題。
- 本質的な整数性、素数性、格子点、個数、組合せ条件。
- 物理、確率、3次元、球面・双曲幾何、証明だけを要求する問題。
- 元問題の branch や非退化条件を言語化できず、図の見た目だけで選ぶ必要がある問題。

scale は勝手に消してはいけない。例えば角度だけが与えられた三角形は相似拡大が無限に残るため、そのままでは有限配置問題にならない。長さを固定する条件が source にある場合に限って scale が決まる。

### 3.2 低次元化と意味保存

solver の性能は、未知座標が多いほど悪くなりやすい。しかし、性能のために数学的に同値そうな別問題へ置き換えてはいけない。最優先順位は次の通りである。

1. 元問題の意味を完全に保存する。
2. ほとんどすべての探索点で作図・条件・target を評価できるようにする。
3. 自由変数の数を小さくする。
4. 数値条件、式の大きさ、branch 数を改善する。

許される低次元化は、source が直接指定したものだけである。

- 平行移動・回転の gauge。
- 「D は BC 上」のような carrier 上の parameterization。
- source が明示した中点、垂足、内心、外心、平行線、垂線などの construction。
- source が明示した二直線の交点や、もう一方の円交点。
- source の作図順に従った定義 DAG。

一方、次は意味保存とはみなさない。

- 角の二等分線を、角の二等分線定理の辺比へ置き換える。
- 接線を方べきや反転の公式だけへ置き換える。
- 問題文にない相似、共円、根軸などを発見して条件を消す。
- target の公式を先に導出し、その公式だけを解く。
- 図の見た目、既知の答え、offline truth で branch を選ぶ。

変換前には、元の各 clause、DSL 上の対応箇所、construction/constraint/guard の種類、branch と退化の扱いを記録する clause ledger を作る。この監査方針は V15 DSL 作成マニュアル（docs/V15_GEOMETRY_DSL_AUTHORING_MANUAL_ja.md）に詳しい。

## 4. V15 JSON DSL の構造

### 4.1 最小の正規形

問題ファイルは概ね次の形を取る。

~~~json
{
  "id": "example",
  "task": "solve",
  "variables": {"names": ["t"]},
  "construction": [
    {"name": "A", "expr": "Point(0, 0)"},
    {"name": "B", "expr": "Point(5, 0)"},
    {"name": "P", "expr": "PointOnCircle(omega, t)"}
  ],
  "constraints": [
    {"def": "Distance(P, A) - Distance(P, B)", "value": 0}
  ],
  "guards": ["Bound(t, -pi, pi)"],
  "answer": "Distance(P, A)",
  "post_process": ""
}
~~~

実際には omega の定義などが必要だが、重要なのは各 field の責務である。

| field | 役割 |
|---|---|
| id | 問題を識別する名前 |
| task | 必ず solve |
| variables.names | solver が直接動かす自由 scalar の名前 |
| construction | 上から順に評価する作図 DAG |
| constraints | 0 に近づける equality residual。def と value の組 |
| guards | 不等式、branch、順序、非退化、定義域など |
| answer | 一つの scalar を返す副作用のない式 |
| post_process | 製品では必ず空文字。丸め・整数化・複数解の集約は禁止 |

construction の式は、自由変数とそれ以前に定義された construction だけを参照できる。これは ordered DAG であり、未来の object を参照する forward reference は無効である。source が決めた object を construction にしても、新しい optimizer 自由度を追加してはいけない。

### 4.2 使える幾何語彙

現在の src/geotarget/dsl_catalog.json には、**87 個の tools** と **29 個の scalar/runtime functions** が登録されている。代表的な分類は次の通りである。

| 分類 | 例 |
|---|---|
| 基本 object | Point、Line、Circle、Segment、Ray、Arc、Polygon |
| parameterization | PointOnLine、PointOnSegment、PointOnCircle、PointOnArc |
| 交点 | Intersect、IntersectLines、IntersectLineCircle、IntersectCircles |
| 作図 | Midpoint、PerpendicularLine、ParallelLine、FootOfPerpendicular、AngleBisector、TangentLine、Reflect、Rotate |
| 三角形中心 | Centroid、Circumcenter、Incenter、Orthocenter、Excenter、NinePointCenter、GergonnePoint、NagelPoint など |
| 円・極 | Circumcircle、Incircle、Excircle、PowerOfPoint、Polar、Pole、RadicalAxis |
| 測定 | Distance、Length、Angle、Area、Radius、Perimeter、Circumference、Dot |
| 関係 | OnLine、OnSegment、OnCircle、Collinear、Parallel、Perpendicular、IsTangent |
| scalar 関数 | abs、sqrt、sin、cos、asin、acos、atan、atan2、min、max など |

実行時に使える引数個数、keyword、戻り値型、selector の値は dsl_contract.py が dsl_catalog.json から機械的に導出する。UI の autocomplete も同じ catalog を利用するため、UIだけに存在する架空の関数を作らない設計になっている。

### 4.3 constraint、guard、answer の違い

- **constraint** は、等式を残差にするもの。例えば Distance(A,B) - 5 は 0 へ近づける。
- **guard** は、等式を 0 にするだけでは表せない意味を保持するもの。点の順序、r >= 0、交点 branch、三角形の非退化、strict inequality などがここに入る。
- **answer** は、条件を満たした配置から最後に読む scalar である。target の公式を先に作って制約へ戻してはいけない。

construction の失敗と guard の失敗は別である。例えば Circle(center, r) は r < 0 では構築できない。三点が共線なら Circumcircle や Circumcenter が未定義になる。construction を先に評価し、構築できた後で guard を評価するため、「壊れた construction を後の guard で救う」ことはできない。

### 4.4 validation が特に守るもの

src/geotarget/validation.py は strict な Pydantic model と式 AST 検査を使い、次を確認する。

- top-level field と型。
- 変数名・construction 名の重複。
- forward reference、未知の関数、引数個数、selector。
- answer が単一 scalar 式であること。
- source の construction 順と native JSON の scalar 型。

重要なのは、入力を検査するために Pydantic で読んでも、engine に渡す source を意味的に書き換えないことである。例えば JSON の 0 を 0.0 に変えてしまうと native source bytes の SHA が変わり、champion の exact replay authority が別問題と判断する。現在の service/API は、検証結果を使いつつ元 JSON の数値型を保持して engine に materialize する。

## 5. 期待する出力と assurance level

models.py が API、CLI、HTTP 共通の結果モデルを定義する。

| status | 意味 |
|---|---|
| exact_complete | 変更されていない exact authority が、対応する scope で完全性まで明示した |
| answers_found_completeness_unknown | 一つ以上の厳密 descriptor は得たが、全 target を列挙した証明はない |
| no_answer_found | 有限 run で採用できる descriptor が見つからなかった。解なしの証明ではない |
| cancelled | ユーザーが停止した |
| invalid_problem | DSL の検証に失敗した |
| resource_error | CPU・メモリなどの要求を満たせなかった |
| engine_error | engine が実行中に失敗した |

exact_complete は「数値が小さかった」だけでは付かない。target の最小多項式、root index、isolation、authority の provenance が揃い、かつ exact route がその scope の完全性を明示した場合だけである。通常の multistart search が一つの target を見つけても、公開結果は answers_found_completeness_unknown になる。

## 6. repository 全体の構成

### 6.1 実行経路

~~~mermaid
flowchart TD
    A[ユーザーの V15 JSON] --> B[CLI / Python API / Loopback HTTP]
    B --> C[Strict validation と native source 保持]
    C --> D[problem SHA と engine manifest 検証]
    D --> E{engine 選択}
    E --> F[凍結 reference engine<br/>1 core / 180 s]
    E --> G[qualified optimized engine<br/>並列・compiled/fused・adaptive]
    F --> H[同じ champion search / HP / exact authority]
    G --> H
    H --> I[descriptor 正規化]
    I --> J[status と checkpoint]
    J --> K[CLI JSON / HTTP polling・SSE / React UI]
~~~

### 6.2 主要な Python モジュール

| ファイル | 役割 |
|---|---|
| models.py | strict input/options/result、ExactAnswer、checkpoint の型 |
| validation.py | V15 JSON と式 AST の検証、native document の保持 |
| dsl_contract.py / dsl_catalog.json | DSL の callable/selector 契約 |
| engine.py | reference/optimized の選択、manifest 検証、deadline、結果抽出、resource/error 境界 |
| service.py | 検証キャッシュ、CPU/メモリ予約、engine 起動、public status の変換 |
| cli.py | doctor、validate、solve、ui コマンド |
| api.py | loopback-only FastAPI、session cookie、FIFO JobManager、polling/SSE、cancel |
| resources.py | 物理 CPU とメモリの予約。要求を黙って縮小しない |
| qualification.py | qualified engine、default mode、900 秒上限などの policy |
| optimized_search.py / optimized_entrypoint.py | equivalent work の shard、ordinal lease、deterministic merge |
| parallel.py | physical-core worker、process isolation、shard coordination |
| runtime_broker.py / hp_preloader.py | 高精度 worker の fork isolation、socket broker、thread=1 |
| adaptive_continuation.py / continuation.py | 初期 prefix 後の安全な追加探索と checkpoint |
| compiled_evaluator.py | V15 DAG 全体を typed evaluator にできるかの capability gate |
| fused_evaluation.py | reference semantics と guard/hard-feasibility の callback fusion |
| typed_refnum_ir.py / typed_refnum_intersections.py | typed RefNum IR、交点・selector・union の評価 |
| lazy_symbolic_geometry.py | 未知の V15 composition を遅延展開する symbolic geometry |
| raw_libmp_backend.py | mpmath/SymPy 系の arbitrary precision geometry と deferred scalar tape |
| flat_tape_backend.py | 高速だが ULP 差があり製品の qualified path ではない実験 backend |
| hp_semantics.py | optimized-only の polar/PointOnCircle など高精度 semantic compatibility |
| reservoir_checkpoint.py / hp_wave_checkpoint.py | pending candidate、HP wave、extension の integrity 付き checkpoint |
| problem_cache.py | source/plan/runtime の再利用と cache metadata |

凍結された transitive runtime は src/geotarget/_engine/runtime/solver/ と geosolver/ に置かれる。src/geotarget/_engine/product-manifest.json は reference の 503 ファイル closure と SHA を、optimized-manifest.json は optimized の closure SHA を記録し、geotarget doctor と solve 前の検証がそれを強制する。

### 6.3 UI と HTTP

frontend/src/ は React/TypeScript のローカル construction workbench である。

- App.tsx：問題編集、作図、条件・guard・target、solver 実行、進捗。
- geometry.ts：2D scene、式の preview、交点候補、world/screen 変換。
- authoring.ts：Fixed/Free/Derived の自由度、guided tool、parameterized point。
- MathFormula.tsx：式を KaTeX で表示。
- MathKeyboard.tsx / ExpressionAutocomplete.tsx：式入力支援。
- ExactResult.tsx：最小多項式・実根番号・近似値・witness の表示。
- useSolverJob.ts：HTTP job の polling、progress、cancel、terminal status。

UI は図の見た目から条件を推測しない。ユーザーが construction、constraint、guard、branch/order、answer を明示する。frontend/src/authoring.test.ts などで、自由点追加、smart construction、型の合わない object の拒否を検証している。

HTTP server は 127.0.0.1/::1 の loopback のみに bind し、same-origin session cookie を要求し、solve job は FIFO に一つずつ実行する。ブラウザの /api/v1/session、POST /api/v1/solves、GET /api/v1/solves/{id}、SSE events、DELETE cancel という境界である。ネットワーク越しの共有サービスや認証・telemetry は製品 scope 外である。

## 7. 最終 champion のアルゴリズム

ここからは、最終的に製品へ入った数値処理を、入力から出力まで順に説明する。

### 7.1 凍結された計算量と policy

reference と optimized の両方で、数値判断に関わる次は固定されている。

| 項目 | 凍結値・ルール |
|---|---|
| engine | champion-v2-poc-preloaded-20260722 |
| 全体の nominal window | 180 秒 |
| 数値 search window | 146 秒（残りは finalize/selection/HP 管理等） |
| 初期 starts | 256 |
| callback / start | 600 |
| aggregate callback cap | 153,600 (= 256 × 600) |
| seed | 入力 option と start ordinal から決まる deterministic stream |
| candidate selection | residual 主、configuration/target の novelty は soft tie-break |
| high precision | 512/768 の独立 lane、安定後に 1024 級 authority |
| restoration | 高精度で失敗した候補だけに bounded dyadic/Walsh antithetic restart |
| exact identity | 最小多項式＋selected real-root index |

search の proposal stream は、candidate.py などで固定された full-support policy である。counter-product の Cauchy insurance を毎 4 proposal に置くが、研究文書の注意どおり、現在の全 stream を「joint IID」とは主張しない。既知 target 数や問題 ID を見て start を変える lane はない。

### 7.2 Step 0：入力を immutable な問題として準備する

1. strict validation で V15 の形、式、参照順、関数契約を検証する。
2. 元 JSON の scalar 型を保った canonical bytes を作り、problem SHA-256 を計算する。
3. engine manifest と frozen source closure の SHA を確認する。
4. engine が読む JSON と digest が一致することを dry plan で確認する。
5. physical CPU、memory、thread 数を予約する。要求が満たせない場合、勝手に core を減らさず resource_error にする。

これにより「同じ数式に見えるが source bytes が変わった」「異なる engine が混ざった」「host の BLAS thread 数だけが違った」という事故を、数値計算の前に止める。

### 7.3 Step 1：自由度 0 の exact bypass

自由変数が 0 個の問題は、探索する必要がない。champion-v2 はこのケースを特別扱いする。

- 空の configuration を唯一の候補にする。
- DSL の construction、constraint、guard、answer を exact AST evaluator で評価する。
- source-exact value から有理数または minimal polynomial/root isolation を作る。
- 数値 PSLQ や近似 descriptor を authority にしない。

これが通れば ZERO_DIMENSIONAL_SOURCE_EXACT_COMPLETE として exact_complete になる。自由度が 1 以上の問題には、これを一般化した completeness claim は付かない。

### 7.4 Step 2：deterministic multistart

自由度がある問題では、同じ初期点から局所 solver を一度走らせるだけでは、別の root や別 branch を見逃す。そこで 256 個の start を、固定された順序・seed・提案規則で用意する。

各 start は次の意味を持つ。

~~~text
start ordinal
    ↓
候補 configuration を生成
    ↓
最大 600 callbacks の local search
    ↓
canonical replay と reservoir admission
~~~

局所 solver の internal return code だけでは採用しない。source evaluator で再計算し、finite、construction 成功、guard/branch/hard-feasibility、正規化した relation residual をもう一度確認する。これは「数値ライブラリが converged と言った点」と「元問題の意味を満たす点」を分離するためである。

### 7.5 Step 3：local numerical search

局所探索は、条件 residual と guard/hard-feasibility を含む augmented relation を使う bounded nonlinear least-squares 型の処理である。

#### 初期 Jacobian と direct Broyden

- 初回は automatic differentiation が利用できる箇所と、課金された finite difference を組み合わせて Jacobian を作る。
- その後は good-Broyden の rank-one secant update で直接モデルを更新する。
- 予測が悪い、または semantic-invalid trial が出た場合だけ full Jacobian を refresh する。
- 固定 iteration 数や固定 rank schedule で毎回 refresh するのではなく、measured model quality を trigger にする。

これにより、毎 callback で高価な全 Jacobian を作るコストを抑えつつ、モデルが外れたときには元の差分計算へ戻れる。

#### スケーリングと step

- 二側 Ruiz scaling は線形代数の前処理にだけ使う。raw model 自体を正しさの根拠にしない。
- CPQR/SVD ベースの LM step を計算し、rank deficiency や ill-conditioning を診断する。
- trust radius を超える step は clipping する。
- source が宣言した bounds だけを使う。
- step の acceptance、residual、guard、construction の意味は常に元 source evaluator が決める。

つまり、optimizer は「よさそうな方向」を提案するだけであり、source semantics が最終審判である。

#### stalled near-root の strict restart

保持した track が stalled_or_budget で、relation norm の改善が Float64 epsilon の立方根程度しかなく、callback がまだ 2 回以上残る場合は、元の start と同一の状態から一度だけ strict semantic-invalid-refresh restart を行う。restart が悪化しても最初の best を置き換えない。安全に root と確認できた候補だけを採用する。これは「少し残差が小さいだけの stationary point」を root と誤認しないための局所的な補助である。

### 7.6 Step 4：target-free endpoint reservoir

探索中に target を先に使うと、既知の答えへ近い候補だけを残す漏洩や、似た target を早く一つにまとめる bias が生じる。champion v0 は target-free reservoir を採用した。

- 候補の admission は Float64 residual、guard、hard-feasibility、configuration の安全性だけで行う。
- 同じ provisional target の候補を理由なく全て捨てない。
- residual の良い primary と、configuration が異なる alternate を保持する。
- cluster 内で最大 2 候補を HP へ渡す。
- 近い候補の重複抑制は residual-scaled の soft predicate にとどめ、独立 insurance lane を削らない。
- 時間不足で HP に送れなかった候補は「落とした答え」ではなく、deferred/unknown と checkpoint に残す。

target の計算はこの段階では provisional な診断にとどまり、最終 descriptor の authority にはしない。これにより「target の値がたまたま既知値に近いから採用」という構造を避ける。

### 7.7 Step 5：高精度 refinement

reservoir の上位候補について、独立した高精度 lane を走らせる。

1. 512-bit lane で configuration、residual、guard、target を replay/refine する。
2. 別実装・別経路の 768-bit lane でも同じ候補を独立に評価する。
3. configuration と target の lane 間の差が agreement gate（現在は概ね 1e-100 級）を通るか確認する。
4. その共通 anchor を original strict stage へ渡し、1024-bit 級の target-stability/authority 確認を行う。
5. finite、hard-feasible、guard OK、residual gate、target relation の全条件が揃わなければ fail closed にする。

高精度化は「小数をもっと長く表示する」ためだけではない。悪条件な方程式では、小さな residual と正しい configuration が大きくずれることがある。そのため、relation residual、configuration disagreement、target disagreement を別々に測定する。以前の point replay だけの実装はこの区別が不十分で、singular な nonroot を provisional target にしてしまう反例が見つかった。現在はその候補を public answer へ昇格させず、refinement queue か unknown に留める。

### 7.8 Step 6：代数的 target の exactification

高精度で安定した target に対して、owned_pslq 系の処理が整数関係を提案・確認する。

- 768-bit で最小多項式候補を提案する。
- 1024-bit で同じ関係が再現することを確認する。
- 係数を primitive、square-free、irreducible に正規化する。
- isolating interval と実根番号を計算する。
- target authority の DSL replay と対応付ける。

target-only の PSLQ を configuration witness の代わりに使わない。近い小数から多項式を当てるだけでは exact answer にならないため、同じ候補 configuration の独立 replay と relation/guard の証拠が必須である。

### 7.9 Step 7：HP failure restoration

candidate が Float64 では有望でも、高精度 lane の agreement や target relation が通らないことがある。残り時間がある場合だけ、bounded restoration bundle を同じ authority へ戻す。

- dyadic scale の小さな再始点。
- Walsh 方向などの antithetic（±）方向。
- 最大 600 callbacks の bounded budget。
- 新しい答えの定義や新しい target lane は導入しない。

restoration は「失敗した候補を何でも救う」機構ではない。同じ high-precision authority にもう一度通る機会を与えるだけであり、残り時間を超えたら unknown として残す。

### 7.10 Step 8：descriptor dedup と public result

最終 output の dedup key は、近似小数ではなく、

~~~text
(minimal polynomial coefficients, selected real root index)
~~~

である。結果には answer の一覧に加えて、engine id/hash、problem SHA、requested/used resources、elapsed、phase、completed/pending ordinals、extension 状態、warning を記録する。これにより、答えだけでなく「どの bounded computation が答えを得たか」も追跡できる。

## 8. reference engine と optimized engine

### 8.1 reference：基準となる凍結実装

reference engine は、2026-07-22 の champion の bytes、実行順、threshold、proposal、600 callbacks/start、HP policy、restoration、exact authority、PointOnCircle semantics を変更しない。

- 1 core のみをサポートする。
- 180 秒の固定 work window を再現する。
- max_time を 180 秒より大きくしても、新しい start は自動的に増えない。
- 一般的な外部 resume file を公開するものではなく、実行中の状態を result checkpoint に記録する。

これは速さではなく、**何が基準の判断なのかを固定するための authority** である。

### 8.2 optimized：同じ数値判断を保った実装・スケジューリング最適化

optimized は、別アルゴリズムを選べる設定ではない。許されるのは、凍結された work を同値な実装・順序付き shard・安全な continuation で実行することだけである。

#### typed whole-problem evaluator と fusion

V15 の construction DAG が capability gate を通る場合、compiled_evaluator.py が問題全体を typed RefNum IR へ落とす。all-or-nothing であり、一部だけを別意味で実行しない。

gate を通らない問題でも、fused_evaluation.py が reference semantics の guard/hard-feasibility snapshot を一つの callback に融合する fallback がある。未知の問題を「compiled evaluator がないから遅いまま」にしない一方、qualified でない flat native tape を勝手に使わない。

145 問に対する 725 differential probes では、fused callback は reference と bitwise mismatch 0 だった。native flat evaluator は microbenchmark では速かったが 4096 ULP の差が出たため、製品 path へ昇格させていない。

#### 並列化と deterministic merge

multi-core では start ordinal の連続範囲を shard へ分ける。worker は file lock で ordinal を lease し、crash した lease は retry できる。各 shard の候補を次の順で結合する。

1. ordinal 順に並べる。
2. full proposal prefix hash が一致することを確認する。
3. callback 数、pending、HP alternate、restoration を検証する。
4. reference と同じ deterministic candidate order に戻して selection/descriptor dedup を行う。

したがって、core 数を増やしただけで別の solver になったり、実行順により答えの優先順位が変わったりしない。CPU/メモリを予約できない場合は resource error で止める。

#### preload と adaptive continuation

高精度 worker を各 physical core に pre-load し、Python/BLAS/Julia の thread を 1 に固定して、import・allocator・JIT の揺れを減らす。初期 256 starts が 0 accepted answers の場合だけ、optimized は 64 starts ずつ追加できる。

- 追加は deterministic batch。
- empty batch が 2 回連続（stability=2）で終了。
- 全体の安全上限は 900 秒以下。
- 最初の 256 starts で一つでも accepted answer が出たら extension しない。
- 新しい proposal/seed lane、既知 target を使う route、完全性の新しい証明は追加しない。

これは「答えが出るまで無限に探す」機能ではなく、初期 prefix が空だった場合に限る bounded policy である。

## 9. champion ができるまでの研究の流れ

研究は、最初から現在の Python champion があったわけではない。初期 lab、局所 solver の比較、悪条件・高精度の監査、target discovery、runtime/productization の順に積み上げた。

### 9.1 2026-07-10 前後：clean-slate lab と baseline

最初の設計では、Python 側の typed construction graph と、Julia 側の open-world plugin ABI、black-box compiled oracle/reference interpreter、deterministic proposal、LM/QR、canonical replay を分離する構想を置いた。これは研究用の実験台としては有効だったが、まだ production の G1+（全 target、完全性、安全な exactification）を満たすものではなかった。

最初の 9 ケース規模の baseline は core-lmqr-bounds-scaled、1 thread、120 iterations/start、600 evaluations/start だった。

| starts prefix | 全 target を取れたケース | target 数 | configuration 数 | false-candidate proxy | 評価回数 |
|---:|---:|---:|---:|---:|---:|
| 2 | 3/9 | 6/16 | 6/18 | 3 | 3,244 |
| 4 | 5/9 | 8/16 | 8/18 | 8 | 5,455 |
| 8 | 6/9 | 9/16 | 9/18 | 13 | 12,391 |

この表から、少なくとも二種類の失敗が見えた。

- **NearRank / Tangent**：residual は小さいのに configuration が正しい root から遠い。local endpoint correctness と conditioning の問題。
- **MultiRootWarped**：local solver は一部の basin に留まり、別の root を一つも capture しない。discovery/coverage の問題。

一方、ScaleLadder や CurvedChain は同じ target を何度も拾った。これは「容易な重複 work」と「近接 root を hard suppression してはいけない」の両方を示した。

### 9.2 R0–R7 の研究 roadmap

研究 roadmap は、前の champion を固定し、次の実験では一つの軸だけ変える evidence gate 方式だった。

| milestone | 調べる内容 |
|---|---|
| R0 | assessor と reported acceptance を分け、baseline と failure trace を信用できるようにする |
| R1 | LM の damping/globalization と Trust Region を比較 |
| R2 | endpoint correction、condition-aware acceptance、rank/target sensitivity |
| R2b | weak Jacobian direction の対称・多尺度 refinement proposal |
| R3 | all-target discovery、independent-uniform insurance、QMC/heuristic の比較 |
| R4 | singular、guard、branch、boundary、deflation など診断済み hard lane |
| R5 | AD、compiler、sparse view、evaluator cost の削減 |
| R6 | 未知の geometry composition/family の holdout |
| R7 | production integration、verification、release gate |

この roadmap の重要な原則は、no_answer を no-solution と呼ばないこと、Gold/truth を runtime routing に入れないこと、候補を棄却する前に failure の因果を閉じることだった。

### 9.3 local solver の比較

過去の 48 development instances × 32 paired starts では、NonlinearSolve 系の Trust Region が当時の LXR-LMQR より良い signal を示した。

| variant | P_local_gold | P_full_target | charged work |
|---|---:|---:|---:|
| NLS-TR | 0.9206 | 0.8958 | 343,469 |
| NLS-LM | 0.8854 | 0.8750 | 493,424 |
| NLS-RMN | 0.9206 | 0.8958 | 346,387 |
| NLS-TR-STRICT | 0.9219 | 0.8958 | 356,176 |
| LXR-LMQR | 0.7956 | 0.8125 | 534,029 |

ただしこれは current frozen assessor での製品結果ではなく、別 adapter・別 budget の development evidence だった。そのため、Trust Region を丸ごと製品へ入れるのではなく、現在の direct-Broyden/TR/LM lineage を、source semantics と fixed callback contract の内側で組み直す方向へ進んだ。

引継ぎ時の小さな damping pilot では、initial_damping=1e-3 より 1e-16/1e-20 が MultiRoot と NearRank の局所 work を減らした。しかしこれは artifact なしの hypothesis generator であり、固定 tiny lambda を production default にする根拠にはしなかった。結果に合わせてしきい値を変えず、正式な globalization/condition 実験へ戻した。

### 9.4 residual だけでは root の正しさにならないことの発見

高精度・singular audit では、

~~~text
F1(x,y) = x + y
F2(x,y) = x + (1 + 10^-13)y
target(x,y) = x
~~~

という、真の root が (0,0) の反例を使った。(1,-1) では F1=0、F2≈10^-13 なので residual tolerance 内に入るが、target は 1 であり真値 0 から大きく外れる。旧 point replay path はこれを provisional target として出し得た。

修正後は、nonzero residual かつ measured rank deficient の候補を fail closed にし、

- semantic replay evidence（その点で DSL を評価できた）
- numerical root evidence（再精密化、rank/condition、forward error）
- validated root evidence（interval/Krawczyk 等があれば）

を別型に分けた。高精度で同じ点を再評価できたことだけで、近くに root が存在する証明とはしない。

### 9.5 weak-direction と singular lane の探索

NearRank、Tangent、MultiRoot の endpoint で Jacobian の最小特異方向を調べ、両符号・多尺度へ局所 proposal を出す pilot を行った。Warped では外側 root の endpoint から weak direction に沿う小さな摂動が内側 root を見つけた例があった。

しかしこれは 1 instance/session の artifact なし pilot であり、一般的な改善とは主張しなかった。formal candidate では、

- 同じ work の isotropic perturbation control。
- 直交変換、scale、signed permutation の metamorphic 一致。
- manifold、nonroot、guard crossing、複数 weak singular value。
- 失敗 proposal の work を全て課金。

を要求した。

rank chart、up-front dense rank diagnostic、固定 SVD cutoff、frozen restarted good-Broyden、point replay だけの BigFloat などは、特定設定で安全性・再現性・経済性の gate を通らなかったため採用しなかった。これは「SVD は使えない」という意味ではなく、**特定の route を無条件の汎用 rescue として使わない**という結論である。

### 9.6 target discovery と scheduler の実験

local solver の問題と、そもそも basin に入れない問題を混ぜないため、まず local pipeline を固定してから discovery stream を比較した。独立 uniform の D0、Halton/Sobol の diagnostic、bounded insurance、weak-direction refinement、soft novelty/scheduler を分離して調べた。

EXP-GLOBAL-001 の S1/S2 では、seed 0 の development 145 問に対し progressive-adaptive-hybrid-v1 が control の 113/145 に対して 116/145、wins/losses 5/2、wall ratio 0.9627、safety 0 という provisional signal を示した。しかし holdout qualification ではないため、単独で production champion にはしなかった。

同時に次の候補も検査した。

- multi-target v4：activation 0。
- rank chart：recall loss が繰り返された。
- rank trust-radius：activation はしたが signal なし。
- incremental evaluator：14/24 で、約 13.8% 遅い。
- BTF-polynomial：15/24。
- clean 0967 transplant：15/24 かつ unsafe。
- interval/Krawczyk activation：145 問で 0。
- strict whole-polynomial route：145 問で 0。
- structure/BTF static applicability：27/145 だが side route は 15/24。

この過程から、固定された full-support proposal、soft reservoir、source semantics の独立 replay、HP authority を一緒にする現 champion の形が選ばれた。

### 9.7 champion v0 → v1 → v2

最終 champion は一つのアイデアを突然実装したものではなく、段階的な合成である。

| 世代 | 追加された考え方 |
|---|---|
| champion v0 | target-free endpoint reservoir、residual と configuration breadth、凍結された local work graph |
| champion v1 | 高精度 bridge、512/768 refinement、condition-aware target stability、original exact authority |
| champion v2 | source-exact zero-dimensional bypass と、v1 の positive-dimensional path を変更せず保持 |

その上で、direct-Broyden、near-root strict restart、512/768/1024 HP schedule、PSLQ authority、restoration、PointOnCircle の polar semantics correction、preloaded worker を凍結した。

### 9.8 productization で見つかった native JSON coercion defect

最初の製品 validation は、Pydantic の float | str field に constraint value を通したため、source JSON の整数 4 が 4.0 になった。数学的には同じに見えるが、champion の exact replay authority は native source bytes の SHA を結び付けているため、別 source として拒否した。

修正は solver の threshold、proposal、callback 数、precision、restoration、exact authority を変えずに行った。

- validation は inspection とし、native JSON をそのまま engine へ渡す。
- frozen native thread environment と subprocess limit を復元する。
- source SHA、entrypoint、precision preload、503-file closure を記録する。

修正版 v4 では、145/145 process accepted、timeout/crash 0、seven-lane の exact-set equal 130/145、false/extra 0、one-shot descriptor equal 138/145 だった。欠けた 4 descriptor は unchanged one-core reference isolation で全て再現でき、archive descriptor が isolation 後に未再現になることは 0 だった。つまり、問題は solver の数学的判断ではなく、source serialization と wall scheduling の product boundary にあった。

### 9.9 evaluator と scheduler の最終最適化

最後に、whole-problem fused evaluator の bitwise equivalence を 145 問×725 probes で確認し、6 end-to-end case で descriptor を全保持したまま median 1.4247 倍の speedup を得た。OMC024-F では starts 155→236、safe endpoints 18→24、descriptor [41,-841] root 0 を保持した。

一方、flat native evaluator は microbenchmark だけなら速かったが 4096 ULP 差が出たため棄却した。scheduler corrective patch も checkpoint admission と未使用 search-time の carry-forward だけに限定し、candidate order、HP、restoration、exact authority は変えていない。

## 10. 最終 qualification の結果

現在 src/geotarget/qualification.json に記録された qualification は次の通りである。

| 指標 | optimized | reference / 比較 |
|---|---:|---:|
| case count | 145 | 145 |
| completed | 145 | — |
| failure | 0 | — |
| descriptor set が reference と等しいケース | 140 | — |
| reference descriptor の lost | 0 | — |
| optimized にのみ現れた descriptor | 5 | truth extra は 0 |
| optimized median | 55.6577 s | 136.2816 s |
| optimized p95 | 177.3803 s | 178.1732 s |
| fused differential probes | 725 | mismatch 0 |

「optimized にのみ現れた descriptor 5」と「truth extra 0」は矛盾しない。5 件は reference の一回の bounded run に現れなかった true target であり、truth に対する偽の exact answer ではなかった。lost_reference_descriptor_count=0 は、reference が返したものを optimized が失わなかったことを表す。

qualification には次の追加監査も含まれる。

- optimized と reference の engine hash、実行条件、problem fingerprint。
- fused callback の 725 differential probe。
- scheduler patch が candidate order と HP/restoration authority を保持したこと。
- polar semantic correction 後の ordinary/HP equation の一致。
- correction を preload しない optimized worker が fail closed すること。

最終 engine hash は、

~~~text
224025b3113b59814bd354e8db2e4181cc64faf010f9de0eaf19d4cbe28f1868
~~~

である。reference closure は 503 ファイル、SHA は、

~~~text
9fa23aecdb9372dfd961b46224b88937c3317eaeb56796a05142563f26078f15
~~~

である。選定時の champion freeze には「131/145 exact target sets、extra 0」と記録されている。これは選定時の一回の frozen run と、後日 product optimized qualification の集計単位・scheduler が異なるため、同じ数字として混同してはいけない。

## 11. 研究・実験をどのように進めたか

### 11.1 事前に固定した原則

実験は、数値結果に合わせてルールを後から変えないために、次を固定した。

- clean Git commit、problem manifest、environment、seed、proposal checksum を記録する。
- reference/control と candidate の source、budget、assessor を分ける。
- runtime は case ID、Gold truth、既知 target 数、正解多項式を見ない。
- source evaluator と candidate algorithm を同じコードへ混ぜない。
- 途中で stop した start、failed restoration、pending HP を work として残す。
- 1 回の prefix だけを fixed-budget の成功率と呼ばない。case-total cumulative callback work も比較する。
- 物理的に同じ意味の座標変換、scale、DAG 表現で結果が変わらないかを確認する。

### 11.2 指標を分ける

「見つけた」と「正しい」は別なので、次を別々に集計した。

1. **reported acceptance**：algorithm が内部的に accepted と報告した数。
2. **canonical valid**：元 DSL の construction/domain/guard/branch を replay できる数。
3. **configuration match**：独立 truth/Gold の配置と一致する数（研究の事後 scorer のみ）。
4. **target match**：target value が一致する数。
5. **exact descriptor set equality**：最小多項式＋root index の set が一致するか。
6. **safety**：false exact、guard-invalid、numeric-target-only、ambiguous witness が 0 か。
7. **work**：callback、HP evaluation、wall time、memory、startup を分けたもの。

この区別によって、NearRank のように residual は小さいが configuration が悪い候補や、同じ target を何度も返す候補を、見かけ上の success に数えないようにした。

### 11.3 failure taxonomy

miss analyzer は原因を最初の失敗 checkpoint に分類する。

~~~text
truth
 → reference/plugin semantics
 → compilation
 → sample/capture
 → local solve
 → canonical residual
 → domain
 → guard
 → branch
 → archive
 → scheduler
 → high precision
 → configuration certificate
 → target identity proof
 → output dedup
~~~

この順序は、例えば「target が見つからないから高精度を上げよう」と短絡しないためである。F4 capture、F5 local、F9 singular、F11 scheduler、F12 high precision、F14 identity proof などを causal evidence なしに断定しない。

### 11.4 negative result の扱い

研究 ledger の reproduced は、特定の mechanism、threshold、adapter、budget の bounded rejection である。例えば、

- hard APOSMM-like suppression を default にしない。
- dynamic expression evaluation を production kernel にしない。
- separate dense rank diagnostic で LM/TR を routing しない。
- frozen restarted good-Broyden の同じ S3 設定を再実行しない。
- BigFloat point replay を root validation と呼ばない。
- flat compiled tape の ULP 差を無視して速さだけで採用しない。

という結論が残った。ただし「Trust Region 全体が駄目」「SVD 全体が駄目」という一般定理にはしていない。再開するには、新しい problem family、counterexample、work accounting、metamorphic gate、独立 replay を用意する。

## 12. repository の読み方と再現方法

### 12.1 最初に読むファイル

おすすめの順番は次の通りである。

1. README.md：現在の起動方法と product boundary。
2. CHARTER.md：何を固定し、何を主張しないか。
3. REQUIREMENTS.md：runtime、API、reference/optimized の制限。
4. docs/V15_GEOMETRY_DSL_AUTHORING_MANUAL_ja.md：問題を DSL にする規則。
5. models.py → validation.py → service.py → engine.py：一回の solve の外側。
6. src/geotarget/_engine/product-manifest.json と qualification.json：どの bytes/数値が authority か。
7. experiment ブランチの docs/handoff/2026-07-11/、docs/research/：研究の仮説・失敗・証拠。

### 12.2 ローカルで製品を動かす

README の手順は次の通りである。

~~~bash
uv sync --frozen
pnpm --dir frontend install --frozen
pnpm --dir frontend build

uv run geotarget doctor
uv run geotarget validate examples/problem.json
uv run geotarget solve examples/problem.json --output result.json
uv run geotarget ui
~~~

solve の主な option は次の通りである。

~~~bash
# qualified default
uv run geotarget solve examples/problem.json \
  --engine optimized --run-mode adaptive --max-time 900 --cores auto

# frozen reproduction
uv run geotarget solve examples/problem.json \
  --engine reference --run-mode fixed_time --max-time 180 --cores 1
~~~

参照 engine に cores > 1 を渡しても silent downgrade はしない。reference は 1 core/180 秒固定である。optimized の max-time は 180–900 秒の範囲で、extension の安全上限として使われる。

### 12.3 テスト

Python 側には現在、次の分野を含むテストがある。

- CLI、public model、validation、HTTP、service/cache。
- frozen/optimized manifest、engine identity、deadline、resource coordination。
- compiled/fused/flat evaluator の qualification 境界。
- raw arbitrary precision、deferred scalar tape、lazy symbolic geometry。
- typed RefNum IR、union、intersection、selector、numeric effects。
- HP preloader、runtime broker、checkpoint、cancel。
- PointOnCircle、periodic、nested angle/distance、polar semantic regression。

tests/ には数えて 243 個の test_*/Test 定義がある（実行時の parameterized case 数とは別の数え方）。frontend には App.test.tsx、MathFormula.test.tsx、MathKeyboard.test.tsx、authoring.test.ts、geometry.test.ts があり、UI の式表示・guided authoring・scene evaluation を検証する。

全体の確認コマンドは次の通りである。

~~~bash
uv run ruff check .
PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
pnpm --dir frontend test
pnpm --dir frontend test:sites
pnpm --dir frontend build
~~~

### 12.4 研究 artifact を読む

main の product closure だけを見て研究の全履歴を再構成することはできない。履歴を読む場合は、

~~~bash
git switch experiment
git show champion-v2-poc-preloaded-20260722:experiment-freeze/20260727/README.md
~~~

などで freeze index を開く。raw artifact 本体は ARCHIVE_INVENTORY.json と checksums に従って外部 archive から復元する。main の _engine/runtime/solver/research/ は、製品の provenance と実行に必要な source snapshot だけを含む。

## 13. 現時点での限界と、まだ主張していないこと

### 数学的な限界

- 有限時間の探索なので、no_answer_found は no-solution proof ではない。
- exact_complete は exact authority が completeness を定義した scope に限られる。
- positive-dimensional search では、見つけた target が全 target だとは限らない。
- target の exact descriptor が得られても、全 configuration の証明や根の一意性を自動で主張するわけではない。
- 連続無限解、最適化、整数・組合せ、3D、cloud/distributed solver は scope 外である。

### 数値・実装上の限界

- 悪条件、singular、近接 root、strict guard boundary は特に難しい。residual の小ささだけで forward correctness を保証しない。
- flat native evaluator は speed と bitwise semantics の両方を満たしていないため未採用である。
- reference は 1 core/180 秒の基準で、host の性能が違えば wall time は変わる。
- optimized の adaptive extension は 0-answer 初期 prefix に限られ、完全性の新しい根拠を作らない。
- 大きな raw evidence は main にない。完全な case-by-case replay は外部 archive と実行環境の復元を必要とする。
- UI は構成を作るための workbench であり、自動定理証明器、図の画像認識器、共同編集サービスではない。

### これから研究できる方向

今後の候補は、現在の exact authority と source semantics を変えないという境界の内側で、例えば次を新しい preregistered experiment として調べることである。

- singular/near-root の typed numerical root evidence と interval capability の拡張。
- qualified whole-problem compiler の適用範囲拡大。ただし bitwise differential と end-to-end gate が必須。
- candidate reservoir の soft scheduling、configuration diversity、deferred work の経済性。
- 未知の geometry family に対する holdout と metamorphic robustness。
- 起動・preload・serialization overhead の削減。ただし candidate order と fixed work prefix は保存する。

## 14. 用語集

| 用語 | 初心者向けの意味 |
|---|---|
| scalar | 長さや角度のような一つの数。点の x/y は二つの scalar |
| configuration | 自由変数を具体的な数にした一つの図形配置 |
| residual | 条件からどれだけ外れているか。等式なら左辺−右辺 |
| guard | 点の順序、内外、非退化、branch など、残差 0 だけでは表せない条件 |
| construction | 前の object から次の点・線・円を作る式 |
| DAG | 依存関係に循環がない有向グラフ。V15 の construction の実行順 |
| multistart | 初期値を複数変えて同じ局所 solver を何度も走らせる方法 |
| basin | 近い初期値が同じ root へ収束する領域 |
| Jacobian | 入力を少し動かしたとき各 residual がどう変わるかの行列 |
| LM | Levenberg–Marquardt。Newton/Gauss–Newton の step を damping する方法 |
| Trust Region | 局所モデルを信用する半径内だけ step を許す方法 |
| Broyden | 毎回 Jacobian を作らず、前回の情報から rank-one 更新する方法 |
| CPQR/SVD | rank deficiency や悪条件を調べながら線形 subproblem を解く分解 |
| Ruiz scaling | 行と列を再スケールして線形代数を扱いやすくする前処理 |
| high precision | Float64 より多い bit 数で計算し、丸め誤差を減らすこと |
| PSLQ | 高精度な数値から整数係数の関係（多項式）を見つける方法 |
| minimal polynomial | 代数的数を根に持つ、primitive/irreducible な最小多項式 |
| isolating interval | 目的の実根だけを含む区間 |
| descriptor | 多項式・root index・区間・小数を組にした exact answer の表現 |
| replay | 同じ source DSL を独立評価して候補を再確認すること |
| target-free | discovery/admission の段階で既知の正解値を使わないこと |
| reservoir | HP に送る候補を一時保持する場所。residual と configuration breadth を見る |
| canonical | 問題の意味を変えない、正規の source evaluator/descriptor 表現 |
| truth/Gold | 研究の事後評価用の期待解。runtime の判断には入れない |
| holdout | 実験者が結果を見て調整できない検証用データ |
| metamorphic test | 座標変換・scale・同値表現を変えて結果が保たれるかを見るテスト |
| fail closed | 不確かな候補を答えとして出さず、unknown/error にすること |
| qualification | correctness、safety、performance、determinism の release gate |

## 15. まとめ

この repository の中心的な研究成果は、単に「非線形 solver を速くした」ことではない。より正確には、

1. 幾何の意味を壊さず少数の自由変数へ落とす V15 DSL。
2. local convergence と global target discovery を分離した deterministic multistart。
3. residual の小ささだけに依存しない canonical replay、candidate reservoir、configuration-aware admission。
4. 512/768/1024-bit の独立高精度 replay と、PSLQ・root isolation による exact target descriptor。
5. reference を immutable authority とし、compiled/fused/parallel/adaptive を同値性の gate 付きで追加する product boundary。
6. false answer を出さないこと、no-answer を no-solution と呼ばないこと、研究上の negative result を過大一般化しないこと。

を一つの実行可能な workflow として閉じた点にある。

その結果、現在の GeoTarget は「入力された有限解の V15 幾何問題から、bounded search の範囲で、独立した高精度・代数的 authority が確認できた target descriptor を返す Linux-local product」として、実装・テスト・研究履歴・限界のすべてを追跡できる状態になっている。

