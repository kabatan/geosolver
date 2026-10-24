# S10 事前登録17・部分B 本計測の準備

**準備のみ完了。本計測・solver・新しい参照の計算は実行していない。** commit/push・外部ネットワーク取得なし。S8のrun-superpc / run-winpc / run-superpc-aborted-attempt1の中身は開かず、S8の準備用ソースのみをコピーした。S8の既存ファイルは変更していない。

`../preregistration-17.md` の「部分Bの固定」を実装した。a14・b14・c14・e14・失敗なし8、64問×4構成×3seed = **768枠**。seed 701–703、内外180秒、各枠1CPUへ固定、内部4種のthread環境変数を1とする。基準はrun-7b / S8と同じ。

## 固定した問題・順序

`select_problems.py` がQ15 `false-attractors/per-problem.csv` の `main_cause` を使い、群内の `SHA256(UTF-8("S10B|"+case_id))` の16進文字列昇順で選ぶ。改行・caseの正規化なし。同値ならcase_id順。群の順序はa,b,c,e,no_failure。結果は `assignment.json` と `selected-problems.csv`、元ファイルhashは `selection-hashes.json` に保存した。

開発群は `benchmarks/cases.jsonl` の323問。Q15の分類CSVは変数あり292問（a110,b16,c19,e87,no_failure55,unknown4,d1）で、変数なし31問は含まれない。Q15事前登録に従い、主因が記録されている指定5群から選ぶ。unknown/dや分類のない31問に主因を補わない。各群とも必要数があり、不足による全件選択はない。

固定FIFOは問題順→seed順→4構成の循環順。循環offsetは `(問題の0開始rank + seed - 701) % 4`（S8の12構成ローテーションを4構成へ変更）。各構成・各seedに64枠。`run-plan.json` は準備物のため `execution_authorized:false` を保持し、自動実行しない。以下の明示的な起動コマンドでのみ実行する。

## ソースと4構成

確認済みソースは `/tmp/mechanism-S10-zqtyfenw/final`。

`source_hash = sha256:2cb435fc35950aafaf6bb2e3a40df30a7415c9fdc65d3ff4b8d969c361ecac75`

253通常ファイルの生バイトhashをswitchesの記録と照合し、`source_tree_hash()` と `verify_engine_lock()` も確認した。`source-hashes.json`、`preflight-preparation.json` に記録。driverは各起動前・再開時・終了後にソース、入力、依存lockを再照合する。BASE1を直接使うとhash不一致で拒否する。

| 構成 | 正確な環境変数集合 | 読み込む実装 |
|---|---|---|
| B0 | 空集合 | S10 patch版の既定挙動 |
| B046 | `GEOSOLVER_ABLATE_NO_NOMAD_GUARD_PENALTY=1` | S10 patch版のみ。BASE1では無効 |
| B056 | `GEOSOLVER_ABLATE_NO_SEARCH_BOX_INFERENCE=1` | S10 patch版のみ。switches/configs.jsonのB005_006と同一 |
| BMADS | `SEARCH_MODE=mads` | このdriverの `s10_worker.py` adapterが消費 |

`configs.json` はswitches/configs.jsonのB0/B046/B005_006から集合をコピー。BMADS以外ではSEARCH_MODEは未設定。各枠で継承した全GEOSOLVER_*、SEARCH_MODE、PYTHON*と前の枠のtokenを除去し、当該構成だけを適用する。PYTHONPATHはrun-bと指定ソースsrcだけ、PYTHONDONTWRITEBYTECODE=1を設定。OMP_NUM_THREADS / OPENBLAS_NUM_THREADS / MKL_NUM_THREADS / NUMEXPR_NUM_THREADS は1。

### BMADSの環境変数に関する実装上の注意

S8/groups-env.mdが明記する通り、**BASE1にも指定hashのS10 patch版にも `GEOSOLVER_ABLATE_SEARCH_MODE` を読む実装はない**。`SEARCH_MODE` 自体もソースに環境変数readerがない。従って環境変数を置くだけではBMADSにならない。

ソースを変更せず、全4構成共通の `solver_entry.py` が標準EngineRunnerにdriver側worker `s10_worker` を指定する。BMADSのworkerだけ、そのモジュールが参照するconfig factoryをbridgeし、既存 `ExternalPipelineConfig.production_baseline_tier(..., global_search_mode="mads")` を呼ぶ。この既存APIはBASE1とS10版の両方に存在する。global_search_modeとprimaryのBaselineSearchPolicyの**両方**をmadsにする。第2探索のhybrid fallback、救済の既定mads、その他の設定、最終検証は既存のまま。M045単独スイッチは使わない。B0/B046/B056は同じworker adapterを通り、設定factoryを置換しない。

変更はworkerモジュールの局所参照だけで、ソースファイルや本来の設定class、integrityの既定resolved_config_hashは変えない。source_hashは上記のまま。介入の識別には環境receiptと凍結したdriver/adapter hashを併せて使う。configのみのpreflightでprimary=mads、元class=disco_mads、engine lock不変を確認済み。**native solverでの試走は行っていない。**

指定ソースが将来消えた場合は `../switches/design.md` の再構成手順を使う。BASE1 `/tmp/mechanism-7b-lkdjle5l/final`（sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3）を新しい `/tmp/mechanism-S10-<乱数>/final` にコピーし、そのルートで `git apply --check <switches絶対パス>/switch-b.patch` → `git apply <同patch>`。元BASE1は変更しない。全253ファイル、生バイトhash、source_tree_hash、engine lockを本driverのverify-planで確認する。`--base-src`で再構成先を明示する。ネットワーク取得や新たなpatch調整は不要。

## 独立参照と採点

`references.json` と `references-hashes.json` を本計測前に固定。**64問すべて採点可能、採点不能0問、一覧は空**（`ungradable-references.json` / `.md`）。出典ごとのファイルhash、field/行番号、既存表記、正規化した集合、各集合hashを保存。新しい幾何参照の計算・solver出力の参照への転用はしていない。

`freeze_measurement_references.py` はS6の既存canonical集合、run-7b（S4.6系列）のexpected_keys、S3/S1の既存manifestの参照式、および `benchmarks/cases.jsonl` の独立公式・source-audit済みanswer集合を照合する。legacy corpus行のverified既定値は `benchmarks/research_runner.py:_load_cases` と同じ。現在のDSLとの対応とhashを固定し、入力hashが異なる旧manifestは候補から外す。小数近似だけの値は正確な有理数へ読み替えず除外。参照式の表記正規化・既存値のexact descriptorへの正規化だけを行う。調査対象と棄却理由も保存し、集合の競合があれば採点不能にする。

独立採点はS8からコピーした `measurement_exact.py` と `grade_one` を使い、正のprimitive最小多項式と昇順実根index（πのアフィン式は係数・定数それぞれ）で集合を比較する。近似許容誤差や部分一致は使わない。解けた=3seed中2回以上で独立参照集合と完全一致。seed費用Cは正解なら起動直前から所有プロセス木回収までの実時間、失敗/timeoutなら180秒。問題のCは3seed平均、群のCは問題平均。中断・参照なしはok/solved/Cをnullにし、失敗や180秒へ置換しない。B046/B056/BMADSそれぞれの群別C−B0、K1–K3、探索的K4をgradeで出力し、負の効果もそのまま残す。

将来、参照のない問題が追加された場合も、新しい参照を本計測の中で計算しない。まずDSL/hashを照合し、既存の独立公式記録・完全解集合の証明を探す。見つからなければ測定前の別作業として独立な導出と全枝の完全性確認（必要なら凍結版最終検証）を実施し、参照式/descriptor・導出根拠・DSL hashを別成果物へ固定し、参照freezeと契約テストを更新する。この準備ではその計算は実行しない。未解決なら全枠を保持したまま「採点不能」として報告し、都合よく除外・正解扱いしない。

## 契約テストとS8からの流用

`driver.py, measurement_*.py, supervise_superpc.py` はS8準備物からコピーし、S10に適応した。S8元ソースのhashは `s8-reuse-hashes.json`。runtimeのFIFO、receipt、affinity、timeout、process-tree cleanup、メモリ/ストレージ監視、rawの2MB分割は継承。新しい部分は問題/構成/パス/seed、BMADS bridge、群別採点、および引数化したsupervisor。`measurement_common.py, measurement_launch.py, measurement_exact.py` はS8とバイト一致。

`test_measurement_contract.py` は軽量な模擬サブプロセスのみ。並列枠最大2（timeoutの模擬子プロセスも親と合わせ2）。固定順、回転/alias、環境汚染除去、CPU/thread環境、timeoutと子の回収、完了枠の非再実行、startのみの中断枠の非再試行、未開始枠のresume、ログ分割、保存容量不足時停止、完全一致採点/C/多数決、BMADS bridge、detachした模擬driverの異常終了→親によるresume、当該campaignの孤児だけを回収することを検査。結果とtested_files_sha256を `measurement-contract-results.json`、実行ログを `contract-test.log` に保存。`artifact-hashes.json` が最終準備物hashを固定。

## 起動コマンド（今回は実行していない）

リポジトリルートで実行する。Pythonは依存lockに一致する3.12環境を指定する。以下の `--max-parallel 16` は目安。**他プロジェクトの負荷が続くなら8や4へ減らす**。選べる上限は利用可能な異なる物理コア数であり、各枠は常に1コア。raw-rootはリポジトリ外の新しい空ディレクトリを指定する。空きが6GiBを下回ると新規枠を開始しない。

```bash
PY=/home/kabatan/work/solver/.venv/bin/python
RUN_B=jssa/difficulty/mechanism-1024/stage/S10/run-b
mkdir -p "$RUN_B/output"
nohup "$PY" -B "$RUN_B/supervise_superpc.py" \
  --max-parallel 16 \
  --raw-root /tmp/mechanism-S10B-raw \
  --output "$RUN_B/output" \
  --base-src /tmp/mechanism-S10-zqtyfenw/final \
  --python "$PY" \
  > "$RUN_B/output/supervisor.log" 2>&1 < /dev/null &
```

supervisorがdetachしたdriverを保持し、予期しないdriver終了時はその出力先のtokenを持つ残存子だけを回収してresumeする。既にstartがある枠は `interrupted_prior_start_no_retry` として閉じ、再試行しない。未開始枠のみ続行する。supervisor自体が止まった場合も、同じoutput/raw-rootで同じコマンドを再起動できる。supervisor/driverそれぞれのflockで二重起動を拒否。完了後は自動で独立採点する。途中データはoutputのreceipts/progress、raw本体はraw-root。元のS8出力先を使わない。

起動時の並列上限をfreezeし、再開ではそれを超えて増やせない。下げることは可能。同じraw-root、ソース、Python、同じhost、同じ入力/driver hashを要求する。中断を含むcampaignの結果は未確定数を保持する。監視・保存容量停止は `supervisor-status.json` を確認する。

solverを呼ばずに事前照合だけする場合：

```bash
"$PY" -B "$RUN_B/driver.py" verify-plan \
  --base-src /tmp/mechanism-S10-zqtyfenw/final
```

模擬契約テストの再検証（本計測を始める前だけ。契約結果ファイルを更新する）：

```bash
"$PY" -B "$RUN_B/test_measurement_contract.py"
```

driverを直接使う場合は `run` または `resume` に同じ `--max-parallel`, `--raw-root`, `--output`, `--base-src`, `--python` を渡す。親による孤児回収と継続のため、通常は上記supervisorを使う。独立採点だけは `driver.py grade --output "$RUN_B/output"`。ここに掲載した本計測コマンドは、今回の準備では一切起動していない。
