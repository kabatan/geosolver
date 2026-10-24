# S10・事前登録17 部分B：スイッチ準備

本成果物はスイッチ実装と制御フローのsmokeのみ。本計測・正誤・桁数比較・commit/pushは行わない。事前登録17は変更しない。S8/run-*とS10の既存結果は開かない。今回新設したswitches/の制御receiptだけを検査する。

## ベース・再構成

指定BASE1 `/tmp/mechanism-7b-lkdjle5l/final`、source_hash `sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3`を読み取り専用として扱った。コピー先は `/tmp/mechanism-S10-zqtyfenw/final`。S9A/design.mdとswitch-r.patchの方式を踏襲し、通常のunified diffを作成、runtime/ablation.pyのactive_ablations()への登録とengine-lock.jsonのsource_tree_hash/standard.hashの更新を行った。適用後hashは `sha256:2cb435fc35950aafaf6bb2e3a40df30a7415c9fdc65d3ff4b8d969c361ecac75`。

再構成はBASE1を別の `/tmp/mechanism-S10-<乱数>/final` にコピーし、そのルートで `git apply --check <switches>/switch-b.patch`、`git apply <switches>/switch-b.patch`。`PYTHONPATH=<コピー>/src`、`PYTHONDONTWRITEBYTECODE=1`で `source_tree_hash()` と `verify_engine_lock()` を確認する。prepare.pyはこの作成過程を再現し、既存source-hashes.jsonがある場合は上書きを拒否する。replay/への実適用と全通常ファイルのバイト一致を確認済み。

`source-hashes.json`はBASE1・適用後・凍結版の全通常ファイル（__pycache__除外）の生バイトSHA256、変更7ファイル、保護12ファイル、既存実装の出所hashを保存する。source_hashの定義はruntime/integrity.py:source_tree_hashと同じ。CRLFの正規化はsource_hash計算だけで行い、生バイト比較では行わない。

## 構成と切替

正本はconfigs.json。各プロセスで継承したGEOSOLVER_ABLATE_*を全消去し、その構成の環境変数集合だけを設定する。各スイッチは値が文字列`1`のときだけ有効。

| 構成 | 環境変数（値は1） | 止めるもの |
|---|---|---|
| B0 | 空集合 | BASE1の挙動 |
| B014 | GEOSOLVER_ABLATE_NO_FLOAT_MARGIN_FLOOR | M014のfloat退化余裕3種 |
| B046 | GEOSOLVER_ABLATE_NO_NOMAD_GUARD_PENALTY | M046のNOMADへ返す目的値へのhard違反罰則 |
| B005_006 | GEOSOLVER_ABLATE_NO_SEARCH_BOX_INFERENCE | M005とM006の探索箱推定を同時停止 |
| B005 | GEOSOLVER_ABLATE_NO_GUARD_BOUND_INFERENCE | M005のguard由来探索境界 |
| B006 | GEOSOLVER_ABLATE_NO_SEARCH_BOX_SCALING | M006の定数・依存関係からの尺度推定 |
| B045 | GEOSOLVER_ABLATE_NO_HIDDEN_CONSTRAINT_MODE | M045のhidden constraint通知 |
| B014_046 | B014とB046の集合 | 余裕と目的値罰則を併用停止（契約確認のみ） |

以下の行番号は適用後の `src/geosolver/` 以下。inventory/INVENTORY.md:147–156,197–198のM番号を照合した。

### M014：float退化余裕

`engine/standard/evaluation/_hard_feasibility_core.py:170–174,200–204,228–232`で、floatのみ直線・除外交点の1e-12、三角形の1e-14を0にする。完全一致・面積0は従来通り不適格。HPの閾値0は変更しない。

**不等式の扱いを限定する。** M014はinventoryでは上記3種のfloat floor。不等式guardの正の余裕は同ファイル:132–147の「margin>0」であり、元々正の固定floorはない。ここやinterpreter/guards/compile.py:550–569の元不等式、許容差、違反量の正規化M013は変更しない。guardそのものを無視したり、厳密不等式の境界を受理したりするスイッチではない。したがってB014だけでは不等式の違反点に罰則が残る。M046も外すB014_046ではNOMAD目的値のその罰則は消えるが、後段の適格判定は残る。

M014はNOMAD専用ではなくfloat hard判定の共通部なので、SciPy・初期probe・候補分類にも作用する。SciPy補助罰則M047自体は残るが、floorだけが理由だった不適格はその判定から消える。選択枝のtie判定、構成失敗、HP、最終検証は残る。

### M046：目的関数の罰則

出所は `jssa/difficulty/nomad-wall/patch/nomad_wall_patch.py:35–40,100–124` のmode N。既存のsitecustomize/ContextVar計装を丸ごと導入せず、同じ「NOMADへ渡すscoreだけを等式残差二乗和にし、候補recordは保持する」処理をソース分岐へ移植した。出所の生バイトhashはsource-hashes.json:provenance。

`engine/standard/search/nomad_blackbox_adapter.py:131–149`で既存順序の正規化残差二乗和を使い、hard不適格時の既定1e6（config.guard_penalty）をNOMADへの出力から外す。制約scale、残差の計算順序、guard/hard評価は残る。:153–171のrecord.scoreには罰則付きscoreが残り、hard_feasible/guard_ok/失敗tagも保持する。従ってledger、候補選抜・再ランキング、精密化入口の安全条件は引き続き働く。M046を候補記録からも消す介入ではない。

既存nomad-wall版はprimaryのdisco_madsスコープだけ。今回のスイッチはadapter共通部に置くため、primary・second attempt・rescueのNOMAD全呼出に作用する。M044のdisco_mads/mads設定は変えない。NOMADを使わない構成や代数迂回では効果がない。M045の評価不能点は別分岐なので、B046だけでは失敗通知を変更しない。

### M005・M006：固定の既定探索箱

`problem/domain_bounds.py:185–190`のsearch_box_domains()を追加。B005またはB005_006ではspec.guardsを探索境界推定用のコピーからだけ除き、spec.boundsの明示境界とPointOnSegment等の構成パラメータ域M004を残す。元spec、mathematical_bounds() (:129–182)、load_problem_bundle.py:56以降の固定変数消去、HP境界、元guardは変更しない。B006単独ならguard由来の境界も残る。

同ファイル:234–244でB006またはB005_006なら依存関係探索・定数尺度の更新を実行せず、:195の各軸10を使う。両方停止時の未拘束軸は[-10,10]。数学的境界が片端にあれば従来の:257–260の幅調整が残るため、全軸を無条件に[-10,10]へ切り詰める介入ではない。M007の外向き丸めも保持。

`engine/standard/interpreter/compile/infer_bounds.py:3–8`も同じsearch_box_domains()を使う。取り外したguard境界をM008の「拡張をロックする端」として残さないため。M008の25%拡張は働き、未拘束の固定箱[-10,10]はNOMAD側で[-15,15]になる (`search/nomad_backend.py:20–40,79–83`)。救済の局所箱、尺度chart M009、affine guard sampler M041/M042、元guardは働くので、箱推定停止はguardを使う全機能の停止ではない。

B005とB006は独立に併用可。その和はB005_006と同じ。B005_006に片方を重ねても同じ。M005を外してもM006が定数から箱を拡大でき、M006だけ外してもM005が不等式で箱を狭められる。この相互作用を契約probeで確認する。

### M045：評価不能点

`search/nomad_config.py:82`でDISCO_MADS_HID_CONSTをfalseへ。DISCO_MADS_OPTIMIZATION、HID_CONST_OUTPUT_VALUE、OBJ、評価予算、seedはそのまま。`search/nomad_blackbox_adapter.py:97–123`で非OKの残差評価について、failure_countと不適格recordを従来通り保存した後、有限の1e30をsetBBOしcallbackの戻り値を0から1へ変更する。1e30は既存NON_FINITE_SCORE_PENALTYで、追加の選定・調整はしない。

デフォルトの無効点出力設定1e20は変更しないが、スイッチ時の有効罰則はそれより大きい1e30。NaN/infを成功候補にはしない。期限到達・TimeoutErrorによるreturn 0は常に残す。失敗率や候補適格フィルタ、最終検証は残る。M044のDiscoMADS自体は動作するため、M045とM044を同時に外す介入ではない。救済のmadsにもcallback分岐は作用する。

## 既定経路と凍結

新フラグが未設定なら既存thresholdの代入・目的値のstr(score)・失敗return 0・既存数学的境界と尺度推定を使う。defaultの数値式と既存設定値を変えない。探索箱用ヘルパーと条件分岐のコストは追加されるため、実行時間のバイト一致を主張しない。BASE1と適用後B0を別プロセスの決定的probeで実行し、stdoutの生バイト一致を確認する。これは全問題・時刻依存の全プロセス出力の一致証明ではない。

最終検証/同定はS1凍結版 `/tmp/mechanism-S1-1m9aomj8/frozen`と、evaluation/final_verifier.py、verification_*.py全6ファイル、exact_assembly/全5ファイルの計12ファイルがBASE1・適用後とも生バイト一致。将来の最終評価は凍結版・全ablation未設定の別プロセスで行う。今回のfull pipeline内部では通常の最終処理に到達し得るが、answer/status/残差/桁数/候補の品質は取り出さず、戻り値は捨てる。

## 動作確認の固定

inputs.jsonはQ15 false-attractors/per-problem.csvの既存順で、main_cause=aとbの先頭IDだけを選択した。AIME-2007-II-15（退化a）、AIME-2009-I-12（逃避b）。分類とID以外の列を選択に使わない。入力はbenchmarks/dslの原問題を読み、hash照合する。

- B0と6つの単独スイッチにつき上記2問、各1回の新規プロセスでrun_external_pipeline()を実行する。数値アルゴリズムの置換や到達強制は行わない。
- seed 0、全構成共通のsmoke用3秒runtime budget、watchdog9秒、親の上限10秒。並列1（上限2以内）、内部スレッド各1、1CPUへaffinity、nice +15。foregroundで親が全子プロセスの終了を回収する。総当たり・180秒実行・detached workerは用意しない。
- traceは呼出回数、floorに使った閾値、search_bounds/_expand_boundsの箱、NOMADパラメータ、罰則分岐/無効通知回数だけ。trace overheadがあるので時間の優劣を比較しない。stdout/stderrは捨て、例外は型だけ。
- 短い実行では代数・他の探索経路に迂回し得る。未到達分岐は「実問題で実証」とせず、probe_worker.pyの決定的な小さい契約probe（tiny/zero float/HP、有限不適格、非有限/評価失敗、期限、箱/明示境界/構成域、mads/disco_mads params）で補う。合成probeの数値は品質比較ではなくプロトコル確認用。
- probeではB014_046、B005+B006の併用、全フラグ値0も確認。BASE1/B0のbyte一致、候補record不変、HP/厳密退化/不等式境界不変をassertする。
- pre-smoke-hashes.jsonでcode/design/config/patch/source-hashes/inputを先に固定し、smoke_driver.pyはsmoke/が既存なら再実行を拒否する。smoke/checks.jsonとsmoke-report.mdには制御確認だけを記録する。

## 継続作業で確定した範囲とB045の依存関係

前任のsmoke/の既存receiptは上書き・再実行しない。14ジョブのdriver.jsonはB0/B014/B046/B005_006/B005/B006が各2件終了コード0、B045が2件ともSIGSEGV（-11）で、B045のworker receiptは未作成。元のsmoke_driver.py:110–115の全ジョブ成功assertは成立せず、checks.json未生成だった。verify_preparation.pyが保存済み契約probeの同じassertを再評価し、全体成功と偽らず結果を新規smoke/checks.jsonへ保存する。

**B045はnativeでの正常動作が未確認。本計測にそのまま投入できる検証済み構成ではない。** Python契約probeではパラメータ切替・有限罰則通知・失敗record保持を確認できたが、実問題の2件は異常終了した。M045のみによる性能差を測れるとは主張しない。

ローカルのPyNomadBBO 4.5.1をnative_check.py:15–21,24–49の有限二次目的関数だけで確認した（geosolver・原問題はimport/読込しない）。`DISCO_MADS_OPTIMIZATION true / HID_CONST false / BB_OUTPUT_TYPE OBJ`はcallback開始前にSIGSEGV。hidden=true、DiscoMADS=false、診断用OBJ-Rは終了コード0。native/に呼出回数・設定・stderr・親の終了コード・インストール済みbinary hashを保存する。各子プロセス10秒上限、並列1、最大8評価、core dump無効。

既存の`jssa/difficulty/nomad-wall/nomad-parameter-help.txt:147–157,177–196,207–221`によれば、HID_CONST=falseではDiscoMADSは不連続性検出モードになり、検出対象の出力に`-R`を付ける。したがってM045設定とM044/output宣言には依存関係がある。現patchのOBJを保った切替は、このインストール済みnativeで動かない。OBJ-Rでの正常終了は依存関係の切り分けに限り、目的値を検出対象とする別の介入なので採用しない。C++の厳密な故障箇所・上流の原因・実問題に対するOBJ-R版の正常動作は**未確認**。DiscoMADS停止・代替backendへのfallback・native更新は行わない。

M014の3つのfloor分岐とB045の無効点通知は今回の実問題traceでは到達を確認できず、合成契約probeでの確認に限定する。B046の罰則除去とB006/B005_006の尺度依存解析停止は実問題traceでも確認。M005のguard境界除去は合成probeで確認（実問題では箱が変わらない場合がある）。

継続時にdesign.mdの行番号訂正と本節を追記した。pre-smoke-hashes.jsonは変更せず、旧design hashを保存し、smoke/checks.jsonにその変更だけを明記する。patch・configs・source-hashes・元のsmokeスクリプト・入力は事前固定のまま。completion-hashes.jsonが最終成果物と制御receiptの生バイトhashを記録する。外部ネットワークの取得、S8/run-*参照、本計測、正誤/桁数比較、commit/pushは行わない。
