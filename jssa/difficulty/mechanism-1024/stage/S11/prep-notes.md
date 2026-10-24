## 追記の案（S11実行前準備、未確定）

以下は事前登録18への追記案であり、登録内容の確定・追記はまだ行っていない。S11の72問×5水準×3 seedの本実行、採点、予測の検定は行っていない。実施したのはコード調査と、小さな2問によるbackend単体の動作確認だけである。

### 調査対象と凍結版の区別

コードの行番号は、特記しない限り準備時点の作業木（HEAD `e68e923530bbc364ce451b79bfaef8341a3b3f93`）のpatch適用前を指す。以下では `src/geosolver/engine/standard/` を省略し、`scipy_multistart_backend.py` は `search/scipy_multistart_backend.py` を指す。

- 指定ソース：`src/geosolver/engine/standard/search/scipy_multistart_backend.py`。SHA256 `248929ad1914a3b596eb576612e7887404ce646d313d1fc66ab8d76f1bb6b229`。定数は39行、使用箇所は1282行。
- S8再実行のNの参照先は `stage/S8/rerun-driver/groups-env.md` と `configs.json`。そこで使ったBASE1は `/tmp/mechanism-7b-lkdjle5l/final`、全体source_hashは `sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3`。
- このBASE1の同名backendファイルのSHA256は `11abaf69a21dc15a2506b6e9a3eacb564adc841dda87de78e1f0453ae272f3c9`。指定ソースとは、ablationのimportと `refinement_selection_pool` の受渡しが異なる。BASE1では定数41行、使用箇所1286行。指定ソースだけにpatchを当てても、S8の全ablationを備えたNになるわけではない。
- 本準備では指定ソースもBASE1も書き換えていない。`halton-start-count.patch` は指定ソースを基準に作成し、専用の `/tmp/mechanism-S11-prep-tdp_r9a2/` のコピーだけに適用した。BASE1についても、この専用ディレクトリ内に同名ファイルをコピーし、patch適用と構文検査だけを確認した。fuzz=0で適用でき、第2hunkの行位置だけ2行ずれた。BASE1全体のN実行はしていない。

### 1. Halton点数の切替案と確認

`halton-start-count.patch` により、`GEOSOLVER_SCIPY_N_HALTON_STARTS` をmodule import時に1回だけ読む。許容値は `1, 4, 16, 64, 320`。未設定時は整数320となり、元と同じ `_N_HALTON_STARTS` が同じ使用箇所へ渡る。環境変数を変更した後は新しいworkerを起動する。空文字・非整数・許容外の整数は `ValueError` とし、誤設定を320へ黙って戻さない。TRF、Haltonのseed・scramble・burn-in、最大評価回数、時間配分、候補選択は変更しない。

将来のN_kでは、S8と同じNの8個の `GEOSOLVER_ABLATE_*` をすべて1とし、この点数変数だけkに設定する案とする。Nの8変数は `NO_NOMAD`, `NO_SECOND_ATTEMPT`, `NO_RESCUE`, `NO_DIVERSE_SELECTION`, `NO_RESIDUAL_REWRITE`, `NO_SCALE_CHART`, `NO_ALGEBRAIC`, `NO_ANALYTIC_JAC`（接頭辞はすべて `GEOSOLVER_ABLATE_`）。S8の既存driverは継承された `GEOSOLVER_*` を除去するため、単に親shellにexportするだけではkが消える。将来driverを用意するときは、環境を清掃した後の子process環境へkを明示し、その実効環境を保存する（`stage/S8/rerun-driver/measurement_runtime.py:14–26`）。本準備ではdriverを改変・起動していない。

動作確認は `verify-switch.py`、実測は `switch-check.log` に保存した。ネットワーク・ダウンロードは使わず、既存Python 3.12.11 / NumPy 2.5.1 / SciPy 1.18.0を使った。CPU affinityは1コア（CPU 0）、BLAS等も1thread、CPU上限45秒・wall alarm 55秒、各backendの時間枠8秒。コマンドはフォアグラウンドで実行し、全確認の経過時間は3.662秒だった。

確認問題は `x-0.125=0, y+0.25=0` と `x*x-0.25=0, y*y-0.0625=0` の2問、範囲は両軸 `[-1,1]`、backend seedは801の1個、追加prefixは `[0.91,-0.83]` の1点である。これは本実行の内部seed数を1に変更する提案ではない。実際のSciPy呼出しを数えるwrapperを置き、optimizerの返り値をそのまま使った。

| k | 生成したlocal Halton点 | Haltonラベルのfinished点 | 追加prefix＋アンカー | 実際のLM呼出し合計 | 実際のTRF呼出し |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 1 | 6 | 7 | 24 |
| 4 | 4 | 4 | 6 | 10 | 24 |
| 16 | 16 | 16 | 6 | 22 | 24 |
| 64 | 64 | 64 | 6 | 70 | 24 |
| 320 | 320 | 320 | 6 | 326 | 24 |

両問でこの表と一致し、全local eventが `finished` だった。元ソース320、patch後の未設定320、patch後の明示320で、選択候補・全候補の座標/score/出所・評価回数・diagnosticsを含む `SearchBatchResult` 全体が一致した。各kのlocal Halton座標は元の320点列の先頭k点と一致し、TRFの24点と非Haltonの座標集合は全kで一致した。0, 2, 321, `abc`, 空文字の拒否も確認した。

再現用の準備コマンド（本実行用ではない、repository rootから）：

```sh
PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B \
  jssa/difficulty/mechanism-1024/stage/S11/verify-switch.py \
  --source-root . --frozen-root /tmp/mechanism-7b-lkdjle5l/final
```

このscriptは自分用の新しい `/tmp/mechanism-S11-prep-*` を作り、コピーにpatchを当てる。既存実験の停止・再開・優先度変更や他processへの操作は含まない。

### 2. Nに残る出発点とkへの依存

ここでkは「local familyの各内部seedに対して生成要求するHalton点数」であり、1問題の全出発点数ではない。`seed_values` 全件に点列を作り、TRFも各seedで回す（backend 1177, 1270–1288, 1362–1374行）。既定の内部seed数は5で、外部 `--seed=s` は通常 `s,...,s+4` になる（`search/nomad_config.py:14,27–35`、`orchestration/run_external_pipeline.py:67–71,1019–1025`）。S8 driverも外部 `--seed` を渡す（`stage/S8/rerun-driver/measurement_runtime.py:69`）。外部seed 801〜803という指定と、内部seedを1個にする操作は同義ではない。Nを保つなら内部seed数も維持し、実効 `seed_values` を記録する案とする。

以下の「一定」は同じ入力・seed・範囲・予算での生成規則を指す。実際に開始/完了した数は、迂回経路、重複除去、評価失敗、時間切れによって少なくなりうる。

| 経路 | 個数・規則（patch前の行番号） | kを変えたとき |
|---|---|---|
| local Halton | backend 272–294, 306–313行。scrambled Haltonをk点生成。`family_tag="local_halton"`、seed変換184–188行。parametric変数ありなら先頭3点をburn-in、なしなら0（48,1269行） | 点数だけk。座標は同一列の先頭k点。burn-inの3点はoptimizerの出発点に数えない |
| `halton_prefix` / `front_tail` / `remaining_tail` | 315–318,340–345,354–359,375–388行。prefixは `min(k,d)`、残りも元の同じk点から分ける | すべてHalton由来。別枠の追加点ではない。3ラベルを合計して数える |
| `extra_prefix` | 332–339行。`self.start_points` を各seedに追加。通常、probeから最大内部seed数S個を選ぶ。1個も選べなければS個の対角上の等間隔fallback（`search/select_search_start_points.py:23–32,35–65`、`orchestration/run_search.py:320–326`） | 選択入力はkより前に決まるので生成規則は一定。既定S=5なら最大5個/内部seed。同じprefixを各seedで再利用する |
| 固定interior anchors | backend 251–269行。d>0で `min(d,4)` 個の0.2/0.4/0.6/0.8巡回、中央1、順逆のlinspace各1。計 `A(d)=min(d,4)+3` 個（d=1,2,3,≥4で4,5,6,7）。d=0は0 | 座標集合・生成数は一定。`front_anchor` / `final_anchor` への分割と他点との順序はkにより変わる（231–248,319–328,397–412行） |
| bounded TRF | backend 52–53,791–865行。別のHalton列 `family_tag="bounded_trf"`、burn-in=0で24点/内部seed。残差・guard・hard feasibilityで順位を付けて回す。`max_nfev=1200` | 24点と順位付け規則は一定。kとは独立のHalton列。local LMのk点には含めない |
| Phase 0 random probe | `orchestration/run_initial_probe.py:20–21,100–125`。50点/seed、通常5seedで250点。これは局所最適化を回す250点ではなく、prefix選択や制約scaleの材料 | 生成規則は一定。残時間・cache利用により実評価回数は異なりうる |
| Phase 0の追加sampling | `orchestration/run_initial_probe.py:42–61`、`search/sampling/manifold.py:28,205–239,279–318`。該当する距離円ごと12方位。AffineGuardSamplerは既存guard通過候補がないとき最大32点（`search/sampling/affine_guards.py:198–218`） | k非依存。条件・重複・範囲・失敗で採用数が変わる。局所探索の追加32回等と数えず、prefix母集団への追加とする |
| finite guard | `search/finite_guard_search.py:65–91,108–129,132–175,206–249`。2〜16択の1座標離散guard、離散軸≤6、直積≤256枝。probeのscore上位3点のうち有限なもの＋一様乱数2点を各枝へ。自由軸ありなら枝ごとLM/TRF、なしなら直接評価。最大5×枝数、上限1280組、bounds等で減る | kを読まない。時間枠 `min(12秒, search枠の20%)` と枝別期限、局所 `max_nfev=min(160,max(1,max_bb_eval))`。実際のattempted/completedをdiagnosticsに保存。kによる定数変更なし |
| primary scalar scan | `orchestration/run_search.py:434–452`、`search/scalar_branch_scan.py:19–51`。1変数かつ通常の `disco_mads` 時に、NのNOMAD fallbackより前に1回。上限2秒 | k非依存。候補があればSciPy local/TRFへ進まず返却 |
| SciPy内の1D scan | backend 868–871,1019–1141,1191–1268行。primary scanで返らずSciPyへ来た場合にも1回。gridは `g=max(81,min(401,max(32,max_bb_eval)+1))` 点＋両端の隣接内点2点をunique化。通常standard `max_bb_eval=200` なら最大203観測点。各制約の符号変化でbrentq、残差極小盆地最大10区間でbounded minimize_scalar、良い生grid位置最大8個も保存 | k非依存。符号変化数は問題依存で、scanの総評価数はgrid点数だけではない。brentq/minimize_scalarは各maxiter=80（948–954,990–994行）。内部seedごとのscanではない |
| 整数二乗差の有限候補 | `search/discrete/square_difference.py:218–255,280–336`、`orchestration/run_search.py:332–359`。1変数で対応する整数条件がある場合に約数から根を列挙、128根を超える場合はこの近道を辞退 | k非依存。Nの `NO_ALGEBRAIC` はこの経路を止めない（primaryのallow_algebraic自体はTrueのまま）。全有限seedが適格ならbaseline探索を迂回 |

local startsは、extra prefix→Halton prefix→アンカーとHalton tailの織込みで作り、完全に同じfloat座標は除く（backend 204–228行）。したがって一般の正確な予定点数は、各seedの `|E ∪ H_k ∪ A|` である。通常の非退化範囲で重複がなければlocalは `k+E+A(d)`、さらにTRFを含む局所探索予定数は `S×(k+E+A(d)+24)`。Haltonとextra/anchorが偶然重なる場合や幅0の軸だけの場合などには、Haltonラベルの実行数もk未満になりうる。確認した2問は重複がなく、Haltonラベルk回の実行まで確認した。

kでアンカー等の生成数を変えるpatchは含めない。ただし順序は変わる。seedごとの浅いprefix枠は `min(total,max(shallow_prefix,24))`（backend 382–394行）で、その枠を全seed分回してから各seedの残りを回す（436–450,1289–1294行）。k=1のアンカーがすべて `front_anchor` でも、k=320では一部が `final_anchor` になりうる。このラベルの個数の変化を「非Halton点が新たに増減した」と解釈しない。時間切れ下の実行順・実際の完了数はkにより変わる。

S8のNでは通常の代数prepassとscale chartは停止している。BASE1の `search/algebraic_branches.py:658`、`search/scale_chart.py:14` がそれぞれablation gateである。整数二乗差、finite guard、probe sampling、残差scale、数値微分や後段のclosure/最終検証は残る。現在の指定ソースを含む作業木にはこれらN用gateがないため、S8のNの再構成を現在の作業木だけで代替しない。

### 3. どこで止まるか

localの多点出発は「最初の適格候補で停止」ではない。backend 1300–1348行は、候補をappendして次のstartへ進む。breakはlocal期限をstart前に超えた場合（1302–1310行）と評価中の `_SearchDeadlineExceeded`（1324–1332行）。recordが作れない場合は次のstartへcontinue（1333–1340行）。`_is_admissible_candidate` を停止条件には使っていない。予定をすべて回すか、期限まで回す。

bounded TRFも同じで、backend 832–865行は候補append後に継続する。期限到達/評価中の期限超過でbreak、通常例外は次の点へcontinue（833–851行）。localが既に適格候補を出していてもTRFを省略する条件はない（1357–1374行）。ただし外側のdeadline/TimeoutErrorも実行を打ち切りうる（153–157,606–609,848–849行）。1点のoptimizer自体は収束許容値または評価上限で終了する。localでは変数数が制約数を超えるとLMではなくPowell（maxiter=400）、それ以外はLM（max_nfev=80）になる（563–622行）。

localとTRFの枠はkによって再配分しない。非parametricは45:45、parametricは60:45の比率で `config.max_time_sec` を配分する（backend 160–181行）。1D scanはlocal期限を作った後に行うためlocal枠を消費し、TRF期限はlocal終了後に作る（1178–1198,1357–1361行）。finite guard等も先にsearch枠を使う（`orchestration/run_search.py:503–525`）。180秒全体がk点のLM専用時間になるわけではない。

一方、経路全体には以下の早期返却がある。

- 1変数primary scalar scan：scanで候補を集めた後、1個以上selectedがあればbaselineから返却（`orchestration/run_search.py:446–447`）。
- SciPy内の1D scan：走査が返した候補のうち1個以上が適格なら、local/TRFを作る前に返却（backend 1213–1227,1259–1267行）。適格条件はstatus OK、残差<1e-6、guard/hard feasible、marginなし又は≥1e-6（737–746行）。primary scanはmarginの追加閾値を課さない（`search/scalar_branch_scan.py:53–66`）。走査そのものは最初の根で止まらず、grid・全符号変化・最大10盆地を時間の許す範囲で調べる。
- 整数二乗差：全有限seedが適格なら返却。一部のみならbaselineも走り結果を結合（`orchestration/run_search.py:343–359`）。
- finite guard：成功候補があってもbaselineを省略する条件はなく、残時間を差し引いてbaselineを実行し結果を結合（`orchestration/run_search.py:521–541`）。枝間も最初の成功で止まらない（`search/finite_guard_search.py:206–297`）。
- 通常の代数prepass：結果があればrun_searchを迂回（`orchestration/run_external_pipeline.py:351–365,391–402`）。S8のNではこのprepassは停止。第2attemptとrescueもNでは停止。

このため、kを増やしても全問で追加LMが動くわけではない。一方、localまで来た問題では最初に当たってからも探索が続くので、Q4の費用は生成kだけでなく開始・完了数と期限打切りも合わせて読む案とする。

### 4. 答えを出した候補の出所の記録案

既存フィールドで大きな経路とlocal startの種類を追跡できる。探索候補の `origin_backend`, `origin_family`, `origin_seed`, `origin_start_point_index`, `origin_attempt`, `candidate_id`, `candidate_uid`, `candidate_key` がある（`contracts/candidate_record.py:82–131`）。精密化後は `RefinedCandidate.source` と派生keyが親候補を保持し、`candidate_record()` はsourceを再帰的にシリアライズする（同143,163–174,214–222行）。

| 既存の印 | 判定できる出所 |
|---|---|
| `origin_backend="scipy"`, `origin_family="1"` | local family。LM又は不足制約時のPowell。これだけではHaltonとアンカー/prefixは区別できない（backend 589–619,719–730行） |
| 上記＋ `search.local_start_events` の `start_kind` | 同じbatch/attemptの候補とcandidate_id又はseed/start_indexで対応。`halton_prefix`, `front_tail`, `remaining_tail` がHalton。`extra_prefix`, `front_anchor`, `final_anchor` はそれ以外（backend 92–109,333–388,415–433,1295–1347行） |
| `origin_backend="scipy"`, `origin_family="2"` | bounded TRF（backend 852–862行）。start indexは順位付け後の番号 |
| `origin_backend="scipy"`, `origin_family="3"` | 1D走査由来（backend 1199–1211行、`search/scalar_branch_scan.py:39–51`）。`primary_scalar_branch_scan` / `one_dimensional_search` のdiagnosticsで呼出経路を補助判定 |
| `origin_backend="finite_guard_local"`, family=`branch:n` | finite guardの枝（`search/finite_guard_search.py:269–282`） |
| `origin_backend="integer_square_difference"` | 整数二乗差の有限候補（`search/discrete/square_difference.py:294–310`） |
| `origin_backend="exact_polynomial"` / `"positive_scale_chart"` | 通常の代数 / 尺度chart（`search/algebraic_branches.py:694–705`, `search/scale_chart.py:84`）。S8のNでは通常この2経路は停止 |

最終結果の `pipeline_summary` に `answer_source_candidate_id`, `best_candidate_id`, `answer_extraction_candidate_ids`, `exact_candidate_records`, `candidate_ledger`, `search` がある（`orchestration/build_pipeline_summary.py:151–169,190–195`）。`exact_candidate_records[*].candidate.source` から受理された答えの親探索候補をたどり、`candidate_uid` / `candidate_key` とlocal eventを結ぶ方法を採る案とする。候補IDだけでfamilyを算術的に推定せず、backend/family/attemptも使う。複数の受理候補・派生closureがあれば全件の出所と最終採用候補を残し、出所不明は不明と記録する。同じ座標へ複数経路が到達していても、答えに使われた候補の親経路を記録する。

既存情報の限界もある。family 1はLM/Powellを明示する独立fieldを持たないため、変数数と制約数の分岐から判定する。family 3はgrid直採用・brentq・minimize_scalarを候補ごとに区別しない。TRFにはlocal_start_eventsと同等の開始/失敗/期限別eventはない。残っているTRF `all_records` の数は完了record数であり、試行総数とは限らない。`candidate_ledger` 単体は `origin_family` を明示せず、選別後の一部のみなので、それだけを保存して出所を断定しない。

将来の本実行では、各case・外部seed・k・実効内部seed列・source/patch hash・実効環境とともに、元の `pipeline_summary`（特に `exact_candidate_records`, `search.local_start_events`, scan/finite guardのdiagnostics）を欠落なく保存する案とする。localでは `finished`, `record_failed`, `deadline_before_start`, `deadline_during_eval`, `not_started_after_deadline` をstart_kind別に集計し、生成kと開始/完了Halton数を分ける。`deadline_during_eval` と `record_failed` は開始済み、`deadline_before_start` と `not_started_after_deadline` は未開始として扱う。1Dや整数近道でlocalへ来なかった場合は0回・迂回理由を明示する。出所記録の追加実装・本実行driver・Q1〜Q4の解析方法の変更は本準備では確定しない。

特に理論式 `1-(1-p)^k` のkと、既定5内部seedで最大5k点＋非Halton点が働く実装上の試行数は区別が必要である。この発見は本実行前に記録し、元の予測式を無断で5kへ置換したり、内部seed数を1へ変更したりはしない。
