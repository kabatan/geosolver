# S9A：事前登録16・部分A「実行前に固定するもの1」

対象はR0〜R3の実装の固定と制御フローだけの短い動作確認。本計測、正誤・正しい桁数の比較、部分Bの表作成、commit/pushは実施しない。事前登録16の予測・対象・判定閾値は変更しない。本計測を解禁する成果物ではない。

## ソースと再構成

- 指定BASE1：`/tmp/mechanism-7b-lkdjle5l/final`。
- 適用前source_hash：`sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3`。
- `switch-r.patch`適用後source_hash：`sha256:25ba4a4412715fda8f2bd7c9148a9ceba08b93162ce8d25c2bdbbd022fafe40a`。
- 適用後コピー：`/tmp/mechanism-S9A-vbs9i8lg/final`。元ソースには書き込まない。
- 最終検証・同定用凍結ソース：S1で保存した`/tmp/mechanism-S1-1m9aomj8/frozen`、source_hash `sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5`。

`source-hashes.json`は適用前・適用後・凍結版それぞれの全通常ファイルの生バイトSHA256、変更ファイル一覧、保護ファイルのバイト一致記録、patchの再適用記録を収録する。`__pycache__`は除外。source_hashは`runtime/integrity.py:source_tree_hash`と同じ定義（相対パス順、パス＋NUL＋CRLFをLFにした内容＋NUL、`.py/.json/.toml`、`engine-lock.json`とfrontend/cacheを除外）。全ファイルhashは改行を正規化しない。

再構成は、指定BASE1を別ディレクトリにコピーし、そのルート（`src/`の親）で`git apply --check <S9A>/switch-r.patch`、`git apply <S9A>/switch-r.patch`を順番に実行する。`PYTHONPATH=<コピー>/src`で`source_tree_hash()`と`verify_engine_lock()`を照合する。実際に別のクリーンコピー`/tmp/mechanism-S9A-vbs9i8lg/replay`へ同手順で適用し、全ファイルのバイト一致を確認した。

変更は`refinement/mpmath_refiner.py`と`runtime/ablation.py`、それに`engine-lock.json`のsource_hash欄のみ。数値設定の既定値や線形ソルバ、line search、最終検証・同定の実装は変更しない。新スイッチは`active_ablations()`にも登録する。lockは適用後hashに更新するため、通常の整合性検査を無効化する必要はない。

## 既存スイッチの可否

`run-7/jssa-ablation-67ad79a-vs-60db4b6.patch`、`switches/new-switches.patch`、S1の`prepare.py/worker.py/driver.py`、`inventory/INVENTORY.md`（M082/M083）、`capability-1024/ablation34/ablation34_driver.py`と`ablation34_extra.py`を確認した。

指定BASE1の`runtime/ablation.py`にあるのは既存8スイッチで、LM減衰固定・ゼロ固定・LM省略の分岐はない。`GEOSOLVER_ABLATE_FIXED_LM_DAMPING=1`を置くだけでは何も変わらない。M082のFIXED_LM_DAMPINGも「新規」「案」であり、既存patchには実装されていない。そのため今回の薄いpatchが必要。減衰初期値だけ0にする方法では、成功時`max(damping_min, damping / 4)`で非ゼロに戻るのでR1を満たさない。

## 現コードの精密化経路

以下の行番号は指定BASE1の`src/geosolver/engine/standard/`以下。

### LM：`refinement/mpmath_refiner.py:1388–1524` (`_run_stage`)

1. 元の残差を評価し、必要ならゼロ制約の平滑化または整数closureの残差置換を行う。boundsとhard feasibilityは別扱い。
2. `_run_stage`は与えられた精度の外側で呼ばれる。既定スケジュールは50/100/120 dps。差分Jacobianは同一点では再利用し、受理した更新の後に破棄する。Angleのcuspには片側差分fallbackを残す。
3. `levenberg_marquardt_step.py`は`(JᵀJ + λI) Δ = −Jᵀr`を`mp.lu_solve`で解く。λは各段階で`config.damping_initial`から開始し、既定1e-6。改善時÷4（下限1e-12）、失敗時×4。
4. `line_search.py:run_line_search`はα=1から最大20回、αを1/2にし、bounds・trial_filter・有限残差・残差ノルムの厳密減少を確認する。通常は開始候補がhard feasibleなら各試行もhard feasibleに制限する。整数closureのときだけ、最初の探索失敗後にhard filterなしの探索を再試行する既存経路がある。
5. 最大80反復、停滞5回、line search失敗12回、目標到達、評価不能、deadlineの既存停止条件を使う。段階の目標未達でもpromotion閾値以下なら次の精度へ進む。

**「信頼領域」の実装上の意味を限定する。** このmpmath精密化には半径Δ、trust ratio、dogleg/TRFの独立した信頼領域処理はない。あるのはLMの対角正則化と残差減少型バックトラック。SciPy探索の`search/scipy_multistart_backend.py`にはbounded TRFがあるが、S1の保存候補からの精密化では呼ばない。したがってR0の「LM＋信頼領域」は事前登録上の名称として維持し、実装は「既定LM＋バックトラック＋既存Newton経路」と固定する。新たな信頼領域アルゴリズムは追加しない。

### Newton/closure：`mpmath_refiner.py:954–1147`

`_run_findroot_closure`はまず元の全残差・boundsで開始点をcertifyし、既に目標以下なら反復せず返す。以後は与えられた残差関数を使い、1変数1残差はsecant、1変数複数残差または多変数の十分な残差数では`mp.findroot(..., solver="mnewton")`を呼ぶ。実際のmpmathでは残差がタプルなら`MDNewton`に切り替わる（`mpmath/calculus/optimization.py`）。従って「Newtonのみ」も全ケースで同じ厳密なNewton実装という意味ではなく、この既存closureファミリー（1次元secantを含む）である。

多変数Newtonの内部には、残差が減るまでステップを半分にするmpmath側のdampingが残る。これはLMのλIによる正則化とは別。R3でもこのバックトラックは止めない。

通常解が得られない／元の全残差のcertifyに通らない場合、`_run_rank_aware_findroot`で局所的な独立行・独立列を選び、残りの座標を固定したチャートで解く。これは特異・不足決定系向けの既存fallback。ヤコビアンには使用可能な解析微分、なければ差分を使う。最後は部分系だけでなく元の全残差とboundsでcertifyする。所定の数値例外とclosure deadlineは失敗扱い（None）。外側runtime deadlineも残す。

### warm Newton・direct accept・post-LM polish

`_refine_single_candidate` (`:1846`) はdirect accept判定をLMより先に行う。direct acceptされた候補も整数closureや高精度polishを経るので、全構成でLMを通らずに返る場合がある。

warm Newton (`:1983–2023`) は、多変数、制約数≧変数数、保存候補のhard feasible、整数制約なし、未期限切れの場合だけ、最大スケジュール精度120 dpsで最大12ステップ試す。solver toleranceは目標残差の二乗。失敗・hard infeasibleなら元の点を保つ。成功しても通常の各段階とpolishは残る。

`_apply_post_lm_closure_polish` (`:1676`) は最大LM精度で残差とhard feasibilityを確認し、hard feasibleかつ残差が`max(stage_tolerance, promotion_threshold)`以下のときのみclosureを行う（既定の入口閾値は1e-10）。closureは既定120/250/350/500 dps、最大ステップ数は`max(max_stage_iters, 2*dps)`。更新は元の残差のcertify・hard feasibilityを通ったものだけ採用。期限切れには最後の完了点を保存する。これらは全構成で変更しない。

## 4構成の固定

環境変数の正本は`configs.json`。プロセスごとに継承した`GEOSOLVER_ABLATE_*`を全て除き、その構成の集合だけ設定する。他のBASE1スイッチ（NO_RESIDUAL_REWRITE、NO_ANALYTIC_JAC等）は全て未設定。3つの新スイッチは同時設定しない。誤って併用した場合のコードの優先順位はNEWTON_ONLY→ZERO_LM_DAMPING→FIXED_LM_DAMPINGだが、登録構成には含めない。

| 構成 | 環境変数集合 | LM相当段階 | 共通のNewton経路 |
| --- | --- | --- | --- |
| R0 | 空集合 | 既定λ、適応更新、バックトラック | direct/warm/post/integer経路を保持 |
| R1 | `GEOSOLVER_ABLATE_ZERO_LM_DAMPING=1` | λ=0でGN方向。成功時の下限適用も失敗時の増加も停止 | 同上 |
| R2 | `GEOSOLVER_ABLATE_FIXED_LM_DAMPING=1` | 保存configの初期λに固定（S1は1e-6）。成功・失敗時の調整を両方停止 | 同上 |
| R3 | `GEOSOLVER_ABLATE_NEWTON_ONLY=1` | LMループを既存Newton closure呼び出しに置換 | direct/warm/post/integer経路を保持 |

R1の「純粋GN」はLM段階の方向計算を意味する。backtracking、bounds、hard filter、Jacobian再利用、精度promotion、warm Newtonとpolishは残る。精密化パイプライン全体をGNだけにする変更ではない。

λ=0で`JᵀJ`が特異／数値的に解けない場合、既存のstep solverは例外を捕捉してゼロ方向を返す。擬似逆・QR・正のλへの復帰は追加しない。ゼロ方向ではline searchが厳密減少を得られず、同じ点とJacobianのまま繰り返し、既定では12回のline search失敗でその段階を止める。元の点・最良点を保持し、promotionとpost-polishの条件判定は既定通り。warm Newtonが既に成功していた場合などはこの失敗に至らない。R1とR3は同じ方法ではない。

R2はλの大きさを結果から選ばず、保存`RefinerConfig.damping_initial`をそのまま使う。固定値を使ってもline searchによるα調整は残る。

R3は`_run_stage`の初期残差評価直後、LM用Jacobian・LM線形系・LM側のline searchに入る前に`_run_findroot_closure`を呼ぶ。各段階の精度・target・80ステップ上限・同じ平滑化/整数残差関数を使い、solver toleranceはwarm Newtonと同様にtarget²。現在のruntime deadlineを渡す。元の残差のcertifyとboundsを通った返値だけ受け取り、hard feasibilityを保存する入口では返値にもhard checkを課す。失敗時は部分的に改善した点を採用せず開始点を返し、`newton_failed`（期限切れなら`deadline_reached`）とする。通常の段階間promotion判定は残す。

単に段階を何もしないで飛ばす実装にはしない。そうするとwarm Newton対象外の1変数・整数・hard infeasible候補で、polishの入口閾値にも届かずNewtonを一度も試さない場合があるため。今回のR3では、その場合も段階のNewton呼び出しを行う。独立したtrust-region処理は元々なく、LMのλ・LM側バックトラックは通らない。既存warm Newtonはその前に動き得るし、post-LMという名前のpolishもLMを実行したかどうかでなく従来の入口条件で動く。整数closure/projectionからの`_run_stage`呼び出しにも同じ新スイッチが適用される。

R0では新フラグが全てfalseなので従来のλ初期値・更新式・停止条件をそのまま通る。スイッチの読み取りと分岐の費用だけ増える。R0の数値品質を本作業で比較することはしない。

## 最終検証・同定の凍結

`evaluation/final_verifier.py`、`evaluation/verification_*.py`の全6ファイル、`exact_assembly/`内の全5ファイル、計12ファイルについて、指定BASE1・patch適用後・S1の凍結版の**生バイト一致**を確認した。各hashは`source-hashes.json:protected_files`に保存する。

将来の最終検証・同定は別プロセスで`PYTHONPATH=<frozen>/src`、全ablation未設定に固定する。`verify_final_candidate`、`identify_answer`、`verify_identified_answer`等は凍結版から呼ぶ。モジュールキャッシュが混ざる同一プロセス内のPYTHONPATH切り替えは行わない。今回のsmokeではこれらを呼ばず、同定・正誤の出力も読まない。refiner内部の元残差certifyやhard feasibilityは段階の制御条件として通常通り動くが、それを最終正誤として集計しない。

## 将来の実行driver設計（今回は実行しない）

S1 `driver.py:stage/stream`と`worker.py`のrefine分岐を参照した。S1のsearch/scales/measure/verify/analyzeを一括実行するdriverは再使用しない。

1. S1の`pre-run-hashes.json`と`raw-hashes.json`で保存候補`runs/<case>/initial.pkl`・入力JSONのhashを照合する。pickleの内容は`(candidates, RefinerConfig)`。seed 0の主探索直後の候補を全構成で共有し、再探索・再選抜・再順序付けを行わない。S3・72問について追加の保存候補取得が必要な場合も本作業では取得しない。
2. 問題・構成ごとに独立プロセスを起動。上記の環境変数集合・patched PYTHONPATH・内部スレッド各1・1コアaffinityを設定。最大4プロセス。同一問題内でも候補集合全体に90秒、候補ごと90秒ではない。
3. 入力からS1の`ordinary()`と同じ方法で`load_problem_bundle`と`build_ir_evaluator`を作り、保存configの`MpmathRefiner(config)`を使う。スイッチのためにconfigを変更しない。`mp.workdps(180)`と`runtime_session(start+90)`内で`refine_candidates(... candidates=保存された全tuple, deadline_monotonic=start+90)`を1回だけ呼ぶ。R3も入口は同じ。
4. 精密化終了後、refined候補をpickleで保存し、入力・候補・source_hash・環境変数集合・制御フロー・時間を出力する。再試行なし。S1同様の監視プロセスを別途置くが、上限・終了時の途中候補の扱い・構成順・出力スキーマを本計測前に別途固定する。本作業では90秒driverの実装・起動や入力一覧の拡張はしない。
5. 原尺度での桁数評価が後日必要になった場合は、S1のmeasure/scales/reference修正を踏まえて別工程として明示的に固定する。S1のscales.jsonはLMの入力には使われていないので、今回の動作確認で再計算・閲覧しない。
6. 最終検証・同定は上述の別凍結プロセス。今回のsmoke用コードにはmeasure/verify/searchモードを設けない。

## 短い動作確認の事前固定

`configs.json`、`smoke_worker.py`、`smoke_driver.py`、この設計、patch・全ソースhash・候補/input hashを`pre-smoke-hashes.json`に固定してから実行する。

- 問題：S1の入力順で先頭の`AIME-2015-II-15`。保存tupleの先頭候補を無条件に選ぶ。残差や正誤を見て問題・候補を選ばない。
- 保存候補：`/tmp/mechanism-S1-1m9aomj8/runs/AIME-2015-II-15/initial.pkl`、SHA256 `b097b18229c2a91377e8ec34976b532f4ce1745c7447efe42851cd8522714555`。S1のraw-hashesと照合する。
- 各構成1プロセス・1回、順序R0→R1→R2→R3、並列1（最大4の制約内）。内部deadline 8秒、worker強制終了タイマー9秒、親プロセスの上限10秒。再試行なし。
- **このsmokeは`refine_candidates`全経路を回すものではなく、保存候補・保存config・最初の精度50 dpsから`_run_stage`を1回呼ぶ精密化段階の確認。** direct acceptやwarm NewtonでLMを迂回してしまう可能性があるため、切り替え箇所を直接呼ぶ。候補や設定値を作り替えない。整数派生候補の追加も行わない。full pipeline、warm/postの実行到達性はコード読解の範囲であり、この短いsmokeの実証範囲に含めない。
- traceは数値アルゴリズムを置換せず、LM線形ステップ呼び出し回数、λに渡した値、適応更新行の実行回数、line search試行回数、Newton closure呼び出し・Newton線形ステップ試行回数だけを読む。traceのI/O費用があるため、所要時間から速度の優劣を判断しない。
- 正誤、桁数、answer、座標、残差ノルム、収束候補数、品質を含むphase_historyや終了statusは保存・閲覧しない。段階戻り値は捨てる。内部評価は通常通りで、ログへ数値を出さない。親はstdout/stderrも捨て、例外時は型名だけ記録する。
- `smoke/*.json`に制御フローだけのreceipt、`smoke/driver.json`に時間上限・returncode、`smoke/checks.json`に切り替え条件のassertion結果を残す。R0の適応更新、R1のλ=0固定、R2の初期λ固定、R3のLM/line_search非呼出しとNewton呼出しを確認する。答えのデータは読み出さない。

実行結果は`smoke-report.md`に別記する。
