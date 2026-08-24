# GeoSolver

GeoSolverは、有限個の値を答えとして持つ2次元幾何問題を数値探索し、可能な場合は厳密な答えdescriptorを返すsolverです。数値探索は一般には完全性を証明しないため、結果の`completeness`は`proven`または`unknown`として`status`とは独立に返します。

## 対応環境

- `standard`: Linux、Windows、macOS。既定900秒、180〜900秒、自動コア。
- `reference`: Linuxのみ。比較用の決定論的な180秒・1コア実行。

WindowsまたはmacOSで`reference`を指定すると、別engineへ切り替えず`unsupported_platform`を返します。

## インストールとCLI

Python 3.12とJuliaを用意し、Julia projectの依存関係をinstantiateしてください。

```bash
uv sync --extra dev
julia --project=src/geosolver/julia -e 'import Pkg; Pkg.instantiate()'
uv run geosolver doctor
uv run geosolver validate path/to/problem.json
uv run geosolver solve path/to/problem.json --output result.json
uv run geosolver ui
```

CLIは`validate`、`solve`、`doctor`、`ui`を提供します。HTTP APIはloopback限定の`/api/v1`です。

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
result = solve(problem, SolveOptions(engine="standard", cores="auto"))
```

互換layerはありません。正式なpackage/import/CLI名はすべて`geosolver`です。

## 問題JSON

```json
{
  "id": "example",
  "variables": ["x"],
  "constructions": [
    {"name": "A", "expression": "Point(0, 0)"}
  ],
  "conditions": [
    {"left": "x", "operator": "=", "right": 1},
    {"left": "x", "operator": ">=", "right": 0},
    {"predicate": "AcuteTriangle(A, B, C)"}
  ],
  "target": "Distance(A, B)"
}
```

relation operatorは`=`、`!=`、`<`、`<=`、`>`、`>=`です。`right`はbooleanを認めず、整数、浮動小数、厳密式文字列を型を保ったまま扱います。幾何関数とpredicateの一覧は`geosolver ui`のcatalog、または`/api/v1/dsl/catalog`で確認できます。

## 厳密結果

- `algebraic`: 整数係数多項式、実根番号、隔離区間、十進近似。
- `affine_pi`: 既約有理数のπ係数と定数項、十進近似。

ラジアンの`π/2`は`affine_pi`、`Degrees(...)`で変換した`90`は`algebraic`です。workerのcrash、artifact欠落、artifact破損は`engine_error`であり、正常探索後の`no_answer_found`とは区別されます。

## 開発

```bash
uv run pytest
uv run ruff check src tests
cd frontend
pnpm test
pnpm build
pnpm test:sites
```

mainには製品runtimeとreleaseに必要なassetだけを置きます。研究実験、全145問の手動release比較、過去の実行物は`experiment` branchで管理します。
