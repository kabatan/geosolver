# 手動監査報告

`manual_scope_audit.py`で、抽出候補の各行を問題文（JMOは公式画像/PDF）と照合しました。自動抽出の226件（AIME）・222件（HMMT）は候補を作るためだけに使い、scope判定はその後の手動台帳です。

## 監査済み件数

| contest | 抽出/公式問題行 | 手動監査済み・scope内（重複除去） | JSON / 実行可能JSON |
|---|---:|---:|---:|
| AIME | 226 | 108 | 108 JSON（実行可能102） |
| HMMT | 222（2011年の同一問題のtrack重複を含む） | 132 | 132 JSON（実行可能122） |
| JMO予選 | 56公式問題行 + 24補助行 + 20年次リンク | 56 | 56 JSON（実行可能55） |
| 合計 | 548 source rows | **296 unique** | **296 unique JSON**（302 files、unique実行可能279） |

`296`が、2006--2025の20年について、同じ問題の再掲を除いて手動確認した幾何問題の件数です。全296件に、問題文と出典を保持したsource-faithful JSONを割り当てました。ここから現在のsolver DSLで原文の全条項を実行できる「solver scope」はuniqueで279件（別名を含む302ファイルでは285件）です。残り17件は、円弧・図依存の斜線領域・折り返し後の領域・図が定める順序分岐などを現行IRに安全に表せないため、定義を推測せず `reference_only` として保持しています。以前これをscope総数として7と報告したのは誤りでした。

内訳は `extraction_summary.json` の `scope_count_by_contest` に保存しています。HMMT 2011のAlg/Calc/Comb PDFは同じ5問を三つのtrackで再掲するため、HMMTのsource行は142件でもunique scopeは132件です。なお、HMMT 2010 Geometry 7（GEO-09）は公式本文と解答を再確認し、有限分岐（70°/160°）を持つ2D scalar問題として今回追加しました。

## DSLの状態

scope判定とsolver実行可能性は別工程です。AIME/HMMT/JMOの全scope行に `dsl_path` を付け、source_statementとclause_ledgerを保持しました。本文・図から一意に現行IRへ写せない17件は `solver_coverage=reference_only_*` とし、無制約変数を置いたり公開解答をanswerへ埋め込んだりしていません。JMOのcanonical scope内56 rowsは公式画像50件、公式PDF 6件を手作業で確認し、全文を文字起こししてJSONに保存しています。MathNet補助本文11件は公式問題番号との対応を別source rowとして保持し、canonical DSLの問題文には使用していません。

したがって、性能表は全302 JSONを走査し、`reference_only` 17件を明示的に未実行として分離したものです。原文を改変せずに現行solverで探索できる285 files（279 unique）については、成功・正答一致・no_solution・例外・timeoutを個別に保存しています。
