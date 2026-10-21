# Review 03: anonymous numeric answers

採点は `REVIEW_RUBRIC.md` の較正済み数値基準に従い、答案が最後に明示した数値の正誤と説明の妥当性を分けました。`numerical_error` は最終数値またはその最終算術の誤りを指します。したがって、正しい数値でも導出がinvalidなら `numerical_error: false` と `derivation_status: invalid` を併記します。

packet indexと numeric-00..04 の答案全文を確認しました。条件情報には指定されたpacketと5答案だけを使用し、許可されたcompact referenceの DB01、H08、DA15 の一致条件と正答を照合しました。private/plan/snapshot資料は読み込まず、manifestも変更していません。

| case | final answer | reference | answer correct | derivation | valid core | numerical error |
|---|---:|---:|---|---|---|---|
| numeric-00 | 4 | 4 (DB01) | yes | invalid | no | no |
| numeric-01 | 13.5 | 27/2 (H08) | yes | invalid | no | no |
| numeric-02 | 27/2 | 27/2 (H08) | yes | invalid | no | no |
| numeric-03 | 5 | 5 (DA15) | yes | valid | yes | no |
| numeric-04 | 5 | 5 (DA15) | yes | valid | yes | no |

numeric-00 は、答案自身が導いた中心間距離の式が角 A に依存するとした後、整数の見栄えから4を選んでいます（`numeric-00.md:500-505, 523-560`）。正答はDB01と一致しますが、DB01の決め手である二円の外接を答案は述べていません。

numeric-01/02 は、二円の radical axis がPQの垂直二等分線だとする誤りを使っています。正しく言えるのは、radical axis とPQの交点がPQの中点ということまでで、radical axis 自体は一般にはPQに垂直ではありません。01は最終的にそのモデルの対称仮定が与条件と矛盾すると認めながら、対称モデルの面積計算を再利用して推測しています。02は誤った垂直性を検算でも繰り返します。どちらもH08の正しい等角関係を使っていません。

numeric-03/04 は長い探索中に推測的な案もありますが、最後にこの作図にそのまま当てはまる既知のA-Dumpty点定理を正確に述べ、Fが直径AOの円上にあることからピタゴラスの定理を適用しています。DA15の条件と一致し、定理を明示的に撤回していないので、較正基準に従い両方ともvalidとしました。04は定理の言い方が tentative なため不確実性を medium と記録しましたが、較正ルール上はその語調だけで無効にはしません。

機械可読のcaseごとの引用、理由、packet hash、read coverageは隣の `review03-numeric.json` に記録しました。
