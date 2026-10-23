# Q34 — Fractal basins

結論は [answer.md](answer.md)。予測は [prediction.md](prediction.md)、ハッシュ・UTC時刻は [prediction.lock.json](prediction.lock.json)。初回の厳格なフラクタル認定0/12、1ulp感度3/12、完成solverの答え集合変更0/24組。有限尺度候補と数値床、事後追加を区別する。

主な成果物：

- `per-problem.csv` / `local-summary.json`：問題別指数・区間・判定理由。
- `uncertainty.csv` / `uncertainty-curves.png` / `.svg`：14尺度の変更率、根間変更率、実際の変位。
- `full-runs.csv` / `full-comparisons.csv`：完成solverの同seed比較。
- `full-mp-runs.csv` / `full-mp-summary.json`：53ビットmpmath丸めも変えた補足。
- `dense-summary.json` / `dense-uncertainty.csv`：事後に選んだ2問の新1024始点。
- `inputs.json`：凍結DSL・箱・根代表・境界選択用の旧始点。旧データのハッシュも含む。
- `patches/`, `measure/`, `verify/`, `dense/`：局所探索の全終点・ラベル・nfev・実変位。
- `full/`, `full-mp/`, `full-recheck/`：完全workerの結果。`.json.gz` は可逆圧縮。`candidates/` は候補を16件ずつに分けたもの。`dataio.py` が圧縮の有無を透過的に読む。
- `theory.md`, `polynomial-check.json`, `ulp-examples.json`：適用条件、多項式の独立照合、hexで隣接1ulpを確認できる具体例。
- `verification.json`, `manifest.json`, `compression.json`：最終検査とファイルハッシュ。

## 保存結果だけを検査・再集計する

リポジトリrootから実行する。数値計算は元のPython 3.12.11、NumPy 2.5.1、SciPy 1.18.0、SymPy 1.14.0を使った。実際の環境は `implementation-lock.json` にある。下のPythonパスはこの共有機の既存仮想環境。別の機械では同じ依存を入れたPythonへ置き換える。

```bash
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/fractal-basins/analyze.py local
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/fractal-basins/analyze.py full
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/fractal-basins/analyze_supplement.py full-mp
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/fractal-basins/analyze_supplement.py dense
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/fractal-basins/analyze_supplement.py audit
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/fractal-basins/verify.py
```

`analyze.py controls` はsolverを使わない解析的境界の対照。図は `python3 jssa/difficulty/fractal-basins/plot.py` で作れる（この機械のPython 3.14＋matplotlibを作図だけに使用）。モデル実行にPython 3.14は使っていない。図は生成後に目視確認した。

## 新しく測定する

保存結果を別に保管した新しい作業コピーで行う。予測文書と固定記録は保存し、`src` と対象DSLは `60db4b6` のままとする。`prepare` は既存入力を上書きしない。測定の途中再開では `prepare` を繰り返さず、同じbatchを続ける。完了済みJSON/GZIPを見つけるとskipする。

```bash
gcc -shared -fPIC -O2 -frounding-math jssa/difficulty/fractal-basins/fenv.c -o jssa/difficulty/fractal-basins/fenv.so -lm
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/fractal-basins/experiment.py prepare
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/fractal-basins/experiment.py batch locate 165
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/fractal-basins/experiment.py batch measure 165
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/fractal-basins/experiment.py batch verify 165
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/fractal-basins/experiment.py rounding-audit
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/fractal-basins/experiment.py batch full 165
```

各stageの `remaining` が0になるまで同じコマンドを繰り返す。**複数batchを同時に走らせない**。1batch最大3子プロセス、数値ライブラリは1thread、batchは最大170秒、局所試行2秒、完成worker30秒、子プロセスにも外側の制限がある。ユーザーの「並列最大3、1コマンド数分以内」を優先し、一括の長時間コマンドは用意していない。

補足を再現する場合は、元の予測検証と区別したまま `experiment.py batch full-mp 165`、`dense.py batch` をそれぞれ完了まで繰り返す。主比較の集計後、`recheck-jobs.json` に指定された再確認を `experiment.py batch recheck 165` で実行する。今回の再確認は通常版と上向き版の候補分類差を確認する2実行。

`python3 jssa/difficulty/fractal-basins/compress_evidence.py` は生成した完成solver記録だけをgzip化する。展開後のbyte列とSHA-256が一致することを確認してから元のJSONを置き換える。新しい計算や間引きはしない。圧縮前後とも1ファイル5MB未満。集計コードはJSON/GZIPの両方に対応する。

## 数値の読み方

`f` は全ラベルの相違率、`f_root` は既知の異なる根へ行った対の数を全対数で割った率。`conditional_root_f` だけが両端根を条件とする率である。F（不採用）とU（未知の小残差終点）は既知の吸引先として扱わない。α_rawには数値床や稀な変更が混じるので、α<1だけでフラクタルを認定しない。

事前のソースハッシュ、追加計画のハッシュ、実装修正の経緯はそれぞれ `implementation-lock.json`、`supplement.lock.json`、`dense.lock.json`、`deviations.md` にある。予測文書は不変だが、測定後に集計・可逆圧縮対応を修正したため、実験コードの現在のハッシュは初回の実装ロックとは異なる。最終版の各ファイルのハッシュは `manifest.json` を参照する。
