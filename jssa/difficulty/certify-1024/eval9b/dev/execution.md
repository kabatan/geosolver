# 実行と中断時の再開

元の認証器・検算器・符号規則は変更せず、このディレクトリ内のアダプターから使う。実行前の入力・コード・Singularの記録はpre-run-hashes.json。予測・閾値・対象・成功条件は固定したまま。

起動済みの制御プロセスにはcontroller.lockの排他ロックがある。制御プロセスを重ねて起動しても計算を二重に開始しない。各問の開始はruns/<ID>.workのmkdir(exist_ok=False)で排他的に記録する。

中断後に再開が必要になった場合は、同じ作業ディレクトリから次を実行する。実行中の制御プロセスや他のタスクを停止するためのコマンドではない。

```bash
setsid nohup /tmp/q38-58e3993-venv/bin/python -B jssa/difficulty/certify-1024/eval9b/dev/run_dev_9b.py run </dev/null >>jssa/difficulty/certify-1024/eval9b/dev/controller.log 2>&1 &
wait
```

制御プロセスは別セッション・別プロセス群、標準入力/dev/null、ログ出力で起動する。この環境では起動元のコマンドがすぐ終了すると子プロセスも終了するため、起動元にはwaitを残して実行セッションを維持する。Codexとの通常のやり取りからは切り離されるが、アプリ全体・実行基盤・サンドボックス管理側の強制停止まで存続を保証しない。

supervisor_finalized=trueの結果は再実行しない。未確定の.workは「中断」として内容・ファイルhashとともにinterrupted/へ保存し、結果に数えない。その問題だけ最初から1回再実行できる。2回目の中断後の再実行は拒否する。未着手の問題はIDのsha256昇順で進める。600秒・8 GiB・1 CPU/問、並列4を維持する。

全163問の終了後に凍結済みのreport_dev_9b.pyがCSV・集計・日本語報告・終了監査を作成する。集計は保存結果だけを読み、追加の認証計算はしない。

集計後のfinal_audit.pyは保存結果だけを検査し、各CPUでの実行の非重複、C6〜C8の算術、元の非所属判定との整合性、ファイル上限・メモリ上限の根拠を確認する。認証の追加実行や結果区分の変更は行わない。資源上限の具体的な説明をanswer.mdへ追記し、supplementary-audit.jsonとartifact-hashes.jsonlを保存する。
