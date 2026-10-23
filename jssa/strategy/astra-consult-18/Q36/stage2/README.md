# Q36 段階2の記録

登録は commit `bffba67`、凍結srcは `60db4b6`。利用者の別タスクでの明示的許可を受けて実行した。予測・対象・seed・閾値・予算は [prediction.md](../prediction.md) と [next-stage-plan.md](../next-stage-plan.md) のまま。並列上限は利用者の指定を優先して2。

`preflight.json` に、登録成果物14件とlockのコミット同一性、選択元 `input-census.csv` のSHA-256、362入力の照合、実行依存関係、探索箱、実行コードのSHA-256を記録した。説明文書2件だけにマージ時の追記があり、登録時の内容は `3e32bf7` でハッシュ一致を確認した。計算入力・probe・固定代表点は一致している。

新規実行の開始UTCは各 `*.start.json`、終了・外側タイムアウト・終了コード・ファイルハッシュは `*.end.json`。最初の開始時刻は `2026-10-23T16:06:58.369284Z`。`tasks.json` は局所160ジョブと完成solver240実行を列挙する。各コマンドは必ず1ジョブだけを起動し、OSロックで同時実行2件以下に制限する。各ジョブを1物理コアへ固定し、BLAS等も1スレッドにする。ファイルサイズのOS上限は4,999,999 bytes。

## 実行と保存

新しい [stage2.py](../stage2.py) は局所probeと同じ乱数生成、箱、production baseline設定、局所関数、箱外優先・残差・guard/hard・値照合を使う。局所終了理由はSciPy呼出しの返り値を観測するだけで、引数・乱数・返り値は変更しない。完了開始点を `*.partial.json` に随時保存し、最終記録を `*.json` に保存する。未完了開始点の補充はしない。

完成solverは凍結版の公開 `solve` と `EngineRunner` を使用する。[q36_save_worker.py](../q36_save_worker.py) は元のworkerの `main/execute` をそのまま呼び、計算完了後の保存だけを変更する。公開された全答え、status、終了理由、時間、設定、個々のexact-resultと候補UIDの対応を保持し、大きな座標配列・内部診断配列を保存から外す。元のリクエストに結び付いた保存receiptとdeadline検査を使う。計算途中の候補選択・停止規則には介入しない。全返答集合の副本は `*.worker-final.json` に残す。参照値は別の `grading/references.json` に置き、完成solverへ渡す入力は `inputs/*.json` のDSLのみ。

保存コードは新規solverを呼ばずに静的検査と人工の3値集合の保存往復を確認した。新規seedの試走や追加のsmoke testは行っていない。`src/` は編集していない。

## 採点

[stage2_analyze.py](../stage2_analyze.py) は新規seedだけを集計する。完成solverの式は公式採点と同じ `ExactAnswer.canonical_key()` と `describe_exact()` で照合する。復元不能な集合や未解釈の答えは欠測とし、不出現へ置換しない。全正答値の回収（包含）、集合一致、余分な値、空答を別々に数える。全比率にWilsonの二項95%区間を付ける。区間は独立試行を仮定した記述的目安であり、時間打切りやsolver内の依存を取り除かない。

主対象2問のR/C/Z、固定効果量条件、各0.025以下の片側正確二項検定、3対照を別々に報告する。P1/P3の境界、測定不足条件、正確二項確率は人工個数で確認した。採点で参照する既存データは固定された選択・参照値・幾何モデルだけで、登録前seedの成績を新規成績へ合算しない。

実行済みseedを再実行するコマンドは上書き防止で拒否する。集計だけの再確認は次の通り。

```bash
env PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q36/stage2_analyze.py
```
