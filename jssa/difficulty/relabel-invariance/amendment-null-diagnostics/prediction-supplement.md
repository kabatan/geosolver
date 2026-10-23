# Q38 段階1追補：null diagnostics と worker成果物なしの扱い

この追補は**停止後・再開前の事前登録追補**である。今回の新規solver呼出しは **0回**。完備済み84件の再採点、保存記録の集計、import・hash検査だけを行った。batch 21の4件は未採点、残り752件は未実行のままにする。Claudeがこの追補とlockを含むcommit・pushを確認し、**別タスクで明示的に再開を許可するまで実行しない**。lockの作成時刻やローカルGit状態は、その許可を代用しない。

## 登録時点で既知の情報と契約変更の開示

環境修復後の固定840実行は88件で停止した。batch 0〜20の84件は既存assessmentで全件matched。batch 21には保存済みrun JSONが4件あり、そのうち1件が `engine_error / artifact_missing`、`diagnostics=null` だった。既存採点器は `read_run_outcome` でnullに `.get()` を呼んで例外となり、batch全体のassessmentを保存できなかった。停止記録は [answer.md](../answer.md)、[stop-diagnostic.json](../execution-records/stop-diagnostic.json)、[021.assess.log](../execution-records/021.assess.log) に残っている。

**これは「run前に事前登録した契約からの変更」である。** 元の [execution-plan.md](../execution-plan.md) は採点器を変更しないと定めていたが、今回はnullを扱う1行を変更する。84件のmatchedと停止例を知った後の変更であり、最初の88実行より前に登録した変更とは称さない。既存のprediction・lock・選択・変換・seed・実行順序・予算・正解の定義・A/Tの閾値は変更しない。以後の扱いは、問題ID・mode・seed・正答率に依存しない一般規則としてここで固定する。

凍結solverの `src/`、engine lock、依存lock、Q19等の既存結果は変更しない。過去の環境不備による旧4件を「無効実行」として保存した既存の決定も変更しない。今回のworker成果物なしを、その環境不備と同一視して無効化しない。

## 採点器の最小修正と84件の照合

変更箇所は `benchmarks/research_runner.py` の `read_run_outcome` の1行だけである。

```diff
-    diagnostics = result.get("diagnostics", {})
+    diagnostics = result.get("diagnostics") or {}
```

diagnosticsが未指定または有効な辞書の既存入力では意味を変えず、null時に空辞書を使用する。答えの正規化、厳密答え集合の比較、正常終了判定、契約検査、参照答え、時間・分母の計算は変更しない。非nullの有効な辞書については同じ値を読むため、この修正に起因する採点差はない。対応していなかった不正な型一般を修復する変更ではない。

- 変更前SHA-256：`b9ddace01355d8ac4e5c0ae75f61c4543c976d46bc430e8a44203926e42f4b81`
- 変更後SHA-256：`85eae6d8c8f94b73ba679bfd1fd13a962147c7da219aeaf5235b1258e2750ef1`
- 保存diff：[grader-change.diff](grader-change.diff)。補助検査は凍結runnerとの差分がこの1行だけであることを強制する。

[rescore_completed.py](rescore_completed.py) でbatch 0〜20のcampaignを一時ディレクトリへコピーし、修正版の **`assess_campaign` 全体**を呼んだ。答え比較の独自実装や既存matchedの転記で代用していない。元のassessmentとrawは上書きせず、新しいassessmentのみを追補内へ保存した。

結果は **84/84件で全フィールド一致、差分0件**。21個すべての `assessment.jsonl` が元ファイルとバイト単位で一致した。matchedだけでなく、expected/actual、status、failure_stage、wall/CPU、counters等も一致している。[結果JSON](rescore-84/result.json)、[84行の照合表](rescore-84/comparison-84.csv)、[再採点assessment](rescore-84/assessments/)、[元の308ファイルのhash](rescore-84/preserved-inputs.json)。元の308ファイルは前後で不変だった。この実測の対象は84件であり、Q19等を再採点したとは主張しない。それらの保存結果は変更していない。

別途、実データを使わない [check_null_contract.py](check_null_contract.py) で、null・空辞書・diagnostics省略時のoutcomeが同じになることと、正常成功1件＋成果物なし1件の合成campaignが `assessed_count=2 / matched_count=1 / match_rate=0.5` になることを確認した。[合成検査結果](null-contract-check.json)。これはbatch 21の採点ではない。再採点と合成検査はsolver入口と子プロセス起動を禁止したプロセス内で行い、solver呼出し0回だった。

## workerが成果物を残さなかった全ケースに適用する規則

1. 保存run JSONの `solver_result.error.code == "artifact_missing"` をworker成果物なしの観測指標とする。凍結EngineRunnerは、worker終了後に成果物ファイルが無いときにこのcodeを出す。mode、ID、seedやdiagnosticsがnullか否かで対象を選ばない。diagnosticsのnull件数も別途記録するが、**nullだけでworker成果物なしと推測しない**。外側run JSON自体の欠落も別に表示する。
2. worker成果物なしは **答えなし＝不正解** として扱い、元の計画セルを分母から除外しない。修正版の既存採点経路で `normal_completion=false`、`matched=false`、`failure_stage=runtime` となる。失敗の原因が数学・資源・実装のどれかは、この分類だけでは同定しない。独自の正解判定は追加しない。
3. 各問題・各modeの正答率は従来どおり `matchedの和 / 3`、各modeは120実行、全体は840実行、A/Tの主分母は40問のままとする。失敗試行の置換・seed追加・問題除外・成功するまでの再試行はしない。原本反復も同じ規則に従う。
4. Tの比較は従来どおり両方matchedの対応seedだけとし、worker成果物なしの短い終了時間を「速い正答」として比較しない。副指標の失敗時費用は180。CPU、RSS、phase timings、countersの欠測は計測値0の証拠ではなく、欠測として説明する。
5. batch 21の4件の採点は別タスクの許可まで行わない。追補時点では4件とも未採点のままで、成果物なし1件についてもassessmentを捏造しない。未実行752件も不正解に置き換えない。完遂前に全840件の正答率やA/40・T/40を確定値として報告しない。
6. 外側runの欠落、manifest不一致、契約検査違反、run/assess/summarize自体の失敗は引き続き停止・記録の対象とする。nullを空辞書にすることを、他の例外を隠す包括的な回避策にしない。

## 版別の報告形式と集計

[aggregate_missing_artifacts.py](aggregate_missing_artifacts.py) は保存rawと既存assessmentだけを読み、solverも採点器も呼ばない。840セルを維持した `per-run.csv` と、original / original_repeat / point_names / variable_order / condition_order / orders_combined / combined の7行の `per-mode.csv` を出力する。

`per-mode.csv` は、`planned_denominator`、`raw_received`、`assessed_denominator`、`matched`、`incorrect`、`unassessed_raw`、`raw_not_available` に加え、**`worker_artifact_missing`**、`worker_artifact_missing_assessed_incorrect`、`worker_artifact_missing_unassessed`、`diagnostics_null` を独立した列にする。成果物なしで採点済みの行がmatchedになっていれば集計をエラーにする。`assessed_denominator` はその失敗を含む。`match_rate_all_120` は各modeの120件すべてが採点済みになるまで空欄とし、部分集計の率と区別する。

今回保存した [版別表](stage1-mode-counts/per-mode.csv) は次のとおり。これは採点前のworker異常の観測件数であり、batch 21の正誤判定ではない。

| 版 | 固定分母 | raw保存 | 採点済み | 未採点raw | worker成果物なし |
|---|---:|---:|---:|---:|---:|
| original | 120 | 12 | 12 | 0 | 0 |
| original_repeat | 120 | 16 | 12 | 4 | 1 |
| point_names | 120 | 12 | 12 | 0 | 0 |
| variable_order | 120 | 12 | 12 | 0 | 0 |
| condition_order | 120 | 12 | 12 | 0 | 0 |
| orders_combined | 120 | 12 | 12 | 0 | 0 |
| combined | 120 | 12 | 12 | 0 | 0 |

**版間の偏りがあれば、それ自体を結果として報告する。** 偏りのある版や試行を除いて正答率を改善したり、再実行で置き換えたりしない。完了時には件数と各120試行に対する割合、原本・原本反復との差を示す。現在の部分実行では版ごとの観測数が12/16と異なるため、観測分母と未実行数も併記する。この1件だけで版の因果効果や統計的な偏りを確定しない。

将来の集計コマンド（`<new-report-dir>` は新しい出力先）：

```sh
/tmp/q38-58e3993-venv/bin/python -B \
  jssa/difficulty/relabel-invariance/amendment-null-diagnostics/aggregate_missing_artifacts.py \
  --output <new-report-dir>
```

batch 21の回復採点を別ディレクトリへ保存した場合は `--assessment-root <recovered-assessment-root>` を指定する。その下の元campaign名の `assessment.jsonl` を読む。既存assessmentがあるセルについては、別ディレクトリのassessmentがバイト一致しない限り上書き相当の集計を拒否する。今回の部分表は保存したまま、新しい報告先を使う。

## batch 21の一律の処置：既存4件を採点だけする

**再開後、batch 21の保存済み4件を修正版で採点・要約する。solverは再実行しない。** 4件すべてに同じ処置を適用する。4件のIDは固定計画どおり `aime-2000-1-2`、`AIME-2012-II-15`、`HMMT-2017-FEB-GEO-05`、`HMMT-2022-FEB-GEO-03`、modeは `original_repeat`、seedは `380101`。原本run、manifest、停止receipt、失敗ログ、当時のSHA256SUMSは保存する。

選択規則は「固定セルを既に実行し、参照・問題・source・資源の契約を確認できる外側run JSONが揃っており、採点だけが失敗したbatchは、保存runから採点を完了する」である。返却された答えや正答率は選択条件に含めない。今回4件には外側runの欠落がなく、worker成果物なしも保存された実行結果である。workerの読込先を観測できないことだけを理由に、その1件を環境不備の無効実行に変更しない。

batch 21から4件を再実行する案は採用しない。既に消費した固定seedの試行を新しい試行で置き換え、観測された成果物なしを主分母から取り除く機会を作るため、固定840実行・追加再試行なしの趣旨に劣る。全4件一括の再実行でもこの問題は残る。採点だけの回復なら試行数も元の実行順も変わらない。

別タスクでは4件のcampaignを新しい回復採点用ディレクトリへコピーし、hash一致を確認してから、ここで固定した修正版 `assess_campaign` と `summarize_campaign` をこの順で呼ぶ。入力casesは凍結checkout内の固定ファイルを使う。元の停止receiptを「最初から成功した」記録へ書き換えず、回復採点のUTC・採点器hash・入力hash・出力hash・solver呼出し0回を別receiptへ追記する。

その採点・要約と検証が成功した後の新規solver実行は **batch 22から209まで、元の順序の752件だけ**とする。現行 `stage2.py` / `launch_batch.py` はbatch 21の停止receiptを見て継続を拒否するため、そのまま再実行したり、receiptを削除して回避したりしない。回復receiptを確認する再開側の接続は、明示的に許可された別タスクで行う。今回は起動コードを変更・起動しない。

## 再開直前に必ず実施するsolver呼出し0回の検査

実行用checkoutは引き続き `/tmp/q38-58e3993-clean`、commitは `58e399315f259699e99cc1b190aa46c78d573e5a`。その `src/`、実行runner、コーパス、依存lockは凍結commit `60db4b679b04167175c51c479c87c22fa663fda0` のままにする。**修正版採点器は追補を承認したcheckoutから明示的に読み込み、凍結実行checkoutのrunnerを編集しない。** 実行用のdirty検査やimport先検査を緩めず、`--allow-dirty` も使わない。修正版を `support.load_grader()` で絶対パスから読み込む場合も、1行差分を検査し、答えの型・厳密表現は凍結 `src/` を使う。

Claudeによるcommit・push確認と別タスクの実行許可をreceiptに記録した後、**batch 21の回復採点と残りの実行を開始する直前に**、承認された追補checkoutから次を実行する。`<UTC>` は新しい保存名であり、過去の検査結果を再利用しない。

```sh
prlimit --fsize=4900000:4900000 -- \
  /tmp/q38-58e3993-venv/bin/python -B \
  jssa/difficulty/relabel-invariance/amendment-null-diagnostics/check_before_resume.py \
  --output /tmp/q38-null-diagnostics-preflight-<UTC>.json
```

[check_before_resume.py](check_before_resume.py) は次をすべて確認し、不一致なら停止する。

1. 追補lockと固定ファイルのSHA-256、採点器の厳密な1行差分、元prediction lockの261ファイル・200変換の一致。
2. 実行checkoutのcommitとclean状態、凍結src・runner・コーパス・依存lockとsource manifestの一致。
3. 固定環境変数（相対 `PYTHONPATH=src`、1thread等）と修復済みvenvを使い、checkoutをcwdとした親相当プロセス、および新しい一時ディレクトリをcwdとした子相当プロセスを独立に起動する。sys.pathを補正して検査を通すことはしない。
4. 両方の `geosolver.__file__` が `/tmp/q38-58e3993-clean/src/geosolver/__init__.py`、読込済みgeosolver各モジュールも同src配下であること。両方のsource_hashが **`sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5`** と一致し、engine lock・runtime dependency fingerprintも一致すること。
5. 保存済み308ファイルのhashが不変、rawは88件、完備採点84件、batch 21の4件がまだ未採点であること。solver入口の呼出しと、probe内での子プロセス起動を禁止し、solver呼出し0回を記録する。

今回も `--before-seal` を付けた段階1用の同検査を行い、すべて通過した。[今回のimport検査](preflight-stage1.json)。これはlock作成前の証拠であり、**再開直前の再検査では `--before-seal` を使わず、追補lockの検証も必須**にする。検査を通過しても、それ自体が実行許可にはならない。両cwdでのimport-only検査であり、実workerを起動した検証とは称さない。過去に成果物を残さなかったworkerの実import先は依然として観測不能である。

## 保存物とlock

このディレクトリのコード・diff・84件の再採点証拠・合成検査・版別表・import検査・[段階1監査](stage1-verification.json)、修正版採点器、answer.mdの追補要約をSHA-256で固定する。[fixed-files.sha256](fixed-files.sha256) はrepository root相対のhash一覧、[prediction-supplement.lock.json](prediction-supplement.lock.json) は本文SHA-256、ファイルmanifestのSHA-256、**UTC登録時刻**、元lockとの対応を含む。自己参照を避けるためlock自体のhashは内包しない。commit・push確認時はlockのhashも別途記録する。

本追補の作成で段階1を終了する。今回のsolver実行は0回、batch 21の採点も0回、残り752件の再開も0件である。
