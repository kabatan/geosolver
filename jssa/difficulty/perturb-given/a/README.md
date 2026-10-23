# Q40a 段階1

solverと局所探索は未実行。Claudeのcommit・push確認と、別タスクでの実行許可が必要。

- `prediction.md`：選択・摂動・当たり・指標・予言・解析・中止条件。
- `selection-contract.json` / `selected.csv`：Q40bと共有する選択契約と40問。
- `selection-ledger.jsonl`：377候補の採否。`inputs/`は答え・成績を除いた入力。
- `interventions.json` / `variants.jsonl`：連動する数値の扱いと全差分。
- `dsl/`：元40版と変更200版。図が存在するかは未検証。
- `execution-plan.json`：許可後の予定のみ。実行器は含まない。
- `static-checks.json` / `source-manifest.json`：静的確認と凍結src・元データのhash。
- `prediction.lock.json`：本書を含む固定ファイルのSHA256とUTC時刻。
- `answer.template.md`：結果段階の冒頭形式。結果ではない。

リポジトリ直下からの読み取り専用確認：

```sh
python3 jssa/difficulty/perturb-given/a/plan_stage1.py check
```

準備時の`build`と`lock`は既存ロックを上書きしない。実行・解除のオプションはない。
将来の追加コード・結果は`stage2/`、報告は`answer.md`に置き、段階1のロックは変更しない。
Q40bはseedだけで再抽出せず、共通契約・40問・各DSLのhashを合わせる。
`unseen`は未使用出自群の名称であり、他タスクを含め完全に未実行という意味ではない。
