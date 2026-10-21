# テスト

現行solverと評価系の回帰テストを、対象機能別に配置しています。repo直下から実行します。

```bash
uv run python -m pytest --import-mode=importlib
uv run ruff check src tests benchmarks .github/scripts
```

| 場所 | 対象 | 部分実行 |
|---|---|---|
| `solver/` | 公開API、問題のコンパイル、幾何、数値評価、探索、精密化、厳密化、worker | `uv run python -m pytest --import-mode=importlib tests/solver` |
| `gmb/` | GMB環境・計測・比較入力・独立検査器・採点 | `uv run python -m pytest --import-mode=importlib tests/gmb` |
| `benchmarks/` | solver用corpusの整合性・評価runner | `uv run python -m pytest --import-mode=importlib tests/benchmarks` |
| `helpers/` | 複数ファイルで使う人工的な候補・検証記録の構築 | テストを置かない |

solver内でも、`test_compilation.py`、`test_contacts.py`、`test_refinement.py`のように機能名で探せます。
監査日や修正回数でファイルを増やさず、対応する機能のファイルへ検証を追加します。
同じ検証手順の通常値・境界値・単位変更は、意味のある違いを残してパラメータ化します。
公開されているが323問に含まれない幾何機能も、`solver/test_public_geometry.py`で検証します。

テストファイルから別のテストファイルをimportしません。共有処理は`helpers/`へ置き、repoの位置は`paths.py`の`REPO_ROOT`を使います。
テスト専用の問題生成処理・反例・期待値をsolver本体やbenchmark runnerの探索へ混入させません。

GMBのテストは主に人工入力と保存形式の検査です。固定GMB環境を使う任意の統合テストは、環境がない場合にskipします。
自然問題の求解や新しい性能campaignは、通常のテストでは実行しません。
