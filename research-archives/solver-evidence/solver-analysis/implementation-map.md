# e703e2d99の実行経路と、今回の計測位置

対象ソースはresearch worktreeの `e703e2d99484793f162f961bc50126ae65e4069f`。本研究では製品ソースを変更しない。下のリンクは今回実際に読んだ実装であり、計測用の介入は `benchmarks/solver_analysis/` のharnessだけで行う。

## 通常経路

| 段階 | 入力→出力・判断 | 予算と引継ぎ | 主な実装 |
|---|---|---|---|
| 入力と構成 | DSLを読み、幾何構成、残りの条件、目標、guard、変数依存を作る。明示boundsと幾何的な範囲推定を使う | 同じ変数値でも構成が定義できない点がある。評価不能と条件違反を分ける | [load_problem_bundle.py](/home/kabatan/work/solver/src/geosolver/engine/standard/problem/load_problem_bundle.py)、[infer_problem_bounds.py](/home/kabatan/work/solver/src/geosolver/engine/standard/problem/infer_problem_bounds.py) |
| 初期probe | seedに対応した点を評価し、候補、評価失敗率、残差尺度を得る。厳密距離に基づく補助標本も追加する | 元残差と評価可能性から作る。参照答は入力に含めない | [run_initial_probe.py](/home/kabatan/work/solver/src/geosolver/engine/standard/orchestration/run_initial_probe.py) |
| 探索 | 開始点を選び、DiscoMADS、SciPyまたは複合経路で候補を生成する | 標準NOMAD設定は各run最大200 black-box評価。実際のサブ経路・時間切れ・評価回数を併記する | [run_search.py](/home/kabatan/work/solver/src/geosolver/engine/standard/orchestration/run_search.py)、[nomad_config.py](/home/kabatan/work/solver/src/geosolver/engine/standard/search/nomad_config.py) |
| 保持・重複除去 | guardを満たす候補を台帳に残し、残差・距離・seedを用いて後段へ渡す | 標準設定のcompact候補20、seedごとの最低保持3。guard候補用prefixはmax(20×8,64)=160。これは全評価点を完全保存する保証ではない | [build_guard_feasible_ledger.py](/home/kabatan/work/solver/src/geosolver/engine/standard/search/build_guard_feasible_ledger.py)、[deduplicate_search_candidates.py](/home/kabatan/work/solver/src/geosolver/engine/standard/search/deduplicate_search_candidates.py) |
| 精密化 | float候補から高精度の座標・残差・目標・状態を作る。整数条件、closure、rankに応じた経路もある | 通常段階50/100/120 dps、各80反復。終了残差1e−20/1e−50/1e−80。closureは120/250/350/500 dps。実際に通った段階を計測する | [mpmath_refiner.py](/home/kabatan/work/solver/src/geosolver/engine/standard/refinement/mpmath_refiner.py)、[refiner_config.py](/home/kabatan/work/solver/src/geosolver/engine/standard/refinement/refiner_config.py) |
| 最終検証 | 元の式・guard・非退化・枝を再評価する。座標を修正する場合がある | 80/120/180/250/350/500 dps、正規化残差閾値1e−30。検証後の座標は新revisionであり、入力点へ遡及させない | [final_verifier.py](/home/kabatan/work/solver/src/geosolver/engine/standard/evaluation/final_verifier.py) |
| 値同定・出力 | 検証された候補から整数関係・代数的数等を提案し、採否とdescriptorを確定する | 候補を有限時間内で順に処理。検証・同定が完了したrevisionだけを出力へ対応付ける | [assemble_exact_results.py](/home/kabatan/work/solver/src/geosolver/engine/standard/orchestration/assemble_exact_results.py)、[identify_answer.py](/home/kabatan/work/solver/src/geosolver/engine/standard/exact_assembly/identify_answer.py) |

## 専用経路と再探索

自由変数がない入力は探索器を通らず直接高精度評価へ進む。1変数かつ通常DiscoMADS経路では、区間上の枝走査を先に行う。候補が得られればそこで探索段階を終える。候補がなければ残り時間で汎用探索へ戻る。従って全体の成功率を、そのまま多変数最適化の成功率として読むことはできない。[scalar_branch_scan.py](/home/kabatan/work/solver/src/geosolver/engine/standard/search/scalar_branch_scan.py)

最初の探索・精密化・同定でaccepted候補がなく、時間が残る場合に限り、hybrid fallbackを実行する。primaryの内部seedは外部seed一つ、fallbackは外部seedから連番5個である。外部seed0と1のfallbackはそれぞれ0,…,4と1,…,5となり、4個が重なる。さらにhybrid内のSciPy補助探索はseedを5個ずらす経路も持つ。同じ内部seedでも開始候補や残り予算が異なれば同じ試行ではないが、外部seed30個を独立な30試行とは仮定しない。

rescueはaccepted候補の補完が必要で、所定時間が残ったときに局所boxで探索する。標準値は8秒、最大6box、boxごと最大80評価、保持6候補。離散目標の補完は最大256組を上限に別経路で動く。これらは常に作動する処理ではなく、各runのtriggerとskip理由を残す。

## 全体の時間予算

通常実験は180秒、1物理コア、数値ライブラリthread数1、8並列。pipelineの探索時間が未指定なら、その時点の残り時間の55%を探索へ割り当てる。精密化のdeadlineは最終処理のために残り時間の20%、最大30秒を確保する。rescueとfallbackは同じ全体deadlineを共有する。これは段階時間が固定の比率で必ず消費されるという意味ではない。[run_external_pipeline.py](/home/kabatan/work/solver/src/geosolver/engine/standard/orchestration/run_external_pipeline.py)、[external_pipeline_config.py](/home/kabatan/work/solver/src/geosolver/engine/standard/contracts/external_pipeline_config.py)

## キャッシュと数値経路

評価器は問題の解析計画、probe、最終検証、値同定等にキャッシュを持つ。高速化は同じ時間内に実行できる候補数を変え得る。今回の比較では、通常180秒実験と、初期点・反復上限・精度を固定した再実行を分ける。再実行は同じ座標からの新しいoptimizer開始であり、全内部状態の復元ではない。キャッシュも新規となる。

計測時には公開 `IsTangent` 評価と、精密化内部での平滑化された二乗差、signed接触残差を区別する。単に残差の名前が同じでも、同じ式を計算しているとは限らない。介入比較の初期v0で見つかった経路混同は保存し、修正したv2を主解析に使う。

## 保存される証拠とその限界

候補ID、由来、外部seed、内部seed、revision、数値座標、残差、目標、精度、step、line search、rank選択、検証履歴を保存する。mpmath値は二進の符号・仮数・指数・bit数をそのままJSONへ記録し、500桁から15桁環境で読み直しても同一の値を再現する。

通常実行の台帳が保持していない全評価点を、後から復元できたとは主張しない。詳細な探索比較は別のharnessで全呼出しを記録する。解析では、保存点を動かさない独立な元条件評価と、座標を改善し得る最終verifierを分ける。数値条件通過、正答を一つ得たこと、参照集合との完全一致、全解の数学的証明は別の判定である。
