# 事前登録14・段階(1)のみ：全残差の最小特異値

精密化到達精度の段階(2)は実行しない。既存の精密化結果、stage/S1、S3/run、S5/run、S6/run、per-candidate.csv、exact-strong等の成否・桁数一覧は読まない。既存図も再利用しない。git commit/pushはしない。

## 入力と参照図

対象はbenchmarks/dslの323ファイル。凍結版load_problem_bundle後に探索変数が0の問題は理由付き除外。それ以外は凍結版60db4b679b04167175c51c479c87c22fa663fda0、source_hash `sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5` を `/tmp/mech-inv-clean/src` からimportする。毎workerでhashを検証する。

各問題で通常のpublic solve(seed=0, cores=1, time_limit_seconds=180)を1回のみ実行する。S5/worker.pyのMemoryRunnerと同じruntime.worker.executeを使い、通常solveの処理・予算・候補順を変えず、最初の探索候補と最初の最終検証通過座標のみ観測する。通常solve内部の精密化は参照図生成に必要な処理としてのみ実行する。診断の精密化履歴や到達桁数は保存・調査・集計しない。

S5/reference.pyと同じ再検証・620桁closure（1回、180秒、残差1e-580、findroot許容1e-1160、最大1240steps）を行う。保存座標でhard feasibility・残差・目標評価を確認する。独立参照式は `benchmarks/cases.jsonl` の数学的answerだけをDSLファイル名で対応付け、benchmarks/research_runner.pyのreference_expressionsと同じ表記正規化を適用する。これは実験成績表ではなく、参照解の300桁一致門に必要なベンチマークの正答入力である。700桁評価で絶対誤差とmax(1,|ref|)で割った誤差がともに1e-300以下を要求する。参照図を作れない問題は理由を記録する。各問題全体600秒上限、再試行なし。

## 残差と固定除数

σ_baseは凍結版 `_smooth_zero_constraint_residuals` を実際に呼び出して作る既定残差。Distance(P,Q)=0の座標差、接点を使う接する条件の書き換え、正半径補助式を含む。凍結版関数が元残差へfallbackする場合もその実際の動作を保持し、`base_frozen_original_fallback` に記録する。marker residualによって実際の行数とfallbackを確認する。

σ_rawは凍結版evaluate_hp_residualの全残差から作り、残差書き換え一式を適用しない。例外は微分用の接する条件のT1置換のみ。S4/worker.pyのinventory, objects, t1を取り出した `helpers.py` を使う。直線・円は正規化直線係数で `(a*cx+b*cy+c)^2-r^2`、円・円は参照座標で選んだ外接 `d-r1-r2` / 内接 `d-|r1-r2|`。Distance(center,line)=radiusもS4 inventoryで認識してT1とする。接点は使わない。距離0の座標差や半径補助式はrawには含めない。

今回 `/tmp/s3-impl/src` の実装は実行に使わない。GEOSOLVER_S3_TANGENCY_MODE=T1とGEOSOLVER_ABLATE_NO_RESIDUAL_REWRITEの併用は当該ソースではT1関数ごと迂回するため、要求されたrawを明示的に上記のように構築する。すべて凍結版ソース上で計測し、T1のみ許可されたS4/S5手順から抽出。ソース改変なし。環境中のGEOSOLVER_ABLATE_*とGEOSOLVER_S3_*はworkerで除去する。

固定除数はS5/worker.py fixed_scalesが記述するS1と同じ規則：最初の通常探索候補（精密化前）の全点で、元IRの各等式の有限な|lhs|、|rhs|と1の最大値。floatはBoundaryOrigin.INITIAL_POINTで700桁mpfへ境界変換し、700桁で除数を計算する。既存S1の保存値は読まず再生成する。元IRとbundleの行対応はAST等価で取る。Distance=0から作る2行は元行の除数を共有する。bundleの追加行・半径補助式は同じ探索点に同じ規則を適用する（有限評価なしなら1）。参照解は除数計算に使わない。両modeの全行と除数を各sigma-details.jsonに保存する。

## 特異値と分類

mpmath 200桁、中央差分 `h_j=10^-k*max(1,|x_j|)`、k=70と60。各幅で全残差を全探索変数で微分しmp.svd_rを使う。厳密ゼロ行だけをSVD前に除き、列数に対して足りない特異値は0で補う。再構成相対誤差1e-170未満を確認する。全特異値・全ヤコビ行列・各幅の値は200桁の指数付き文字列で問題別JSONに保存する。

σ<1e-60を特異、σ>1e-10を非特異、その他を不定とする。両幅の区分が違えば不定。相対差1e-40以下かどうかも別途記録し、数値ゼロ近傍での相対差と閾値区分の一致を区別する。型は(base区分,raw区分,接する条件の有無)の組。W3対象はraw特異、base非特異、接する条件なし。W1/W2/W4や精密化精度の集計は一切行わない。

## 実行と成果物

`/home/kabatan/work/solver/.venv/bin/python prepare.py` → `driver.py` → `summarize.py` をS7内で実行する。driverは最大8 worker、各workerは1CPUに固定、BLAS等は1thread。600秒でworker内alarm、610秒で監督process group kill。started.jsonの存在する未完了問題は再solveしない。ファイル書込みは3000000bytes未満をassertしworkerにはRLIMIT_FSIZE=2999999を設定する。ログは通常solve中は/dev/nullに捨て、拡大する診断ログを作らない。

pre-run-hashes.jsonは入力・手順・使用凍結ソースの事前hash。used-hashes.jsonは完成後のS7成果物hash。classification.csvは指数表記の要約値、200桁値は問題別sigma-details.json。classification.mdは型別件数・全問題の理由・W3一覧。results/*/reference.jsonはこの実行で作った参照図と門の証跡のみで、段階(2)の結果ではない。

helpers.pyは許可されたS4/worker.pyからinventory/context/objects/t1/t2、S5/worker.pyからfresh_solve/fixed_scales、S5/reference.pyからmake_referenceを抽出し、歴史的manifestのimport時読込みを除いたもの。参照門の不要なabsolute_digits出力のみ除去した。実行スクリプト・入力は事前hashで固定し、実験後に集計・監査を行う。
