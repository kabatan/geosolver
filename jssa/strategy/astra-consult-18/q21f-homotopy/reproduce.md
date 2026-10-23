Q21f 小検証の再実行・保存形式

**背景資料の所在。** Q3・Q4・Q11は `astra-consult-17/Q*/answer.md` ではなく、それぞれ `jssa/difficulty/wall-diagnostic/answer.md`、`multiplicity/answer.md`、`certify-all/answer.md` を参照した。Q5はタスク表が指す `jssa/difficulty/full-solver-nohard/` にも回答ファイルを確認できず、未読。Q5の結果を本報告の根拠には使っていない。封印された未使用問題の結果は開いていない。

**環境。** リポジトリのルートを作業ディレクトリとする。Pythonは `/home/kabatan/work/solver/.venv/bin/python`、`PYTHONPATH=src`。Juliaは `/home/kabatan/.julia/juliaup/julia-1.12.6+0.x64.linux.gnu/bin/julia`。Python環境と既存Juliaキャッシュは読み取り専用で利用した。成果物フォルダの以下の既存キャッシュへのリンクは、このマシン以外にはそのまま持ち出せない。

`prepare_julia.py` は既存の `~/.julia/packages` のソースをローカルのimplicit package環境へsymlinkする。Pkg.add、instantiate、パッケージのコピーやダウンロードは行わない。古いTreeViewsにはProject.tomlがないため、ローダー用の名前・UUIDだけを成果物フォルダ内に書き、srcを既存キャッシュへリンクする。利用候補の一覧は `cached-julia-packages.json`。実際のworkerはHC 2.22.3とJulia 1.12.6を報告した。

`run_hc.py` は `JULIA_PKG_OFFLINE=true`、`JULIA_PKG_PRECOMPILE_AUTO=0`、ローカルdepotと既存depot、`--compiled-modules=existing --pkgimages=existing` を設定する。Julia・GC・BLASは1スレッド。`threading=false`。新しい環境へのインストールではなく、手元に既にあったコードを実行できるよう配置したもの。

**再実行順。** 以下は既存の本フォルダの結果ファイルを上書きする。初回の規則は `protocol.md`、実行済みの入力ハッシュは `input-lock.json` を参照。検証目的での再実行時には、元の結果を別途保存してから実行する。

```bash
export PYTHONPATH=src
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21f-homotopy/prepare_julia.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21f-homotopy/prepare.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21f-homotopy/audit_exact.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21f-homotopy/run_hc.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21f-homotopy/run_local.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21f-homotopy/score_hc.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21f-homotopy/summarize.py
```

**実行前の固定と後処理。**

- `prepare.py`：既存のHの代数化器をimportする。自然問題6問、fresh/inlineの12試行を記録。11入力が上限内の正方系、HMMT 2010 inlineだけ変換失敗。式、順序、係数は `inputs/` に保存。失敗した入力を手直しして混ぜていない。
- `run_hc.py`／`serve.jl`：全44実行のseed、経路終点、return_code、特異フラグ、残差、条件数診断、受理・棄却ステップ数を `hc-runs/` へ保存。`solutions(...; only_nonsingular=false)` により特異終点も回収する。ポリヘドラル法は既定のaffine版（`only_non_zero=false`）。
- `run_local.py`：各問で同じseedから60点を一様生成し、すべてを `local-starts-lock.json` へ保存してから探索する。各開始のdeadlineは `min(問deadline, 開始時刻+2秒)`。タイムアウト時も60を分母にするコードだが、今回は全開始を完了した。
- `measurement.py`：凍結ヘルパーで候補の元残差・箱・guard・hardを評価し、既存 `probe_basins.py` と同じ順序・閾値で採点する。これは既存局所プローブの比較基準であり、完成solverの最終高精度検証ではない。
- `score_hc.py`：HC終点から元DSL変数を取り出す。虚部の絶対閾値1e-7で実射影候補とし、再探索・研磨なしで採点する。相対1e-6の射影クラスタリングは集計用の後処理で、厳密根数の代用品ではない。全補助変数が実数に近いことと、元DSL変数への射影が実数に近いことも別に記録する。例えばHMMT 2014 inline/total_degree/211024では補助変数の虚部のためHCの実根フィルターは0だが、元変数の実射影候補は採点を通る。この違いを厳密根の追加・消失とは読まない。
- `audit_exact.py`：有理数のlex Gröbner基底、標準単項式数（重複度込みの代数的長さ）、単変数因子の次数・実根数を保存。1入力30秒上限。
- `summarize.py`：三角形状の基底から得られる根数をまとめる。AIME IIの6次消去式と補助変数の2通りの持ち上げ、HMMT 2014 fresh/inlineの因子比・基底一致を有理数で追加照合する。相異なる根数と代数的長さは別列。

**環境対応・エラーの履歴。** 初回のsmokeはTreeViewsのローダー情報欠落で失敗（`smoke.log`）。ローカルのメタデータを追加した2回目はseed引数の型で失敗（`smoke-second.log`）。HCが要求する `UInt32` へ呼び出し側を修正し、全実行に同じ修正を適用した。問題式や採点基準の調整ではない。以後、既知の2根系を両開始系で解くwarmupが `[2,2]` を返し、自然問題の全44実行が終了した。最終の `smoke.jl` は型修正後であり、保存済みsmokeログは修正前の失敗履歴である。

HMMT 2010 inlineの準備エラーは、非零条件に残った有理式 `-2*v_w**3/(v_w**2+1)` を多項式化できなかったもの。準備規則どおり欠測として残した。他の11入力は固定上限（変数10、次数積512、2MiB）内だった。

`hc-execution.json` の `return_code=-15` は全ジョブ終了後に対話workerを親から停止した終了コード。各ジョブは `status=ok`、環境ロード約165.7秒、warmup約150.0秒、全体約438.7秒。個々の実行には形状別の追加JITも混ざるので、2seedの秒数を単純平均して方法間の性能比較には使わない。

**保存上の意味。** `hc-summary.csv` の `failed` はHCの失敗分類であり、無限遠を含めない。`n_hc_distinct` はHCによる数値的重複除去後の個数、`comparison.csv` の `exact_distinct_complex` は有理Gröbner基底からの照合値。`n_hit_clusters` は元DSLへ射影し固定採点を通った候補のクラスタ数で、認証された解数ではない。元の問題に対する答えの完全性や存在の証明書は今回作成していない。
