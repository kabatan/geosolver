# GeoSolver

GeoSolverは、有限個の値を答えとして持つ2次元幾何問題を数値探索し、可能な場合は厳密な答えdescriptorを返すsolverです。網羅性は証明せず、結果の`completeness`は常に`unknown`です。

この`research`ブランチにはsolver本体、323問の開発用DSL、回帰テスト、研究用runnerだけを中心に収録しています。
HTTP/UI、Julia、旧solver、過去の大容量実行結果は含めません。
出典と参照値は現行の`benchmarks/cases.jsonl`、研究方針は研究計画書で管理します。
完了済みの移植・修復資料はGit履歴に残し、通常の実行・テストからは切り離しています。

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

## 厳密結果

- `algebraic`: 整数係数多項式、実根番号、隔離区間、十進近似。
- `affine_pi`: 代数的数のπ係数と代数的な定数項、十進近似。

ラジアンの`π/2`は`affine_pi`、`Degrees(...)`で変換した`90`は`algebraic`です。workerのcrash、artifact欠落、artifact破損は`engine_error`であり、正常探索後の`no_answer_found`とは区別されます。

最終検証は通常120・180桁、未確定時は最大500桁まで評価し、枝変更や禁止境界への近さを検査します。
これは数値誤差の推定を伴う検証であり、一般的な存在証明ではありません。
低精度の予備確認でも保持済みの高精度座標は丸め直しません。
同じ座標を作業精度と追加30桁で比較し、幾何関数内部の相殺による丸め誤差も見積もります。
面積0の等式は検証時だけ同値な符号付き残差を使い、公開の`Area`や目的式の意味は維持します。
候補の`answer_precision_dps`は作業精度であり、全桁の正確さを保証しません。
厳密化は記録された不確かさから候補発見用の精度を選び、元の作業精度・誤差範囲で最終照合します。
内部の厳密化記録には`discovery_precision_dps`を併記します。
内部期限で正常に打ち切った場合は完成済みの答えを保持し、`termination_reason=time_limit_reached`を返します。

## 開発

```bash
uv run python -m pytest
uv run ruff check src tests benchmarks .github/scripts
```

研究用campaign runnerと評価資料はwheelへ含めず、repo内で管理します。

```bash
uv run python benchmarks/research_runner.py validate
uv run python benchmarks/research_runner.py run benchmarks/local-evaluation/my-run --jobs 4 --seeds 0
uv run python benchmarks/research_runner.py assess benchmarks/local-evaluation/my-run
uv run python benchmarks/research_runner.py summarize benchmarks/local-evaluation/my-run
```

正式実行はclean tree、engine lock、実際のimport元・依存version・CPU affinityの一致を要求します。
開発途中の実行だけは`run --allow-dirty`で明示的に許可できます。
worker protocolはv3です。過去の評価artifactは書き換えず、runnerの読取adapterで比較します。

323問は既にsolver開発に使用した集合であり、未使用の評価集合ではありません。
問題・出典・履歴の参照方法は[benchmark説明](benchmarks/README.md)、今後の研究方針は
[研究レポート・実験計画](JSSA_2026_REPORT_AND_EXPERIMENT_PLAN.md)を参照してください。

## 作業場所と旧資料

通常の作業場所は`/home/kabatan/work/solver`直下、ブランチは`research`です。
作業用worktreeは追加しません。移植時に作った`solver-wt/research`は解消済みです。

以前の修正報告・実行結果・未追跡ファイルは、repo外の
`/home/kabatan/work/solver-research-assets/workspace-before-research-root-20260830/snapshot/`
へ元の相対パスを保って退避し、全ファイルのSHA-256を照合しました。
旧trackedファイルの未commit変更はstash `d1fccaea8583bdc645f9d88716aa47540ba4f055`にも保存しています。
同保全ディレクトリの`RECOVERY.md`に復旧方法を記録しています。旧作業branchは削除済みですが、保全済みの履歴・研究資産・stashは維持しています。
