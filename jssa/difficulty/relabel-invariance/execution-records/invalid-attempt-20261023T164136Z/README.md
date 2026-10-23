Q38の段階2は、最初のbatchにおける `executed_import_root_mismatch` により停止した。**無効4実行・未実行836実行。主比較は未完。** 結論と停止理由は [answer.md](answer.md)。予測・変換・選択・計画は固定のままである。

| ファイル | 内容 |
|---|---|
| results-summary.json | 全体の状態、開始・停止UTC、CPU・load、rawの所在・サイズ・ハッシュ |
| runs.csv | 計画された840セル全部。空のmatchedは欠測 |
| per-problem.csv / per-stratum.csv | 固定40問・8層の実行状況。A/Tは算出不能 |
| invalid-run-diagnostics.json | 4無効実行の答え（未採点）、counters、時間、候補採用元などの要約 |
| execution-records/ | preflight・開始・停止・起動ログの小さな記録 |
| import-diagnostic.json | solverを実行しないimport先の再現診断 |
| verification.json | ハッシュ・件数・記録・ファイル上限の最終検査 |

元の生データは `/tmp/q38-58e3993-execution/campaigns/b00-s380101-point_names/runs/` にある。旧担当の未実行起動記録は `/tmp/q38-58e3993-launch-unstarted-20261023T162327Z/` に保存している。いずれもリポジトリへコピーしていない。

再集計だけを行う場合は、この作業木のルートから次を実行する。上記の一時ファイルと実行用checkout、既存Python環境が必要。solver呼出しは0回であり、予定セルの未実行を失敗に変換しない。

```sh
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/relabel-invariance/report_stopped.py
```

`stage2.py start` や `launch_batch.py` を使った再試行・次batchの実行は今回の停止後には行っていない。環境修正後の再実行方針を別途確定するまで、これらを再開コマンドと扱わない。
