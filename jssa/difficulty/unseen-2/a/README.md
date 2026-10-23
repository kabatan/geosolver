# Q30a — AIME 未使用17問、段階1

2000〜2005・2010〜2019年のAIME I/IIの全480スロットを確認し、
既存重複83問、主題・表現上の対象外380問を除いた17問を作成した。
17問すべて、原文との読み合わせ、正解図の代入、公式出力への変換照合に合格した。
solver・局所探索・PSLQは実行していない。

| ファイル | 内容 |
|---|---|
| `prediction.md`, `prediction.lock.json` | 最後に固定する予測、実行条件、UTC時刻、SHA-256 |
| `authoring-rules.md` | 作成・除外・監査・実行ゲートの規則 |
| `manifest.json`, `audit/selection.csv` | 全480問の採否と根拠 |
| `cases.jsonl`, `dsl/` | runner互換ケース、17個のDSL |
| `mapping.json`, `cards/`, `cards.md` | 原文と全構成・条件・targetの対応 |
| `source-evidence/` | ユーザー提供の保存HTML64ページと取込・抽出記録 |
| `references.json`, `score.py` | 幾何量の参照値と公式整数出力への変換 |
| `hand_witnesses.py`, `audit/substitution.json` | 手計算で作った18配置の90桁代入検算 |
| `audit/duplicate-audit.json` | 323+20+54問および他担当のsnapshotとの機械的重複検査 |
| `audit/validation.json`, `audit/scoring-contract-check.json` | 静的検査・採点契約検査。solver成績ではない |

指定された `benchmarks/new-2026/authoring-rules.md` は作業コピー・参照可能な履歴・
元ディレクトリで確認できなかった。存在する2026年20問のDSLとREADME、
Q29の追記、Q30、ユーザーの明示規則を用いた。旧unseen-1983の31行目は使っていない。

一次資料はユーザーが取得したAoPS WikiのWayback保存HTMLである。
コピー時にファイル全体・ページ識別・15問題節または15解答を検査しSHA-256を記録した。
取得日時やHTTPステータスは観測しておらず、HTML内のアーカイブ時刻とコピー時刻を区別している。
外部へのcurlや新たなダウンロードはしていない。解説ページは使用していない。

`cases.jsonl`の`answer`は**採点用の幾何量**であり、DSLには含まれない。
既存research_runnerはsolver入力と参照値を分離している。
整数化・既約分数・床などは`score.py`で変換する。raw幾何量の厳密集合一致と
公式出力一致の両方を要求し、余分な答え、答えなし、異常終了、実行契約違反を不正解にする。

段階1の再現コマンド（ロック前のみ、探索を含まない）:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 jssa/difficulty/unseen-2/a/collect_sources.py 2019
PYTHONDONTWRITEBYTECODE=1 python3 jssa/difficulty/unseen-2/a/author_cases.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-2/a/audit_inputs.py
PYTHONDONTWRITEBYTECODE=1 python3 jssa/difficulty/unseen-2/a/selection.py
PYTHONDONTWRITEBYTECODE=1 python3 jssa/difficulty/unseen-2/a/verify_bundle.py
```

`verify_bundle.py`はロック後も読み取り専用で検証できる。
ユーザーによる予測のcommit・push確認と、**別タスクでの明示的な実行許可**が必要。
このディレクトリに自動実行用campaignやsolver起動スクリプトは用意していない。
このタスクではcommit・pushも行わない。

代入検算は正解配置の存在確認である。目標値の一意性については各カードの手計算・枝の説明を
併記しており、全解の自動網羅探索を行ったという主張ではない。
2問は未知変数のない有限式評価であり、17問がすべて同じ難度という主張もしない。
