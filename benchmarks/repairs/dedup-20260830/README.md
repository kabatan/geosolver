# 重複6登録の除去

2026-08-30。ユーザーの指示により、現行評価セットの329登録を323登録へ整理した。
自然問題数は323のままであり、独立した問題は失っていない。
全323登録が実行可能・参照確認済みで、`dedupe_key` の重複は0件。

## 残す登録の選び方

公式のコンテスト・問題番号付きIDを優先し、MathNet転載より主催者の一次出典を持つ登録を残した。
solverの成功・失敗・実行時間は選択に使っていない。
HMMTの `dedupe_key` は過去の対応関係を保つため旧別名のままにし、残す登録のメタデータも変更していない。

| 削除した重複ID | 残したID | DSLの違い |
|---|---|---|
| `HMMT-2011-regular-hexagon` | `HMMT-2011-FEB-ALGGEO-08` | IDのみ |
| `HMMT-2011-square` | `HMMT-2011-FEB-ALGGEO-10` | IDのみ |
| `HMMT-2011-collinear-circumcircle` | `HMMT-2011-FEB-ALGGEO-18` | IDのみ |
| `JMO-2019-MATHNET-08ya` | `JMO-2019-PRE-10` | IDと条件の順序のみ |
| `JMO-2019-MATHNET-08yk` | `JMO-2019-PRE-08` | IDと条件の順序のみ |
| `JMO-2022-MATHNET-08z4` | `JMO-2022-PRE-12` | IDのみ |

6組とも参照集合が一致する。共線問題の参照は `{7, 35/11}` の両方を保持した。
DSLの比較ではIDだけを除き、条件順が異なる2組に限って条件の配列を並べ替えて比較した。
変数・構成順・求値式・各条件の内容は一致する。
これは数学的な条件集合の一致を確認する処理であり、条件順を変えても探索の挙動が同じと主張するものではない。
**残したDSLの条件順は変更していない。**

全登録について同じ比較を行い、既存の `dedupe_key` が異なるのに同じDSLを持つ追加の重複は見つからなかった。
任意の異なるDSL間で幾何的な同値性を一般に判定した、という意味ではない。

## 保全・再生成

- [removed-cases.jsonl](removed-cases.jsonl)：削除直前の6登録をそのまま保存。埋込DSL・参照・出典・移行履歴を含み、復元可能。
- [ledger.json](ledger.json)：削除IDと残すID、比較方法、削除前の登録hash・DSLファイルhash。
- 現行の `benchmarks/cases.jsonl` と `benchmarks/dsl/` から6登録・6ファイルを削除。
- 通常の修復生成・stagingでは再導入しない。旧97件の修復台帳は過去の履歴として保持する。
- 過去campaign・監査artifact・原資料は変更しない。歴史的な診断はアーカイブしたDSLを明示的に読む。
- solver本体・残る323登録・そのDSL・参照集合は変更しない。

残存登録は295件のAIME/HMMT/JMO主層と、28件のAIME追加層。
条件矛盾で削除したHMMT 2013の1件は[別の監査記録](../corpus97/HMMT_2013_GEO_09_SOURCE_CHECK.md)にあり、今回の6重複とは区別する。

## 確認方法

```sh
.venv/bin/python benchmarks/research_runner.py validate
.venv/bin/python -m benchmarks.repairs.corpus97.apply_repairs --check
.venv/bin/python -m pytest tests/test_corpus_deduplication.py tests/test_corpus97_repairs.py tests/test_research_runner.py -q
```

回帰試験では、自然問題IDと正規化DSLの重複ゼロ、参照集合の一致、残した6代表の登録・DSL hash、削除済み7登録（矛盾1件＋重複6件）を修復生成で復活させないことを確認する。
旧別名の正解配置・複数解の回帰試験はアーカイブしたDSLを使って維持する。

確認結果：関連54テスト、変更したPython 5ファイルのRuff lint・format check、修復生成器の整合検査、現行323件のvalidateが通過した。
全323登録とDSLファイルの削除前後のhashは不変で、取り除いたIDは対応表の6件だけだった。
solver本体の変更や新しい性能評価は行っていない。
