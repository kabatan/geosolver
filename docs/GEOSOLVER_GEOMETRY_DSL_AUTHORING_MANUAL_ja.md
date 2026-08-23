# GeoSolver Geometry DSL 作成マニュアル

## 文書構造

問題は`id`、`variables`、`constructions`、`conditions`、`target`の5項目から成ります。未知変数は`variables`へ文字列で、作図は評価順に`constructions`へ記述します。

```json
{
  "id": "right-angle",
  "variables": [],
  "constructions": [
    {"name": "A", "expression": "Point(0, 0)"},
    {"name": "B", "expression": "Point(1, 0)"},
    {"name": "C", "expression": "Point(0, 1)"}
  ],
  "conditions": [],
  "target": "Angle(B, A, C)"
}
```

## 条件

代数的なrelationは`left`、`operator`、`right`で表します。`right`には整数、浮動小数、または`sqrt(2)`のような厳密式文字列を指定できます。`true`と`false`は数値として扱いません。

```json
{"left": "Distance(A, B)", "operator": "=", "right": 5}
```

幾何predicateは公開名をそのまま記述します。

```json
{"predicate": "AcuteTriangle(A, B, C)"}
```

公開catalogには内部探索用の仮定関数や境界関数を含めません。

## targetと角度

`target`はscalar式にします。`Angle(A, B, C)`の単位はradianで、頂点は中央の`B`です。degreeが必要な場合は`Degrees(Angle(A, B, C))`を使用します。

## 安全性と完全性

式はGeoSolver catalogに登録された関数だけを使用できます。属性アクセス、import、任意コード実行は許可されません。GeoSolverの通常探索は数値的であり、有限解問題であっても解の完全列挙を一般には証明しません。`completeness: unknown`を数学的な不存在証明として解釈しないでください。
