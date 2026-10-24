# S8 superPC FSIZE障害の確認・修正・再実行準備

本計測は起動していない。solver実行は原因確認のqueue 578の1件のみ（foreground）。正誤・answer・独立参照との比較は行っていない。外部ネットワーク、commit/pushなし。既存S8ファイル・rawはすべて保存。

## 原因確認

対象: queue 578 / HMMT-2015-FEB-GUTS-24 / seed 601 / C1 / CPU 1。元start receiptと選択環境変数、CLI引数、180秒、1コア、CPU固定を照合。メモリ4096MiB、address space 16384MiBも同じ。変更はRLIMIT_FSIZEを2,900,000から1,073,741,824バイト（soft/hard）へ拡大したこと。観測対象の親・worker・子の /proc/limits でも1GiBを確認。

結果はexit 0、outer completed、errorなし、JSON構文有効、resource violationなし。経過8.447秒。worker artifactは4,173,913バイト、最終raw result.jsonは6,830,539バイト。旧上限2,900,000を超えるworker artifactが保存でき、元のartifact_missingが消えた。この代表1枠ではFSIZEによるartifact書込み失敗を確認した。残る88枠について個別の追試はしていない。通常の結果は本計測・報告・320枠の置換に使わず、再実行計画にはqueue 578も残す。

新workerのstderr末尾（例外なし）:

```text
could not apply the optional Linux address-space limit
Warning: it is currently not recommended to activate QUAD_MODEL_SEARCH or QUAD_MODEL_SEARCH_SIMPLE_MADS with DiscoMads as it may be much slower.
```

最初の警告はworkerが既存の16GiB hard limitより大きな任意AS limitを設定できなかったもの。親から継承したAS上限は維持。原計測のouter stderrファイルは存在せず、EngineRunnerはartifact_missing時にworker stderrを外へ返す前にTemporaryDirectoryを破棄するため、元の例外末尾は取得不能。新実行でworker stderrを外側から観測して記録した。証拠は `diagnostic-0578/cause-only.json`, `stderr-tail.txt`, start/end receipt、`cause-code-hashes.json`。生rawは `/tmp/mechanism-S8-fsize-diagnostic-0578/`（リポジトリ外、約7MB）。

## 元320枠の構成別×原因別

| 構成 | exit 1：FSIZE切断 | exit 2：FSIZE疑い※ | 時間切れ | 合計 |
|---|---:|---:|---:|---:|
| N | 44 | 14 | 0 | 58 |
| C1 | 29 | 12 | 0 | 41 |
| C2 | 44 | 15 | 0 | 59 |
| C3 | 29 | 12 | 0 | 41 |
| C4 | 29 | 12 | 0 | 41 |
| C5 | 28 | 12 | 0 | 40 |
| BASE | 28 | 12 | 0 | 40 |
| 合計 | 231 | 89 | 0 | 320 |

※89枠すべて8問の `artifact_missing / worker exited with code 1 without an artifact`。うちqueue 578の1枠は代表確認済み、88枠は同一機序の疑いのまま。表は元の原因区分を保持する。231枠すべてresult.jsonのサイズが2,900,000バイトでJSON不正であることを直接確認した。320枠内に時間切れはない。時間切れその他の元793枠は再実行対象にしない。

`slot-cause-evidence.json` は320枠の元receipt/resultのhash、サイズ、原因区分。`invalidated-slots.json` はこの320枠を `interrupted_driver_fsize`, ok/C=nullとして扱う非破壊の無効化記録。元CSVは証拠として維持し、そこにある旧nonzero_exitの失敗費用や集計は修正版の判定に流用しない。

## 修正版

S8直下のdriver一式を `../rerun-driver/` にコピー。旧S8ファイルは変更していない。launcherのFSIZEを1GiBへ変更し、runtime終了時の「rawが3MB以上なら例外」を削除。rawはrepo外。`measurement_common.save` と元集計処理の3MB未満制限は維持。参照・exact採点・grade・負荷照合reportのコードは元とバイト一致。

`--slots-file ../run-plan-rerun.json` を拡張。元per-run.csvのreason=nonzero_exitの320枠だけを、元queue順・同じcase_id/seed/configuration/DSL hash/180秒/1コアで計画化した。計画は元CSV/freezeのhashと全job記述を照合し、追加・欠落・順序変更・seed変更を拒否。凍結ソース・Python・入力・依存lock・参照・メモリ契約も元と同じであることを開始前に照合する。

supervisorはforegroundでdriverを待ち、再起動時はfreezeの有無に応じてrun/resumeを選択。完了済み・開始済み枠は再実行せず、未開始枠だけを継続する。異常終了時は当該raw-rootを明示しているsolver木だけを回収する。保存空きが6GiBを下回ると新規枠を始めない。並列上限は8、各枠1CPUへ固定。resumeで並列数を増やせない。

完了後のgradeは320枠だけを直接集計しない。元1113枠のreceiptを別の `run-superpc-rerun/merged/` に合成し、320枠だけ新receiptへ置換して、元と同じgrade/reportを実行する。新receiptがない対象枠はok/C=nullの中断にし、旧失敗へfallbackしない。`replacement-map.json` に全置換元/hashを保存する。元の53問×7構成×3seed、解けた基準・費用・負荷制約は維持し、時間効果の最終支持は引き続き保留する。

## 起動（ユーザーが行う。ここでは実行していない）

リポジトリルートで:

```bash
bash jssa/difficulty/mechanism-1024/stage/S8/rerun-driver/run-superpc-rerun.sh
```

スクリプトの実体は次のsupervisorコマンド。nohupや末尾&を使わずforegroundで実行する。同じコマンドがresumeになる。

```bash
/home/kabatan/work/solver/.venv/bin/python -B \
  jssa/difficulty/mechanism-1024/stage/S8/rerun-driver/supervise_superpc.py \
  --slots-file jssa/difficulty/mechanism-1024/stage/S8/run-plan-rerun.json \
  --max-parallel 8 \
  --output jssa/difficulty/mechanism-1024/stage/S8/run-superpc-rerun/ \
  --raw-root /tmp/mechanism-S8-rerun-raw \
  --base-src /tmp/mechanism-7b-lkdjle5l/final \
  --repo-root "$PWD" \
  --python /home/kabatan/work/solver/.venv/bin/python
```

本計測の `run-superpc-rerun/measurement-freeze.json`、receipts、`/tmp/mechanism-S8-rerun-raw` は今回作っていない。完了の確認先は `run-superpc-rerun/supervisor-status.json`（state=complete）、320 end receipt、`merged/replacement-map.json` と `merged/answer.md`。単発診断の終了をcampaign完了と混同しない。

## 検証と保存物

S8: 模擬9件成功、solver呼出し0、最大並列2。FIFO/CPU固定/timeout/木回収/完了枠非再実行/start-only枠中断/未開始resume、supervisorのrun異常終了→resume、320枠完全一致、FSIZEの親子継承、3MB超rawと3MB集計拒否を検査。`contract-test.log` と修正版の `measurement-contract-results.json` に結果/hashを保存。`preflight.json` はsolver呼出し0でソース・入力・依存lock/Pythonと320枠の事前照合が成功した記録。

S10部分B: `measurement_launch-original.py` を保存し同じ1GiB修正、rawの3MB例外も解除。模擬11件成功・最大並列2・solver呼出し0。変更前ファイルとhash、差分、変更後hashを `../../S10/run-b/fsize-fix-history/` に保存し、`artifact-hashes.json` を更新。既存 `output/` とその旧freezeは変更していない。旧freezeに対する修正版resumeはhash不一致となるため、そのfreezeを書換えて継続しない。今回S10の停止・再開・再実行はしていない。

S8差分: `S8-driver-changes.patch` と `S8-driver-change-hashes.json`。全元ファイルhash: `original-S8-hashes.json`。最終照合: `verification.json`。現行driver/成果物hash: `final-hashes.json`。コピー先に含まれる旧 `measurement-driver-hashes*.json` / `SHA256SUMS` はコピー元の履歴であり、修正版には `final-hashes.json` と現行の契約結果hashを使用する。
