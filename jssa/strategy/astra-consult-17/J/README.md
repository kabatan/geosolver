# astra-Jの再現用ファイル

結論は [answer.md](answer.md)。新しい中心成果としては採用見送り。既存データを再計算した探索であり、新しい局所探索・完成solverの実行はない。

## 再現

リポジトリのルートで、次を**順番に**実行する。Pythonは指定された既存venv、計算は1プロセスで、BLAS等も1スレッド。追加パッケージは不要。pandasは環境にないため使っていない。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/J/explore.py > jssa/strategy/astra-consult-17/J/explore.log
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/J/validate_depth.py > jssa/strategy/astra-consult-17/J/validate-depth.log
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/J/verify.py
```

`-B` は読み込んだモジュールの場所にキャッシュを書かないため。スクリプトの出力先は自分のあるJフォルダに固定してある。モデル学習はnumpyの小行列計算、統計はscipyで行う。全体はこの環境で数十秒の集計規模であり、重い探索ジョブではない。

## ファイル

| ファイル | 内容 |
|---|---|
| `exploration-plan.md` | 候補一覧を見る前の三方向と、最初の結果を見た後に固定した追加解析。正式な事前登録とは区別 |
| `findings-before-candidate-list.md` | consult-17の候補一覧を読む直前に固定した結論 |
| `explore.py` | 既存323問・両seedの集計、作図グラフ、複数の値、条件数などの探索 |
| `exploration-per-problem.csv` | 323問の結合表。空欄・`nan`は未観測 |
| `exploration-summary.json` | 三方向の初期探索。多重比較を含むので確認研究の結果として使わない |
| `branch-counts.csv` | 複数の参照値を持つ8問×2 seed |
| `validate_depth.py` | 人間とsolverの相関差、群ブートストラップ、年度を外す交差検証 |
| `depth-analysis-per-problem.csv` | 人間難度131問の解析表。`n_cons`は作図数であり等式の数ではない |
| `human-source-join.csv` | Easy2Hardの原文・難度131問の照合記録 |
| `depth-summary.json` | 回答の主表の数値 |
| `depth-cross-validation.csv` | 目的変数ごとの全foldの予測と二乗誤差 |
| `input-sha256.json` | 使用した入力652ファイルのハッシュ。J内の派生CSVも含む |
| `verify.py`, `verification.json` | 分母、結合、実行の重複、原データ件数、入力ハッシュ、ASTを使った独立な深さ計算の照合 |

深さはDSL上の作図の最長依存鎖であり、人間の証明の段数ではない。正答近傍の特異値は既存の `first_hit` の保存値を使う。solver費用は各実行の正誤を反映した180秒ペナルティの3回平均。数値結果の解釈上の制約はanswer.mdを参照。

## 調査と実行の記録

- 指定の背景3資料を読んでから仮説を記録し、consult-17-promptは予備結論を固定した後に読んだ。
- 初回にpandasのimportが失敗したので、標準csvとnumpyに置き換えた。インストールしていない。
- データ照合では文字列からの浮動小数点変換により6問に約1.1×10⁻¹⁶の差があった。最初の過度に厳しい完全一致チェックを、解析側と同じ1e-12以内の照合に直し、実際の最大差も保存した。
- 独立なAST構文解析による深さは323問すべてで一致し、解析不能・循環依存は0件だった。
- ワークスペースに元からあったJ外の未追跡3ファイルは触っていない。コード、集計表、文書の新規作成はJ内のみ。
