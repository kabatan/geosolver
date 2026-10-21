# GeoSolver

GeoSolverは、有限個の値を答えとして持つ2次元幾何問題を数値探索し、可能な場合は厳密な答えdescriptorを返すsolverです。網羅性は証明せず、結果の`completeness`は常に`unknown`です。

この`research`ブランチでは、固定した幾何solverと、数値教師から幾何的能力への転移を調べる学習実験の資産を管理します。
研究作業の入口は[研究ガイド](docs/research/README.md)です。

| 構成 | 場所 |
|---|---|
| solver本体 | [`src/geosolver`](src/geosolver) |
| Qwen3-4B環境 | [`qwen/`](qwen/README.md) |
| 幾何323問・研究runner | [`benchmarks/cases.jsonl`](benchmarks/cases.jsonl)、`benchmarks/dsl/`、[`benchmarks/research_runner.py`](benchmarks/research_runner.py) |
| GMB独立環境・比較 | [`benchmarks/gmb`](benchmarks/gmb/README.md)、[`benchmarks/gmb_comparison`](benchmarks/gmb_comparison/README.md) |
| 学習用求値セット | [`benchmarks/humpty_configurations_v2`](benchmarks/humpty_configurations_v2/README.md) |
| 証明評価セット | [`benchmarks/humpty_proof_evaluation_v2`](benchmarks/humpty_proof_evaluation_v2/README.md) |
| 研究メモ | [`docs/research`](docs/research/README.md) |

solverの固定版は以下のtagで識別します。

## 固定版と再現性

2026-09-01に、修正・整理後のsolverをannotated tag **`solver-a1`** として固定しました。
再現には移動し得る`research`のHEADではなく、このtagを指定してください。
実装・既定設定・依存・評価入力を変更して固定し直す場合は、新しいtagを作成し、既存tagを移動しません。

- 実装・既定設定・依存の識別：`src/geosolver/engine-lock.json`。
- 依存の再現：Python 3.12、`uv.lock`、`uv sync --all-extras --frozen`。
- 開発用入力：`benchmarks/cases.jsonl`と対応する323問の`benchmarks/dsl/`。
- 正式な研究実行：Linux、180秒／問題、1物理コア／job、seed 0を基準とする。反復実験のseed列は実行前に別途固定する。
- 実行の識別：runnerがcommit、ソース・入力のhash、設定、環境を記録します。

`engine-lock.json`は固定した実装と実行契約の整合性を検査します。
tagの注釈にもソース・設定・依存・入力のhashと検証範囲を記録しています。

固定前のLinux検証は、1040テスト（失敗・skipなし）、323問の静的整合性、Ruff、schema、
compileall、2通りのfresh-process import、engine lock・導入依存照合を通過しました。
`uv.lock`の依存バージョンを使う独立wheel環境で、CLI・worker・代数的数およびπを含む厳密値返却も確認しました。
commit後に作業ツリーがcleanであることを確認してtagを付けています。

2026-09-01の固定時には323問の求解評価を再実行しておらず、過去の測定値をその固定ソースの成績とは扱いません。
同日の固定時にはWindows／macOSの実機検証は未実施です。固定は、欠陥不存在や全解発見の保証ではありません。

## 2026-10-11の性能改善

現在の作業版では、多倍長演算、解析微分、同じ高精度座標での検証結果の再利用、
有限な代数的候補の生成、構成から証明できる接触・接続の等式を改善しました。
候補を元の問題で独立に検証する契約、厳密な答えdescriptor、180秒・1コアの設定は維持しています。
この作業版は既存tag `solver-a1` とは別で、ソースhashは
`sha256:f92ee9ba5bea9b124f19e79e95d89e47e66252fede326bb1a569eb1d318e969b` です。

元の実装も同日に再測定しました。以下は起動時間と失敗した実行を含むprocess wall時間です。
公開323問の入力・正解は変更せず、同じ物理コア群を使い、6並列・各問題180秒・1コアで測定しました。
作業ツリーでの実行を`--allow-dirty`で明示し、全記録のソースhash・依存・入力・実行契約を照合しています。

| 測定 | 答え集合の完全一致 | 実時間中央値 | 実時間平均 | 95パーセンタイル |
|---|---:|---:|---:|---:|
| 改善前・seed 0 | 309/323（95.67%） | 6.183秒 | 27.287秒 | 175.222秒 |
| 改善後・seed 0 | 321/323（99.38%） | 2.997秒 | 14.569秒 | 104.320秒 |
| 改善後・seed 0, 1, 2合算 | 958/969（98.86%） | 3.124秒 | 14.464秒 | 95.329秒 |

seed 1は320/323、seed 2は317/323でした。3 seedすべてで一致した問題は316/323問です。
**3 seed合算では、目標の完全一致率99%と中央値1秒未満はいずれも未達です。**
seed 0の合計実時間は8813.652秒から4705.764秒へ減少しました。
同じseedで287問が短縮し、36問が増加しています。変数数0・1・2・3・4以上の各区分の中央値は短縮しましたが、
JMO-2017-PRE-10は20.331秒から173.568秒へ悪化しました。差の大半は精密化にあり、
最終版の他の2 seedも約149秒かかっています。この退行は残存課題として扱います。

969回の不一致は、答え不足9回と追加の答え2回です。追加の2回はJMO-2014-PRE-09で、
現行の端点を含むDSLが正解表にない`5`を許すことを別途検査しました。
採点基準とsolver出力を調整せず、この2回も不一致のまま集計しています。
実行エラー・実行契約違反は0回でした。

公開323問は開発中に繰り返し使っています。その成績だけで未知問題への汎化を主張しません。
問題名・正解値への分岐がないことだけでも過適合は否定できないため、
独立レビューで根拠が狭いと判断した格子点配置の近道と正半径の専用サンプラーは通常実行から除外しました。
対応する実験モジュールは残っていますが、通常経路から呼ばれないことを回帰テストで確認しています。
名前変更・単位変更・係数違いは不変性の検査であり、それぞれを独立した未知の問題族とは数えません。

未使用の評価は6つの構造的な問題族から生成した48入力です。
実装を固定してから初めて求解し、その結果を見た追加調整は行っていません。
完全一致は38/48から48/48、実時間中央値は2.650秒から0.858秒へ改善しました。
この小規模な合成集合の成績は、任意の未知問題での成功率や全解発見の保証ではありません。
Linux上でsolver関連1503テストと導入後36テスト、Ruff、schema、compileall、
固定依存を使う独立wheel環境の`doctor`と求解を確認しました。Windows／macOSの実機検証は未実施です。

生の実行記録と比較資料はローカルの`benchmarks/local-evaluation/optimization-20261011/`に保存しています。
`final-report.json`にseed別・変数数別・問題族別の結果と残存失敗、
`final-paired-seed0.csv`に全323問の新旧比較、`overfit-audit-receipt.json`に採否の根拠があります。
これらの一時評価資料はGit管理対象外です。測定は他の処理も動く同一ホストで行っており、微小な時間差には揺らぎを含みます。

### 追加高速化の追試

中央値1秒未満・平均3秒程度を目指して、同日に`gpt-6.1-sol`の並列実験と独立レビューを追加しました。
**この追試から通常実行へ採用した変更はありません。現在のソースhashと3 seedの成績は上記のままです。**

有望に見えたNewton法の打ち切りは、5関数族の単位・平行移動・精度を変えた180条件で、
従来法が成功する48条件を失いました。元の初期点・反復数・精度から従来法を実行する経路を追加すると、
この退行は解消しましたが、JMO-2017-PRE-10の約174秒から約26秒への短縮も消えました。
この修正を含む試作版の全323問・seed 0は320/323一致、中央値3.280秒、平均15.912秒で、
採用版の321/323・2.997秒・14.569秒を改善しませんでした。
失根1件は精密化前の既存の補助計算がCPU時間上限に達したためで、同一コアの新旧4実行では両方の根を取得しました。
この非交互の全問比較に加え、固定24問を同一コアで従来版→試作版→試作版→従来版の順に測定しました。
厳密な答え集合は24問すべてで一致しましたが、失敗込みの平均は14.459秒から15.727秒へ8.77%悪化しました。

角度・三角関数の解析微分も、対象24問×新旧各2回の厳密な答え集合は全一致しましたが、
問題別平均時間の合計は286.161秒から282.436秒への1.30%短縮にとどまりました。
HMMT-2023-FEB-GEO-04では9.895秒から19.342秒への悪化が両反復で再現し、採用を見送りました。
多倍長演算の低水準化、追加キャッシュ、多項式の消去・目的値の像を使う候補も、求解全体の改善を確認できませんでした。

修正版Newton法のsolver関連1541テストと独立レビューは通過しています。数学的な妥当性と速度の採否は別に判断しました。
事前に凍結した11構造族・88入力の未使用集合は、選抜を通った変更がないため求解せずに保持しています。
変更のない採用版の323問×3 seed測定は再実行しておらず、上記969実行の結果を引き続き参照しています。
試作ソース・反例・対比較・採否の記録は`benchmarks/local-evaluation/optimization-speed-20261011/`に保存しています。
同ディレクトリの`final-report.json`に測定結果、採否、各監査記録への参照をまとめています。

## 対応環境

単一の`standard` engineをLinux、Windows、macOSで提供します。既定は180秒・1コアで、一般APIでは180〜900秒と正の整数コア数を指定できます。研究用の正式実行は180秒・1コアに固定します。

core指定は使用上限です。現在のsolver内部は1 coreで実行し、問題単位の並列化は研究runnerの`--jobs`で行います。

## インストールとCLI

Python 3.12を用意してください。

```bash
uv sync --all-extras --frozen
uv run geosolver doctor
uv run geosolver validate path/to/problem.json
uv run geosolver solve path/to/problem.json --output result.json
uv run geosolver catalog --json
```

`standard`のNOMAD検索にはNOMAD 4の`PyNomadBBO`を使用します。対応wheelがない環境ではSciPyフォールバックになります。
高精度演算には固定した`gmpy2`を使います。worker間の値は多倍長数の二進表現を桁落ちなく受け渡します。

CLIは`validate`、`solve`、`doctor`、`catalog`を提供します。

## Python API

```python
from geosolver import GeometryProblem, SolveOptions, solve, validate

problem = GeometryProblem(
    id="example",
    variables=["x"],
    constructions=[],
    conditions=[{"left": "x", "operator": "=", "right": 1}],
    target="x",
)

assert validate(problem).valid
result = solve(problem, SolveOptions(time_limit_seconds=180, cores=1))
```

互換layerはありません。正式なpackage/import/CLI名はすべて`geosolver`です。

## 問題JSON

```json
{
  "id": "example",
  "variables": ["x"],
  "constructions": [
    {"name": "A", "expression": "Point(0, 0)"},
    {"name": "B", "expression": "Point(x, 0)"},
    {"name": "C", "expression": "Point(x/2, 1)"}
  ],
  "conditions": [
    {"left": "x", "operator": "=", "right": 1},
    {"left": "x", "operator": ">=", "right": 0},
    {"predicate": "AcuteTriangle(A, B, C)"}
  ],
  "target": "Distance(A, B)"
}
```

relation operatorは`=`、`!=`、`<`、`<=`、`>`、`>=`です。`right`はbooleanを認めず、整数、浮動小数、厳密式文字列を型を保ったまま扱います。幾何関数とpredicateの一覧は`geosolver catalog --json`で確認できます。

DSL 1.1では`PointOnSegment(A,B,t)`は相異なる端点と`0≤t≤1`を要求します。
延長上の点には`PointOnLine`を使いますが、パラメータの基準が異なるため、単なる関数名の置換はできません。
`PointOnCircle`のパラメータは任意の実数、`PointOnArc`は`[0,1]`、
`InscribedPolygon`の配置パラメータはすべて`(0,1)`です。
長い小数を入力する場合は式文字列を使ってください。呼び出し元で既にPython floatへ丸めた値の原文は復元できません。

## 数値評価

solverの通常精度の構成評価には、53 bitに設定した数値専用の幾何関数を使います。
`PointOnCircle`や後続の交点計算にSymPyの数式を持ち回りません。記号計算用の幾何関数は別に維持します。
高精度評価・最終検証の作業精度を通常精度へ下げる変更ではありません。

構成の依存関係と条件は問題単位で準備し、必要な構成から評価します。
変数に依存する結果は、同一の座標・演算種別・精度のときだけ、問題ごとの上限付きcacheで共有します。
近い別座標を同一視せず、交点の枝と関数呼び出しの検査記録も再利用時に引き継ぎます。
残差に不要な構成も、最終的な配置検査からは除外しません。
変数に依存しない構成は、異なる座標でも演算種別・精度ごとに再利用します。
論理条件の等式部分は、原文と枝の選択順序を保持した共有表現で評価します。

高精度の型検査は、既知のスカラー型の判定を簡略化し、エラー位置の文字列は混入を検出したときだけ作ります。
辞書・配列の検査結果は保存せず、再呼び出し時も中身を確認します。後から変更された値や、入れ子に混入したPython・NumPy・SymPyの浮動小数も検出します。

探索の前に、対応する式から有限な多項式系の候補を求める場合があります。
有理係数の消去、実根の隔離、平方根や角の必要等式を使いますが、変形によって増えた根は元の幾何条件で検査します。
各根の隔離区間と検証後の座標を照合し、候補数や答えの値が一致しただけでは枝の確認を完了としません。
未確認の枝が残るときは、同じseedの通常探索を実行して、各経路で検証済みになった候補を保持します。
正の一様拡大縮小で条件・定義域が保たれ、目的値が不変だと式から確認できる場合にも、追加の候補を生成します。

これらの任意処理には計算量と時間の上限があり、未対応の式や処理失敗は通常の数値経路へ戻します。
Linuxでは短い代数計算の内部予算をCPU時間で数え、別に要求全体の実時間制限を適用します。
必要なCPUタイマーを使えない環境では、その任意の代数処理を省略します。
解析微分は精密化を助けるための任意処理であり、生成できない場合は従来の数値微分を使います。
最終検証・厳密値の独立再確認・問題全体の180秒という既定値は維持しています。

## 厳密結果

- `algebraic`: 整数係数多項式、実根番号、隔離区間、十進近似。
- `affine_pi`: 代数的数のπ係数と代数的な定数項、十進近似。

ラジアンの`π/2`は`affine_pi`、`Degrees(...)`で変換した`90`は`algebraic`です。workerのcrash、artifact欠落、artifact破損は`engine_error`であり、正常探索後の`no_answer_found`とは区別されます。

最終検証は通常120・180桁、未確定時は最大500桁まで評価し、枝変更や禁止境界への近さを検査します。
これは数値誤差の推定を伴う検証であり、一般的な存在証明ではありません。
名前付きの構成だけでなく、条件・目的式・guardに直接書かれた図形にも非退化性の検査を適用します。
低精度の予備確認でも保持済みの高精度座標は丸め直しません。
同じ座標を作業精度と追加30桁で比較し、幾何関数内部の相殺による丸め誤差も見積もります。
面積0・接線条件0の等式は検証時だけ同値な符号付き残差を使い、公開の`Area`・`IsTangent`や目的式の意味は維持します。
候補の`answer_precision_dps`は作業精度であり、全桁の正確さを保証しません。
厳密化は記録された不確かさから候補発見用の精度を選び、元の作業精度・誤差範囲で最終照合します。
内部の厳密化記録には`discovery_precision_dps`を併記します。
内部期限で正常に打ち切った場合は完成済みの答えを保持し、`termination_reason=time_limit_reached`を返します。
精密化の途中で期限が切れた場合も、最後の改善済み座標を未検証の候補として保持します。
残り時間で最終検証と厳密化を通ったものだけを答えに含め、未検証の候補値は公開しません。

## 開発

```bash
uv run python -m pytest --import-mode=importlib
uv run ruff check src tests benchmarks qwen .github/scripts
```

研究用campaign runnerと評価資料はwheelへ含めず、repo内で管理します。

```bash
uv run python benchmarks/research_runner.py validate
uv run python benchmarks/research_runner.py run benchmarks/local-evaluation/my-run --jobs 16 --seeds 0
uv run python benchmarks/research_runner.py assess benchmarks/local-evaluation/my-run
uv run python benchmarks/research_runner.py summarize benchmarks/local-evaluation/my-run
```

正式実行はclean tree、engine lock、実際のimport元・依存version・CPU affinityの一致を要求します。
開発途中の実行だけは`run --allow-dirty`で明示的に許可できます。
worker protocolはv4です。候補revisionと保存完了通知を照合し、期限内にatomic保存が完了した結果だけを受理します。
過去のv3 artifactは読取adapterで扱い、書き換えません。

solver側の一時実行結果・profile・ソース複製は`benchmarks/local-evaluation/`へ出力し、
不要になったものは削除します。GMBの実行記録・比較記録は別に保持します。
`dist/`と`build/`は配布物の生成先で、通常実行には不要です。`uv build`で必要時に再生成できます。
回帰テストと`tests/fixtures/`は実行結果ではなく、現行の検証に必要な入力として残します。

323問は既にsolver開発に使用した集合であり、未使用の評価集合ではありません。
問題・出典・履歴の参照方法は[benchmark説明](benchmarks/README.md)を参照してください。

Qwen3-4Bの環境構築・診断・単発推論は[qwen/README.md](qwen/README.md)を参照してください。
学習用・評価用データセットの構成と再生成は各ディレクトリのREADMEを参照してください。

## 作業場所

通常の作業場所は`/home/kabatan/work/solver`直下、ブランチは`research`です。
作業用worktreeは追加しません。
