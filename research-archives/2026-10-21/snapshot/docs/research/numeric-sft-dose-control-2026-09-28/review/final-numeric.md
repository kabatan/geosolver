# Final packet: anonymous numeric answer

採点は既存rubricの較正済み数値基準に従い、最終数値と幾何関係の妥当性を分けました。指定されたpacket indexとnumeric-00答案全文だけを条件情報として確認し、H12の既知性質をcompact referenceで照合しました。private/plan/snapshot資料は読まず、manifestも変更していません。

| case | final answer | reference | answer correct | derivation | valid core | numerical error |
|---|---:|---:|---|---|---|---|
| numeric-00 | 15/2 | 15/2 (H12) | yes | valid | yes | no |

答案は (P,Q,V) の一直線性、すなわち (Q) の (AC) への垂足が (V) であるという、H12と一致する既知性質を具体的に述べています。条件が完全に一致するので、較正基準により再証明なしで利用可能です。その後は (MV=1)、(QV=10) を計算し、指定された側と距離順から (PQ=QV-PV=15/2) を得ています。

答案は途中で「数値がきれいになる」ことも支持材料に挙げますが、それ単独では導出になりません。ここでは正確なH12性質を明示して使い、後で撤回・置換していないため、較正後の判定はvalidです。厳格に自己完結証明のみを要求する場合の穴はJSONに分けて記録しました。

引用、hash、read coverage、厳格/較正読み、不確実性は `final-numeric.json` に保存しました。
