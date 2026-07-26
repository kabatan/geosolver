# 旧v15幾何DSL 問題作成仕様・変換マニュアル

## 0. この文書の目的

この文書は、2次元ユークリッド幾何の問題を、旧v15数理最適化solver用のJSON DSLへ変換するための自己完結した仕様書である。読者がsolverのsource code、既存benchmark、補助script、repository内の別文書を参照できないことを前提とする。

このDSLは、問題文をそのまま多数の自由座標へ展開するためのものではない。少数の自由scalarをdriverとし、問題文に記された作図順序に沿って点・直線・円などを順次再構成する、低次元の実行parameterizationである。

本書で用いる規範語は次の意味を持つ。

- **必須**：満たさないファイルは受理しない。
- **禁止**：構文上動く場合があっても、新しい問題には使用しない。
- **推奨**：特別な理由がなければ従う。
- **条件付き**：明記された前提、意味監査、通常精度・高精度のreplay確認をすべて満たす場合だけ使用できる。

最も重要な優先順位は次である。

1. 元問題の意味を完全に保存する。
2. ほとんどすべての探索parameterでconstructionと残差を評価可能にする。
3. 自由変数数を小さくする。
4. 数値条件、式の大きさ、branch数を改善する。

低次元化のために元問題を非自明に言い換えることは、いかなる場合も認めない。

---

## 1. まず問題を選定する

### 1.1 受理する問題の必須条件

次の全条件を満たす問題だけをDSLへ変換する。

1. **純粋な2次元ユークリッド幾何である。**
   - 点、直線、線分、半直線、円、円弧、多角形を扱う。
   - 距離、長さ、角、面積、周長、所属、交点、接線、平行、垂直、順序、内外、凸性などのユークリッド幾何条件で記述できる。
   - 固定された整数・有理数・代数的数・角度定数を条件に使うことはよい。

2. **解となる幾何配置が有限個である。**
   - 平面全体の平行移動と回転だけを座標gaugeとして除いた後、labelを保った幾何配置が有限個でなければならない。
   - 鏡映、二交点、左右の接線などの有限branchは残っていてよい。
   - scaleは勝手に除去しない。長さを決める条件がなく、相似拡大で連続無限個の配置が生じる問題は不採用である。
   - 配置が連続無限個だが、偶然targetだけ一定になる問題も不採用である。

3. **求めるものが単一の幾何scalarである。**
   - 例：長さ、距離、角、半径、面積、周長、長さの比、これらからなるscalar式。
   - 有限個の配置から複数のdistinct target値が生じてもよい。solverはその有限集合を探索対象とする。

4. **問題文の全条件、branch、非退化条件、targetを、このDSLで意味保存して表現できる。**
   - 「図から見ればこちら側」など、言語化されていない図依存のbranchしかない問題は、そのままでは不採用である。
   - 交点選択を`exclude`、`near`、`far`、順序条件などの幾何predicateで明示できなければならない。

### 1.2 除外する問題

次のいずれかに該当する問題は変換しない。

- 最大化、最小化、最大値、最小値、最適配置を求める問題。
- `task: "optimize"`を必要とする問題。
- 解配置が連続無限個のlocus問題、可動図形問題、任意parameterを残す問題。
- 整数性、素数性、有理数性、格子点、偶奇、個数、組合せ条件が本質的に入る問題。
- 「辺長が整数」「面積が素数」「x座標が有理数」など、純粋な連続2D幾何ではない条件を含む問題。
- 確率、物理、速度、時間、質量、力、rolling、動力学などを含む問題。
- 3次元幾何、球面幾何、双曲幾何、射影空間そのものを対象とする問題。
- 証明だけを要求し、単一のscalar targetを持たない問題。
- 配置数を数える問題。DSLの`answer`は一つの配置からscalarを評価する式であり、全配置のcardinalityを返す演算ではない。
- source条件を保ったまま有限branchを表現できない問題。

実装上は`IsInteger`や`IsPrime`という関数が存在するが、本コーパスの問題選定基準に反するため使用禁止である。

### 1.3 有限解判定の実務手順

問題を採用する前に、次を順番に確認する。

1. label付きの代表点`A`を原点へ置き、別の保証された相異なる点`B`をx軸上へ置く。
2. これで除かれるのは平行移動2自由度と回転1自由度だけである。
3. sourceの条件と作図をすべて適用した後、自由な連続parameterが残るかを確認する。
4. scaleを固定する条件がsourceに存在するかを確認する。
5. 鏡映や交点選択が有限branchとして残るのは許容する。

次の例は不採用である。

- 角度しか与えられていない三角形：scaleが自由。
- 円上の任意点`P`について一定値を示す問題：`P`が連続自由。
- 「周長一定の三角形の面積を最大化」：最適化問題。
- targetが常に`1`だが、関係のない自由点が残る問題：配置が無限。

---

## 2. 絶対原則：意味保存を低次元化より優先する

### 2.1 許される低次元化

低次元化は、次のようなsourceの直接的な作図・定義・対称性だけを使う。

- 平行移動と回転の座標gauge。
- 「`D`は線分`BC`上」のような、sourceに明記されたcarrier上の1変数parameterization。
- sourceが直接「中点」「垂足」「内心」「外心」「平行線」「垂線」などとして定義したobjectのconstruction化。
- sourceが直接「二直線の交点」「既知点ではないもう一方の交点」と定義したobjectのconstruction化。
- sourceの順序どおりに作図DAGを組み、後続objectを前のobjectから計算すること。
- sourceが定義的に一意なobjectを与えており、その一意性とbranchが明白な場合のconstruction化。

これらは、問題を解いているのではなく、sourceが既に与えた構成写像を実行表現へ移しているだけである。

### 2.2 禁止される非自明な言い換え

次は、たとえ数学的に正しく見えても禁止する。

- 角の二等分線条件を角の二等分線定理による辺比へ置き換える。
- 接線条件を方べき、接弦定理、反転、相似などで別の式へ置き換える。
- 円に内接する条件をPtolemyの定理だけへ置き換える。
- 問題文にない相似、homothety、共円、根軸、極・極線などを発見し、それを主表現にする。
- targetの公式を先に導き、その公式を満たすscalarだけを解く。
- 既知の答え、offline truth、図の見た目を使ってbranchを選ぶ。
- 「この図ではいつもこうなる」というcase固有の性質で点や条件を削除する。
- 元問題の条件を、同値証明を伴わない別条件へ差し替える。
- sourceでは任意の接円なのに、三角形を作って`Incircle`や`Excircle`として扱う。

#### 良い例

source：

> `D`は`BC`上にあり、`AD`は`∠BAC`の内角二等分線である。

sourceの定義順序を直接使う表現：

```text
bisector_A = AngleBisector(B, A, C)
D = Intersect(Line(B, C), bisector_A)
guard: AssumeEq(OnSegment(D, B, C), 0)
```

#### 悪い例

角の二等分線定理を持ち込み、

```text
BD / DC = AB / AC
```

から`D`を直接比で配置する。これはsourceの作図を写したのではなく、変換者が定理を適用して問題を言い換えている。

### 2.3 clause ledgerを先に作る

JSONを書く前に、次の表を作る。これはJSON外の変換監査記録である。

| clause ID | 元問題の文 | DSL上の場所 | 種類 | branch・退化の扱い |
|---|---|---|---|---|
| C01 | `AB=5` | `B = Point(5,0)` | gauge＋given | scaleはsourceの5で固定 |
| C02 | `AC=7` | constraint 0 | equality | なし |
| C03 | `D`は`BC`上 | construction＋guard | construction/order | `B-D-C` |
| T01 | `BD`を求める | `answer` | target | scalar |

必須条件は次である。

- sourceの全条件が少なくとも1か所へ対応する。
- DSLだけに存在する条件には、gauge、definedness、sourceからの直接導出のいずれかの説明がある。
- branch selectorの根拠を明記する。
- targetを導く定理や答えを変換に使わない。

---

## 3. DSLの全体構造

### 3.1 推奨する正規形

新しい問題は次の形で記述する。

```json
{
  "id": "UNIQUE_PROBLEM_ID",
  "task": "solve",
  "variables": {
    "names": ["u", "v"]
  },
  "construction": [
    {
      "name": "A",
      "expr": "Point(0, 0)"
    }
  ],
  "constraints": [
    {
      "def": "some_scalar_expression",
      "value": 0
    }
  ],
  "guards": [
    "some_guard_expression"
  ],
  "answer": "single_scalar_expression",
  "post_process": ""
}
```

JSONにはcomment、末尾comma、single-quoted JSON stringを使用できない。DSL式そのものはJSON stringの中へ書く。

### 3.2 top-level field

| field | 必須 | 型 | 意味 |
|---|---:|---|---|
| `id` | 必須 | string | 問題の一意識別子 |
| `task` | 必須 | string | 必ず`"solve"` |
| `variables` | 必須 | object | optimizerが直接探索する自由scalar |
| `construction` | 必須 | array | 上から順に評価される定義DAG |
| `constraints` | 必須 | array | equality残差 |
| `guards` | 必須 | array | source branch、順序、不等式、非退化条件 |
| `answer` | 必須 | string | 副作用のない単一scalar式 |
| `post_process` | 必須 | string | 必ず空文字`""` |
| `bounds` | 原則省略 | array | optimizer探索範囲。通常は書かない |

### 3.3 使用禁止の互換field

parserが受理する場合があっても、新規問題では次を使わない。

- `variables.n`
- `variables.bounds`
- `m`
- top-level `v`
- `objective`
- `maximize`
- `task: "optimize"`
- 非空の`post_process`
- 未定義の独自field

`post_process`でround、int変換、複数解のsum、既知形式への加工を行ってはならない。target authorityは`answer`の純粋scalar式だけである。

---

## 4. 自由変数とconstruction

### 4.1 `variables.names`

```json
"variables": {
  "names": ["Cx", "Cy", "tD"]
}
```

- 各要素はscalar自由変数である。
- optimizer次元は、このlistの長さそのものである。
- 名前は`[A-Za-z_][A-Za-z0-9_]*`に従う。
- 同名を重複させない。
- construction名、関数名、`pi`、`sqrt`などと衝突させない。
- 点を自由にする場合は通常`Px`, `Py`の2scalarを使う。
- ただし点がcarrier上にあるなら、まず1parameter表現を検討する。

### 4.2 `construction`

```json
"construction": [
  {"name": "A", "expr": "Point(0, 0)"},
  {"name": "B", "expr": "Point(5, 0)"},
  {"name": "line_AB", "expr": "Line(A, B)"},
  {"name": "D", "expr": "PointOnLine(line_AB, tD)"}
]
```

- 上から順に評価される。
- 各`expr`は自由変数と、それ以前に定義されたconstructionだけを参照できる。
- forward referenceは禁止。
- `name`は一意のidentifierにする。
- constructionは新しいoptimizer自由度を追加しない。
- constructionが失敗すると、そのparameter点で後続のconstraints、guards、answerも評価できない。
- sourceで決定的に定義されたobjectを自由座標に戻してはならない。

### 4.3 constructionとconstraintの違い

```text
M = Midpoint(A, B)
```

は、`M`を`A`,`B`から常に計算するconstructionであり、自由変数を増やさない。

一方、

```text
M = Point(Mx, My)
Distance(A,M) = Distance(M,B)
OnSegment(M,A,B) = 0
```

は`M`を2自由度にしてoptimizerへ解かせる。sourceが`M`を中点として定義しているなら冗長である。

---

## 5. constraints、guards、answer

### 5.1 constraints

推奨形式は次である。

```json
{
  "def": "Distance(A, B)",
  "value": 5
}
```

これは、

```text
Distance(A,B) - 5 = 0
```

を意味する。

`value`はJSON数値、またはscalar DSL式を表すstringにできる。

```json
{
  "def": "Distance(A, B)",
  "value": "3*sqrt(13)"
}
```

左右とも幾何式である場合も書ける。

```json
{
  "def": "Distance(A, B)",
  "value": "Distance(C, D)"
}
```

また、stringだけを置いた場合はtarget値`0`のconstraintになる。

```json
"constraints": [
  "Parallel(Line(A,B), Line(C,D))"
]
```

ただし可読性と監査性のため、object形式を推奨する。

#### constraint作成規則

- equalityはconstraintへ置く。`AssumeEq`だけにしない。
- residualはscalarでなければならない。
- arbitraryな二乗、巨大な係数、answerを知った上での重み付けをしない。
- `lhs=rhs`を表すために、分母が0になり得る比へ変形しない。
- sourceが長さ equalityなら`Distance(...)=Distance(...)`のまま書く。
- sourceが平行なら`Parallel(...)=0`のまま書く。

### 5.2 guards

guardsは、sourceが要求する不等式、順序、branch、非退化条件をcandidateへ課す。

```json
"guards": [
  "Bound(tD, (0, 1))",
  "AssumeNe(Area(A, B, C), 0)",
  "AssumeEq(OnSegment(D, B, C), 0)"
]
```

重要事項：

- guardsは主にcandidateを除外するものであり、equality solverを導く主残差ではない。
- sourceの主要equalityをguardだけへ移さない。
- constructionはguardより先に評価される。壊れたconstructionを後のguardで救うことはできない。
- 図の見た目だけを根拠に`AssumeGt(Cy,0)`などを追加しない。
- sourceが明示した側、順序、内外、acuteなどだけを書く。

### 5.3 answer

```json
"answer": "Distance(B, D)"
```

- 単一のscalar式でなければならない。
- `Point`、`Line`、`Circle`、listを返してはならない。
- sourceが角度をdegreeで問う場合だけ、`Angle(...)*180/pi`としてよい。
- rounding、integer cast、format変換を入れない。
- `post_process`は必ず空にする。

---

## 6. 式の文法

### 6.1 許される基本文法

DSL式は、制限されたPython expression syntaxを使う。

使用できる主な要素：

- 整数・decimal数値・string・`True`・`False`・`None`
- `+`, `-`, `*`, `/`, `**`
- unary `+`, unary `-`, `not`
- `<`, `<=`, `>`, `>=`, `==`, `!=`
- `and`, `or`
- `x if condition else y`
- 関数呼び出し
- keyword argument
- tuple、list
- attribute access
- subscript、slice

`//`と`%`はparser上の互換構文として受理され得るが、離散的・不連続な意味を導入するため新規問題では使用禁止である。`**`は原則として整数冪に使う。条件式`x if condition else y`や`and`/`or`も、sourceに明示された有限branch・論理条件を忠実に表す場合だけ使い、数値的なcase分けを変換者が追加する目的には使わない。

### 6.2 禁止されるもの

- assignment、loop、comprehension、lambda
- import
- arbitrary callback
- file操作
- `eval`, `exec`, `open`
- `__`を含むattribute
- class定義、関数定義
- solver runtimeやbackendの操作

### 6.3 JSON string内のquote

外側がJSONのdouble quoteなので、DSL内のstring keywordにはsingle quoteを使う。

```json
{"name": "I_A", "expr": "Excenter(A, B, C, vertex='A')"}
```

式の中ではPython spellingを使う。

```text
True, False, None
```

top-level JSONではJSON spellingを使う。

```text
true, false, null
```

### 6.4 数値literal

厳密値には整数、分数式、根号、`pi`を使う。

推奨：

```text
1/3
sqrt(2)
3*sqrt(13)
pi/6
17*pi/180
```

非推奨：

```text
0.333333333333
1.41421356237
0.5235987756
```

decimal literalは数値近似として扱われ得る。sourceがdecimal近似を明示した場合を除き、厳密な分数・代数式を使用する。

### 6.5 angleの単位

すべてradianである。

```text
30 degrees = pi/6
90 degrees = pi/2
```

---

## 7. 低次元parameterizationの作り方

### 7.1 自由度の目安

| object | 素朴な自由度 | 推奨表現 |
|---|---:|---|
| 自由Point | 2 | `Point(x,y)` |
| 自由Line | 2 | Hesse型または既知点＋方向 |
| 自由Circle | 3 | center 2＋radius 1 |
| 直線上のPoint | 1 | `PointOnLine` |
| 線分上のPoint | 1 | `PointOnSegment`＋`Bound` |
| 円周上のPoint | 1 | `PointOnCircle` |
| sourceで一意な作図点 | 0 | construction |
| 二直線の正則交点 | 0 | `Intersect` |

多くの問題で自由変数6以下を目標にする。ただし、意味保存やほぼ至る所での評価可能性を壊してまで6以下へ押し込まない。

### 7.2 SE(2) gauge

sourceとtargetが平行移動・回転で不変であり、`A != B`がsourceから保証される場合、

```text
A = Point(0,0)
B = Point(s,0)
```

と置ける。

- `AB=L`がsourceで既知なら`B=Point(L,0)`。
- `AB`が未知なら`s`は自由変数として残し、`AssumeGt(s,0)`でorientationを定められる。
- `B=Point(1,0)`としてscaleまで固定することは禁止。sourceが`AB=1`と与えている場合だけよい。
- 鏡映は自動では除かない。`Cy>0`を図から追加しない。

### 7.3 線分上の点

#### 悪い表現

```json
"variables": {"names": ["Dx", "Dy"]},
"construction": [
  {"name": "D", "expr": "Point(Dx, Dy)"}
],
"constraints": [
  {"def": "OnSegment(D, B, C)", "value": 0}
]
```

`D`に2自由度を与え、solverへ線分所属まで解かせている。

#### 良い表現

```json
"variables": {"names": ["tD"]},
"construction": [
  {"name": "D", "expr": "PointOnSegment(B, C, tD)"}
],
"guards": [
  "Bound(tD, (0, 1))"
]
```

`D=(1-tD)B+tD C`であり、sourceの「線分上」を直接parameter化している。

- 閉線分なら`inclusive=True`のdefaultを使う。
- 開線分なら`Bound(tD,(0,1),inclusive=False)`。
- 半開区間は`Bound`一つでは表せない。必要なら片側を別guardで表す。

### 7.4 直線上の点

```json
{"name": "D", "expr": "PointOnLine(line_BC, tD)"}
```

`tD`は実数全体であり、sourceに区間指定がなければ`Bound`を付けない。

### 7.5 円周上の点

```json
{"name": "P", "expr": "PointOnCircle(omega, tP)"}
```

`tP`は1周を`1`とするperiodic parameterである。

- 全円を覆うには、unboundedのままでもよい。
- canonicalな1周期を示したい場合は`Bound(tP,(0,1))`を使える。
- `(0,1)`の開区間にすると`tP=0`の円周点を失うため、sourceがその点を除外していない限り禁止。
- `[0,1]`は同じendpointを二重に含むが、意味は失わない。

### 7.6 半直線上の点

`PointOnRay`という関数は存在しない。sourceが`A`を始点として`B`方向の半直線上に`P`を置く場合、

```json
{
  "name": "P",
  "expr": "Point(A.x + sP*(B.x-A.x), A.y + sP*(B.y-A.y))"
}
```

とし、

```json
"AssumeGe(sP, 0)"
```

を加える。`A != B`が必要である。open rayなら`AssumeGt(sP,0)`。

### 7.7 自由直線

自由直線を係数`a,b,c`の3変数で作るとscale重複がある。次の2変数chartを使える。

```text
Line(cos(theta), sin(theta), -rho)
```

これは、

```text
cos(theta)*x + sin(theta)*y - rho = 0
```

を表す。`theta`はperiodicであり、`(theta,rho)`と`(theta+pi,-rho)`が同じ直線を表す二重被覆を持つ。

既知点`P`を通る自由直線なら1変数にできる。

```text
Line(P, Point(P.x + cos(theta), P.y + sin(theta)))
```

### 7.8 自由円

自由円は通常、centerの2変数とradiusの1変数である。

悪い例：

```text
C = Circle(Point(cx,cy), r)
guard: AssumeGt(r,0)
```

constructionはguardより先に評価されるため、`r<0`の探索点では`Circle`が失敗する。

評価域を広く保つ例：

```text
C = Circle(Point(cx,cy), abs(r_raw))
guard: AssumeGt(abs(r_raw),0)
```

または、

```text
C = Circle(Point(cx,cy), r_raw**2)
guard: AssumeNe(r_raw,0)
```

どちらも全正半径を覆うが、前者は`0`で非滑らか、後者は`0`で導関数が消える。問題に応じて選ぶ。radiusに根拠のない上限を付けない。

### 7.9 sourceで決まるobject

#### 悪い例

```text
M = Point(Mx,My)
constraints:
  OnSegment(M,A,B)=0
  Distance(A,M)=Distance(M,B)
```

#### 良い例

sourceが`M`を中点として定義しているなら、

```text
M = Midpoint(A,B)
```

sourceが`Gamma`を`ABC`の外接円として定義しているなら、

```text
Gamma = Circumcircle(A,B,C)
```

ただし、変換者が途中で「実はこの円は外接円だ」と発見しただけなら使用禁止である。

### 7.10 交点の完全消去とone-slack表現

二直線の交点は、非平行例外が通常measure zeroなのでconstructionにしやすい。

```text
P = Intersect(line_1, line_2)
```

一方、自由な二円の交点は、交わらないparameter領域が正のmeasureを持ち得る。次の完全消去は、探索域の大部分でconstructionを未定義にする可能性がある。

```text
P = Intersect(c1, c2, near=Q)
```

その場合は、変数が1個増えても次を優先する。

```text
P = PointOnCircle(c1, tP)
constraint: OnCircle(P,c2)=0
guard: Bound(tP,(0,1))
```

これは`P`を一方の円上で常に再構成し、他方への所属だけをoptimizerへ残す。低次元化は、評価可能域を正のmeasureで失う完全消去より優先されない。

---

## 8. boundsの方針

### 8.1 top-level `bounds`は原則書かない

次のようなboundsを、単なる探索上の都合で追加してはならない。

```json
"bounds": [
  [-100, 100],
  [-100, 100],
  [0, 50]
]
```

座標や半径の真の範囲がsourceから自明でない限り、この範囲はvalidな解を削除し得る。boundsはperformance hintではなく、探索対象を切り取る意味変更になり得る。

特に禁止するもの：

- `x,y`座標への任意の`[-10,10]`、`[-100,100]`。
- radiusへの任意の上限。
- angle parameterへの、sourceやperiodicityに基づかない区間。
- 既知解が入るように後から調整したbounds。

### 8.2 parameterの自然domainには`Bound` guardを使う

次は適切である。

```text
Bound(t_segment,(0,1))
Bound(t_arc,(0,1))
Bound(t_circle,(0,1))
```

これは座標を推測で切るのではなく、parameterizationそのものの自然domainを宣言している。

### 8.3 top-level `bounds`の互換構文

やむを得ずsourceが自由scalarの明示的数値区間を与える場合だけ、次の構文を使える。

全変数へ同じ範囲：

```json
"bounds": [-5, 5]
```

変数ごと：

```json
"bounds": [
  [-5, 5],
  null,
  [0, 1]
]
```

各区間は`lo < hi`でなければならない。ただし新規幾何問題では、通常このfield自体を省略する。

---

## 9. evaluation-definedなconstructionを作る

solverにとって重要なのは、解そのものが少数であることだけではない。自由変数`x`を与えたとき、ほとんどすべての`x`で全objectを再構成し、全残差とtargetを有限値として評価できることが重要である。

### 9.1 主な未定義条件

| operation | 未定義・危険な条件 |
|---|---|
| `Line(A,B)` | `A=B` |
| `Circle(O,r)` | `r<0` |
| `Angle(A,B,C)` | `A=B`または`C=B` |
| `Circumcircle(A,B,C)` | 3点が共線 |
| `Circumcenter(A,B,C)` | 3点が共線 |
| `Orthocenter(A,B,C)` | 3点が共線 |
| `PointOnLine(line,t)` | `line`が未定義 |
| `Intersect(line1,line2)` | 平行・一致 |
| `Intersect(line,circle)` | 実交点が存在しない場合 |
| `Intersect(circle1,circle2)` | 離れている、包含、同心など |
| `Pole(line,circle)` | 分母が0になる場合 |
| `TangentLine(P,circle)` | `P`が円内部、またはbranch不明 |
| `sqrt(expr)` | `expr<0` |

### 9.2 guardはconstruction failureより後

次は不十分である。

```text
Gamma = Circumcircle(A,B,C)
guard: AssumeNe(Area(A,B,C),0)
```

`A,B,C`が共線の探索点では、guardを評価する前に`Gamma`が失敗し得る。ただし共線集合がmeasure zeroであり、source上も非退化三角形なら実用上許容できる場合がある。

一方、自由二円が交わらない領域のように、正のmeasureで失敗するconstructionはprimary chartにしない。

### 9.3 hidden nonlinear solveは禁止

construction内で一般非線形方程式を数値的に解いてobjectを作ってはならない。許されるのは、DSLに用意された明示作図、一般的な低次数交点、直接式だけである。

---

## 10. branchと順序を保存する

### 10.1 鏡映

`A=(0,0), B=(L,0)`と置いても、x軸に関する鏡映は残る。

sourceが「`C`は有向直線`AB`の左側」などを明示していないのに、

```text
AssumeGt(Cy,0)
```

を追加してはならない。diagram上で上側に描かれているだけでは根拠にならない。

### 10.2 交点selector

推奨順位は次である。

1. `exclude=known_point`
2. `near=reference_point`または`far=reference_point`
3. branchを消さず、carrier parameter＋constraintで表す
4. `n=...`は使用しない

`n`は内部の交点list順に依存する1始まりindexであり、幾何的意味を持たない。

#### other intersection

source：

> 直線`l`と円`omega`は`A`でも交わる。もう一方の交点を`B`とする。

```text
B = Intersect(l, omega, exclude=A)
```

#### near/far

sourceが明示的に「`Q`に近い方」と言っている場合だけ、

```text
P = Intersect(c1, c2, near=Q)
```

を使う。tie時の意味がsourceで定まらないなら、問題自体を再確認する。

### 10.3 順序

legacy構文`AssumeOrder(A,P,B)`は`A-P-B`、すなわち`P`が`A`,`B`の間という意図を持つ。しかし高精度guard replayとの互換問題があるため、新規問題では使用しない。

点が線分上であることは、driver pointなら`PointOnSegment(A,B,t)`＋`Bound`、constructed pointのreplayなら次を使う。

```text
AssumeEq(OnSegment(P,A,B),0)
```

`OnLine(..., ordered=True)`も引数順が直感的でないため使用しない。

---

## 11. 完全な作成例

### 11.1 元問題

> 三角形`ABC`において、`AB=5`, `AC=7`, `BC=8`とする。  
> `D`は`∠BAC`の内角二等分線と線分`BC`の交点である。  
> `BD`を求めよ。

この問題は、平行移動・回転を除けば鏡映を含む有限個の配置しか持たず、純粋な2Dユークリッド幾何であり、targetはscalar長さなので採用できる。

### 11.2 推奨DSL

```json
{
  "id": "MANUAL_ANGLE_BISECTOR_EXAMPLE",
  "task": "solve",
  "variables": {
    "names": ["Cx", "Cy"]
  },
  "construction": [
    {
      "name": "A",
      "expr": "Point(0, 0)"
    },
    {
      "name": "B",
      "expr": "Point(5, 0)"
    },
    {
      "name": "C",
      "expr": "Point(Cx, Cy)"
    },
    {
      "name": "line_BC",
      "expr": "Line(B, C)"
    },
    {
      "name": "bisector_A",
      "expr": "AngleBisector(B, A, C)"
    },
    {
      "name": "D",
      "expr": "Intersect(line_BC, bisector_A)"
    }
  ],
  "constraints": [
    {
      "def": "Distance(A, C)",
      "value": 7
    },
    {
      "def": "Distance(B, C)",
      "value": 8
    }
  ],
  "guards": [
    "AssumeNe(Area(A, B, C), 0)",
    "AssumeEq(OnSegment(D, B, C), 0)"
  ],
  "answer": "Distance(B, D)",
  "post_process": ""
}
```

### 11.3 この例が低次元かつ意味保存である理由

- `A=(0,0)`と`B=(5,0)`は、sourceの`AB=5`を使った平行移動・回転gaugeである。
- scaleを勝手に`1`へ固定していない。
- `C`だけが自由点なので2変数である。
- `D`はsourceが直接定義した内角二等分線と`BC`の交点として再構成する。
- `AssumeEq(OnSegment(D,B,C),0)`で「線分`BC`上」をreplayする。
- 角の二等分線定理による辺比へ言い換えていない。
- 鏡映branchを`Cy>0`で削除していない。
- coordinate boundsを設定していない。

### 11.4 冗長な悪い表現

```text
variables = Ax,Ay,Bx,By,Cx,Cy,Dx,Dy
A = Point(Ax,Ay)
B = Point(Bx,By)
C = Point(Cx,Cy)
D = Point(Dx,Dy)

constraints:
  Distance(A,B)=5
  Distance(A,C)=7
  Distance(B,C)=8
  OnSegment(D,B,C)=0
  Angle(B,A,D)=Angle(D,A,C)
```

これは平面剛体対称性も、sourceが与えた`D`の構成も使わず、8変数にしている。

### 11.5 非自明に言い換えた悪い表現

```text
D = PointOnSegment(B,C,5/(5+7))
```

これは角の二等分線定理を変換者が適用したものであり禁止である。正しい答えを返しても、sourceの意味を忠実に実行したDSLではない。

---

## 12. 幾何object constructorの完全リファレンス

この節以降のstatus：

- **推奨**：新規問題で通常使用できる。
- **条件付き**：sourceが直接要求し、定義域・branch・通常精度と高精度のreplayを確認した場合だけ使う。
- **禁止**：新規authoring profileでは使わない。

### 12.1 `Point`

```text
Point(x, y) -> Point
```

- 2次元点。
- attribute：`.x`, `.y`
- 点はvectorとして`+`, `-`, scalar倍、scalar除算を行える。

例：

```text
A = Point(0,0)
P = Point(A.x + t*(B.x-A.x), A.y + t*(B.y-A.y))
```

status：**推奨**

### 12.2 `Line`

```text
Line(P, Q) -> Line
Line(a, b, c) -> Line
```

第二形式は`a*x+b*y+c=0`。

- `Line(P,Q)`には`P != Q`が必要。
- `(a,b)`は同時に0であってはならない。
- 係数は内部で`a^2+b^2=1`となるよう正規化される。
- 直線の符号はcanonicalではない。endpointを逆にすると`a,b,c`の符号が反転し得る。
- attribute：`.a`, `.b`, `.c`
- 係数そのものをtargetにしない。

status：**推奨**

### 12.3 `Circle`

```text
Circle(center, radius) -> Circle
```

- `center`はPoint。
- `radius >= 0`がconstruction時に必要。
- attribute：`.center`, `.radius`

status：**推奨**

### 12.4 `Segment`

```text
Segment(A, B) -> Segment
```

- attribute：`.p1`, `.p2`
- 長さは`Length(Segment(A,B))`。
- `A=B`でもconstructor自体は作れるが、sourceの非退化条件に従う。

status：**推奨**

### 12.5 `Ray`

```text
Ray(A, B) -> Ray
```

- 始点`A`から`B`方向の半直線。
- `A != B`が必要。
- attribute：`.start`, `.through`
- `PointOnRay`や一般的なray membership関数はないため、実用上は明示parameter式を推奨する。

status：**条件付き**

### 12.6 `Arc`

```text
Arc(circle, A, B)
Arc(circle, A, B, including=P)
Arc(circle, A, B, excluding=P)
```

- `A`,`B`をendpointとする`circle`上の円弧。
- `including`と`excluding`は同時指定できない。
- `A`,`B`,`P`がcircle上にあることはconstructorだけでは検証されない。source constructionまたはconstraintで保証する。
- attribute：`.circle`, `.start`, `.end`, `.including`, `.excluding`, `.center`, `.radius`
- sourceがmajor/minor arcや特定点を含む弧を区別するならselectorを必須にする。

status：`Midpoint(Arc(...))`やarc intersectionは**条件付き**。`PointOnArc`は後述の理由で新規使用禁止。

### 12.7 `Polygon`

```text
Polygon([A, B, C, D]) -> Polygon
```

- 必ず1個のlistを渡す。`Polygon(A,B,C)`ではない。
- 3頂点以上。
- attribute：`.vertices`, `.edges`, `.area`, `.perimeter`
- 通常精度と高精度でobject representationが異なるため、attributeをanswerやconstraintで直接使うことは避ける。
- 面積は`Area(A,B,C,D)`、周長はDistanceの和を推奨する。
- 凸性guardには`AssumeConvex([A,B,C,D])`のようにlistを直接渡す方が安全。

status：**条件付き**

---

## 13. 測定・vector・基本関係の完全リファレンス

### 13.1 `Distance`

```text
Distance(P, Q) -> Scalar
Distance(P, line) -> Scalar
Distance(line, P) -> Scalar
Distance(P, circle) -> Scalar
Distance(circle, P) -> Scalar
```

- Point–Point：通常距離。
- Point–Line：垂直距離。
- Point–Circleは通常精度backendには存在し、**中心までの距離ではなく、円周までの絶対距離**を返す。
- ただし高精度replay側にPoint–Circle signatureがないため、新規問題では使用禁止。円周までの距離は次の高精度互換な式で書く。

```text
abs(Distance(P, Center(circle)) - Radius(circle))
```

- 円の中心までなら`Distance(P, Center(circle))`。
- Line–Line、Circle–Circleは未対応。
- `Distance(P)`という原点距離の互換形は通常精度と高精度のsignatureが一致しないため使用禁止。`Distance(P,Point(0,0))`と書く。

status：Point–PointとPoint–Lineの2引数形は**推奨**。Point–Circleは**禁止**。

### 13.2 `Midpoint`と`midpoint`

```text
Midpoint(A, B) -> Point
Midpoint(circle) -> Point
Midpoint(arc) -> Point
midpoint(A, B) -> Point
```

- 2点の中点。
- `Midpoint(circle)`はcenter。
- `Midpoint(arc)`は選択された弧の中点。
- lowercase `midpoint`は2点専用の互換alias。新規問題ではuppercaseへ統一する。

status：2点・circleは**推奨**。arcは**条件付き**。

### 13.3 `Center`

```text
Center(circle) -> Point
Center(arc) -> Point
```

status：**推奨**

### 13.4 `Angle`

```text
Angle(A, B, C) -> Scalar
Angle(line1, line2) -> Scalar
```

- `Angle(A,B,C)`のvertexは中央の`B`。
- rangeは`[0,pi]`のunsigned angle。
- `A=B`または`C=B`で未定義。
- line–line angleはorientationを無視したacute angleで、rangeは`[0,pi/2]`。
- degreeではなくradian。

status：**推奨**

### 13.5 `Radius`

```text
Radius(circle) -> Scalar
```

status：**推奨**

### 13.6 `Area`

```text
Area(circle) -> Scalar
Area(A, B, C) -> Scalar
Area(A, B, C, D, ...) -> Scalar
```

- circle areaは`pi*r^2`。
- 点列はshoelaceによる**unsigned** area。
- orientationや左右判定には使えない。
- `Area(Polygon(...))`は使わない。

signed orientationが必要なら、

```text
(B.x-A.x)*(C.y-A.y) - (B.y-A.y)*(C.x-A.x)
```

を使う。ただしsourceのorientation条件がある場合だけguardに用いる。

status：**推奨**

### 13.7 `Vector`

```text
Vector(A, B) -> Point-like vector
```

`B-A`を返す。

status：**推奨**

### 13.8 `Dot`

```text
Dot(v, w) -> Scalar
Dot(line1, line2) -> Scalar
```

典型例：

```text
Dot(Vector(A,B), Vector(C,D))
```

status：**推奨**

### 13.9 `OnLine`

```text
OnLine(P, line) -> residual
OnLine(P, A, B) -> residual
```

- residualが0なら所属・共線。
- `OnLine(P,line)`は非負のdistance residual。
- `OnLine(P,A,B)`はcross-product residual。
- `ordered=True`は引数順が直感的でないため使用禁止。

status：**推奨**。`ordered=True`は禁止。

### 13.10 `Collinear`

```text
Collinear(A, B, C, ordered=False) -> residual
```

`OnLine(A,B,C)`の互換alias。

- `ordered=True`では中央argument`B`が`A`,`C`の間というlegacy semanticsになる。
- 混乱を避け、順序なし共線だけに使う。
- 順序は、driver pointなら`PointOnSegment`＋`Bound`、constructed pointのreplayなら`AssumeEq(OnSegment(B,A,C),0)`で書く。

status：`ordered=False`のみ**推奨**。

### 13.11 `OnSegment`

```text
OnSegment(P, A, B) -> residual
```

residual 0はclosed segment `AB`上を意味する。sourceで`P`が線分上のdriverなら、constraintとして使うより`PointOnSegment`を推奨する。

status：**推奨**

### 13.12 `OnCircle`

```text
OnCircle(P, circle) -> residual
```

`Distance(P,Center(circle))-Radius(circle)`というsigned radial residual。

status：**推奨**

### 13.13 `IsTangent`

```text
IsTangent(line, circle) -> residual
IsTangent(circle, line) -> residual
IsTangent(circle1, circle2) -> residual
```

- line–circle：中心からlineまでの距離とradiusの差。
- circle–circle：外接または内接のうち小さいresidualを返す。
- circle–circleでsourceが外接・内接を指定する場合、`IsTangent`だけではbranchを保存できない。

外接を明示：

```text
Distance(Center(c1),Center(c2)) = Radius(c1)+Radius(c2)
```

内接を明示：

```text
Distance(Center(c1),Center(c2)) = abs(Radius(c1)-Radius(c2))
```

同一円などsourceが除く退化もguardで明示する。

status：line–circleは**推奨**。circle–circleはbranchを問わないsourceだけ**条件付き**。

### 13.14 `Perpendicular`

```text
Perpendicular(line1, line2) -> residual
```

0で垂直。

status：**推奨**

### 13.15 `Parallel`

```text
Parallel(line1, line2) -> residual
```

0で平行。

status：**推奨**

### 13.16 `ParallelismMeasure`

```text
ParallelismMeasure(line1, line2)
ParallelismMeasure(line1, line2, method='cross')
```

- defaultは正規化line係数のsigned cross。
- line endpoint順を反転すると符号が変わり得る。
- 0条件だけなら`Parallel`を推奨する。
- 符号をbranch guardに使う場合、sourceに有向関係があり、line orientationを固定できることが必要。

status：**条件付き**

### 13.17 `Slope`

```text
Slope(line) -> Scalar
Slope(A, B) -> Scalar
```

- vertical lineで未定義。
- 2点形式は高精度互換性が弱い。
- 平行・垂直条件には`Parallel`、`Perpendicular`を使う。

status：原則**禁止**。どうしても必要なら`Slope(Line(A,B))`を条件付き使用。

### 13.18 `Length`

```text
Length(segment) -> Scalar
```

status：**推奨**

### 13.19 `Perimeter`

```text
Perimeter(A, B, C) -> Scalar
```

legacy高精度実装は三角形3点形に限定される。多角形には次を使う。

```text
Distance(A,B)+Distance(B,C)+Distance(C,D)+Distance(D,A)
```

`Perimeter(Polygon(...))`はobject propertyとの互換問題があるため使用禁止。

status：3点形のみ**条件付き**。一般にはDistanceの和を推奨。

### 13.20 `Circumference`

```text
Circumference(circle) -> Scalar
```

status：**推奨**

---

## 14. parameterization関数の完全リファレンス

### 14.1 `PointOnLine`

```text
PointOnLine(line, t) -> Point
```

line上の、原点に最も近いbase pointから正規化directionへ`t`進んだ点。

- `t`は実数。
- line係数の符号が反転すると`t`の向きも反転する。
- sourceに自然区間がなければboundしない。

status：**推奨**

### 14.2 `PointOnSegment`

```text
PointOnSegment(A, B, t) -> Point
```

```text
(1-t)A+tB
```

- closed segmentには`Bound(t,(0,1))`。
- open segmentには`Bound(t,(0,1),inclusive=False)`。
- constructor自体は`t`を制限しない。

status：**推奨**

### 14.3 `PointOnCircle`

```text
PointOnCircle(circle, t) -> Point
```

angle `2*pi*t`。`t=0`はcenterからx正方向の円周点。periodは1。

status：**推奨**

### 14.4 `PointOnArc`

```text
PointOnArc(arc, t) -> Point
```

構文は存在するが、legacy実装はendpoint angleを単純補間し、`including`/`excluding`によるmajor/minor arc選択やbranch cutを完全には反映しない。

status：**禁止**。arc上の自由点が必要なら、`PointOnCircle`＋arc membershipを別途厳密に表せる場合だけ代替し、そうでなければ問題を保留する。

### 14.5 `InscribedPolygonVertices`

```text
InscribedPolygonVertices(circle, t2, t3, ...) -> list[Point]
```

- 最初の頂点はcenterからy正方向の固定点。
- 各`t`は、直前のangleから1周完了までの残りangleに対するfraction。
- 各`t`の自然domainは`[0,1]`。
- 一般的な「円に内接する多角形」のparameterizationとしては、固定された最初の頂点がsourceの他objectとの関係を壊さないか監査が必要。

status：**条件付き**

### 14.6 `InscribedPolygon`

```text
InscribedPolygon(circle, t2, t3, ...) -> Polygon
```

通常精度と高精度でreturn representationが一致しないため、新規問題では使用しない。必要なら`InscribedPolygonVertices`を使い、list subscriptで点を取り出す。

status：**禁止**

---

## 15. 基本constructionの完全リファレンス

### 15.1 `PerpendicularLine`

```text
PerpendicularLine(line, P) -> Line
PerpendicularLine(P, line) -> Line
```

両順序を受け付ける。新規問題では`PerpendicularLine(line,P)`へ統一する。

status：**推奨**

### 15.2 `ParallelLine`

```text
ParallelLine(line, P) -> Line
ParallelLine(P, line) -> Line
```

新規問題では`ParallelLine(line,P)`へ統一する。

status：**推奨**

### 15.3 `PerpendicularBisector`

```text
PerpendicularBisector(A, B) -> Line
```

`A != B`が必要。

status：**推奨**

### 15.4 `AngleBisector`

```text
AngleBisector(A, B, C) -> Line
```

- vertexは中央の`B`。
- internal angle bisector。
- `A != B`, `C != B`が必要。
- sourceが外角二等分線を指定する場合には使えない。

status：**推奨**

### 15.5 `FootOfPerpendicular`

```text
FootOfPerpendicular(P, line) -> Point
FootOfPerpendicular(line, P) -> Point
```

新規問題では`FootOfPerpendicular(P,line)`へ統一する。

status：**推奨**

### 15.6 `ClosestPoint`

```text
ClosestPoint(P, line) -> Point
ClosestPoint(line, P) -> Point
ClosestPoint(P, circle) -> Point
ClosestPoint(circle, P) -> Point
```

- Point–Lineは垂足。
- Point–Circleはcenterから`P`方向の円周点。
- `P`がcircle centerと一致する場合、円周上のclosest pointは一意でない。legacy実装はcenter自体を返すため、幾何的なcircle pointとして使ってはならない。
- 高精度互換性のため、新規問題ではPoint–Lineだけを推奨する。

status：Point–Lineは**推奨**。Point–Circleは**禁止**。

### 15.7 `CircleThroughPoint`

```text
CircleThroughPoint(O, P) -> Circle
```

center`O`、`P`を通るcircle。

status：**推奨**

### 15.8 `CircleThroughThreePoints`

```text
CircleThroughThreePoints(A, B, C) -> Circle
```

3点が非共線であることが必要。`Circumcircle`と同じ意味のconstruction。

status：**推奨**

### 15.9 `ContactPoint`

circle–line overload：

```text
ContactPoint(circle, line) -> Point
ContactPoint(line, circle) -> Point
```

これはcenterからlineへの垂足を返す。**circleとlineが接すること自体は検証しない。**

したがってsourceに接線条件がある場合は、

```text
constraint: IsTangent(circle,line)=0
T = ContactPoint(circle,line)
```

のようにする。

三角形のincircle contact overloadも存在するが、曖昧なので`IncircleContactPoint`を明示的に使う。

status：circle–lineは**条件付き**。

### 15.10 `TangentLine`

通常構文：

```text
TangentLine(P, circle, use_first=True) -> Line
```

- `P`はcircle上または外部。
- 外部なら2本あり、`use_first`は座標実装依存branch。
- legacy通常精度と高精度で引数順の互換問題がある。

status：**禁止**。sourceが接線を定義する場合は、必要に応じてlineを1方向parameter化し、`IsTangent`などのconstraintを残す。

### 15.11 `Rotate`

通常構文：

```text
Rotate(P, theta)
Rotate(P, theta, center=O)
```

legacy通常精度と高精度で引数順の互換問題があるため、新規問題では使用しない。

sourceが回転を直接定義する場合は、次の明示式を使える。

```text
Point(
  O.x + cos(theta)*(P.x-O.x) - sin(theta)*(P.y-O.y),
  O.y + sin(theta)*(P.x-O.x) + cos(theta)*(P.y-O.y)
)
```

これは回転の定義式を展開しただけであり、sourceが回転を明記している場合に限り意味保存である。

status：関数`Rotate`は**禁止**。

### 15.12 `Reflect`

```text
Reflect(P, O) -> Point
Reflect(P, line) -> Point
```

- axisがPointなら点`O`に関する点対称。
- axisがLineならline reflection。
- Point以外のobjectのreflectionは未対応。

status：**推奨**

### 15.13 `RegularPolygon`

```text
RegularPolygon(A, B, n, ccw=True) -> Polygon
```

- `A`,`B`を最初の有向辺とする正`n`角形。
- `n`は3以上の固定integer。
- `ccw`は鏡映branchを選ぶ。
- sourceがorientationを指定しない場合、勝手に`ccw=True`だけへ固定しない。
- return representationのbackend差があるため、後続利用は慎重に行う。

status：**条件付き**

---

## 16. 交点関数の完全リファレンス

### 16.1 `Intersect`

```text
Intersect(obj1, obj2)
Intersect(obj1, obj2, exclude=A)
Intersect(obj1, obj2, near=Q)
Intersect(obj1, obj2, far=Q)
Intersect(obj1, obj2, n=1)
```

対応：

- Line–Line
- Line–Circle
- Circle–Circle
- Line–Arc
- Circle–Arc
- Arc–Arc

return：

- 一意ならPoint。
- 複数交点でselectorがなければlist。
- 交点なしでは`None`またはempty list、selector付きならerrorになり得る。

selector：

- `exclude=A`：`A`と一致する交点を除く。
- `near=Q`：`Q`に最も近い交点。
- `far=Q`：`Q`から最も遠い交点。
- `n`：1始まりの内部list index。幾何的意味がないため禁止。

重要：

- selectorなしのLine–Circle、Circle–CircleをPoint名へ代入しない。
- tangent時は同一点が2回返る場合がある。
- 自由な円同士の完全交点消去は正のmeasureで未定義になり得る。
- sourceのbranchをselectorで説明できない場合は、点をcarrier上parameter化して所属constraintを残す。

status：Line–Lineと意味付きselectorは**推奨**。実根存在がparameter域の一部に限られる場合は**条件付き**。

### 16.2 `IntersectLines`

```text
IntersectLines(line1, line2) -> Point or None
```

low-level関数。Line–Lineには`Intersect`へ統一する。

status：**非推奨**

### 16.3 `IntersectLineCircle`

```text
IntersectLineCircle(line, circle) -> list[Point]
```

- 常にlistとして扱う。
- list順はbranch semanticsではない。
- backendにより非交差時の扱いが異なり得る。

status：**禁止**。`Intersect`＋意味付きselectorまたはone-slack表現を使う。

### 16.4 `IntersectCircles`

```text
IntersectCircles(circle1, circle2) -> list[Point]
```

list順に幾何的意味がない。

status：**禁止**。`Intersect`＋意味付きselectorまたはone-slack表現を使う。

---

## 17. 三角形constructionの完全リファレンス

以下はすべて、非退化三角形が必要である。sourceがそのcenter/circleを直接定義している場合だけconstructionに使う。変換者が定理でそのobjectだと発見した場合には使わない。

### 17.1 基本center

```text
Centroid(A,B,C) -> Point
Incenter(A,B,C) -> Point
Circumcenter(A,B,C) -> Point
Orthocenter(A,B,C) -> Point
NinePointCenter(A,B,C) -> Point
```

- `Circumcenter`, `Orthocenter`, `NinePointCenter`は共線三点で未定義。
- `Incenter`も退化三角形へ使わない。

status：sourceが直接定義する場合は**推奨**。

### 17.2 triangle circle

```text
Incircle(A,B,C) -> Circle
Circumcircle(A,B,C) -> Circle
NinePointCircle(A,B,C) -> Circle
```

status：sourceが直接定義する場合は**推奨**。

### 17.3 excenterとexcircle

```text
Excenter(A,B,C)
Excenter(A,B,C,vertex='A')
Excenter(A,B,C,vertex='B')
Excenter(A,B,C,vertex='C')

Excircle(A,B,C)
Excircle(A,B,C,vertex='A')
Excircle(A,B,C,vertex='B')
Excircle(A,B,C,vertex='C')
```

- defaultはAに対するexcenter/excircle。
- string`'A'`, `'B'`, `'C'`を推奨する。
- numeric `0,1,2`やPointそのものをvertexに渡す互換形は使わない。

status：**推奨**

### 17.4 incircle contact point

```text
IncircleContactPoint(A,B,C) -> [point_on_BC, point_on_CA, point_on_AB]
IncircleContactPoint(A,B,C,side='BC') -> Point
IncircleContactPoint(A,B,C,side='CA') -> Point
IncircleContactPoint(A,B,C,side='AB') -> Point
```

- side stringを推奨。
- `0,1,2`やopposite vertexを渡すlegacy形は使わない。
- listを返す形ではsubscriptで取り出せる。

例：

```text
contacts = IncircleContactPoint(A,B,C)
D = contacts[0]
```

ただし明示side形の方が監査しやすい。

status：**推奨**

### 17.5 named advanced centers

```text
SymmedianPoint(A,B,C) -> Point
GergonnePoint(A,B,C) -> Point
NagelPoint(A,B,C) -> Point
Mittenpunkt(A,B,C) -> Point
SpiekerCenter(A,B,C) -> Point
FeuerbachPoint(A,B,C) -> Point
FermatPoint(A,B,C,first=True) -> Point
FermatPoint(A,B,C,first=False) -> Point
IsodynamicPoint(A,B,C,first=True) -> Point
IsodynamicPoint(A,B,C,first=False) -> Point
```

- sourceが点をこの名前または完全な定義で直接指定する場合だけ使う。
- `first`/`False` branchがsourceのどの点に対応するかをclause ledgerへ記録する。
- rare centerは通常精度・高精度の両方でreplayする。

status：**条件付き**

### 17.6 `TriangleCenter`

```text
TriangleCenter(A,B,C,n) -> Point
```

対応index：

| n | center |
|---:|---|
| 1 | Incenter |
| 2 | Centroid |
| 3 | Circumcenter |
| 4 | Orthocenter |
| 5 | NinePointCenter |
| 6 | Symmedian/Lemoine |
| 7 | Gergonne |
| 8 | Nagel |
| 9 | Mittenpunkt |
| 10 | Spieker |
| 11 | Feuerbach |
| 13,14 | Fermat pair |
| 15,16 | Isodynamic pair |

`12`および他のindexは未対応。

numeric indexは誤記しやすいため、named functionを使う。

status：**禁止**

---

## 18. 円のadvanced construction

これらはsourceが直接その概念を定義する場合だけ使用できる。変換者が問題を解く途中で発見して使うことは禁止する。

### 18.1 `PowerOfPoint`

```text
PowerOfPoint(P, circle) -> Scalar
```

```text
Distance(P,Center(circle))**2 - Radius(circle)**2
```

status：sourceが方べきを直接条件・targetにする場合のみ**条件付き**。

### 18.2 `Polar`

```text
Polar(P, circle) -> Line
```

status：**条件付き**

### 18.3 `Pole`

```text
Pole(line, circle) -> Point
```

特定の分母が0になる配置で未定義。

status：**条件付き**

### 18.4 `RadicalAxis`

```text
RadicalAxis(circle1, circle2) -> Line
```

同心円では未定義。二円が同一の場合もsourceの扱いを明示する。

status：**条件付き**

---

## 19. guard関数の完全リファレンス

### 19.1 `Assume`

```text
Assume(condition)
```

例：

```text
Assume(Cy > 0)
```

raw comparisonはtolerance semanticsが分かりにくいため、可能なら型別関数を使う。

status：**条件付き**

### 19.2 scalar comparison guards

```text
AssumeEq(lhs,rhs)
AssumeNe(lhs,rhs)
AssumeLt(lhs,rhs)
AssumeLe(lhs,rhs)
AssumeGt(lhs,rhs)
AssumeGe(lhs,rhs)
```

- equalityをsolverへ解かせる場合はconstraintへ置く。
- guardsではsource branch、不等式、非退化だけを表す。

例：

```text
AssumeNe(Distance(A,B),0)
AssumeGt(Area(A,B,C),0)
AssumeLt(Distance(P,A),Distance(P,B))
```

status：**推奨**

### 19.3 `Bound`

```text
Bound(value,(lo,hi))
Bound(value,(lo,hi),inclusive=True)
Bound(value,(lo,hi),inclusive=False)
```

- `inclusive=True`：両端closed。
- `inclusive=False`：両端open。
- half-openは一つの`Bound`では表せない。
- natural parameter domainにのみ使う。

status：**推奨**

### 19.4 triangle shape guards

```text
AssumeAcute(A,B,C)
AssumeRight(A,B,C)
AssumeObtuse(A,B,C)
```

これらは`∠ABC`一つではなく、三角形全体がacute/right/obtuseかを判定する。

特定vertexの角を指定するなら、

```text
AssumeLt(Angle(A,B,C),pi/2)
AssumeEq(Angle(A,B,C),pi/2)
AssumeGt(Angle(A,B,C),pi/2)
```

ただしright angle equalityは主要条件ならconstraintへ置く。

status：sourceが三角形全体を分類する場合は**推奨**。

### 19.5 polygon guards

```text
AssumeConvex([A,B,C,D])
AssumeNoSelfIntersecting([A,B,C,D])
```

listを渡す。`Polygon` objectを渡す形はbackend差があるため避ける。

status：**条件付き**

### 19.6 `AssumeOrder`

```text
AssumeOrder(A,P,B)
```

意図上は`A-P-B`、すなわち`P`が`A`,`B`の間を表す。ただしlegacy高精度guard contextとの型互換問題がある。

status：**禁止**。`PointOnSegment`＋`Bound`、または`AssumeEq(OnSegment(P,A,B),0)`を使う。

### 19.7 tolerance keyword

`message`, `rel_floor`, `abs_floor`, `tol`などの互換keywordは、問題authorが調整しない。source semanticsではないsolver内部閾値を問題ごとに変えることになるため、新規問題ではdefaultを使う。

---

## 20. scalar関数とconstant

### 20.1 使用できるscalar関数

```text
pi
sqrt(x)
sin(x)
cos(x)
tan(x)
asin(x)
acos(x)
atan(x)
atan2(y,x)
abs(x)
min(x,y,...)
max(x,y,...)
```

注意：

- trig入力・出力はradian。
- `sqrt`は負の実数入力で未定義。
- `asin`,`acos`はinput domainを守る。
- `tan`はpoleを持つ。
- `abs`, `min`, `max`は非滑らかな点を持つため、source semanticsに必要な場合だけ使う。
- `atan2`のargument順は`atan2(y,x)`。

### 20.2 使用禁止

```text
evalf(...)
int(...)
float(...)
IsInteger(...)
IsPrime(...)
```

- `evalf`, `float`は高精度・exact targetを損なう。
- `int`やroundingはtargetを変更する。
- `IsInteger`, `IsPrime`を必要とする問題は、問題選定段階で除外する。

`exp`, `log`, `floor`, `ceil`などはauthoring profileにない。

---

## 21. attributeとlist access

使用可能な主なattribute：

| object | attribute |
|---|---|
| Point | `.x`, `.y` |
| Line | `.a`, `.b`, `.c` |
| Circle | `.center`, `.radius` |
| Segment | `.p1`, `.p2` |
| Ray | `.start`, `.through` |
| Arc | `.circle`, `.start`, `.end`, `.center`, `.radius` |
| Polygon | `.vertices`, `.edges`, `.area`, `.perimeter` |

ただしPolygon attributeはbackend差のため新規constraint・answerでは使わない。

list returnはsubscriptで参照できる。

```text
contacts = IncircleContactPoint(A,B,C)
D = contacts[0]
```

交点listを`[0]`, `[1]`で選ぶことは禁止。list順に幾何的意味がない。

---

## 22. 存在するがDSL式へ書いてはいけないtechnical symbol

次はruntime・registry・backend操作用であり、問題DSLの幾何関数ではない。

```text
geometry_symbol
get_function
list_functions
MultiFunctionWrapper
BackendType
GeometryRuntime
use_runtime
fast_mode
high_precision_mode
get_precision
get_backend
AssumptionError
```

また、次のlegacy spellingや未公開関数へ依存しない。

```text
MidPoint
Triangle
Tangent
AreConcyclic
AssumeOrderedCollinear
PointOnRay
OtherIntersection
Between
Inside
Cross
Degrees
```

共円条件は、sourceで非共線な3点が保証される場合、

```text
Gamma = Circumcircle(A,B,C)
constraint: OnCircle(D,Gamma)=0
```

のように表す。退化branchをsourceが許す場合は、この置換だけでは意味保存できないため別表現が必要である。

---

## 23. 良い表現・悪い表現の追加例

### 23.1 交点

source：

> `P`は直線`AC`と直線`BD`の交点。

良い：

```text
P = Intersect(Line(A,C),Line(B,D))
```

悪い：

```text
P = Point(Px,Py)
OnLine(P,A,C)=0
OnLine(P,B,D)=0
```

ただし二直線が平行になり得るsource-valid branchがあるなら、単純な完全消去はできない。

### 23.2 接円

source：

> 円`omega`は直線`l1`,`l2`および円`Gamma`に接する。

悪い：

```text
omega = Incircle(A,B,C)
```

sourceに三角形の内接円とは書かれていない。

意味保存する表現：

```text
O = Point(Ox,Oy)
omega = Circle(O,abs(r_raw))
constraints:
  IsTangent(omega,l1)=0
  IsTangent(omega,l2)=0
  external_or_internal_tangency_equation_to_Gamma=0
guards:
  AssumeGt(abs(r_raw),0)
  sourceのside/inside branch
```

自由度が高くても、sourceにないmacroへ言い換えてはならない。

### 23.3 coordinate bounds

悪い：

```json
"bounds": [[-50,50],[-50,50]]
```

良い：

```text
top-level boundsを省略
```

自然parameterだけ：

```text
Bound(tD,(0,1))
```

### 23.4 交点branch

悪い：

```text
P = Intersect(c1,c2,n=1)
```

良い：

```text
P = Intersect(c1,c2,exclude=A)
```

ただしsourceが`A`ではないもう一方を指定している場合。

### 23.5 鏡映branch

悪い：

```text
AssumeGt(Cy,0)
```

根拠が「図で上にある」だけ。

良い：

- sourceが有向直線の側を指定するならsigned determinant guardを置く。
- sourceが指定しないなら鏡映branchを残す。

---

## 24. 作成workflow

### Step 1：問題選定

- 純粋な2Dユークリッド幾何か。
- 最大最小化ではないか。
- discrete・physics・3D条件がないか。
- SE(2)だけを除いて解配置が有限か。
- scalar targetか。

一つでも満たさなければ変換しない。

### Step 2：source clauseを分解する

- given object
- constructed object
- equality
- strict/non-strict inequality
- order/side/inside
- branch selector
- nondegeneracy
- target

### Step 3：clause ledgerを作る

まだ答えや既存DSLを見ず、sourceだけから対応表を作る。

### Step 4：gaugeを決める

- translationとrotationだけ。
- anchor distinctnessを確認する。
- scaleとreflectionを勝手に除かない。

### Step 5：driverを選ぶ

- 自由pointは2変数。
- carrier上のpointは1変数。
- source constructionは0変数。
- できるだけ作図順にDAG化する。

### Step 6：evaluation-definednessを確認する

- 正のmeasureで失敗するintersectionやsqrtを避ける。
- 必要ならone-slack chartに戻す。
- radiusはnegative parameterでconstructorが壊れないようにする。

### Step 7：constraintsとguardsを分ける

- equalityはconstraints。
- branch、順序、不等式、非退化はguards。
- source clauseを一つも落とさない。

### Step 8：answerを書く

- 単一scalar。
- roundingなし。
- post processなし。

### Step 9：独立review

reviewerは次だけを確認する。

- sourceとDSLの意味一致。
- clause coverage。
- branch coverage。
- 不正な定理適用がない。
- 自由変数が不必要に多くない。
- arbitrary boundsがない。
- constructionが広いparameter域で評価可能。

---

## 25. 最終チェックリスト

### 問題採否

- [ ] 純粋な2Dユークリッド幾何である。
- [ ] 最大化・最小化問題ではない。
- [ ] 整数・素数・格子・個数・物理などの非幾何条件がない。
- [ ] SE(2)だけを除去した後、幾何配置が有限個である。
- [ ] 配置が連続無限でtargetだけ一定、という問題ではない。
- [ ] targetは単一の幾何scalarである。

### 意味保存

- [ ] 全source clauseがledgerにある。
- [ ] sourceにない条件を追加していない。
- [ ] 非自明な定理で問題を言い換えていない。
- [ ] 既知解・target値を使っていない。
- [ ] 鏡映や交点branchを図の見た目で削除していない。
- [ ] source-validな退化を勝手に除外していない。

### 低次元性

- [ ] translation・rotation gaugeを安全に使った。
- [ ] scaleを勝手に固定していない。
- [ ] carrier上の点を1parameterにした。
- [ ] sourceの決定的constructionを自由座標にしていない。
- [ ] 問題を言い換えずに6変数以下へできないか確認した。
- [ ] 完全消去が正のmeasureの未定義域を作る場合、one-slackを検討した。

### bounds

- [ ] top-level `bounds`を原則省略した。
- [ ] 座標・半径へ任意の数値範囲を付けていない。
- [ ] `Bound`はsegment、arc、periodなどの自然parameter domainにだけ使った。

### 構文

- [ ] `task`は`"solve"`。
- [ ] `variables.names`は一意なidentifier。
- [ ] constructionは依存順。
- [ ] 全constraintはscalar。
- [ ] equalityをguardだけにしていない。
- [ ] `answer`は単一scalar。
- [ ] `post_process`は`""`。
- [ ] `n=`による交点選択を使っていない。
- [ ] `PointOnArc`、`Rotate`、`TangentLine`、`AssumeOrder`などの禁止関数を使っていない。
- [ ] `IsInteger`、`IsPrime`を使っていない。
- [ ] decimal近似で厳密値を置き換えていない。

### definedness

- [ ] `Line(A,B)`で`A != B`が保証される。
- [ ] circle radiusがconstruction時に非負。
- [ ] angleのrayが非零。
- [ ] circumcircle系で非共線。
- [ ] intersectionの実根存在域を確認した。
- [ ] guardより前に正のmeasureでconstruction failureが起きない。
- [ ] constraintsとanswerがほとんどすべてのparameterで有限評価できる。

---

## 26. 最小template

```json
{
  "id": "REPLACE_WITH_UNIQUE_ID",
  "task": "solve",
  "variables": {
    "names": []
  },
  "construction": [],
  "constraints": [],
  "guards": [],
  "answer": "0",
  "post_process": ""
}
```

このtemplateへobjectを足す前に、必ず次の順で考える。

1. そのobjectは本当に自由か。
2. sourceの前のobjectから構成できないか。
3. 何らかのcarrier上なら1parameterにできないか。
4. その低次元化はsourceの直接的な作図か、それとも変換者による非自明な問題の言い換えか。
5. ほとんどすべてのparameterで後続評価が定義できるか。

「自由変数を少なくすること」は重要だが、「元問題と同じ問題であること」が常に優先される。
