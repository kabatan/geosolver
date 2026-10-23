4基準の判定：①直感に反する＝未確認（完備4問では大差なし）、②深い理論が必要＝未確認、③広がりと再現＝未検証、④solverならでは＝未確認。**Aの中心を担えるか：現時点では不可。固定840実行が未完で、中心に据える証拠は得られていない。**

**段階1追補（停止後・再開前）。** [null diagnostics追補](amendment-null-diagnostics/prediction-supplement.md)と[lock](amendment-null-diagnostics/prediction-supplement.lock.json)を追加した。run前の「採点器を変更しない」契約からの変更として、nullを扱う1行を修正し、[84件の再採点が全フィールド・全21ファイルで一致](amendment-null-diagnostics/rescore-84/result.json)した。solver呼出し0回。worker成果物なしは不正解として分母に残し、[版別件数](amendment-null-diagnostics/stage1-mode-counts/per-mode.csv)を別欄に報告する。batch 21の4件は現在も未採点で、許可後に保存runを採点だけし、新規実行はbatch 22からの752件に限定する。[再開前import検査](amendment-null-diagnostics/preflight-stage1.json)も通過したが、commit・push確認と別タスクの明示許可まで停止する。以下の本文は追補以前の停止時点の記録として保持する。

Q38・段階2、環境修復後の再実行。**import先の修復は確認できたが、88実行後に別のworker異常と既存採点器の例外で停止した。84件は採点済み・全件matched、停止batchの4件は未採点、752件は未実行。840件は完遂していない。** 採点器の変更・独自採点・問題の除外・追加再試行は行っていない。40問全体のA/Tと事前予測は未判定である。

**環境修復と旧4件の扱い。** 旧4実行は、ユーザーの指示どおり**「契約違反の無効実行（環境不備、再実行して置換）」**として保存した。正解にも不正解にも数えない。旧rawは `/tmp/q38-58e3993-execution/` に変更なく残し、旧報告・記録・実行補助コードを[保存manifest](execution-records/invalid-attempt-20261023T164136Z/archive-manifest.json)のSHA-256で検証した。[旧報告全文](execution-records/invalid-attempt-20261023T164136Z/answer.md)。

再実行の理由は環境修復のみであり、結果を見ての選択ではない。旧4件も含め、固定840セルをbatch 0から始め直した。既存venvを `/tmp/q38-58e3993-venv` へオフラインでコピーし、`_editable_impl_geosolver.pth` の参照先だけを `/tmp/q38-58e3993-clean/src` に変更した。通常ファイル7,300件を照合し、内容差分はこの1ファイルだけ。既存venvと `/home/kabatan/work/solver` は変更していない。

同じ固定環境変数、特に相対 `PYTHONPATH=src` のまま、checkoutから起動した親と、一時ディレクトリから起動した子の両方がクリーンcheckoutをimportすることを**solver呼出し0回**で確認した。依存版とengine lockも一致。[修復検査](execution-records/environment-repair.json)、[再実行の扱い](execution-records/resume-audit.json)。新88件のうちworker情報が保存された87件では、実際のimport先もすべてクリーンcheckoutだった。異常終了した1件はdiagnosticsがなく、workerの実読込先を観測できない。新しい `executed_import_root_mismatch` の記録はない。

**固定内容とUTC。** 承認commitは `58e399315f259699e99cc1b190aa46c78d573e5a`。予測lockのSHA-256は `1db2ccc64213d70f5ea97e8b89f90efb4989f81db9292068f5fa7fd7430e4bc5`、ソースハッシュは従来どおり `sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5`。旧問題はソースハッシュの違いではなく読込先契約の不備だった。

予測・変換規則・問題選択・DSL・実行計画・solver・採点器・runnerの契約検査は一切変更していない。`stage2.py` の変更は、計画のプレースホルダーに当てるPython絶対パスと外部保存先の2行だけ。開始前と停止後に、lock対象261ファイル・全200変換の一致、実行checkoutのclean状態、凍結commit `60db4b6` に対するソース・runner・コーパス・依存lockの一致を確認した。静的再検証は240文書・210batchを通過し、新規solver呼出しは0回。[事前検査](execution-records/preflight.json)、[最終監査](verification.json)。

新しい実行開始は **`2026-10-23T16:55:00.333291Z`**、停止は **`2026-10-23T17:04:51.080445Z`**。batch 0〜20の21batchが完了し、batch 21で停止した。[開始記録](execution-records/execution-start.json)、[停止receipt](execution-records/021.json)。旧無効4件を含むsolver呼出し総数は92件、新しい840計画に対する実行数は88件である。

**今回の停止理由。** batch 21は固定順序の `original_repeat`、seed `380101`。`HMMT-2017-FEB-GEO-05` が `engine_error / artifact_missing` を返した。記録は「workerが終了code 1で成果物を残さず終了」、CLIのreturn codeは2、外部timeoutはfalseである。公開結果の `diagnostics` は `null` だった。

runコマンドは0で終了したが、続く無変更の採点器は [research_runner.py](../../../benchmarks/research_runner.py) の `read_run_outcome`、565行目の `diagnostics.get("process_info", {})` で `AttributeError` となり、assessはreturn code 1で停止した。[採点ログ](execution-records/021.assess.log)。このbatchの `assessment.jsonl` は生成されておらず、4件とも未採点として扱う。

workerが成果物を残さなかった根本原因は未同定である。保存された公開結果にworkerのstderrがなく、内部の一時ディレクトリも終了時に消去される。ファイル上限との因果関係も、証拠なしに断定しない。今回の障害を以前のimport先違反と同一視したり、solverの数学的失敗と採点したりしていない。[停止診断](execution-records/stop-diagnostic.json)。

この結果を継続して採点するには、null diagnosticsの扱いを直すなどの採点器変更、または採点・再試行手順の変更が必要になる。いずれも今回の許可範囲を超えるため、固定計画の停止条件に従い、以後のbatchは実行しなかった。停止後の診断・集計・監査はsolver呼出し0回である。

| 停止batchの問題 | 返却status | 未採点wall秒 | CPU秒 | 固定CPU | 扱い |
|---|---|---:|---:|---:|---|
| aime-2000-1-2 | solved | 27.737 | 13.56 | 0 | 未採点 |
| AIME-2012-II-15 | solved | 4.645 | 2.98 | 1 | 未採点 |
| HMMT-2017-FEB-GEO-05 | engine_error | 18.058 | 欠測 | 2 | worker成果物なし・未採点 |
| HMMT-2022-FEB-GEO-03 | solved | 17.304 | 8.78 | 3 | 未採点 |

上表の `solved` を独自に正解へ置き換えていない。外側のrun JSONは88件すべて保存されており、run記録の欠落は0件。ただし異常1件にはworker成果物・詳細diagnosticsがない。

**得られた結果の範囲。** 最初の4問は、原本＋5変換＋原本反復、各3seedの計84実行が揃い、既存採点器の厳密答え集合一致 `matched` は84/84だった。これは完備4問に限った記述であり、40問全体の正答率ではない。

| 全条件が揃った問題 | matched | A | T | 原本反復A/T |
|---|---:|---:|---:|---:|
| HMMT-2006-FEB-GEO-01 | 21/21 | なし | なし | なし／なし |
| HMMT-2021-FEB-GEO-03 | 21/21 | なし | なし | なし／なし |
| HMMT-2023-FEB-GEO-04 | 21/21 | なし | なし | なし／なし |
| JMO-2019-PRE-04 | 21/21 | なし | なし | なし／なし |

完備部分ではA=0/4、T=0/4、時間比較可能な問題に限ってもT=0/4。変換20比較の正答率1/3差は0、60対応seedの正誤不一致も0。改善・悪化とも0で、原本反復のA/Tも0/4だった。**40問を分母にしたA/40・T/40は算出不能であり、0/40とは報告しない。** 残り36問は条件不足で、8層のどの層も全5問は完備していない。

時間差が一切なかったわけではない。`HMMT-2023-FEB-GEO-04` の `orders_combined`、seed `380102` は原本13.158秒から3.797秒へ約3.47倍の短縮だった。しかしseed `380101` は12.705→6.063秒で3倍未満、`380103` は4.576→7.121秒と逆方向だった。同じ方向の閾値超過が2seedに達しないため、固定定義のTには該当しない。原本反復でもseed `380103` は4.576→9.482秒と約2.07倍の変動があり、T未満の背景変動は残る。[全seedの対応表](pairs.csv)、[全mode比較](per-comparison.csv)。

副指標の成功時費用 `min(wall,180)`／失敗時180も、未採点・未実行は欠測のまま集計した。完備部分は全件成功なので費用はwall時間に等しく、原本の平均8.813秒、原本反復9.447秒、各変換8.221〜9.351秒だった。問題を混ぜた4問のみの記述値で、因果効果の推定ではない。[mode別集計](per-mode.csv)。

| 固定予測 | 判定 |
|---|---|
| P1：Aが0〜4/40問、点予測2問 | 未検証。完備4問ではA=0 |
| P2：Tが12〜20/40問、点予測16問 | 未検証。完備4問ではT=0 |
| P3：点名だけでA=0、T=0〜2問 | 未検証。完備4問ではA=0、T=0 |
| 変数順を含む3modeが全Tの2/3以上 | 未検証。40問全体のTが未確定 |

少数seedと5変換中の最大差を用いる計画であり、完了しても母成功確率の差や厳密な不変性の証明にはならない。今回の完備4問を固定40問や323問の母集団へ外挿しない。

**診断とQ34。** 上記の単一seedの時間短縮では、高精度残差評価回数が原本16,829から3,333へ、refinement時間が7.601秒から0.707秒へ変化していた。採用候補の出所はいずれもNOMADで、採用数は11から16へ変化した。原本反復ではこれらのカウンタが原本と一致していてもwall時間は変わった。[対応した保存診断](mechanism-observations.json)、[全88件の診断要約](diagnostics/)。

これは計算経路と費用が変わった記述であり、始点の幾何的対応、NOMADの方向列、尺度軸、丸め誤差の寄与を直接同定したものではない。追加介入は行っていない。Q34の保存結果は、局所1ulp摂動による行き先変更3/12問、厳格なフラクタル認定0/12問、完成solverの同seed最終答え変更0/24組だった。Q38の変数順・条件順による有限の変更を、Q34と同じ機構やフラクタルの証拠とは呼べない。今回の未完データもそれを補強・反証するには不十分である。

**負荷・保存・再集計。** AMD Ryzen 9 9950X3D、16物理コア・32論理CPU。CPU 0/1/2/3は異なる物理コアで、各runは1コア、最大4並列。全88件のCLI affinityと、観測可能87件のworker affinityが指定CPUに一致し、batch間の重複起動はなかった。BLAS等は1thread。各batchをnohup非同期セッションで起動し、1本ずつ監視した。

開始時load average（1/5/15分）は **12.394／11.628／13.730**。実行中の保存サンプル範囲は **12.394〜23.542／11.628〜18.441／13.685〜16.249**。CPU固定は共有機やSMT兄弟との競合を除かず、時間差を入力変換だけに帰属させない。

新rawは `/tmp/q38-58e3993-repaired-execution/campaigns/` に保存し、未完のため計画上の全件完了後の `results/` への移動は行っていない。保存ファイル上限4,900,000 bytesを維持し、最大保存rawは **4,435,183 bytes**、5MB超の生データは作っていない。全rawのハッシュは [results-summary.json](results-summary.json)、840セルは [runs.csv](runs.csv)、40問と8層は [per-problem.csv](per-problem.csv)・[per-stratum.csv](per-stratum.csv)、210batchの状態は [batches.csv](batches.csv) に残した。失敗・欠測・未実行を隠していない。

再集計は `report_repaired.py`、整合性監査は `audit_repaired.py`。いずれも保存結果のみを読み、solver・採点器を呼ばない。監査は旧無効実行の保存、固定内容、全88runのchecksum、84assessmentの転記、840セル、対応seedの比率・閾値、4問から40問へ結論を拡張していないことを確認した。以後の実行は停止したままである。
