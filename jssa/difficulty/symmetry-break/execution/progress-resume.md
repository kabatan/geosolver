更新 UTC 2026-10-24T06:18:03.429768+00:00 / 状態: complete / 工程: complete

| 工程 | 結果あり | 開始済み・工程結果なし |
|---|---:|---:|
| local | 752/752 | 0 |
| full | 534/534 | 0 |
| verify | 534/534 | 0 |
| scaling | 38/38 | 0 |
| jacobian | 793/793 | 0 |

2026-10-24の再監査では局所752/752ブロック（35,600試行）、完成solver500/534件が完了。
完成0500・0501の2試行は開始済み・結果なしで、中断失敗（T=180秒）として保持し再実行しない。
未着手32件だけを追加実行。完了済み試行の再実行、seed追加、予算延長はしない。
同時実験は最大2、BLAS/OMP各1スレッド。元の採点器・実装・段階1の封印を維持。

`ps`で確認できたPID名前空間内に旧実験プロセスなし。`batch.lock`は排他取得できたため、
保持プロセスなしと確認し、同じファイルを残して使用する。他タスクのプロセスには触れない。
`setsid nohup`で端末・標準入出力を切り離した。通常のバックグラウンド起動だけでは
コマンド終了時にsandboxのPID名前空間が消えるため、実行セッションの親を待機させて保持。
アプリ全体停止後の生存はこの環境では保証できない。

順序: local → full → verify（未処理候補のみ反復）→ J prepare → scaling → jacobian → analyze → audit。
再監査: [resume-20261024b.json](resume-20261024b.json)。
制御ログ: `/tmp/q41-stage2-resume-b.log`。状態: [resume-controller.json](resume-controller.json)。


最終結果: P1〜P4はすべて外れ。中断失敗2件・再試行0件。Jは645/793点を測定、148点はNA。
最終監査は[final-audit.json](final-audit.json)で通過（エラー0）。[結果](../answer.md)。
生記録14,079ファイル（2,160,053,588 bytes）は外部に保存し、[raw-manifest.json](../raw-manifest.json)にhashを記録。
