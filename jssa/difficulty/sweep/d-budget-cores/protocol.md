# Q43d 探索実験の測定規則

2026-10-24（JST）。予測は置かず、選択・測定・採点だけを実行前に固定した。

- 凍結版は `60db4b679b04167175c51c479c87c22fa663fda0`、source_hash は `sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5`。`git diff 60db4b6 -- src` は空、import先はこの作業ツリーの `src/geosolver`。engine lockと依存関係の照合も通った。各実行前にも再照合する。
- 現在の `benchmarks/research_runner.py` に他作業の変更があるため、同コミットの内容を `git show` で読み、入力読込み・指紋・厳密答えの正規化だけに使用する。求解は凍結版の公開CLI→通常worker。solverの関数・worker・保存処理を差し替えない。
- 開発323問、凍結後作成の2026年20問を母集団とする。群名は `dev` / `postfreeze2026`。`SHA256("2026102404:<群名>:<ID>")` の昇順、同値ならID順で、各群先頭10問。成績・変数数による選別なし。選択済み20問を [selection.csv](selection.csv) に固定。失敗時も交換しない。
- 2026年群はsolver開発には未使用だが、現在は他の実験で実行済み。今回の結果を未見問題での確認とは呼ばない。探索に使った20問は以後の確認用から除く。
- 全20問で180秒×指定1/2/4/8コア×seed `430401,430501`（160本）。全20問で180秒×1コア×追加seed `430601,430701`（40本）。各群のハッシュ順位0・1の計4問に360/900秒×1コア×最初の2 seed（16本）。計216本。seedは内部の連続fallback seedと重ならないよう100刻み。
- コア順は問題ごとの `random.Random(2026102404 + i)` でシャッフル。長予算の位置を問題番号の偶奇で前後に分ける。正確な順番は [jobs.csv](jobs.csv)。問題番号 `i mod 3` の固定レーンで順次実行し、途中成功による残りの省略はしない。
- 公開 `--cores` の指定を振る。凍結版 `application/service.py:123` は実使用を1コアに固定する。実装を変更して真の8コア実行にしない。指定値と実使用値、workerのaffinityを別々に保存する。これは実コア数のスケーリング試験ではない。
- 最大3 solverジョブ、BLAS類は1スレッド。開始前3回×1秒のCPU利用率から、SMT兄弟の合計利用率が小さい別々の物理コアを3個選ぶ。以後固定し、同じ問題の比較は同じCPU。専有は保証できない。他タスクはPID名前空間で見えない場合があるため、相手のタスク名を推測しない。
- 共有機のload average・全CPUの利用率・空きメモリ・`/tmp`空きを5秒ごとに記録。workerのCPU秒、経過秒、affinityも保存し、時間差をコア指定の因果効果と即断しない。
- 各実行は別プロセス。制限T秒は凍結版で管理し、外側は既存runnerと同じT+8秒。異常終了・timeout・欠測は正答集計で失敗。原因の解釈では答え不一致と実行障害を区別する。未実行セルを成功とも無効果とも扱わない。
- 正答は公開出力の厳密答え集合と参照集合の完全一致。候補に答えがあっても公開返却に失敗すれば正答に数えない。採点用の参照値をworkerへ渡さない。
- seed数1/2/4について、(a)少なくとも1回の完全正答、(b)返却した答え集合の和集合が参照と完全一致、を別々に測る。(a)は定義上悪化しない。(b)は余分な答えが加わると悪化しうる。最初の2 seedと追加の2 seedを独立な反復として比較する。複数seedを走らせた費用は合計経過秒で、並列化による短縮とは区別する。
- 見つかった図は公開結果に保存された `accepted` 候補の座標から比較する。図の全解を回収したという意味ではない。生の座標・出自は外部保存し、答えと図の変化を分ける。
- 全public JSON・stdout/stderr・図の座標・時系列はmanifestの `raw_root`（`/tmp/...`）へ置く。public JSONは採点後に可逆gzip圧縮し、元bytesとgzipの両hashを残す。リポジトリは入力規則・コード・小さいreceipt・集計のみ。src・既存結果は編集しない。

実行:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/sweep/d-budget-cores/run.py prepare
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/sweep/d-budget-cores/run.py run
```

`prepare` は既存manifestの上書きを拒否する。`run` は完了receiptを再実行せず、開始記録だけが残るセルは自動再試行しない。結果を捨てて再試行したり、問題を入れ替えたりしない。216本すべて上限までかかる場合、固定レーンの最大は約5.1時間。短く終了する問題ではそれより早い。
