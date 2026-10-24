# 本計測driver案（未実行）

今回の許可は準備と24回のsmokeのみ。本計測3816回は実行していない。`driver.py` は `verify-plan` のみ実装し、実行コマンドを持たない。以下は、今後本計測を行う場合に実装する設計である。S5/S6の独立プロセス・CPU固定・受領証・独立採点の設計を流用する。

入力は configs.json / assignment.json / run-plan.json / source-hashes.json。106問×3 seed×12構成=3816枠、各PCは53問×36=1908枠。同じ問題の全seed・全構成はassignmentのPCに限定。順序はsha256順位→seed 601,602,603→12構成を `(sha256_rank + seed - 601) % 12` 左回転。N+1はC1へのaliasで追加枠を作らない。

実行前に全固定ファイル・DSL・BASE1ソース・engine/dependency lock・Python binary/依存版を照合し、OS/WSL/kernel、CPU model、affinity、ホスト名、負荷、内部thread環境を実行受領証へ保存する。今回のsmoke用profileは本計測では使用しない。2台の実測時間は機種差を含むため、比較は同じ問題・seed・PC内の構成間を基本とする。

実行キューはmachineでfilterした既存順FIFO。最大6並列、6個の異なる利用可能CPUを1つずつ貸し出し、各プロセス木を1コアに固定。環境は継承GEOSOLVER_*を全て除去し、configsの8変数とthread_environmentを適用。PYTHONPATHは指定BASE1/srcのみ。OPENBLAS等の内部thread=1。memory limitは同じ値を両機で明示固定し、子孫を含むRSS/affinity/threadと実環境を監視する（S6/run/driver.pyのJob.sample相当）。

1枠ごとに新しいCLI/EngineRunner→worker→symbolic workerを起動。CLIの予定形は次のとおり。ここには現在実行可能な一括runエントリーポイントを実装していない。

```text
taskset -c CPU PYTHON -B -m geosolver.application.cli solve DSL_PATH
  --time-limit-seconds 180 --cores 1 --seed SEED --output UNIQUE_RAW/result.json
```

180秒の外側wall deadlineも持ち、到達時は当該枠の所有プロセス木だけ終了する。workerの内部reserveやPSLQ/検証設定はBASE1既定のまま。準備のsmokeはEngineRunnerへ20秒、外側28秒だったが、本計測の外側180秒・費用定義と混用しない。起動直前時刻から所有プロセス木の終了までを実時間とし、終了/回収の遅れも生値に保存する。タイムアウト・欠測は消さない。

各枠のstart受領証を排他的作成し、plan index、問題・DSL hash、構成・8変数、seed、CPU、source hash、Python hash、コマンド、時刻を保存する。end受領証はreturncode、終了理由、wall/CPU時間、peak RSS、stdout/stderr/resultのhash、監視違反を保存する。atomic renameと排他的lockで二重起動を防ぐ。再開時は有効なend受領証付き枠だけskipし、startだけ残った枠は欠測扱いで報告し、自動再試行しない。失敗した構成を隠して止めず、問題・seed・構成の完全な分母表へ残す。

採点プロセスは求解環境と分離する。実行前に凍結した公式参照集合と正規化方法のhashを採点側に保持し、workerにはDSL以外の正答・既存結果を渡さない。今回参照答えの算出や採点は一切しない。将来の本計測では事前登録15の「3seed中2回以上で答え集合が完全一致」を問題×構成で判定する。seedごとの費用Cは完全一致なら実時間、不正解/欠測は180秒。既存smokeログを性能/正答率へ流用しない。

将来の単体契約確認は、模擬サブプロセスで順序・機械filter・再開・タイムアウト・所有木の回収・環境汚染除去を検証する。実問題を追加実行して検証しない。今回行った確認はprepare時の再構築照合、read-only preflight、24回smokeとその分岐監査のみ。
