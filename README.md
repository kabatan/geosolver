# GeoSolver

GeoSolverは、有限個の値を答えとして持つ2次元幾何問題を数値探索し、可能な場合は厳密な答えdescriptorを返すsolverです。網羅性は証明せず、結果の`completeness`は常に`unknown`です。

`research`ブランチは、最新版のsolver pipeline、GMBの独立実行環境、両者のbenchmarkと検証に必要なものに絞っています。

| 構成 | 場所 |
|---|---|
| solver・Python API・CLI | [`src/geosolver`](src/geosolver) |
| solver用323問・DSL・評価runner | [`benchmarks`](benchmarks/README.md) |
| GMB独立実行環境 | [`benchmarks/gmb`](benchmarks/gmb/README.md) |
| GMB比較入力・独立検査器・評価runner | [`benchmarks/gmb_comparison`](benchmarks/gmb_comparison/README.md) |
| 回帰テスト・CI・実行契約 | [`tests`](tests)、[REQUIREMENTS.md](REQUIREMENTS.md)、`.github/` |

Qwen、Humptyデータ、研究案、過去の実行結果は`experiment`ブランチへ移管しました。[保存先](docs/archive.md)を参照してください。

## バージョンと再現性

固定版`solver-a1`（2026-09-01）と、現在の作業版を区別してください。
現在の実装は10月11日の改善を含み、10月21日の整理で通常実行から外れていた格子点探索・正半径サンプラーを取り除いています。
この整理後の性能測定は実施していません。整理前の成績を現在のソースの測定値とは扱いません。

- 実装・既定設定・依存の識別：`src/geosolver/engine-lock.json`。
- 環境の再現：Python 3.12、`uv.lock`、`uv sync --all-extras --frozen`。
- solver評価入力：`benchmarks/cases.jsonl`と対応する323問の`benchmarks/dsl/`。
- 正式な求解評価：Linux、180秒／問題、1物理コア／job、seed 0を基準に、seed列を実行前に固定。
- 実行記録：runnerがcommit、ソース・入力のhash、設定、環境を保存。

既存の固定tagは移動しません。過去の性能報告・ソース・実行記録の参照方法は[保存先](docs/archive.md)にまとめています。

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

## 開発と評価

```bash
uv run python -m pytest --import-mode=importlib
uv run ruff check src tests benchmarks .github/scripts
uv run python -m compileall -q src tests
uv run python -m geosolver.schemas.generate --check
uv run python benchmarks/research_runner.py validate
uv build
uv run python .github/scripts/verify_wheel.py
```

solverを変更した場合は、検証前に`.github/scripts/update_engine_lock.py`でlockを更新します。
入力・正解・評価条件を変更して性能改善を見せる用途には使いません。

```bash
uv run python .github/scripts/update_engine_lock.py
uv run python benchmarks/research_runner.py run benchmarks/local-evaluation/my-run --jobs 8 --seeds 0
uv run python benchmarks/research_runner.py assess benchmarks/local-evaluation/my-run
uv run python benchmarks/research_runner.py summarize benchmarks/local-evaluation/my-run
```

正式実行はclean tree、engine lock、実際のimport元・依存version・CPU affinityの一致を要求します。
開発途中の実行は`run --allow-dirty`で明示的に許可します。
worker protocolはv4です。候補revisionと保存完了通知を照合し、期限内にatomic保存が完了した結果だけを受理します。
過去のv3 artifactは読取adapterで扱い、書き換えません。

runnerはwheelへ含めず、repo内で管理します。`benchmarks/local-evaluation/`は新しい評価結果の出力先として利用できるGit対象外の領域です。
完了した評価記録は必要に応じてrepo外へ移し、`research`には蓄積しません。
回帰テストはsolver・GMB・benchmark別に配置しています。部分実行と追加先は[テストガイド](tests/README.md)を参照してください。
GMB環境の構築・診断・計測は[GMBの説明](benchmarks/gmb/README.md)、共通配置検査による比較は[比較評価の説明](benchmarks/gmb_comparison/README.md)を参照してください。
