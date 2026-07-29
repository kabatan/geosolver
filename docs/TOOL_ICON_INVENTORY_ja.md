# GeoTarget 作図ツール・アイコン一覧

この一覧は `src/geotarget/dsl_catalog.json` のV15関数とUIの作図ツールを対応させたものです。アイコンの識別子は関数IDと同一にし、ファイル名は `tool-<ID>.svg` を推奨します。

## アイコン共通仕様

- SVG、`viewBox="0 0 24 24"`、背景なし
- 線幅は原則1.5、`stroke="currentColor"`。意味のある点だけ塗りつぶす
- 通常の点は半径1.5前後。入力を示す点と、生成物を示す点・線を視覚的に区別する
- 文字・関数名・色だけに意味を依存させない
- 同じ図柄の使い回しを避け、関数の「入力→生成物」が24pxでも分かる構図にする
- 「直接」はキャンバスを直接クリックするツール、「図選択」は既存オブジェクトを順に選ぶツール、「フォーム」は数値・式・可変長引数を設定して使うツール

## 点・交点

| ID | 表示名 | 操作 |
|---|---|---|
| `Point` | 座標で点を作る | 直接 |
| `PointOnLine` | 直線上の点 | 図選択 |
| `PointOnSegment` | 線分上の点 | 図選択 |
| `PointOnCircle` | 円上の点 | 図選択 |
| `Intersect` | 交点 | 図選択 |
| `Midpoint` | 中点 | 図選択 |
| `ClosestPoint` | 最近点 | 図選択 |
| `Center` | 円・円弧の中心 | 図選択 |

## 直線・線分

| ID | 表示名 | 操作 |
|---|---|---|
| `Line` | 2点を通る直線 | 直接 |
| `Segment` | 線分 | 直接 |
| `Ray` | 半直線 | 図選択 |
| `Vector` | ベクトル | 図選択 |
| `FootOfPerpendicular` | 垂線の足 | 図選択 |
| `PerpendicularBisector` | 垂直二等分線 | 図選択 |
| `AngleBisector` | 角の二等分線 | 図選択 |

## 円・円弧

| ID | 表示名 | 操作 |
|---|---|---|
| `Circle` | 中心と半径の円 | フォーム |
| `CircleThroughPoint` | 中心と通過点の円 | 直接 |
| `CircleThroughThreePoints` | 3点を通る円 | 図選択 |
| `Arc` | 円弧 | 図選択 |

## 多角形

| ID | 表示名 | 操作 |
|---|---|---|
| `Polygon` | 多角形 | 直接 |
| `RegularPolygon` | 正多角形 | 図選択＋頂点数・向き |
| `InscribedPolygonVertices` | 内接多角形の頂点 | フォーム |

## 平行・垂直・接線

| ID | 表示名 | 操作 |
|---|---|---|
| `ParallelLine` | 平行線 | 図選択 |
| `PerpendicularLine` | 垂線 | 図選択 |
| `ContactPoint` | 接点 | 図選択 |
| `TangentAtPoint` | 接点における接線 | 図選択 |

## 変換

| ID | 表示名 | 操作 |
|---|---|---|
| `Reflect` | 鏡映 | 図選択 |

## 三角形の中心・円

| ID | 表示名 | 操作 |
|---|---|---|
| `Centroid` | 重心 | 図選択 |
| `Incenter` | 内心 | 図選択 |
| `Circumcenter` | 外心 | 図選択 |
| `Orthocenter` | 垂心 | 図選択 |
| `Excenter` | 傍心 | 図選択＋頂点A/B/C |
| `NinePointCenter` | 九点円の中心 | 図選択 |
| `FermatPoint` | フェルマー点 | 図選択＋分岐 |
| `GergonnePoint` | ジェルゴンヌ点 | 図選択 |
| `NagelPoint` | ナーゲル点 | 図選択 |
| `SymmedianPoint` | 類似重心 | 図選択 |
| `Incircle` | 内接円 | 図選択 |
| `Circumcircle` | 外接円 | 図選択 |
| `Excircle` | 傍接円 | 図選択＋頂点A/B/C |
| `NinePointCircle` | 九点円 | 図選択 |
| `IncircleContactPoint` | 内接円の接点 | 図選択＋辺BC/CA/AB |

## 測定

| ID | 表示名 | 操作 |
|---|---|---|
| `Distance` | 距離 | 図選択 |
| `Ratio` | 2つの長さの比 | 図選択 |
| `Length` | 長さ | 図選択 |
| `Angle` | 角度 | 図選択 |
| `Area` | 面積 | 図選択 |
| `Perimeter` | 周長 | 図選択 |
| `Radius` | 半径 | 図選択 |
| `Circumference` | 円周 | 図選択 |
| `Dot` | 内積 | 図選択 |

## 幾何条件

| ID | 表示名 | 操作 |
|---|---|---|
| `OnLine` | 直線上 | 図選択 |
| `OnSegment` | 線分上 | 図選択 |
| `OnCircle` | 円周上 | 図選択 |
| `Collinear` | 共線 | 図選択 |
| `IsTangent` | 接する | 図選択 |
| `Parallel` | 平行 | 図選択 |
| `Perpendicular` | 垂直 | 図選択 |

## ガード・範囲

| ID | 表示名 | 操作 |
|---|---|---|
| `Assume` | 条件を仮定 | フォーム |
| `AssumeEq` | 等しい | フォーム |
| `AssumeNe` | 異なる | フォーム |
| `AssumeLt` | 未満 | フォーム |
| `AssumeLe` | 以下 | フォーム |
| `AssumeGt` | より大きい | フォーム |
| `AssumeGe` | 以上 | フォーム |
| `Bound` | 変数の範囲 | フォーム |
| `AssumeAcute` | 鋭角三角形 | 図選択 |
| `AssumeRight` | 直角三角形 | 図選択 |
| `AssumeObtuse` | 鈍角三角形 | 図選択 |
| `AssumeConvex` | 凸多角形 | フォーム |
| `AssumeNoSelfIntersecting` | 自己交差しない | フォーム |

## 高度な構成

| ID | 表示名 | 操作 |
|---|---|---|
| `RadicalAxis` | 根軸 | 図選択 |
| `Polar` | 極線 | 図選択 |
| `Pole` | 極 | 図選択 |
| `PowerOfPoint` | 点の冪 | 図選択 |
| `IsodynamicPoint` | 等力点 | 図選択＋分岐 |
| `FeuerbachPoint` | フォイエルバッハ点 | 図選択 |
| `Mittenpunkt` | ミッテン点 | 図選択 |
| `SpiekerCenter` | シュピーカー中心 | 図選択 |

## 新規作図アイコンを作らない互換関数

次はDSL parserが既存JSONの読み込み用に保持していますが、V15 manual上、新規問題では禁止または非推奨です。誤用を誘発するため通常paletteへは出しません。

`PointOnArc`, `IntersectLines`, `IntersectLineCircle`, `IntersectCircles`, `InscribedPolygon`, `TangentLine`, `Rotate`, `AssumeOrder`

## UIへの受け渡し

アイコン実装時は、上記IDをkeyにして `PaletteGlyph` の対応を置き換えます。1つのアイコンを複数IDへ流用する場合も、意味が同一の場合だけにしてください。特に以下は別図柄にします。

- `PerpendicularLine` と `FootOfPerpendicular`
- `Circle`, `CircleThroughPoint`, `CircleThroughThreePoints`
- `ParallelLine` と制約の `Parallel`
- `PerpendicularLine` と制約の `Perpendicular`
- `Incenter` と `Incircle`
- `Circumcenter` と `Circumcircle`
- `Excenter` と `Excircle`
