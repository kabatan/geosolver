# Q37 段階2の実行記録

**最終状態：凍結採点器の hash 不一致で停止。104／360件を実行、256件は未着手。開始済みの試行・監督プロセスは終了済み。正答集合の採点は実施していない。最終報告は [answer.md](answer.md)。**

ユーザーの別タスクでの明示的な実行許可を受け、`58e399315f259699e99cc1b190aa46c78d573e5a` の予測・選択・手順を保持して実行を開始した。ローカルの origin 追跡参照もこの commit を指す。commit 時刻は `2026-10-23T16:18:31Z`。push が `16:18:35Z` 前後だったことはユーザーの申告であり、リモートサーバーの時刻を独立に取得したわけではない。

`prediction.lock.json` 自体の SHA-256 は `0e4729ecb1a500bd46c2e01127f016ae23601e6b1f45d52af96ce142e88c2cbc`。lock 内の13成果物と出典 manifest 内の271ファイルの hash・bytes がすべて一致した。予測固定時の `execution_authorized: false` は歴史的な記録として変更していない。今回の許可は [preflight.json](execution/preflight.json) と [開始記録](execution/execution-start.json) に別記した。

開始時刻は **2026-10-23T16:28:46.841162Z**。全360本は [jobs.csv](jobs.csv) の順序を使用する。lane 0/1/2/3 をそれぞれ CPU **4/10/14/15** に固定し、同じ問題・seed の3予算を同じ CPU で連続して実行する。これらは socket 0 の異なる物理コアであり、SMT の相方は CPU 20/26/30/31。実行環境は32論理CPU・16物理コアを公開している。

CPU 選択では3秒×3回の使用率を測定し、affinity の設定と読み戻しができた独立物理コアから、SMT 相方を含む平均負荷の低い4コアを選んだ。選んだ CPU 番号の昇順で lane に割り当てた。先行する3回の保守的な空き判定では開始を待ったが、solver は起動していない。計画の「利用可能なコア」は affinity を設定できるコアとして扱う。共有ホストの専有予約はできず、この PID 名前空間から他のホストジョブの一覧も見えない。CPU の固定は他ジョブによる競合の排除を意味しない。

開始時の load average（1/5/15分）は **20.6362/18.3286/15.2925**。全体を30秒間隔、各試行を2秒間隔で観測する。各親・子・孫プロセスの affinity は2秒間隔で観測し、正常返却では凍結 runner 自身も worker の affinity・実行ソース・依存版を検査する。2秒未満で消える子プロセスは観測に載らないことがあるが、起動親の1 CPU affinity を継承する。負荷の偏り、SMT の競合、OS のスケジューリングは壁時計期限に影響し得るため、予算だけの因果効果として強く解釈しない。

solver と採点器は `60db4b679b04167175c51c479c87c22fa663fda0` と同一 bytes。product source hash は `sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5`。既存 Python `/home/kabatan/work/solver/.venv/bin/python` を使い、`runtime_fingerprint()` の issues は空。インストール・ネットワーク利用はない。

各試行は独立した Python 親プロセスで凍結 `research_runner` を import し、`CANONICAL_TIME_LIMIT_SECONDS` を当該予算に設定して `_run_one` を呼ぶ。公開 CLI → 本番 worker、元の T+8秒監視、プロセス終了処理を保持する。親を起動する前に `PYTHONHASHSEED=0`、`PYTHONPATH=src:作業ツリー`、OMP/OPENBLAS/MKL/NUMEXPR の各スレッド数1を設定する。他実験の環境変数・sitecustomize・worker hook は使わない。

保存前に JSON bytes が **4,900,000未満**であることを確認して元の保存関数へ渡す薄い guard を親側に置いた。solver の出力や候補を削減する変換はしない。全プロセスに `RLIMIT_FSIZE=4,900,000` を継承し、中間ファイルも5 MBを超えない。小さな恣意的 assertion 上限は設けない。保存障害は原票の最小メタデータと例外を残し、`solver_result=null` のまま不明として集計する。期限内の通常の `no_answer_found` と記録欠落を混同せず、再試行もしない。

採点は各区画の40原票が揃った後、既存の `assess_campaign` をそのまま使用する。`matched=True` かつ正常終了だけを正答とする。欠測の元の採点ラベルは保存し、機構判定は未知セルとして N/R/V の厳密な上下限を計算する。集計コードの検査には合成した0/1/?配列だけを使い、solver の追加実行はしていない。

長い実行は非同期の監督セッションで動作し、状態確認コマンドは短く返る。[execute_stage2.py](execute_stage2.py) の SHA-256 は preflight に封じ、各試行でも照合する。実行開始済みの試行を再投入する経路はない。原票・中間ファイルは `.gitignore` で除外し、報告・集計・小さな検査記録だけを共有対象とする。

## 不明原票と記録処理の例外

AIME-2024-II-05、seed 370201 の3予算では、公開 CLI の整形済み JSON が約5.16 MBになり、ファイル上限に達した。原票には `solver_result=null` と `OSError: [Errno 27] File too large` が残った。上限を緩めず、エラー表示中にある部分的な答えを採点へ転用しない。

同問 seed 370301 の3予算では `engine_error / artifact_missing` が返り、`diagnostics=null` だった。凍結 `read_run_outcome` がこの null を扱えず、最初の1件で監督処理が新規投入を停止した。開始済みの他ジョブが終了した後、**元の原票と実行コードを保持して未着手分だけ再開**した。以後は外側の [監視処理](resume_stage2.py) が [不明の完了記録](recover_receipt.py) を補う。これは solver の再実行や採点器の変更ではない。

復元したのは、原票・開始記録・例外ログに裏付けられる最小メタデータだけ。終了側の時刻は原票ファイルの更新時刻であり、失われた worker の完了時計ではない。これらの試行の2秒ごとの負荷・プロセス監視・子CPU積算は復元できないので未記録と明示する。停止期間は全体の経過時間に含まれ、問題や予算の順番は変えていない。

全360件終了後の採点例外を分離する補助コード [assess_views.py](assess_views.py) を準備したが、採点器の hash 不一致が生じたため、この処理は実行していない。採点用の別ビュー・代替採点・N/R/V の集計結果は作っていない。固定した採点器の不一致は実行条件を緩めず停止する理由とした。
