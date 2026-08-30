# research移植後の追加整理

対象は移植commit `faf43a85`に残っていた、確認済みの未使用補助関数・旧import・ローカル生成物。
探索アルゴリズム、探索・精密化の設定、最終受理の閾値、323問のDSLと参照値は変更していない。

## 削除したもの

- `geometry/mp/mp_api.py`の未使用`_ensure_point`・`_ensure_line`。
- 同moduleの、存在しない`mpmath_geometry`をimportする旧経路と、呼ばれていなかった面積fallback。
  現役の`MP_Area`・`MP_PolygonArea`は従来の専用実装を引き続き使う。
- `operations/intersections.py`の未使用な数値変換・距離・許容値の転送関数3個と、そのimport。
- `operations/intersections_selection.py`末尾の旧転送関数4個。現役の交点選択・枝traceは維持。
- `safety/__init__.py`の旧鋭角判定wrapperと、それ以外に参照されない`safety/numeric.py`の実装。
  現役の`AssumeAcute`は`guards.py`の精度・scaleに対応した判定を引き続き使う。
- 高精度素数判定に使われなくなった固定素数表と、通常精度側の未使用set。
  通常精度の記号式生成で実際に使う素数表は維持した。

製品Pythonソースは7ファイルを変更し、差引286行削減した。
登録decoratorを介して呼ばれる関数、公開alias、現役のNOMAD/SciPy/hybrid経路は削除していない。
削除した未使用関数は12個。整理前後のAST比較で、残した関数の変更が以下の2つのimport修正だけであることも確認した。

## 修正した接続

`operations/numeric.py`の`IsInteger.mp()`・`IsPrime.mp()`は、存在しない
`geometry.operations.mp_impl`をimportして`ModuleNotFoundError`になっていた。
正しい`geometry.mp.mp_number_constraints`の実装へ接続した。

通常のDSL高精度評価は以前から別の正しいwrapperを使っていたため、今回その数値式を変更する必要はない。
直接の`.mp()`呼出しとMP runtimeでの呼出しを、DSL高精度評価と比較するテストを追加した。
負値、整数、非整数、1000より大きい素数、近整数を80・180桁で検査し、SymPyへのfallbackで失敗を隠していないことも型で確認する。

## 再発防止と検証

`tests/test_geometry_cleanup.py`を追加した。最初の11テストを修正前の製品で実行し、
MP接続・旧helper・欠損importの検査10件が失敗し、現役の面積・鋭角判定の対照例1件が成功することを確認した。
未使用素数表の再導入防止2件を追加した後、修正版で新規13件すべてが成功した。

- 全体テスト：既存296件＋新規13件、**309件成功**（113.19秒）。性能比較値ではない。
- Ruff（`--no-cache`）、262 Pythonファイルの構文検査、schema `--check`：成功。
- corpus validator：323 inventory、323 DSL、323 runnable、323 verified、issuesなし。
- 323 DSLと`cases.jsonl`：移植台帳のSHA-256と全件一致。
- engine lock、実import元、runtime依存の一致：成功。
- 16種類の独立process importと、各processでのengine lock確認：成功。
- Linuxの新規wheelをrepo外の新しいvenvへ、lockに固定した依存versionとともにインストール。
  修復したMP backend、`sqrt(2)*pi+sqrt(3)`、`sqrt(2)+1e-110`、変数を持つ`x=2`、`doctor`の動作確認に成功。

今回323問をsolverで全件再探索したわけではない。Windows/macOS実機での新規確認、
性能比較、バグ不存在の証明、`solver-a0`等のfreeze tag作成は行っていない。

## 生成物と版識別

repo内に残っていた`dist/`（旧wheel、約336KB）と`.ruff_cache/`（約52KB）を削除した。
これらは再生成可能であり、研究データではない。実行環境の`.venv/`は維持した。
新しいwheelと検証venvはrepo外の一時領域に作成し、このcommitへ含めない。
旧作業ツリー、原資料、修正台帳、過去の実験結果は変更していない。

整理前source：`sha256:3992894ba012da1f0b43c219b04a860ba29b3307f1bdc8cbfb0f9db88abcf678`

整理後source：`sha256:6ecc0b4c0f71b4bc0ccb1e3b94baaa600afe7e43dc96a1dee07389c083eed6d6`

config・dependency lockのhashは変更していない。
`engine-lock.json`は正式な更新スクリプトで再生成した。
`RESEARCH_IMPORT_MANIFEST.json`は移植当時の証拠なので変更しない。
