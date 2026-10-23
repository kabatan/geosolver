# Q40b 段階1

計画は [prediction.md](prediction.md)。solver・局所探索は実行していない。

- 元40問＋摂動200版、3 seed、予定720回。開発20問、開発外20問。
- 共通元はQ40a。選択規則・コード・数値の連動表・入力・DSLを `shared/` に同じバイト列で保存する。
- `shared/selection-contract.json`、`shared/selected.json`、`shared/interventions.json`、`shared/variants.jsonl` が規則・40問・操作・全DSLハッシュ。
  aの固定済みファイルと全て照合してから、bを固定する。aのlockも `sibling-prediction.lock.json` に保存する。
- `shared/dsl/` は入力だけ。古い答え、実測値、探索済み候補は含まない。
- `execution-plan.json` は未実行の順序表。実行コマンドやランナーは含まない。
  `shared/execution-plan.json` はaの計画の写しであり、bの720回の計画とは別。

repoのルートから、読み取りだけの静的再検証：

```sh
python3 -B jssa/difficulty/perturb-given/b/stage1.py check
```

aの成果物が揃ってから、同じ共通規則・入力かを照合：

```sh
python3 -B jssa/difficulty/perturb-given/b/stage1.py check-sibling
```

aがなければ照合は失敗して止まる。それを無視して実行しない。
`sync` は固定前の入力同期専用、`seal` はSHA-256とUTC時刻の固定専用。固定後は同期・lock上書きとも拒否する。
静的検証では幾何的な可解性を確認していない。数値の連動表を使っても条件が両立しない場合はあり、その失敗も分母に残す。

次の開始には、Claudeのcommit・push確認、別タスクの明示的許可、a/b照合、ロック検査が全て必要。
