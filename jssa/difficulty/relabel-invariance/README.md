Q38段階2は、専用Python環境でimport先を修復して固定計画を最初から実行したが、batch 21のworker異常と既存採点器の例外で停止した。**新88実行＝84件採点済み（全件matched）＋4件未採点、残り752件未実行。840実行は未完。** 結論と4基準は [answer.md](answer.md)。

旧4件は「契約違反の無効実行（環境不備、再実行して置換）」として [旧実行保存manifest](execution-records/invalid-attempt-20261023T164136Z/archive-manifest.json) に保存した。再実行は環境修復のみを理由とし、結果を見ての選択ではない。固定内容・solver・採点器・runner契約検査は無変更。

| ファイル | 内容 |
|---|---|
| execution-records/environment-repair.json | 子プロセスのimportのみの検査。solver呼出し0回 |
| execution-records/execution-start.json | 新しい開始UTCと負荷 |
| execution-records/021.json / 021.assess.log / stop-diagnostic.json | 別障害による停止と、原因を特定できない範囲 |
| results-summary.json | 件数・欠測・負荷・rawの所在とハッシュ |
| runs.csv / batches.csv | 予定840セル・210batchを全件保存 |
| pairs.csv / per-comparison.csv | 全seedの対応、正誤差、時間比と固定閾値 |
| per-problem.csv / per-stratum.csv / per-mode.csv | 40問・8層・全modeの状態と部分結果 |
| diagnostics/ / mechanism-observations.json | 保存rawから得た診断。未採点の答えは未採点のまま |
| verification.json | 固定内容・checksum・採点転記・件数・サイズの監査 |

新rawは `/tmp/q38-58e3993-repaired-execution/campaigns/`、旧無効rawは `/tmp/q38-58e3993-execution/campaigns/` にある。全件完了後の移動条件を満たしていないため、rawは外部保存先に保持した。

保存結果の再集計と監査は、この作業木のルートから以下を順番に実行する。上記の一時保存先とクリーンcheckoutが必要。いずれもsolverや採点器を呼ばず、欠測を不正解へ変えない。

```sh
/tmp/q38-58e3993-venv/bin/python -B jssa/difficulty/relabel-invariance/report_repaired.py
/tmp/q38-58e3993-venv/bin/python -B jssa/difficulty/relabel-invariance/audit_repaired.py
```

`report_stopped.py` は最初のimport先違反を報告した旧スクリプトであり、現行結果の再集計には使わない。`stage2.py` と `launch_batch.py` は停止条件を維持しており、停止後の追加実行・再試行は行っていない。
