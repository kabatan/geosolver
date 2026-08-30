# 323問の原因調査で確認した入力6件の訂正

DSLの誤り5件と参照値の誤り1件だけを訂正する。solver実装、実行設定、評価対象ID・順序・件数（323件）、過去の実行結果は変更しない。

| ID | 訂正 |
|---|---|
| AIME-2018-II-12 | 凸四角形の向きと矛盾する `dy<0` を `dy>0` へ |
| AIME-2021-I-13 | 二交点の片方Pに `n=1` を指定。P,Qのラベル交換は条件・求値に影響しない |
| HMMT-2022-FEB-GEO-05 | targetを `BD²+CD²` へ |
| JMO-2013-PRE-08 | 4円の内接条件に合わせ、中心距離を `r-ri` へ |
| JMO-2015-PRE-11 | 面積4の対象をA'B'C'からA'B'Cへ |
| AIME-2020-I-15 | 参照値を `3*sqrt(55)` へ。求値対象は面積なので、原問題の最終整数58にはしない。DSLは変更なし |

各訂正の原資料URL、理由、旧新の行・DSL・ファイルhashは `ledger.jsonl` にある。訂正前の6行は `before.jsonl` に保存した。従来の `migration` は過去の移行記録なので改変せず、今回の変更は別の `repair` 欄で追跡する。JSONL内のDSLと独立DSLファイルを同期する。

`witnesses.json` は原問題に基づく有効配置の対照。JMO-2015-PRE-11のみ、solverとは独立な三角形の面積計算から求めた600桁の数値座標を保存している。他の5件は厳密な座標式。これらは入力と最終検証・厳密化の回帰試験であり、探索の成功率試験ではない。

回帰試験：`tests/test_corpus323_input_corrections.py`。全6件の高精度残差、hard条件、最終受理と厳密値を検査する。誤った旧条件が有効配置を排除すること、P/Qの両ラベルで同じ答えになること、旧target・旧参照が正しい値と異なることも検査する。

前回の診断記録 `benchmarks/local-evaluation/corpus323-diagnosis-20260830/` と、元の323件評価は履歴として変更しない。本訂正で6件すべてが180秒以内に自力探索できるようになったと主張するものではなく、成功率の更新には別の再評価が必要。

## 確認結果

- `python -m benchmarks.research_runner validate`：323件すべてvalid、問題ID・DSL対応・参照の検査でissuesなし。
- `python -m pytest -q -o addopts= tests/test_corpus323_input_corrections.py tests/test_corpus97_repairs.py tests/test_corpus_deduplication.py tests/test_research_runner.py`：67 passed。
- 新規テストのRuff検査・format検査・構文検査：合格。
- 6行以外の317行と、ID順序は不変。元campaignの主要7ファイルのSHA-256も一致。
- solver source hashは引き続き `sha256:53e6f65a84a7f23b035edf8ed18d48956eaa3ba82a290905f8863f05c441dd8c`。

境界誤受理、精密化と後段の時間配分、`max_iters` による入口棄却について、solver本体の変更は今回行っていない。commit・pushも行っていない。
