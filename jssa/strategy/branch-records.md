# 設計の7分岐に関する過去記録

分岐番号は `jssa/strategy/v15-design-branches.md` に従う。数値は出典の表記のまま転記し、再計算・補間はしていない。「記録なし」は調査した記録に比較結果または指定条件が見つからなかった欄を指す。問題数・候補数・実行数・表現別の腕数は区別する。

`experiment:` で始まる出典は、読み取り専用リポジトリ `/home/kabatan/work/solver` の experiment ブランチ、commit `7b6691be8d8a15a7a95816b532cad06cc2819112` のファイルと行番号。取得には git show / git grep / git log を使った。それ以外の相対パスは本作業ディレクトリのファイル。旧リポジトリ kabatan/GeoSolver の記録は、実際に読めた `jssa/history/` の転載・調査記録を出典とし、旧リポジトリの commit を直接確認したものとは区別した。GeoTarget 系は各行で明記した。

保存済みの結果だけを対象とした。S7/S8/S9 の実験は起動せず、事前登録・動作確認を性能比較の結果に加えていない。異なる版・機械・負荷・検査指標の数値は各行の条件を保った。S1/S3 の「桁数」は目標値誤差、旧 tangency-signed の「桁数」は残差ノルムであり、同じ指標に置き換えていない。

## 1：何を解くか

| 分岐番号 | 試した別の枝 | 結果(数値そのまま) | 条件(問題数・時間・seed) | 出典(ファイルパス:行 または commit) |
|---|---|---|---|---|
| 1 | 数値探索＋同定に対し、座標多項式系を msolve 0.9.4 で求解 | 答えの集合が一致201、正次元65、自由な変数が残る3、時間切れ・エラー24、多項式にできない15、未知数がない・未実行15 | 323問、1問1800秒、4並列、メモリ5GB、同じPC。solverは既存計測で1回以上正解した問題を照合。msolveのseed：記録なし | jssa/draft/supplement-v14.md:713、jssa/draft/supplement-v14.md:717 |
| 1 | 強化版厳密法 R1〜R4（目標射影・飽和・定数変換・未知数0の直接評価）：開発外 | 解けた20/29、solver ≥3/5正解・強化版未解決8問 | 開発外29問、各問1回、全工程600秒、8 GiB、各1 CPU、最大4並列。solverはQ30の既存5 seed。厳密法のseed：記録なし | jssa/difficulty/exact-strong-1024/stageB/answer.md:3、jssa/difficulty/exact-strong-1024/stageB/answer.md:25、jssa/difficulty/exact-strong-1024/preregistration-8.md:8 |
| 1 | 強化版厳密法 R1〜R4：以前の msolve が答え集合を出せなかった開発群 | 解けた39/122 = 32.0%、solver ≥1/3正解・強化版未解決82/122 | 開発群122問、各問1回、全工程600秒、8 GiB、各1 CPU、最大4並列。solverは既存3 seed。厳密法のseed：記録なし | jssa/difficulty/exact-strong-1024/stageB/answer.md:5、jssa/difficulty/exact-strong-1024/stageB/answer.md:25 |
| 1 | 強化版厳密法と solver の、両方が解けた問題だけの時間比較 | 強化版0.906秒 対 solver 2.694秒（58問） | 開発外19問＋開発群39問。強化版は各1回600秒上限、solverは正解seedの問題別中央値。別時点の既存計測で負荷・並列数は不一致 | jssa/difficulty/exact-strong-1024/stageB/answer.md:92、jssa/difficulty/exact-strong-1024/stageB/answer.md:98 |
| 1 | 強化版厳密法の変換・消去・復元を含む求解 | 未解決計92問のうち変換不能54問。時間切れは lift_and_final_verify 1問、saturate_eliminate_lex 14問 | 上の開発外29問＋開発群122問、各1回600秒、8 GiB。unsupported理由にはANGLE_TARGET、NONALGEBRAIC_PI等を記録 | jssa/difficulty/exact-strong-1024/stageB/answer.md:12、jssa/difficulty/exact-strong-1024/stageB/answer.md:60、jssa/difficulty/exact-strong-1024/stageB/answer.md:71 |

## 2：問題の表し方

| 分岐番号 | 試した別の枝 | 結果(数値そのまま) | 条件(問題数・時間・seed) | 出典(ファイルパス:行 または commit) |
|---|---|---|---|---|
| 2 | 作図表現から座標多項式系への変換 | 未知数の中央値：探索変数3個→未知数9個 | 323問の msolve 比較、1問1800秒、4並列、メモリ5GB。seed：記録なし | jssa/draft/supplement-v14.md:713、jssa/draft/supplement-v14.md:724 |
| 2 | 作図を自由点＋追加等式へ展開（k=0/1/2/3） | 正解数（45回中）42 / 40 / 42 / 41、当たる確率の中央値0.96 / 0.77 / 0.40 / 0.38、費用比1.00 / 1.55 / 1.80 / 3.43 | 直接入力15問、探索変数1〜4、作図3つ以上。solver各3回、失敗は費用180秒。seed番号：記録なし | jssa/draft/supplement-v14.md:664、jssa/draft/supplement-v14.md:668、jssa/draft/supplement-v14.md:672 |
| 2 | 元の系／自由点の系／ずれの系を同じ出発点で比較 | 当たる確率の中央値0.85 / 0.52 / 0.67 | 14問、k=3、各60出発点、LM・箱なし、元と追加座標の終点の箱を検査。AIME 2009 I-5は22出発点・3系とも当たり0で除外。時間上限・seed番号：記録なし | jssa/draft/supplement-v14.md:543、jssa/draft/supplement-v14.md:566 |
| 2 | 作図で点を消さない展開版：開発外 | BASE 94/102、展開95/102、両方正解94組の時間比中央値1.01倍。展開4問だけは12/12 対12/12、時間比中央値1.28倍 | 開発外34問、seed311〜313、180秒、各1コア、最大4並列。中点8点（4問）を展開、未対応作図30件は保持 | jssa/difficulty/capability-1024/exp3-expand/answer.md:3、jssa/difficulty/capability-1024/exp3-expand/answer.md:8、jssa/difficulty/capability-1024/exp3-expand/answer.md:19、jssa/draft/supplement-v14.md:952 |
| 2 | 物理座標／構成表現の元残差／構成表現のsigned：Euclid2024-8A | 成功配置4/4 / 0/4 / 4/4、数値時間中央値（物理／構成signed）0.054 / 0.636秒 | 根近傍の同じ物理配置4個、全持上げ16枝、各表現・各物理配置の総反復上限80。seed・壁時間上限：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/final_results.md:21、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/final_results.md:25 |
| 2 | 物理座標／構成表現の元残差／構成表現のsigned：Guts2023-17 | 成功配置4/4 / 0/4 / 4/4、数値時間中央値（物理／構成signed）0.032 / 0.247秒 | 根近傍の同じ物理配置4個、全持上げ8枝、各表現・各物理配置の総反復上限80。seed・壁時間上限：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/final_results.md:21、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/final_results.md:26 |
| 2 | 物理座標／構成表現の元残差／構成表現のsigned：General2025-8 | 成功配置8/8 / 0/8 / 8/8、数値時間中央値（物理／構成signed）0.035 / 0.699秒 | 根近傍の同じ物理配置8個、全持上げ16枝、各表現・各物理配置の総反復上限80。seed・壁時間上限：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/final_results.md:21、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/final_results.md:27 |
| 2 | 正則条件を消去した reduced／消去と一次化を併用した reduced_signed | 放物線族：reduced 約7.39桁、reduced_signed 約74.09桁、再二乗 約8.01桁 | 生成放物線法線fold族、根中心の4開始、80反復、100桁作業。seed・壁時間上限：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/final_results.md:5、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/final_results.md:17 |
| 2 | 正の尺度固定等を追加した v5（v4との版比較） | v4 319/323、中央値4.362秒、平均22.5秒 → v5 322/323、中央値3.093秒、平均15.2秒 | 323問、seed0、180秒、1コア。v5はscale_chart・positive_scale_chartのほかalgebraic_branch_boxes等も変更した版 | jssa/history/candidates-v1-v8.md:12、jssa/history/candidates-v1-v8.md:25、jssa/history/candidates-v1-v8.md:26 |
| 2 | 代数的前処理を外す NO_ALGEBRAIC | 解けた問題69/72 対69/72、実行正解203/216 対203/216、費用平均29.56秒 対29.96秒（BASE／除去） | 固定72問、seed401〜403、180秒、1コア、WinPC WSL・並列6。「解けた」は3 seed中2回以上完全一致 | jssa/difficulty/mechanism-1024/run-7/winpc-wsl/README.md:5、jssa/difficulty/mechanism-1024/run-7/winpc-wsl/README.md:16、jssa/difficulty/mechanism-1024/run-7/winpc-wsl/README.md:18 |
| 2 | デカルトDAGのメモ化 | baseline 26.143590667983517秒、別コア初回cached 35.09547824796755秒、同一コアcached再測定29.898450957174646秒、全discovery出力同一、rejected | 224入力の代数discovery走査。1コア、既存optional CPU予算0.5秒、全体solve比較は未実行。seed：記録なし | experiment:research-archives/solver-evidence/optimization-speed-20261011/algebra-negative-receipt.json:25、experiment:research-archives/solver-evidence/optimization-speed-20261011/algebra-negative-receipt.json:32 |
| 2 | grevlex→FGLM による有限枝列挙 | finite 102→96、26.143590667983517→27.018079639266944秒、NotInvertible 5、optional timing losses 2、gained finite 1、rejected | 同じ代数discovery走査、全体solve比較は未実行。seed：記録なし | experiment:research-archives/solver-evidence/optimization-speed-20261011/algebra-negative-receipt.json:34、experiment:research-archives/solver-evidence/optimization-speed-20261011/algebra-negative-receipt.json:72 |
| 2 | 座標解から元の目標値の有限像を厳密計算 | finite coordinate sets 102、proved60、cpu_timeout4、unresolved_image38、CPU合計5.811154638000004秒、duplicate image sets3、research only | 102有限座標集合、全体solve比較は未実行。seed：記録なし | experiment:research-archives/solver-evidence/optimization-speed-20261011/algebra-negative-receipt.json:74 |
| 2 | 必要条件イデアルから目標へ直接消去・射影 | eligible224、proved74、unresolved57、unsupported_or_budget93、CPU合計20.038405602999976秒、incremental over coordinate path covered2、research only | 224入力、1コア、全体solve比較は未実行。covered all three seeds22は保存記述子との照合。seed番号：記録なし | experiment:research-archives/solver-evidence/optimization-speed-20261011/algebra-negative-receipt.json:85 |
| 2 | 尺度固定だけを単独で外す／戻す比較 | 記録なし | v4→v5は上記の複数変更を含む。S8 G4/G5の性能結果は記録なし | jssa/history/candidates-v1-v8.md:26、jssa/difficulty/mechanism-1024/stage/S8/smoke-check.md:3 |

## 3：大域探索

| 分岐番号 | 試した別の枝 | 結果(数値そのまま) | 条件(問題数・時間・seed) | 出典(ファイルパス:行 または commit) |
|---|---|---|---|---|
| 3 | Phase A を disco_mads にする比較基準 | 正解308/323、全問時間中央値4.28秒、正解のみ3.92秒、90%点30.4秒、合計1.30時間、評価回数中央値200、評価失敗2,689 / 74,261 | 323問、seed0、180秒、1コア、4並列、第2探索off、rescue有効かつ常にmads、2026-10-22〜23 | jssa/results/search-mode-ablation/README.md:3、jssa/results/search-mode-ablation/README.md:7 |
| 3 | Phase A を mads に変更 | 正解309/323、全問時間中央値4.20秒、正解のみ4.04秒、90%点29.4秒、合計1.22時間、評価回数中央値200、評価失敗1,116 / 51,695 | 上と同じ323問・seed0・180秒・1コア、第2探索off、rescue有効かつ常にmads | jssa/results/search-mode-ablation/README.md:3、jssa/results/search-mode-ablation/README.md:8 |
| 3 | Phase A を SciPy 多点出発に変更 | 正解319/323、全問時間中央値19.96秒、正解のみ16.53秒、90%点118.1秒、合計3.60時間、評価回数中央値12,607、評価失敗24,040 / 6,862,982 | 上と同じ323問・seed0・180秒・1コア、第2探索off、rescue有効かつ常にmads | jssa/results/search-mode-ablation/README.md:3、jssa/results/search-mode-ablation/README.md:9 |
| 3 | 9月記録：同じ表現・同じ有効開始点で NOMAD 対 SciPy（1変数） | 完全一致12/12 対12/12、数値配置あり12/12 対12/12 | 成績を見て選んだ非零変数8開発問題のうち1変数12腕、固定実評価呼出し・共通元HP・共通Phase C。予算値・seed：当該表に記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/selection_and_comparators.md:5、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/selection_and_comparators.md:9 |
| 3 | 9月記録：同じ表現・同じ有効開始点で NOMAD 対 SciPy（多変数） | 完全一致8/19 対4/19、数値配置あり13/19 対9/19 | 同じ非零変数8開発問題の多変数19腕。固定実評価呼出し・共通元HP・共通Phase C。予算値・seed：当該表に記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/selection_and_comparators.md:10、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/selection_and_comparators.md:12 |
| 3 | NOMAD単独から hybrid_legacy_nomad（SciPy併用）へ既定を変更：旧GeoSolver | UQ10_P4でNOMAD開始5点が同じ誤basin。SciPy併用前後の正解数・時間は記録なし | NOMAD 5 seeds × 200 evals、追加SciPy 320 Halton starts＋LM/TRF、残時間だけ使用。全体問題数・総時間上限：記録なし | jssa/history/r1-design-rationale.md:94、jssa/history/r1-design-rationale.md:105、jssa/history/r1-design-rationale.md:107（旧47d4b2a・db54a09の転載） |
| 3 | LM主＋DEフォールバック：旧GeoSolverの experiment/solver-generalization | 標準ケース58〜80% | 別系統の実験。問題数・時間・seed：記録なし | jssa/history/winpc-sweep.md:23（旧a225038・c3ff8ad・c628d74の調査記録） |
| 3 | LM主＋DEの再現：旧GeoSolver | 4/4 | 2026-03-10の計画再現記録。時間・seed：記録なし。他の手法とは分母が異なる | jssa/history/winpc-sweep.md:24 |
| 3 | PyNomad欠如でSciPy fallbackへ入っていた状態からNOMADを復旧 | PyNomadBBO==4.5.1を追加。復旧前後の正解数・時間比較は記録なし | 2026-08-26。問題数・時間上限・seed：記録なし | jssa/history/superpc-sweep.md:32、commit 7b2ebf1223d27279c9789bf765df955765a8fe8a |
| 3 | 第2探索を外す NO_SECOND_ATTEMPT | 解けた69/72→67/72、実行正解203/216→198/216、費用平均29.56→30.64秒。複数値8問は18/24で同じ | 固定72問、seed401〜403、180秒、1コア、WinPC WSL・並列6。「解けた」は3 seed中2回以上完全一致 | jssa/difficulty/mechanism-1024/run-7/winpc-wsl/README.md:5、jssa/difficulty/mechanism-1024/run-7/winpc-wsl/README.md:16、jssa/difficulty/mechanism-1024/run-7/winpc-wsl/README.md:18 |
| 3 | NOMAD対DEを同じ問題で比較 | 記録なし | 10月323問比較はDE経路がなく除外。旧リポ調査にも同問題比較表なし | jssa/results/search-mode-ablation/README.md:3、jssa/history/r1-design-rationale.md:61、jssa/history/winpc-sweep.md:34 |
| 3 | NOMAD対CMA-ES | 記録なし | 問題数・時間・seed：記録なし | 検索対象commit 7b6691be8d8a15a7a95816b532cad06cc2819112 のdocs/・research/・research-archives/比較文書、jssa/history/・jssa/results/ |

## 4：精密化

| 分岐番号 | 試した別の枝 | 結果(数値そのまま) | 条件(問題数・時間・seed) | 出典(ファイルパス:行 または commit) |
|---|---|---|---|---|
| 4 | LMの減衰状態を段階間で初期化／継続、λ下限1e−12 | 両側とも全107点で80反復上限、100桁終了時の目標精度差中央値＋0.016桁、全精密化終了時＋0.016桁 | 同じ107保持候補、100桁段階の開始座標全対一致。初期化側1点は30秒安全上限、分母から除外せず。seed：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/damping_results.md:1、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/damping_results.md:5、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/damping_results.md:9 |
| 4 | 同上、λ下限1e−24 | 初期化側全107点で5回停滞、継続側全107点で80反復上限、100桁終了時＋2.708桁、全精密化終了時＋2.868桁 | 同じ107保持候補、100桁段階の開始座標全対一致。seed：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/damping_results.md:1、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/damping_results.md:6 |
| 4 | 同上、λ下限1e−48 | 初期化側全107点で5回停滞、継続側100点で38回・7点で39回後に停滞、100桁終了時＋11.439桁、全精密化終了時＋12.943桁 | 同じ107保持候補、100桁段階の開始座標全対一致。seed：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/damping_results.md:1、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/damping_results.md:7 |
| 4 | 改善率の分母床δだけ1e−30→1e−80 | 元38回でstalled、変更側80回上限、38回目まで座標完全一致 | 保持台帳の点0の1対、同じ100桁開始点・継続λ、λ下限1e−48、80反復上限。seed・時間上限：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/damping_results.md:19 |
| 4 | 残差を7倍／1/7倍し、λも二乗倍する／固定する | λも変更時のstep相対差最大値の開始点内中央値 約4.3e−65 / 7.4e−65、λ固定でも目標精度差中央値0桁 | 台帳順16開始点、20反復。λ/σ_eff²最大値中央値 約8.5e−27。seed・時間上限：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/damping_results.md:15 |
| 4 | 減衰なしGN＋半分ずつの線探索で元の系／自由点の系／ずれの系を追跡 | 最初の長さ1/128 対1/8192、元7回で収束、自由点は200回上限で未収束。同じ10出発点で元・ずれ10回、自由点1回が当たり | AIME 2014 II-14の1問、k=0、u0=(458.6,194.2)。LM対GNの性能比較ではなくGN内の表現比較。時間上限・seed：記録なし | jssa/draft/supplement-v14.md:571、jssa/draft/supplement-v14.md:576、jssa/draft/supplement-v14.md:581 |
| 4 | bounded Armijo Newton v1 | raw答え集合一致24、truth match23、screen size24。遠いatan初期点でnativeの成功を失いrejected | 開発24問、seed0、180秒、1コア。baseline6並列／candidate1並列で時間比較不可。atan初期点1e10/1e12 | experiment:research-archives/solver-evidence/optimization-speed-20261011/refinement-receipt.json:27、experiment:research-archives/solver-evidence/optimization-speed-20261011/refinement-receipt.json:115、experiment:research-archives/solver-evidence/optimization-speed-20261011/refinement-receipt.json:130 |
| 4 | scaled trust Newton v2：独立非線形グリッド | native172/180、candidate124/180、native-success lost48、rejected | 5非線形族・180 parameterizations、translationを含む。seed・各条件の時間上限：記録なし | experiment:research-archives/solver-evidence/optimization-speed-20261011/refinement-receipt.json:37、experiment:research-archives/solver-evidence/optimization-speed-20261011/final-report.json:187 |
| 4 | scaled trust Newton v2：開発24問の対応比較 | exact answer sets一致24/24、平均13.791162514835984→12.923285835625089秒、中央値1.0690804015030153→1.0949181054893415秒、合計330.9879003560636→310.15886005500215秒。独立グリッドの退行によりrejected | 開発24問、seed0、180秒、1コア。同じhost・single coreだがCPUと測定時期は異なる | experiment:research-archives/solver-evidence/optimization-speed-20261011/refinement-trust-matched-comparison.json:2、experiment:research-archives/solver-evidence/optimization-speed-20261011/refinement-receipt.json:115、experiment:research-archives/solver-evidence/optimization-speed-20261011/refinement-receipt.json:140 |
| 4 | bounded Newton＋元の開始点からnative fallback v3：全323問 | 正解321→320、平均14.568928622665359→15.912442388786374秒、中央値2.9973676779773086→3.280458669003565秒、CPU合計3944.25→4257.26秒 | 323問、seed0、180秒、1コア、失敗込み。baselineとcandidateは交互の対応計測ではない。HMMT-2013-FEB-GEO-04の不一致は前段のpositive-scale-chart CPU予算中断として別監査 | experiment:research-archives/solver-evidence/optimization-speed-20261011/final-report.json:39、experiment:research-archives/solver-evidence/optimization-speed-20261011/final-report.json:104、experiment:research-archives/solver-evidence/optimization-speed-20261011/final-report.json:208 |
| 4 | bounded Newton＋元の開始点からnative fallback v4：同一コアABBA | 答え集合・descriptor・status一致24/24、平均14.458819857250395→15.726539132626689秒、中央値0.9789202932515764→0.9239791425061412秒、process sum変化8.76779217040038%、不採用 | 固定24問、96実行、seed0、180秒、1コア、同一コアABBA・各版2 fresh processes、失敗込み | experiment:research-archives/solver-evidence/optimization-speed-20261011/final-report.json:106、experiment:research-archives/solver-evidence/optimization-speed-20261011/final-report.json:134、experiment:research-archives/solver-evidence/optimization-speed-20261011/refinement-receipt.json:78 |
| 4 | LM-QR対NLS-TR：GeoTarget系 EXP-LOCAL-004 | safe-full37/48→42/48、target recovery71/88→77/88、accepted Gold-inconsistent endpoints62（close-target ambiguities59）、callback work1.379倍、不採用 | 8族×6例×32 paired starts、4608試行。時間上限・seed：当該登録に記録なし | experiment:docs/research/EVIDENCE.md:33 |
| 4 | DFO-LS 1.6.5：GeoTarget系 EXP-LOCAL-005 T0 | qualified targets3/10 対control4/10、safe-full2/5 対2/5、callbacks33,916 対13,531、local caps16、accepted-endpoint safety violations0、不採用 | 同じ5ケース・8 paired starts、5 physical-core shards。時間上限・seed：当該登録に記録なし | experiment:docs/research/EVIDENCE.md:36 |
| 4 | SciPy 1.18.0 native-bound exact-SVD TRF：GeoTarget系 | qualified targets3/10 対control4/10、safe-full2/5 対2/5、callbacks25,309 対25,286、NearRank1/1→0/1、local caps18、不採用 | 5 physical-core shards、case-cumulative callback threshold4800まで。時間上限・seed：当該登録に記録なし | experiment:docs/research/EVIDENCE.md:37 |
| 4 | SciPy/MINPACK Powell hybrid：GeoTarget系 EXP-LOCAL-007 | T1 family-equal safe-full0.571429→0.857143、work比0.499822。T2 safe-full0.738095で同点、work9.47%減、StrictGuard6/6→3/6、MultiRoot2/6→1/6、Gold不一致5、不採用・コード削除 | T1 representative-nine、T2 48ケース。SciPy1.18.0 root(method=hybr)、finite-box tanh chart。時間上限・seed：READMEに記録なし | experiment:research/experiments/EXP-LOCAL-007/README.md:10、experiment:research/experiments/EXP-LOCAL-007/README.md:15、commit 379264c5ae0217640251c88905415abd319c2105 |
| 4 | restarted multiprecision good-Broyden／analytic inverse-secant：GeoTarget系 EXP-SINGULAR-001 S3 | 両方0/12 isolated/coalesced singular endpoints、全eligible trajectory setで64反復上限・typed unknown、不採用 | 凍結30ケース、endpoint-global64反復。時間上限・seed：当該登録に記録なし | experiment:docs/research/EVIDENCE.md:29 |
| 4 | poll-only OrthoMADS／extreme barrier：GeoTarget系 EXP-LOCAL-008 | recovered target1 対control5、safe-full0 対2、work比1.4723926380、Gold不一致のStrictGuard boundary-ghost endpoints2、T0不採用・コード削除 | 6ケース、caseごとのcallback workは4800でright-censor、normalized finite-box・declared residual scaling。時間上限・seed：READMEに記録なし | experiment:research/experiments/EXP-LOCAL-008/README.md:13、experiment:research/experiments/EXP-LOCAL-008/README.md:18、commit 77effffc946483f5ca499413e5befc0166dafee7 |
| 4 | feasibility-restoring line-search GN／CPQR：GeoTarget系 EXP-LOCAL-009 | qualified targets8 対control5、MultiRoot追加3、work比0.9901840491、unsafe NearRank1・strict-boundary ghost roots7、T0不採用・コード削除 | 6ケース、caseごとのcallback workは4800でright-censor、direct-box・宣言済み残差尺度・固定減衰なし。時間上限・seed：READMEに記録なし | experiment:research/experiments/EXP-LOCAL-009/README.md:11、experiment:research/experiments/EXP-LOCAL-009/README.md:16、commit 77effffc946483f5ca499413e5befc0166dafee7 |
| 4 | nullspace-Newton：旧GeoSolverの計画再現 | 7/7（180秒超） | 2026-03-10の別系統の再現記録。seed・詳細な時間：記録なし | jssa/history/winpc-sweep.md:24 |
| 4 | S9A R1：LMの減衰を0に固定する純GNと既定の比較 | 記録なし | 事前登録16では同じseed0主探索候補・各90秒の計画。結果は記録なし | jssa/difficulty/mechanism-1024/stage/S3/preregistration-16.md:11、jssa/difficulty/mechanism-1024/stage/S3/preregistration-16.md:14 |
| 4 | S9A R2：適応減衰を止めるFIXED_LM_DAMPINGと既定の比較 | 記録なし | 同上、結果は記録なし | jssa/difficulty/mechanism-1024/stage/S3/preregistration-16.md:15 |
| 4 | S9A R3：LMを飛ばすNewtonのみと既定の比較 | 記録なし | 同上、結果は記録なし | jssa/difficulty/mechanism-1024/stage/S3/preregistration-16.md:16 |
| 4 | 手法変更に要した人の作業時間の比較 | 記録なし | 開発時刻、solve時間、callback数、profile時間とは別の値。分岐4の人の総作業時間は記録なし | 調査対象jssa/history/candidates-v1-v8.md:7、experiment:research-archives/solver-evidence/optimization-speed-20261011/final-report.json:39、experiment:research-archives/solver-evidence/optimization-speed-20261011/refinement-receipt.json:100 |

## 5：残差の形

S3の以下12行は T0／T1／T2 の順。T0は元の接条件の残差、T1は直線円のδ²−r²・円円の近い枝の符号付き距離差、T2は接点・共通点を示せる場合に接点式へ置き換え、他はT1と同じ。距離0の座標差と半径補助式は3条件とも既定のまま。定義は `jssa/difficulty/mechanism-1024/stage/S3/README.md:5` と同 `preregistration-10.md:13`、固定条件は同 `rules.md:5`。各行の桁数は精密化直後の最良候補の目標値絶対誤差の−log10。

| 分岐番号 | 試した別の枝 | 結果(数値そのまま) | 条件(問題数・時間・seed) | 出典(ファイルパス:行 または commit) |
|---|---|---|---|---|
| 5 | S3 T0／T1／T2：AIME-2015-II-15 | 桁数482.91 / 482.91 / 482.91、精密化秒1.46 / 1.56 / 1.49 | S1の同じ224候補を用いる12問中1問、seed0、各構成90秒、各1コア・2並列 | jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:16、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:43、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:64、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:66 |
| 5 | S3 T0／T1／T2：AIME-2018-II-14 | 桁数6.27 / 6.63 / 484.16、直後通過0 / 0 / 7、最終通過4 / 5 / 7、精密化秒90.02 / 90.01 / 22.67 | 同じ保存候補、seed0、各構成90秒、凍結版最終検証は各集合別枠90秒 | jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:17、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:44、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:66 |
| 5 | S3 T0／T1／T2：HMMT-2008-FEB-GEO-09 | 桁数380.86 / 353.30 / 353.30、精密化秒5.71 / 24.58 / 24.90 | 同じ保存候補、seed0、各構成90秒 | jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:18、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:45、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:66 |
| 5 | S3 T0／T1／T2：HMMT-2009-FEB-GEO-10 | 桁数478.72 / 480.53 / 480.53、精密化秒26.94 / 49.14 / 20.03 | 同じ保存候補、seed0、各構成90秒 | jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:19、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:46、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:66 |
| 5 | S3 T0／T1／T2：HMMT-2010-FEB-GEO-09 | 桁数498.51 / 497.69 / 497.69、精密化秒24.74 / 5.69 / 4.95 | 同じ保存候補、seed0、各構成90秒 | jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:20、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:47、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:66 |
| 5 | S3 T0／T1／T2：HMMT-2020-FEB-GEO-09 | 桁数349.77 / 349.77 / 349.77、精密化秒1.53 / 1.41 / 1.65 | 同じ保存候補、seed0、各構成90秒 | jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:21、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:48、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:66 |
| 5 | S3 T0／T1／T2：HMMT-2022-FEB-GEO-10 | 桁数-1.79 / -1.79 / -1.79、精密化秒3.84 / 5.11 / 0.55 | 同じ保存候補、seed0、各構成90秒 | jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:22、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:49、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:66 |
| 5 | S3 T0／T1／T2：HMMT-2023-FEB-GEO-07 | 桁数8.04 / 160.84 / 484.53、精密化秒90.01 / 90.01 / 90.01 | 同じ保存候補、seed0、各構成90秒 | jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:23、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:50、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:66 |
| 5 | S3 T0／T1／T2：JMO-2013-PRE-05 | 桁数6.73 / 8.33 / 353.80、精密化秒12.98 / 90.01 / 45.25 | 同じ保存候補、seed0、各構成90秒 | jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:24、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:51、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:66 |
| 5 | S3 T0／T1／T2：JMO-2024-PRE-06 | 桁数0.36 / 6.13 / 339.61、精密化秒8.79 / 28.08 / 10.22 | 同じ保存候補、seed0、各構成90秒 | jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:25、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:52、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:66 |
| 5 | S3 T0／T1／T2：aime-2001-2-7 | 桁数494.31 / 484.20 / 484.20、精密化秒48.86 / 5.42 / 5.23 | 同じ保存候補、seed0、各構成90秒 | jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:26、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:53、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:66 |
| 5 | S3 T0／T1／T2：aime-2002-2-14 | 桁数5.54 / 159.30 / 159.30、精密化秒83.60 / 71.36 / 31.59 | 同じ保存候補、seed0、各構成90秒 | jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:27、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:54、jssa/difficulty/mechanism-1024/stage/S3/run/answer.md:66 |
| 5 | S5（事前登録12）T0／T1／T2：HMMT-2014-FEB-GEO-08 | 桁数159.25 / 159.56 / 260.39、T2−T1 100.83 | 新規固定32問中1問、型P、seed0、各構成90秒、同じ保存主探索候補、各1コア・最大8ストリーム | jssa/difficulty/mechanism-1024/stage/S5/run/answer.md:29、jssa/difficulty/mechanism-1024/stage/S5/run/rules.md:5 |
| 5 | S5（事前登録12）T0／T1／T2：JMO-2014-PRE-01 | 桁数5.84 / 5.98 / 484.19、T2−T1 478.21 | 同じ32問中1問、型P、seed0、各構成90秒、同じ保存主探索候補 | jssa/difficulty/mechanism-1024/stage/S5/run/answer.md:40、jssa/difficulty/mechanism-1024/stage/S5/run/rules.md:6 |
| 5 | S5（事前登録12）T0／T1／T2：HMMT-2017-FEB-GEO-05 | 桁数483.41 / 482.17 / 483.41、T2−T1 1.24、型Bの個別予測は外れ | 同じ32問中1問、seed0、各構成90秒、同じ保存主探索候補。U3は型Bが1問のため判定不能 | jssa/difficulty/mechanism-1024/stage/S5/run/answer.md:5、jssa/difficulty/mechanism-1024/stage/S5/run/answer.md:31、jssa/difficulty/mechanism-1024/stage/S5/run/rules.md:6 |
| 5 | 旧 tangency-signed：書き換え一式あり／なし | 最良残差ノルムが300桁超：11問／5問、なしで50桁未満：7問、8〜48桁 | 接条件24問中候補・精密化のある12問、seed0、主solve180秒、同じ候補に各90秒、off_first/on_firstの2順序。接条件・距離0・半径補助を一括停止 | jssa/results/tangency-signed/README.md:5、jssa/results/tangency-signed/README.md:10、jssa/results/tangency-signed/README.md:33 |
| 5 | 7b：精密化の残差書き換え一式を外す | BASE 解けた69/72・完全一致205/216・費用平均26.790秒 → 除去68/72・201/216・33.120秒 | 固定72問、seed401〜403、180秒、1コア・並列16、開始時load中央値29.93。最終検証の書き換えは止めていない | jssa/difficulty/mechanism-1024/run-7b/answer.md:10、jssa/difficulty/mechanism-1024/run-7b/answer.md:17、jssa/difficulty/mechanism-1024/run-7b/answer.md:34、jssa/difficulty/mechanism-1024/stage/S8/nrr-final-check.md:3 |
| 5 | 9月：General6の元／signed一次化／再二乗／安定gap | signedの50桁で補助目標＋30.214桁・物理目標＋22.249桁、再二乗0 / 0、安定gap−0.774 / −1.549。signedは各精度両目標4/4が20桁、他腕0/4 | 1自然問題、4開始×4残差腕×50/100/200桁の48条件＋物理配置対応36条件。seed・壁時間上限：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/mid_results.md:7、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/mid_results.md:11 |
| 5 | 9月：Euclid2026-8Aの元／signed残差 | 物理目標の桁数中央値7.79 / 74.18、signedの元条件数値検査＋20桁4/4 | 根中心4開始、各80反復・100桁。50/100/200桁でもsigned全条件通過。seed・壁時間上限：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/final_results.md:5、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/final_results.md:11、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/final_results.md:15 |
| 5 | IsTangentの同一円での残差変更 | d == 0 and r1 == r2 で r1 + r2 を返す。変更単独の正解数・時間比較は記録なし | 2026-08-30。問題数・時間・seed：記録なし | jssa/history/dev-history-superpc.md:34、commit faf43a85625bea31742d2b9a1ce5a5824a6385e3 |
| 5 | signed_tangencyを局所微分用に追加 | 公開IsTangentと同じ絶対値・domainを保ちzero cuspを除くと記載。変更単独の正解数・時間比較は記録なし | 2026-08-31。問題数・時間・seed：記録なし | jssa/history/dev-history-superpc.md:36、commit 18be44312a1f96c1503e0845ffc7f22a7bcfce5c |
| 5 | 距離0→座標差だけを単独で外す／戻す比較 | 記録なし | 旧tangency-signed・7bでは接条件や半径補助と一括変更 | jssa/results/tangency-signed/README.md:5、jssa/difficulty/mechanism-1024/preregistration-7b.md:8 |
| 5 | 半径の補助行だけを単独で外す／戻す比較 | 記録なし | 正半径samplerの除外記録は別にあるが、補助行単独の比較数値は記録なし | jssa/results/tangency-signed/README.md:5、jssa/history/candidates-v1-v8.md:33 |

## 6：候補の選び方

| 分岐番号 | 試した別の枝 | 結果(数値そのまま) | 条件(問題数・時間・seed) | 出典(ファイルパス:行 または commit) |
|---|---|---|---|---|
| 6 | 散らして選ぶ代わりに残差順上位20：7b全体 | BASE 解けた69/72・完全一致205/216・費用平均26.790秒 → 除去68/72・203/216・32.452秒 | 固定72問、seed401〜403、180秒、1コア、並列16。「解けた」は3 seed中2回以上完全一致 | jssa/difficulty/mechanism-1024/run-7b/answer.md:12、jssa/difficulty/mechanism-1024/run-7b/answer.md:17、jssa/difficulty/mechanism-1024/run-7b/answer.md:34 |
| 6 | 同上：複数値8問 | BASE19正解、残差順上位20は13正解、減少6回 | 複数値8問×seed401〜403＝24実行、180秒、1コア | jssa/difficulty/mechanism-1024/run-7b/answer.md:5、jssa/difficulty/mechanism-1024/run-7b/answer.md:34 |
| 6 | 同上：他64問 | BASE63問、残差順上位20は64問が解けた、差＋1問。問題別時間比中央値の中央値0.9757 | 他64問、seed401〜403、180秒、1コア、問題別時間比は両構成完全一致の実行だけ | jssa/difficulty/mechanism-1024/run-7b/answer.md:6、jssa/difficulty/mechanism-1024/run-7b/answer.md:7、jssa/difficulty/mechanism-1024/run-7b/answer.md:12 |
| 6 | 9月：4順位×保持数K=1/4×元／signed HP | 元HPで元条件検査＋目標20桁0/24群、signed24/24群、最良目標桁数の群内最大値の中央値7.958 / 78.185 | 1自然問題、元台帳3つ、48条件群・120局所再開始。K=1は1点80反復、K=4は各点20反復、合計80。seed・時間上限：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/selection_and_comparators.md:1、experiment:research-archives/solver-evidence/solver-analysis/analysis/development-comparisons-v1/summary.json:156 |
| 6 | 旧GeoSolver：上位保持を広げmulti-box rescue | 真値との差0.1785→0.0344、まだ完答ではない | OMCE019F 1問、Phase A 1000点、guard通過379点。時間・seed：記録なし | jssa/history/winpc-sweep.md:20（旧a238648:docs/SIMPLE_EXTERNAL_SOLVER_INTEGRATION_PLAN.mdの調査記録） |
| 6 | 旧GeoSolver：残差順top-Nからfarthest-point開始点へ | UQ10_P4で開始5点が同じ誤basin、dedup threshold0.01 normalized。変更後の正解数・時間は記録なし | NOMAD 5 seeds × 200 evals。全体問題数・時間：記録なし | jssa/history/r1-design-rationale.md:95、jssa/history/r1-design-rationale.md:105、jssa/history/r1-design-rationale.md:107 |

## 7：値の確定

| 分岐番号 | 試した別の枝 | 結果(数値そのまま) | 条件(問題数・時間・seed) | 出典(ファイルパス:行 または commit) |
|---|---|---|---|---|
| 7 | S2：保存図から値を作り、PSLQの桁数／係数上限を変更 | 13件×6条件＝78条件、実施54条件：正しい式50、誤式0、棄却4、到達不可24。P4〜P6判定不能 | (a)上限1e8・120/250/500桁、(b)実測到達桁数固定・上限1e8/1e14/1e21。max_degree8、max_steps20000、各段180秒、並列2、各1 CPU。探索seedを追加しない保存図実験 | jssa/difficulty/mechanism-1024/stage/S2/answer.md:3、jssa/difficulty/mechanism-1024/stage/S2/answer.md:7、jssa/difficulty/mechanism-1024/stage/S2/rules.md:5、jssa/difficulty/mechanism-1024/stage/S2/rules.md:12 |
| 7 | S2：AIME-2014-II-10__areaの桁数／係数上限 | 到達620桁、真の最大係数27763975108827。(a)120/250/500桁：棄却/棄却/棄却、(b)1e8/1e14/1e21：棄却/正しい式/正しい式 | 保存図を620桁closure、参照700桁。PSLQ各条件180秒、max_degree8、max_steps20000。保存図実験、探索seedなし | jssa/difficulty/mechanism-1024/stage/S2/answer.md:11、jssa/difficulty/mechanism-1024/stage/S2/answer.md:13、jssa/difficulty/mechanism-1024/stage/S2/rules.md:12 |
| 7 | S2補遺：AIME-2019-I-12__lengthの桁数／係数上限 | 実測到達351桁、計算設定500桁、真の最大係数131886598434451146000。(a)120/250/D：棄却/棄却/棄却、(b)1e8/1e14/1e21：棄却/棄却/正しい式 | 通常精密化経路を各量1回、closure120→250→350→500桁、参照700桁、各段180秒・各量精密化計600秒以内、並列2・各1 CPU。保存図実験、探索seedなし | jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:13、jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:20、jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:22、jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:24 |
| 7 | S2補遺：AIME-2019-I-12__areaの桁数／係数上限 | 実測到達350桁、計算設定350桁、真の最大係数308249968294125。(a)120/250/D：棄却/棄却/棄却、(b)1e8/1e14/1e21：棄却/正しい式/正しい式 | 同上、各量1回・各段180秒、保存図実験、探索seedなし | jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:14、jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:20、jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:22 |
| 7 | S2補遺：対照AIME-2021-I-13の桁数／係数上限 | 実測到達500桁、採用値の計算設定120桁、6条件すべて正しい式 | 値672は参照値との一致でD上限500を記録。500桁計算を意味しない。各量1回・各段180秒、保存図実験、探索seedなし | jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:15、jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:18 |
| 7 | S2補遺：対照HMMT-2010-FEB-GEO-02の桁数／係数上限 | 実測到達350桁、計算設定350桁、6条件すべて正しい式 | 各量1回、(a)120/250/D、(b)1e8/1e14/1e21、各段180秒、保存図実験、探索seedなし | jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:16、jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:24 |
| 7 | S2補遺：到達不可だった4量の通常経路での値取得と同定 | 4量×6条件＝24条件、正しい式15、誤式0、棄却9、到達不可0、欠測0。P4′〜P6′的中（事後補遺）、元S2主判定は判定不能のまま | 通常経路各量1回、各段180秒、各量精密化計600秒以内。PSLQ呼出し合計12.995秒、精密化合計0.093秒。上限超過返却1条件も保持 | jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:3、jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:7、jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:9、jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:24、jssa/difficulty/mechanism-1024/stage/S2-addendum/answer.md:26 |
| 7 | 9月：誤った二次提案の棄却後も提案列を継続 | 旧500桁候補では正しい三次関係を取得 | 1保存候補の値・不確かさ・tier固定。座標・幾何条件を再評価しない単独再生。時間・seed：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/exactification_results.md:1 |
| 7 | 9月：元／signed HPと提案継続の有無の交差比較 | 元HP：元提案0/107・継続0/107、signed HP：元提案107/107・継続107/107、相互作用0 | 1開発問題の107保持開始点、全428腕。同じHP出力の対は同じverifier出力hash。時間上限・seed：記録なし | experiment:research-archives/solver-evidence/solver-analysis/report/fragments/exactification_results.md:3、experiment:research-archives/solver-evidence/solver-analysis/report/fragments/exactification_results.md:7、experiment:research-archives/solver-evidence/solver-analysis/analysis/development-comparisons-v1/summary.json:130 |
| 7 | Julia独自PSLQの二精度照合：GeoTarget系 | 103 tests、degree2〜12 radical probeを両精度で通過。同じprimitive irreducible polynomialとreal rootをPとP+256で要求 | 独立したJulia GeoTargetExact実装、PSLQは候補生成。時間・seed・Pの具体値：当該登録に記録なし | experiment:docs/research/EVIDENCE.md:35、jssa/history/dev-history-pc.md:20 |
| 7 | 最終検証を最低120桁・180桁の連続二段にした設定と、別桁数の比較 | 記録なし | 120/180桁の数値確認という設定説明はあるが、その桁数を選んだ比較結果は記録なし | jssa/strategy/qa-prep-1024.md:27、jssa/strategy/qa-prep-1024.md:29 |
| 7 | PSLQの既定係数上限1e8を決めた当時の比較・選定履歴 | 記録なし | S2は既存値の事後比較。次数8・係数10⁸等のtier設定と、公式答えの最小多項式を用いた診断は記載されている | jssa/draft/supplement-v14.md:305、jssa/draft/supplement-v14.md:453、jssa/difficulty/mechanism-1024/stage/S2/answer.md:23 |

## 失敗・撤回・作業記録（依頼6の補足）

以下も同じ5列で記録する。同じ分岐内の上表と同じ比較を繰り返さず、削除・撤回・作業記録自体を1件とした。

| 分岐番号 | 試した別の枝 | 結果(数値そのまま) | 条件(問題数・時間・seed) | 出典(ファイルパス:行 または commit) |
|---|---|---|---|---|
| 2 | v6をそのまま使わずv7/v8へ修正 | v5 322/323→v6 318/323（欠落4、余分1、no_answer3）。v6回帰logで1件失敗、v7回帰logで2件失敗、v8で解消 | 323問、seed0、180秒、1コア。v6にはangle_equations等の複数変更、v7/v8にも複数修正 | jssa/history/candidates-v1-v8.md:12、jssa/history/candidates-v1-v8.md:27、jssa/history/candidates-v1-v8.md:28 |
| 3 | 整数セグメント経路と正半径samplerを既定探索から除外 | 両方exclude_insufficient_generalization。v7で既定から除外、v8は整数セグメントを全production search modeで無効化 | 2026-10-11、監査対象v6と計画中C7。配置倍率の独立ablation、未使用構造族の根拠は記録なし。除外単独の成功率・時間・seed比較は記録なし | jssa/history/candidates-v1-v8.md:28、jssa/history/candidates-v1-v8.md:29、jssa/history/candidates-v1-v8.md:33 |
| 4 | 不採用Powell hybridの実装・依存・試験を削除：GeoTarget系 | 17 files changed、24 insertions(+)、4895 deletions(-) | commit日時2026-07-12 12:48:43 +0900。T2不採用commitは同日12:03:55 +0900。作業時間：記録なし | commit 379264c5ae0217640251c88905415abd319c2105、commit cfffdef7cf0a285cd30e803b1c60af19bb761d67 |
| 4 | rank-first精密化の試作 | rejected（診断でinitial-J rank欠損の機会なし）。比較数値は記録なし | 2026-10-11 optimization-speed。診断問題数・時間上限・seedは当該versions欄に記録なし | experiment:research-archives/solver-evidence/optimization-speed-20261011/refinement-receipt.json:11 |
| 4 | norm2-only精密化の試作 | not selected（診断不変・対応時間mixed）。比較数値は当該versions欄に記録なし | 2026-10-11 optimization-speed。診断問題数・時間上限・seedは当該versions欄に記録なし | experiment:research-archives/solver-evidence/optimization-speed-20261011/refinement-receipt.json:16 |
| 4 | centered finite difference精密化の試作 | rejected（診断不変）。比較数値は当該versions欄に記録なし | 2026-10-11 optimization-speed。診断問題数・時間上限・seedは当該versions欄に記録なし | experiment:research-archives/solver-evidence/optimization-speed-20261011/refinement-receipt.json:22 |
| 4 | Angle/sin/cos/tanの安定解析微分拡張 | 24問の4プロセスで全答え維持、sum of problem means改善1.30197%、10%以上改善5件・悪化5件、9.895→19.342秒の悪化が両repeatで再現、不採用 | 固定24開発問、96実行、seed0、180秒、1コア、同一コアABBA。人の作業時間：記録なし | experiment:research-archives/solver-evidence/optimization-speed-20261011/final-report.json:136、experiment:research-archives/solver-evidence/optimization-speed-20261011/final-report.json:195 |
| 4 | Newton反復のprofileによる費用記録 | native Newton903反復、residual callbacks159822、Newton166.842秒、full closure167.05秒 | JMO-2017-PRE-10の診断profile、profiling overheadあり。人の作業時間ではない。seed：当該profile欄に記録なし | experiment:research-archives/solver-evidence/optimization-speed-20261011/refinement-receipt.json:100 |
| 5 | S1の桁数・参照値測定の修復（求解の再実行なし） | 測定実装の不備2点、探索・精密化・最終検証の再実行0 | float(digits)→float(str(digits))、無理数参照値5問を同じ式・同じ700桁で評価し直した。規則・閾値変更なし。作業時間：記録なし | jssa/difficulty/mechanism-1024/stage/S1/answer.md:40 |

## 調査範囲と未記録項目

依頼書の重点1は分岐3、重点2は分岐4、重点3は分岐1・2、重点4は分岐5、重点5は分岐7、重点6は各不採用行と末尾の補足に対応する。

読んだ範囲は、本作業ディレクトリの依頼書・設計分岐一覧、jssa/history/のPC・スーパーPC・旧リポ調査記録、jssa/results/の比較README、段階比較S1/S2/S3/S4/S5・7/7b・強化版厳密法の結果と規則、S8の動作確認・最終検証スイッチ確認、事前登録12・16、補足v14の該当結果表、experimentのresearch-archives/solver-evidence/（solver-analysis、optimization-20261011、optimization-speed-20261011）、docs/research/EVIDENCE.md、EXP-LOCAL-007/008/009、git logの関連commitである。experimentのresearch-archives/2026-09-08/・2026-10-21/のMarkdownもCMA-ES・DE・NOMAD/SciPy比較の語で検索した。

記録なしの行は、尺度固定単独（分岐2）、同問題のNOMAD対DE・CMA-ES（分岐3）、S9AのR1/R2/R3比較結果・手法別総作業時間（分岐4）、距離0の座標差単独・半径補助行単独（分岐5）、最終検証桁数の比較・既定1e8を選定した当時の比較（分岐7）。分岐全体が記録なしのものはない。

収録件数は補足の失敗・削除記録を含む105行。「結果欄が記録なし」は結果欄全体を「記録なし」とした11行を数える。採否・変更の記録はあるが比較数値や条件の一部が未記録の行は、各欄にその旨を残した。

| 分岐 | 収録行数 | うち結果欄が記録なし |
|---|---:|---:|
| 分岐1 | 5 | 0 |
| 分岐2 | 16 | 1 |
| 分岐3 | 13 | 2 |
| 分岐4 | 29 | 4 |
| 分岐5 | 24 | 2 |
| 分岐6 | 6 | 0 |
| 分岐7 | 12 | 2 |
| 合計 | 105 | 11 |
