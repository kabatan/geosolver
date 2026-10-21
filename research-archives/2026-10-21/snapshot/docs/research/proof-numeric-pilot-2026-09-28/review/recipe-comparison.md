# 旧数値SFTとAP01数値SFTのレシピ比較

モデルの新しい原出力・private keyは読まず、教材、設定、評価job、旧評価receiptのジョブハッシュだけを比較した。以下は実際の差であり、今回の数値低下や証明不変の原因を特定したものではない。

| 項目 | 旧 program-self-training / transfer-followup | 今回 AP01 pilot |
| --- | --- | --- |
| 学習問題 | 7構図（H01, H04, H07, H13, H15, DA01, DA05）×各8問、計56問。各構図は固定した求値量を、4 visible + 4 repairの数値条件で反復。 | AP01の1構図、64非相似三角形×各4問、計256問。各形状で21点対の距離queryから4種類を選び、実際のtrainには21種類すべてが現れる。 |
| 学習入力 | 共通prefixは “Give only the requested numerical value, with at least 10 significant digits when appropriate. Do not give a proof or explanation.”。各問の既知量は主に2〜3個の高精度小数（例：BCとAM、またはAB/BC/CA）。 | AP01前提全文と3つの整数辺長（AB/BC/CA、5..40）を提示。“Give the requested length as a decimal rounded to six digits after the decimal point.”。明示的な推論・証明要求はない。 |
| 教師target | 全56件が説明なしの裸の小数。小数部13〜16桁（28件が16桁、20件が15桁）。 | 全256件が説明なしの裸の小数で、小数部は厳密に6桁。座標・式・証明は含まない。 |
| 更新・提示回数 | LoRA r8/alpha16/dropout0、学習率5e-6、勾配累積4、128更新。合計512教材提示=56件を約9.14巡（各教材9回、一部10回）。32更新checkpoint時点は約2.29巡。 | 同じモデルrevisionとLoRA/学習率/勾配累積、128更新。合計512教材提示=256件をちょうど2巡。32更新時点は0.5巡。学習seedも旧2026092701と今回2026092801で異なる。 |
| 主数値評価の問い | 12の未学習構図×各2推論seed=24job。関連構成6構図、異なる構成・合成6構図。全jobが厳密数値と英語での推論説明を要求。採用されたv2はさらに末尾のAnswer行を要求。 | 同じAP01構図の未見非相似8形状×1問と、既見4形状の再出題×1問、計12job。各jobは学習と同じ6桁小数指示で、推論説明もAnswer行も要求しない。 |
| 答案形式・採点 | 旧の最終採点コードは末尾の明示的Answer行またはboxed式を抽出し、単独の裸の最終数値は無視する。解の妥当性は別監査。厳密数値式のkeyと比較する。 | 明示した最終回答を抽出し、絶対誤差1e-4または相対誤差1e-5。bareな単独最終小数も許容し、曖昧さ・打切りは別記する。 |
| 比較条件 | 旧followup主評価はbase・code128・numeric128・OPD32の4条件。 | baseとAP01数値SFTの2条件。 |

## 旧最終評価jobの原文指示

24件の冒頭に共通する指示は次のとおり（この後に空行と問題本文）。

> Solve the following geometry problem. Give the exact numerical answer and explain your reasoning in English. You have no access to tools.

24件の問題本文の後に共通する指示は次のとおり（本文との間に空行）。

> End with a single line of the form Answer: <exact numerical expression>.

旧最終評価の使用jobは推測ではなく確認済み。transfer-reanalysisの eval-jobs-v2.json のSHA256は 5a6043b47d3a53ba018fc425bc70c89f0925ae0e0478263a17d30af2fda54190 で、旧 numeric-numeric128-32768/receipt.json の jobs_sha256 と一致する。初版 eval-jobs.json は同じ24問だがAnswer行の追加指示がない。旧v2と今回の数値評価はいずれも温度0.7、top_p0.95、top_k20、presence penalty0.2、thinking false、batch4、初期cap32768/context40960の生成設定を使う。

出力形式に関しては、旧**学習**も数値だけを教えており、旧**評価**がそれに反して導出と厳密式のAnswer行を明示していた。今回は学習・評価ともに直接6桁小数へ誘導する。従って、親担当から報告された「今回SFTは短い直接小数、baseは長い計算過程」という差とprompt文面は整合的だが、文面だけで出力短縮や正答率低下の原因とは断定できない。

交絡は少なくとも教材反復数、構図の幅、同一構図内のquery多様性、入力数の精度、教師の桁数、評価promptの推論要求、評価の未見対象、学習seed、採点形式に及ぶ。旧の未学習12構図の転移結果と、今回のAP01未見8形状・既見4形状の数値診断は同じ母集団の測定ではない。因果を絞るには、同じAP01教材とcheckpointに対し「6桁を直接回答」と「途中計算を示しAnswer行に記す」を同じ形状・seedで対にしたprompt比較、および教材提示回数を揃えた比較が必要である。今回予定の128→512更新は提示回数差を縮める診断になるが、他の差は残る。

参照：旧 train-numeric.json、旧 config-numeric128.json、transfer-reanalysisの eval-jobs.json / eval-jobs-v2.json / score_numeric.py、旧followup numeric128生成receipt、今回 train.json / numeric-jobs.json / config-128.json / PROTOCOL.md。
