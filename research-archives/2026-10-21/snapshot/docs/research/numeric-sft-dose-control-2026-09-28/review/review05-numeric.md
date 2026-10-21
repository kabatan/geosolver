# Review 05: anonymous numeric answers

採点は前回と同じ較正済み数値基準に従い、最終数値と幾何導出を分けました。答案全文を確認し、指定されたindexと4答案だけを条件情報として扱いました。既知定理の条件照合には許可されたcompact referenceのDB08のみを参照しました。private/plan/snapshot資料は読まず、manifestも変更していません。

| case | final answer | reference | derivation | valid core | numerical error |
|---|---:|---:|---|---|---|
| numeric-00 | 6 | 6 (DB08) | valid | yes | no |
| numeric-01 | 6 | 6 (DB08) | valid | yes | no |
| numeric-02 | 6 | 6 (DB08) | valid | yes | no |
| numeric-03 | 6 | 6 (DB08) | valid | yes | no |

DB08は、この正確な構図でOP（=PX）が円(KLX)にXで接することを述べています。4答案はいずれもこの関係を答案中で述べ、または「この構図での既知定理」として具体的に呼び出し、(PZ=PY+YZ=12) と方べき (PX^2=PYcdot PZ=36) に適用しています。したがって最終値6は正しく、説明も較正基準上validです。定理の再証明は要求されません。

numeric-01は「一意な数値を求める問題だから接線である」という別の推論もしていますが、これは根拠になりません。numeric-02/03はさらに、直径PXの円がΓにAで接するとする誤った補助説明を含みます（直角はAでなくX）。ただし、いずれもこの誤りでOPとσの接線関係を明示撤回・置換してはいません。正しい特別定理の明示適用を有効な核心として保持し、誤った付記はJSONの `incidental_error` に分離して記録しました。

caseごとの短い引用、hash、理由、不確実性、全文確認範囲は `review05-numeric.json` に記録しました。
