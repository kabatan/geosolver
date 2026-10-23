# Q18 未使用54問の入力監査

**結論：合格26問、修正要1問、除外候補27問。未判定0問。**
修正要1問は **HMMT-2016-FEB-GEO-01の集合採点・出力契約**であり、幾何DSL式の誤りではない。今回の読み合わせで、幾何DSLの条件・枝・目標式を変更すべき明白な誤りは検出しなかった。一次照合できない27問を、二次資料の答えだけで合格にしていない。

| 区分 | 合格 | 修正要 | 除外候補 | 合計 |
|---|---:|---:|---:|---:|
| AIME 1983〜1999 | 23 | 0 | 13 | 36 |
| HMMT February | 3 | 1（集合採点仕様） | 14 | 18 |
| 合計 | 26 | 1 | 27 | 54 |

**選別はソルバーの結果を見ずに行った。対象54問のソルバー結果は見ていない。** solver・局所探索・pの推定・数値的な配置生成・DSL式の数値評価・残差評価・解の列挙は実施していない。既存の封印実行やその結果ファイルも参照していない。見た答えは、監査に必要な一次解答と入力作成時に分離保存された参考答だけである。

## 判定の意味と範囲

- **合格**：指定一次資料の本文と答えを照合でき、記号的な読み合わせで条件・枝・不等式・非退化・目標量に修正点を見つけなかった。探索で解けること、全実数解の存在・一意性、数値安定性を認証したという意味ではない。
- **修正要**：一次照合は済んだが、本検証前に具体的に直すべき出力・採点仕様が残る。修正案を別ファイルへ保存した。
- **除外候補**：指定一次資料が不足している。今回のオフライン監査では本検証へ入れる根拠がそろわず、27問すべてを理由付きで保留する。将来一次資料が得られれば再監査できる。難度・変数数・予想成功率を選別に使っていない。

この監査は一担当による静的・記号的なレビューであり、独立した第二査読や形式的同値性証明ではない。整数証人、床関数、論理枝、三角関数の実行時挙動は検査範囲外である。原問の証明要求と数値答の一致も区別する。

## 答えの照合結果

**確認できた範囲で答えの不一致は0件。** AIMEのHF `secondary_answer`とAoPS Answer Keyを比較できた23件は全て一致した（026と26などの先頭0は整数表記の差）。残る13件は一次答えがないため、一致とも不一致とも判定していない。AIME36件すべてで、HF原JSONLのQuestion/Answerが保存本文/secondary_answerと一致することは別途確認した。

HMMTの公式冊子がある4件は、既存`official_answer`と保存公式Answer行・PDF表示が一致した。これら4行の`corpus_reference_answer`はnullなので、HF二次答との一致を確認したとはいわない。GUTS/TEAMの14行はコーパス参考答しかなく、**公式答え未入手**である。

| HMMT公式照合 | 公式答 | 問題PDF | 解答PDF |
|---|---|---|---|
| 2016 GEO-01 | {2, 6} | p1 | p1 / テキスト8行 |
| 2022 GEO-07 | 16902 | p1 | p3 / テキスト148行 |
| 2022 GEO-08 | 2402 | p1〜2 | p4 / テキスト187行 |
| 2023 GEO-06 | 68 | p1 | p3 / テキスト110行 |

### 注意すべき目標量・枝

- **2016 GEO-01**：`Area(S,I,X)`の像の集合が原問の答え。公式値2または6の一方だけで合格にしてはならない。公開結果モデルにはanswersリストがあるため、スカラーtargetだから表現不能とは判断しない。既存READMEの集合採点未実装を受け、[全答集合との一致を要求する案](proposed-fixes/HMMT-2016-FEB-GEO-01.md)と[機械可読な契約案](proposed-fixes/HMMT-2016-FEB-GEO-01.answer-contract.json)を置いた。幾何DSLはそのままでよく、この案も実行系へは適用していない。
- **2022 TEAM-03（除外候補）**：R=1のDSLはXY/Rを返す。原問の長さは係数にRを掛けて復元する。保存参考答sqrt(3)Rを、そのままスカラー目標へ渡すのは誤り。原問の証明要求も残る。
- **2016 GUTS-10（除外候補）**：保存コーパスは外心Oを使う。似た公式2016 GEO-02は垂心Hを使い、答え14である。類似した本文という理由でその公式答えを転用しなかった。
- **2022 GEO-07**：第2最大辺長の二乗が既約a/b、目標は100a+b。六つのペアのminをmaxでまとめる式を全数照合し、PDFでsqrt(a/b)を再確認した。
- **AIMEの既約分数**：整数分子分母、正の分母、整数Bezout証人の式を確認。長さ・比そのものへ目標を差し替えず、原文のm+n等を保持している。整数化・平方根表現・floor・度数法の対応も各問に記録した。

## 一次資料と不足

AIMEは依頼に従い、保存AoPS Wikiを一次照合資料として扱った。MAAの大会原本を再取得したわけではない。[fetch-log.json](primary/aops/fetch-log.json)にある取得成功HTML27本のbytes/SHA-256を全て再照合し、問題本文はHTMLのProblem節・数式画像alt・asy記述から読み取った。HTMLの外部画像本体は新規取得していない。画像がない問題でも本文だけで条件が完結する場合は、その根拠を個別記録に書いた。asyの描画座標や解由来数値を修正入力へ転用していない。

| AIME取得失敗 | 対象番号 | 件数 | 扱い |
|---|---|---:|---|
| 1992 Problems / Answer Key | 09, 14 | 2 | 一次資料で照合不能(取得失敗) |
| 1993 Problems / Answer Key | 02, 12, 13, 15 | 4 | 同上 |
| 1994 Answer Key | 02, 08, 10 | 3 | 問題本文は一次確認済み、答え未照合 |
| 1999 Problems / Answer Key | 02, 09, 12, 14 | 4 | 一次資料で照合不能(取得失敗) |

HF二次資料の出所は[既存README](../source-evidence/aime-1983-1999/README.md)のgneubig/aime-1983-2024。SHA-256は`5b29347ce7c807ab1ce23951577ca8530c2c10b18e52c9da8099e3e443779012`。一次不足13問のHF照合は、CSVの`secondary_*`と各問の「二次参考」に分離した。

HMMTは`/home/kabatan/work/solver-research-assets/corpus97-sources/`の保存公式問題・解答テキスト/PDFを使用し、[既存README](../README.md)、[v2 README](../revisions/v2-before-aime/README.md)、[v2 manifest](../revisions/v2-before-aime/manifest.json)にある出所と照合した。題字・日付・部門・公式問題番号、PDFの数式、解答欄を目視確認した。指定保存ディレクトリにGUTS/TEAM冊子はない。該当14問のIDはコーパスの暫定indexで、公式番号の保証もない。元の取得URLがこのREADME/manifestにない資料に、推測のURLを追加していない。

出所・各PDF/テキストのhashは[hmmt-primary-evidence.json](hmmt-primary-evidence.json)、保存冊子の有無は[hmmt-source-inventory.json](hmmt-source-inventory.json)、目視したページは[pdf-review/](pdf-review/)に記録した。AoPSの抽出と答え対応は[primary-extracts.json](primary-extracts.json)、取得ログとの一致は[source-checks.json](source-checks.json)にある。

## 全54問の判定一覧

一次答と二次参考答は独立の列にしている。「未入手」を二次答で埋めない。詳細な根拠は後半の個別記録と[audit.csv](audit.csv)に固定した。

| ID | 判定 | 一次答 | 二次参考答 | 要点 |
|---|---|---|---|---|
| AIME-1983-04 | 合格 | 026 | 26 | 一次本文・解答026と一致し、条件と目標に修正点なし。 |
| AIME-1983-12 | 合格 | 065 | 65 | 一次本文・解答065と一致。有限範囲への整数証人の切詰めはしていない。 |
| AIME-1983-14 | 合格 | 130 | 130 | 一次本文・解答130と一致し、非退化とPの両側の枝を明示。 |
| AIME-1984-03 | 合格 | 144 | 144 | 一次本文・図の接続・解答144と一致。 |
| AIME-1984-06 | 合格 | 024 | 24 | 一次本文・解答024と一致。面積式は定義の照合のみで数値評価していない。 |
| AIME-1985-09 | 合格 | 049 | 49 | 一次本文・解答049と一致。 |
| AIME-1985-11 | 合格 | 085 | 85 | 一次本文・解答085と一致。 |
| AIME-1986-09 | 合格 | 306 | 306 | 一次本文・解答306と一致。 |
| AIME-1986-15 | 合格 | 400 | 400 | 一次本文・解答400と一致。 |
| AIME-1987-09 | 合格 | 033 | 33 | 一次本文・解答033と一致。 |
| AIME-1988-07 | 合格 | 110 | 110 | 一次本文・解答110と一致。 |
| AIME-1988-14 | 合格 | 084 | 84 | 一次本文・解答084と一致し、反射の係数比較が記号的に同値。 |
| AIME-1990-07 | 合格 | 089 | 89 | 一次本文・解答089と一致。 |
| AIME-1991-02 | 合格 | 840 | 840 | 一次本文・解答840と一致。反復の検査は式の文字列/AST照合で、配置も長さも評価していない。 |
| AIME-1991-12 | 合格 | 677 | 677 | 一次本文・解答677と一致。 |
| AIME-1991-14 | 合格 | 384 | 384 | 一次本文・解答384と一致。 |
| AIME-1992-09 | 除外候補 | 未入手 | 164 | 一次資料で照合不能(取得失敗)：1992 Problems/Answer Key。HF二次資料との読み合わせに明白な修正点はないが一次確認の代わりにならない。 |
| AIME-1992-14 | 除外候補 | 未入手 | 94 | 一次資料で照合不能(取得失敗)：1992 Problems/Answer Key。参考答94を一次確認済みと扱わない。 |
| AIME-1993-02 | 除外候補 | 未入手 | 580 | 一次資料で照合不能(取得失敗)：1993 Problems/Answer Key。参考答580を一次確認済みと扱わない。 |
| AIME-1993-12 | 除外候補 | 未入手 | 344 | 一次資料で照合不能(取得失敗)：1993 Problems/Answer Key。参考答344を一次確認済みと扱わない。 |
| AIME-1993-13 | 除外候補 | 未入手 | 163 | 一次資料で照合不能(取得失敗)：1993 Problems/Answer Key。参考答163を一次確認済みと扱わない。 |
| AIME-1993-15 | 除外候補 | 未入手 | 997 | 一次資料で照合不能(取得失敗)：1993 Problems/Answer Key。参考答997を一次確認済みと扱わない。 |
| AIME-1994-02 | 除外候補 | 未入手 | 312 | 一次資料で照合不能(取得失敗)：1994 Answer Key。Problems本文は確認済みだが、HF参考答312は未照合。 |
| AIME-1994-08 | 除外候補 | 未入手 | 315 | 一次資料で照合不能(取得失敗)：1994 Answer Key。Problems本文は確認済みだが、HF参考答315は未照合。 |
| AIME-1994-10 | 除外候補 | 未入手 | 450 | 一次資料で照合不能(取得失敗)：1994 Answer Key。Problems本文は確認済みだが、HF参考答450は未照合。 |
| AIME-1995-04 | 合格 | 224 | 224 | 一次本文・解答224と一致。 |
| AIME-1995-09 | 合格 | 616 | 616 | 一次本文・解答616と一致。画像の必須追加条件はなく本文で完結。 |
| AIME-1996-13 | 合格 | 065 | 65 | 一次本文・解答065と一致。現行版には必要なt>=1が既に入っている。 |
| AIME-1996-15 | 合格 | 777 | 777 | 一次本文・解答777と一致。 |
| AIME-1997-04 | 合格 | 017 | 17 | 一次本文・解答017と一致。 |
| AIME-1997-07 | 合格 | 198 | 198 | 一次本文・解答198と一致。 |
| AIME-1998-06 | 合格 | 308 | 308 | 一次本文・解答308と一致。 |
| AIME-1999-02 | 除外候補 | 未入手 | 118 | 一次資料で照合不能(取得失敗)：1999 Problems/Answer Key。HF参考答118は未照合。八つの合同枝はASTでも全数確認済み。 |
| AIME-1999-09 | 除外候補 | 未入手 | 259 | 一次資料で照合不能(取得失敗)：1999 Problems/Answer Key。HF参考答259は未照合。 |
| AIME-1999-12 | 除外候補 | 未入手 | 345 | 一次資料で照合不能(取得失敗)：1999 Problems/Answer Key。HF参考答345は未照合。 |
| AIME-1999-14 | 除外候補 | 未入手 | 463 | 一次資料で照合不能(取得失敗)：1999 Problems/Answer Key。HF参考答463は未照合。 |
| HMMT-2012-FEB-GUTS-01 | 除外候補 | 未入手 | \sqrt{10} | 公式答え未入手。指定保存資料にGUTS冊子がなく、問題番号もcorpus indexのまま未確認。参考答sqrt(10)は一次未照合。 |
| HMMT-2013-FEB-TEAM-03 | 除外候補 | 未入手 | \frac{7}{2} | 公式答え未入手。TEAM冊子・公式番号が未確認。参考答7/2の一致は判定不能。 |
| HMMT-2014-FEB-TEAM-08 | 除外候補 | 未入手 | 96 / 41 | 公式答え未入手。TEAM冊子・公式番号が未確認。参考答96/41の一致は判定不能。 |
| HMMT-2015-FEB-GUTS-02 | 除外候補 | 未入手 | 2 | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答2の一致は判定不能。 |
| HMMT-2016-FEB-GEO-01 | 修正要 | {2, 6} | なし | 公式答え{2,6}の転記は一致。修正対象は幾何DSLでなく採点・出力契約。公開結果モデルはanswersリストを持つため、スカラーtargetだけを根拠に表現不能とはしない。一方2または6の一方だけで正答扱いすることは不可。 |
| HMMT-2016-FEB-GUTS-03 | 除外候補 | 未入手 | \sqrt{2} | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答sqrt(2)の一致は判定不能。 |
| HMMT-2016-FEB-TEAM-03 | 除外候補 | 未入手 | 14040 | 公式答え未入手。TEAM冊子・公式番号が未確認。参考答14040の一致は判定不能。 |
| HMMT-2016-FEB-GUTS-10 | 除外候補 | 未入手 | \frac{91}{6} | 公式答え未入手。GUTS冊子・公式番号が未確認。類似するGEO-02と本文が異なるため照合済みにはできず、参考答91/6も未確認。 |
| HMMT-2017-FEB-GUTS-06 | 除外候補 | 未入手 | 169 | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答169の一致は判定不能。 |
| HMMT-2020-FEB-GUTS-02 | 除外候補 | 未入手 | 33^{\circ} | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答33度の一致は判定不能。 |
| HMMT-2021-FEB-GUTS-03 | 除外候補 | 未入手 | 673 | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答673の一致は判定不能。 |
| HMMT-2021-FEB-GUTS-09 | 除外候補 | 未入手 | 141 | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答141の一致は判定不能。 |
| HMMT-2022-FEB-GUTS-01 | 除外候補 | 未入手 | 3 | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答3の一致は判定不能。 |
| HMMT-2022-FEB-TEAM-03 | 除外候補 | 未入手 | \sqrt{3}R | 公式答え未入手。TEAM冊子・公式番号が未確認。単位正規化の対応は記号的に確認したが、公式答えと原問の証明要求は未完了。 |
| HMMT-2022-FEB-GEO-07 | 合格 | 16902 | なし | 公式問題PDF p1と解答PDF p3の16902に一致。抽出テキストで崩れたsqrt(a/b)をPDFで確認。 |
| HMMT-2022-FEB-GEO-08 | 合格 | 2402 | なし | 公式問題PDF p1-2と解答PDF p4の2402に一致。 |
| HMMT-2023-FEB-GEO-06 | 合格 | 68 | なし | 公式問題PDF p1と解答PDF p3の68に一致。 |
| HMMT-2024-FEB-GUTS-06 | 除外候補 | 未入手 | \frac{\sqrt{7}}{12} | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答sqrt(7)/12の一致は判定不能。 |

## 除外候補27問（理由付き固定一覧）

機械可読な同一一覧：[exclusions.csv](exclusions.csv)。

| ID | 一次資料の不足と理由 |
|---|---|
| AIME-1992-09 | 一次資料で照合不能(取得失敗)：1992 Problems/Answer Key。HF二次資料との読み合わせに明白な修正点はないが一次確認の代わりにならない。 |
| AIME-1992-14 | 一次資料で照合不能(取得失敗)：1992 Problems/Answer Key。参考答94を一次確認済みと扱わない。 |
| AIME-1993-02 | 一次資料で照合不能(取得失敗)：1993 Problems/Answer Key。参考答580を一次確認済みと扱わない。 |
| AIME-1993-12 | 一次資料で照合不能(取得失敗)：1993 Problems/Answer Key。参考答344を一次確認済みと扱わない。 |
| AIME-1993-13 | 一次資料で照合不能(取得失敗)：1993 Problems/Answer Key。参考答163を一次確認済みと扱わない。 |
| AIME-1993-15 | 一次資料で照合不能(取得失敗)：1993 Problems/Answer Key。参考答997を一次確認済みと扱わない。 |
| AIME-1994-02 | 一次資料で照合不能(取得失敗)：1994 Answer Key。Problems本文は確認済みだが、HF参考答312は未照合。 |
| AIME-1994-08 | 一次資料で照合不能(取得失敗)：1994 Answer Key。Problems本文は確認済みだが、HF参考答315は未照合。 |
| AIME-1994-10 | 一次資料で照合不能(取得失敗)：1994 Answer Key。Problems本文は確認済みだが、HF参考答450は未照合。 |
| AIME-1999-02 | 一次資料で照合不能(取得失敗)：1999 Problems/Answer Key。HF参考答118は未照合。八つの合同枝はASTでも全数確認済み。 |
| AIME-1999-09 | 一次資料で照合不能(取得失敗)：1999 Problems/Answer Key。HF参考答259は未照合。 |
| AIME-1999-12 | 一次資料で照合不能(取得失敗)：1999 Problems/Answer Key。HF参考答345は未照合。 |
| AIME-1999-14 | 一次資料で照合不能(取得失敗)：1999 Problems/Answer Key。HF参考答463は未照合。 |
| HMMT-2012-FEB-GUTS-01 | 公式答え未入手。指定保存資料にGUTS冊子がなく、問題番号もcorpus indexのまま未確認。参考答sqrt(10)は一次未照合。 |
| HMMT-2013-FEB-TEAM-03 | 公式答え未入手。TEAM冊子・公式番号が未確認。参考答7/2の一致は判定不能。 |
| HMMT-2014-FEB-TEAM-08 | 公式答え未入手。TEAM冊子・公式番号が未確認。参考答96/41の一致は判定不能。 |
| HMMT-2015-FEB-GUTS-02 | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答2の一致は判定不能。 |
| HMMT-2016-FEB-GUTS-03 | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答sqrt(2)の一致は判定不能。 |
| HMMT-2016-FEB-TEAM-03 | 公式答え未入手。TEAM冊子・公式番号が未確認。参考答14040の一致は判定不能。 |
| HMMT-2016-FEB-GUTS-10 | 公式答え未入手。GUTS冊子・公式番号が未確認。類似するGEO-02と本文が異なるため照合済みにはできず、参考答91/6も未確認。 |
| HMMT-2017-FEB-GUTS-06 | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答169の一致は判定不能。 |
| HMMT-2020-FEB-GUTS-02 | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答33度の一致は判定不能。 |
| HMMT-2021-FEB-GUTS-03 | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答673の一致は判定不能。 |
| HMMT-2021-FEB-GUTS-09 | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答141の一致は判定不能。 |
| HMMT-2022-FEB-GUTS-01 | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答3の一致は判定不能。 |
| HMMT-2022-FEB-TEAM-03 | 公式答え未入手。TEAM冊子・公式番号が未確認。単位正規化の対応は記号的に確認したが、公式答えと原問の証明要求は未完了。 |
| HMMT-2024-FEB-GUTS-06 | 公式答え未入手。GUTS冊子・公式番号が未確認。参考答sqrt(7)/12の一致は判定不能。 |

## 静的検査・保存範囲

[static-checks.json](static-checks.json)：54問・2,239式、JSONモデル/AST/関数名/引数/定義順エラー0件。手作業監査に加え、次の反復は添字と式のASTを全数確認した。

- AIME 1991-02：668等分点と335本の距離和。
- AIME 1993-02：40日分の方向周期と負号。
- AIME 1999-02：合同四角形の8対応と各6距離等式。
- HMMT 2016 GEO-01：12直角、固定辺以外の11辺長、非隣接54辺組の非交差条件。
- 凸多角形4問：全辺と非隣接頂点の外積条件。HMMT 2016 GUTS-03：八角形全頂点の中心角。HMMT 2022 GEO-07：第2最大用の全6ペア。

[input-snapshot.json](input-snapshot.json)の元ファイル335本（primary/を含む）は監査開始時とSHA-256不変。元DSL・cases・manifest・公式答記録は変更していない。追加・更新はaudit/内のprimary/以外のみ。ネットワーク、git fetch、commit、push、環境変更、指定作業フォルダ外への書込みは行っていない。最大ファイルサイズも最後の[delivery-checks.json](delivery-checks.json)に記録する。

AST検査スクリプトは`geosolver.engine`、`geosolver.geometry`、NumPy、SciPy、SymPyをimportしていないことも検査した。GeometryProblemのモデル検査とAST専用の_expression_issuesだけを使い、式を評価するvalidateやengine_documentは呼んでいない。これは禁止した実験の代替計測ではない。

監査の再確認（書込み先は本監査フォルダのみ、ソルバーは動かさない）：

```bash
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/unseen-1983/audit/verify_audit_static.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/unseen-1983/audit/collect_hmmt_evidence.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/unseen-1983/audit/build_report.py
```

手作業判定の原記録は[reviews.jsonl](reviews.jsonl)。prepare_evidence.pyは監査開始時の抽出・hash記録用であり、既存input-snapshot.jsonを更新して基準を動かすために再実行しない。

## 問題ごとの読み合わせ記録

### AIME-1983-04 — 合格

**判定理由：** 一次本文・解答026と一致し、条件と目標に修正点なし。

- 原文（一次）：[1983_AIME_Problems.html](primary/aops/1983_AIME_Problems.html)（Problem_4; line 620）。一次本文照合済み。
- 答え（一次）：**026**。[1983_AIME_Answer_Key.html](primary/aops/1983_AIME_Answer_Key.html)（解答順序リスト第4項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`26`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：半径sqrt(50)、AB=6、BC=2、直角ABC、A/Cの円周上を原文と照合。座標固定は合同変換のみ。
- 枝・不等式・非退化：notched circleの図の接続をasyの記述で確認。Bを円内部に置くq2が切欠きの枝を指定する。描画座標・asy内の解由来数値は採用しない。
- 目標量：BOの距離二乗を直接求め、整数化の取り違えなし。
- 入力：[元DSL](../dsl/AIME-1983-04.json)。SHA-256 `f3604f59255096023114b8a5890e59d9541a16a59d673017d123c0a519874c2e`。AST合格。

### AIME-1983-12 — 合格

**判定理由：** 一次本文・解答065と一致。有限範囲への整数証人の切詰めはしていない。

- 原文（一次）：[1983_AIME_Problems.html](primary/aops/1983_AIME_Problems.html)（Problem_12; line 654）。一次本文照合済み。
- 答え（一次）：**065**。[1983_AIME_Answer_Key.html](primary/aops/1983_AIME_Answer_Key.html)（解答順序リスト第12項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`65`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：AB=10a+b、CD=10b+a、a/bの十進桁範囲、直径と垂直弦、円周上C/Dを保持。OH=p/qと整数p,qにより正の有理数条件を保持。
- 枝・不等式・非退化：h>0は左右鏡映の固定で目標を変えない。q>0、p>0。図画像は未保存だが本文だけで条件が完結し、C/Dの上下交換にも依存しない。
- 目標量：直径Distance(A,B)が元の二桁整数そのもの。
- 入力：[元DSL](../dsl/AIME-1983-12.json)。SHA-256 `b6ebcb828da4aa856c94f583431e96d46d171a2c344225bcf3e7e0f9127e3c12`。AST合格。

### AIME-1983-14 — 合格

**判定理由：** 一次本文・解答130と一致し、非退化とPの両側の枝を明示。

- 原文（一次）：[1983_AIME_Problems.html](primary/aops/1983_AIME_Problems.html)（Problem_14; line 663）。一次本文照合済み。
- 答え（一次）：**130**。[1983_AIME_Answer_Key.html](primary/aops/1983_AIME_Answer_Key.html)（解答順序リスト第14項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`130`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：二円半径8/6、中心距離12、Pが両円上、Q/Rが各円上、Q/P/R共線と等長を保持。
- 枝・不等式・非退化：py>0は鏡映固定。QP>0とPからQ/Rへの内積<0でQ=P、R=Pおよび同方向の誤枝を除く。asyのsqrt(130)は図の生成用でありDSLにはない。
- 目標量：QP²を保持。
- 入力：[元DSL](../dsl/AIME-1983-14.json)。SHA-256 `1c650b81b9da5ef8710901c41f08bd46b3167ed28cf8ae407e09701751172a24`。AST合格。

### AIME-1984-03 — 合格

**判定理由：** 一次本文・図の接続・解答144と一致。

- 原文（一次）：[1984_AIME_Problems.html](primary/aops/1984_AIME_Problems.html)（Problem_3; line 614）。一次本文照合済み。
- 答え（一次）：**144**。[1984_AIME_Answer_Key.html](primary/aops/1984_AIME_Answer_Key.html)（解答順序リスト第3項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`144`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：Pを通る三本の平行線の交点を直接定義。AB側/AC側/BC側のPを頂点とする小三角形に面積4/9/49を対応させ、一次図のt1/t2/t3と一致。
- 枝・不等式・非退化：b>0、cy>0と三辺への正の外積で非退化ABCとPの厳密な内部を保持。
- 目標量：大三角形Area(A,B,C)を保持。
- 入力：[元DSL](../dsl/AIME-1984-03.json)。SHA-256 `aa9d451654881d05e52066b736cfee0579e03b61009221c561a6f018394552af`。AST合格。

### AIME-1984-06 — 合格

**判定理由：** 一次本文・解答024と一致。面積式は定義の照合のみで数値評価していない。

- 原文（一次）：[1984_AIME_Problems.html](primary/aops/1984_AIME_Problems.html)（Problem_6; line 627）。一次本文照合済み。
- 答え（一次）：**024**。[1984_AIME_Answer_Key.html](primary/aops/1984_AIME_Answer_Key.html)（解答順序リスト第6項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`24`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：三中心・半径3を保持。単位法線(nx,ny)の符号付き距離を[-3,3]へ切り詰めた円欠面積F(d)=9acos(-d/3)+d sqrt(9-d²)を足し、総面積の半分27pi/2に等置。線がBを通るので中円は9pi/2。
- 枝・不等式・非退化：法線の符号をny>0で固定。ny=0の垂直線では他二中心の距離が-3と2となり面積半分を満たせない（円欠面積の厳密単調性）ため除外に損失なし。
- 目標量：直線方向(-ny,nx)の傾き絶対値abs(nx/ny)を保持。
- 入力：[元DSL](../dsl/AIME-1984-06.json)。SHA-256 `d9ab59d29bd6d6e317d77e830123c358228c9e8ac6d6ef955a0bac67fb9a69bb`。AST合格。

### AIME-1985-09 — 合格

**判定理由：** 一次本文・解答049と一致。

- 原文（一次）：[1985_AIME_Problems.html](primary/aops/1985_AIME_Problems.html)（Problem_9; line 642）。一次本文照合済み。
- 答え（一次）：**049**。[1985_AIME_Answer_Key.html](primary/aops/1985_AIME_Answer_Key.html)（解答順序リスト第9項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`49`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：同一円の平行弦長2/3/4と中心角alpha/beta/alpha+betaを直接指定。alpha,beta>0、和<pi、cos(alpha)>0を保持。
- 枝・不等式・非退化：弦の中心からの上下位置は原文で限定されず両方を残す。r>0、既約分数の整数m,n,u,v、n>0、um+vn=1を保持。
- 目標量：cos(alpha)=m/nの既約正分数の分子分母和m+nを保持。
- 入力：[元DSL](../dsl/AIME-1985-09.json)。SHA-256 `c25e7b6d3c57b5e4cfb1e1039caf3627f2dc2f8eba095903ab7f42bee4a707ac`。AST合格。

### AIME-1985-11 — 合格

**判定理由：** 一次本文・解答085と一致。

- 原文（一次）：[1985_AIME_Problems.html](primary/aops/1985_AIME_Problems.html)（Problem_11; line 652）。一次本文照合済み。
- 答え（一次）：**085**。[1985_AIME_Answer_Key.html](primary/aops/1985_AIME_Answer_Key.html)（解答順序リスト第11項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`85`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：二焦点(9,20)/(49,55)、T=(t,0)、距離和Lを保持。t方向の距離和の微分ゼロがx軸への接線条件。
- 枝・不等式・非退化：焦点がともにx軸より上にあるので距離の分母は正で、軸上距離和は厳密凸。停留条件が唯一の接点を表し、L>F1F2で楕円の非退化を保持。
- 目標量：焦点距離和Lは長軸の全長2aであり、半長軸との取り違えなし。
- 入力：[元DSL](../dsl/AIME-1985-11.json)。SHA-256 `b03635c60b7fdfee52deb646fb857176c4955637a2b49ea2796d06f0a2c43fcc`。AST合格。

### AIME-1986-09 — 合格

**判定理由：** 一次本文・解答306と一致。

- 原文（一次）：[1986_AIME_Problems.html](primary/aops/1986_AIME_Problems.html)（Problem_9; line 639）。一次本文照合済み。
- 答え（一次）：**306**。[1986_AIME_Answer_Key.html](primary/aops/1986_AIME_Answer_Key.html)（解答順序リスト第9項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`306`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：AB=425、BC=450、AC=510とPを通る三辺への平行線・両端交点を保持。三つの弦長を共通dに等置。
- 枝・不等式・非退化：cy>0は鏡映固定。三つの正の外積がPの内部、d>0が非退化を保証し、交点は対応する辺の内部になる。
- 目標量：共通線分長dそのもの。
- 入力：[元DSL](../dsl/AIME-1986-09.json)。SHA-256 `56e6d24e071e76c80761cbc23f53c0b32c2fb3c92cdb642782d9c4df3d759e46`。AST合格。

### AIME-1986-15 — 合格

**判定理由：** 一次本文・解答400と一致。

- 原文（一次）：[1986_AIME_Problems.html](primary/aops/1986_AIME_Problems.html)（Problem_15; line 663）。一次本文照合済み。
- 答え（一次）：**400**。[1986_AIME_Answer_Key.html](primary/aops/1986_AIME_Answer_Key.html)（解答順序リスト第15項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`400`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：未知A/B/C、AB=60、Cでの内積ゼロ、BC/ACの中点M/Nを定義。A,Mをy=x+3、B,Nをy=2x+4に置き、両中線を保持。
- 枝・不等式・非退化：Area(ABC)>0で頂点一致・共線を除外。絶対座標条件のため不当な座標固定なし。
- 目標量：符号なし三角形面積を保持。
- 入力：[元DSL](../dsl/AIME-1986-15.json)。SHA-256 `9b076391befdc6d07689ab6a89f2daec0b8f528ffc7ed7962f7fff8c7d56eda9`。AST合格。

### AIME-1987-09 — 合格

**判定理由：** 一次本文・解答033と一致。

- 原文（一次）：[1987_AIME_Problems.html](primary/aops/1987_AIME_Problems.html)（Problem_9; line 634）。一次本文照合済み。
- 答え（一次）：**033**。[1987_AIME_Answer_Key.html](primary/aops/1987_AIME_Answer_Key.html)（解答順序リスト第9項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`33`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：B直角、PA=10、PB=6と三つのP中心角の相等を保持。
- 枝・不等式・非退化：a,c,x,y>0、x/a+y/c<1で厳密な内部を指定。Angleは[0,pi]の通常角で内部の三等角に対応。画像本体は未保存だが本文条件で完結。
- 目標量：PCの長さそのもの。
- 入力：[元DSL](../dsl/AIME-1987-09.json)。SHA-256 `6b4e8d418c7fe5c79e3c6dd616ff21c4606f2e9766b1570239f2559a81cf79aa`。AST合格。

### AIME-1988-07 — 合格

**判定理由：** 一次本文・解答110と一致。

- 原文（一次）：[1988_AIME_Problems.html](primary/aops/1988_AIME_Problems.html)（Problem_7; line 632）。一次本文照合済み。
- 答え（一次）：**110**。[1988_AIME_Answer_Key.html](primary/aops/1988_AIME_Answer_Key.html)（解答順序リスト第7項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`110`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：高さの足HをBCの内部、BH=3、HC=17に固定。h>0とtan(CAB)=22/7を保持。BH/HCの入替えは鏡映・頂点名交換で面積不変。
- 枝・不等式・非退化：通常の三角形角でtanが正なので角CABは鋭角。q2の<pi/2は原条件の帰結であり過剰制約ではない。
- 目標量：ABCの面積を保持。
- 入力：[元DSL](../dsl/AIME-1988-07.json)。SHA-256 `05945ea140756eb257a5a078a116506f66763a5a2a7008f2ec45e625640cdbfb`。AST合格。

### AIME-1988-14 — 合格

**判定理由：** 一次本文・解答084と一致し、反射の係数比較が記号的に同値。

- 原文（一次）：[1988_AIME_Problems.html](primary/aops/1988_AIME_Problems.html)（Problem_14; line 667）。一次本文照合済み。
- 答え（一次）：**084**。[1988_AIME_Answer_Key.html](primary/aops/1988_AIME_Answer_Key.html)（解答順序リスト第14項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`84`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：y=2xで反射した基底ベクトルU/Vから逆反射（反射自身）の座標積を展開し、x²/xy/y²/定数の係数をk倍して対応させる。
- 枝・不等式・非退化：k!=0とx²係数12が方程式の尺度を固定。図上の少数点の代入だけで曲線全体を置換していない。
- 目標量：指定係数b*cを保持。
- 入力：[元DSL](../dsl/AIME-1988-14.json)。SHA-256 `3366dde319cf1965e899c07947ff6337f1f0121f071a9b3f24a66e0abc96a632`。AST合格。

### AIME-1990-07 — 合格

**判定理由：** 一次本文・解答089と一致。

- 原文（一次）：[1990_AIME_Problems.html](primary/aops/1990_AIME_Problems.html)（Problem_7; line 627）。一次本文照合済み。
- 答え（一次）：**089**。[1990_AIME_Answer_Key.html](primary/aops/1990_AIME_Answer_Key.html)（解答順序リスト第7項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`89`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：P/Q/Rの絶対座標を保持し、内心IとPを通る直線をax+2y+c=0に等置。
- 枝・不等式・非退化：Incenterにより内角二等分線を選び、外角二等分線を混ぜない。指定三角形は非共線。
- 目標量：指定された直線係数の和a+cを保持。
- 入力：[元DSL](../dsl/AIME-1990-07.json)。SHA-256 `a61bcf002e60671d69c5206276c3d1f07cf7883365a9b662f08577f859999df8`。AST合格。

### AIME-1991-02 — 合格

**判定理由：** 一次本文・解答840と一致。反復の検査は式の文字列/AST照合で、配置も長さも評価していない。

- 原文（一次）：[1991_AIME_Problems.html](primary/aops/1991_AIME_Problems.html)（Problem_2; line 606）。一次本文照合済み。
- 答え（一次）：**840**。[1991_AIME_Answer_Key.html](primary/aops/1991_AIME_Answer_Key.html)（解答順序リスト第2項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`840`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：4×3長方形、AB/CBとAD/CDの168等分をk=1..167について定義。全668個の等分点式と目標335項をASTテンプレートで全数照合済み。
- 枝・不等式・非退化：0<k/168<1の添字範囲を保持。構成済みの固定長方形なので追加自由変数・非退化条件は不要。
- 目標量：AC一回と二系列の線分167本ずつの長さ和。端点重複や168番目の追加なし。
- 入力：[元DSL](../dsl/AIME-1991-02.json)。SHA-256 `99ada126dc065aac5d43f33d1da86f0f56c0edc2b0550ba4d158166e3efe5af0`。AST合格。

### AIME-1991-12 — 合格

**判定理由：** 一次本文・解答677と一致。

- 原文（一次）：[1991_AIME_Problems.html](primary/aops/1991_AIME_Problems.html)（Problem_12; line 656）。一次本文照合済み。
- 答え（一次）：**677**。[1991_AIME_Answer_Key.html](primary/aops/1991_AIME_Answer_Key.html)（解答順序リスト第12項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`677`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：長方形の各辺内部P/Q/R/S、PB=15、BQ=20、四辺等長と対角線PR=30/QS=40を保持。
- 枝・不等式・非退化：w>15,h>20,0<rx<w,0<sy<hが辺上順序と凸性を保証。整数m,n,u,v、m,n>0、um+vn=1で既約正分数を保持。
- 目標量：長方形周長2(w+h)=m/nに対するm+nで、菱形周長との取り違えなし。
- 入力：[元DSL](../dsl/AIME-1991-12.json)。SHA-256 `22894bbff4eb2193bffebea194058d78fc8d555e3ff71a5567fb5d5ee59ece02`。AST合格。

### AIME-1991-14 — 合格

**判定理由：** 一次本文・解答384と一致。

- 原文（一次）：[1991_AIME_Problems.html](primary/aops/1991_AIME_Problems.html)（Problem_14; line 664）。一次本文照合済み。
- 答え（一次）：**384**。[1991_AIME_Answer_Key.html](primary/aops/1991_AIME_Answer_Key.html)（解答順序リスト第14項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`384`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：AB=31、残り五辺81、ABCの外接円上にD/E/Fを置く。
- 枝・不等式・非退化：各有向辺と他の全頂点の外積>0を24本指定し、円周上の順序・凸性・相異なる頂点を保証。自己交差六角形を混ぜない。
- 目標量：Aからの三対角線AC/AD/AEの和を保持。
- 入力：[元DSL](../dsl/AIME-1991-14.json)。SHA-256 `1eedb2130ca5e84f291b06ccf4b409bea117441e79b51776821ea96426968417`。AST合格。

### AIME-1992-09 — 除外候補

**判定理由：** 一次資料で照合不能(取得失敗)：1992 Problems/Answer Key。HF二次資料との読み合わせに明白な修正点はないが一次確認の代わりにならない。

- 原文（一次）：未入手。一次資料で照合不能(取得失敗)。
- 答え（一次）：**未入手**。未入手。一次答未入手につき比較不能。HF参考値のみ。
- 二次参考：`164`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：HF参考：台形AB=92/CD=19/BC=50/AD=70、AB上の中心P、半径rと両脚への垂足を保持。
- 枝・不等式・非退化：h>0、0<=p<=92、r>0、接点が線分BC/AD上にある条件を保持。既約分数の整数Bezout証人あり。
- 目標量：AP=m/nのm+nを保持。
- 入力：[元DSL](../dsl/AIME-1992-09.json)。SHA-256 `ee2cc903a768efe7bbc2964b6dc26374d0b48a8b5760f879d4544f5147e59a1e`。AST合格。

### AIME-1992-14 — 除外候補

**判定理由：** 一次資料で照合不能(取得失敗)：1992 Problems/Answer Key。参考答94を一次確認済みと扱わない。

- 原文（一次）：未入手。一次資料で照合不能(取得失敗)。
- 答え（一次）：**未入手**。未入手。一次答未入手につき比較不能。HF参考値のみ。
- 二次参考：`94`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：HF参考：三角形の三辺上A'/B'/C'と共点O、三つの距離比の和92を保持。
- 枝・不等式・非退化：各辺内点・O内部・全分母>0。端点の共点ではいずれかの分母が消えるため、厳密内点への制限は原文の定義可能性と整合。AB=1は比の相似正規化。
- 目標量：同じ三距離比の積を保持。
- 入力：[元DSL](../dsl/AIME-1992-14.json)。SHA-256 `0f56c79c096ce1439294fb1e2043308a689ffd1bc6fab965323e9cd0f1b5e41c`。AST合格。

### AIME-1993-02 — 除外候補

**判定理由：** 一次資料で照合不能(取得失敗)：1993 Problems/Answer Key。参考答580を一次確認済みと扱わない。

- 原文（一次）：未入手。一次資料で照合不能(取得失敗)。
- 答え（一次）：**未入手**。未入手。一次答未入手につき比較不能。HF参考値のみ。
- 二次参考：`580`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：HF参考：40日分の東北西南の循環と各日n²/2の移動をP0..P40の式で保持。
- 枝・不等式・非退化：西/南の-n**2/2はASTで-(n**2)/2となり符号は正しい。全40式をテンプレート照合し、実座標を計算しない。
- 目標量：40日後と始点の距離であり、移動距離総和ではない。
- 入力：[元DSL](../dsl/AIME-1993-02.json)。SHA-256 `e10774b7008ae6ec98998e321a0904755771e66cd2626084805b3a0f3615156a`。AST合格。

### AIME-1993-12 — 除外候補

**判定理由：** 一次資料で照合不能(取得失敗)：1993 Problems/Answer Key。参考答344を一次確認済みと扱わない。

- 原文（一次）：未入手。一次資料で照合不能(取得失敗)。
- 答え（一次）：**未入手**。未入手。一次答未入手につき比較不能。HF参考値のみ。
- 二次参考：`344`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：HF参考：A/B/Cの座標、内部始点(k,m)、六回のラベル選択と中点写像、P7=(14,92)を保持。
- 枝・不等式・非退化：各ziの0/1/2選択をorで全て残す。確率問題ではないので面ラベルの重複は結果の可能性を変えない。未知の出目を答えから固定していない。
- 目標量：始点の座標和k+mを保持。
- 入力：[元DSL](../dsl/AIME-1993-12.json)。SHA-256 `41851d9dd407a3d246dcb705db1ba49a0e28ed3855f208b3724086231eb0d72d`。AST合格。

### AIME-1993-13 — 除外候補

**判定理由：** 一次資料で照合不能(取得失敗)：1993 Problems/Answer Key。参考答163を一次確認済みと扱わない。

- 原文（一次）：未入手。一次資料で照合不能(取得失敗)。
- 答え（一次）：**未入手**。未入手。一次答未入手につき比較不能。HF参考値のみ。
- 二次参考：`163`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：HF参考：幅200の平行路、半径50、速度1/3、初期相互距離200と両時刻の視線接条件を保持。
- 枝・不等式・非退化：j+k<0は同方向の歩行で最初に遮蔽される手前側を指定。t>0と接点の線分上条件で延長線の接触を除く。既約分数条件あり。
- 目標量：遮蔽継続時間t=m/nのm+n。
- 入力：[元DSL](../dsl/AIME-1993-13.json)。SHA-256 `42e0b4aad9580a5185a4cbc28625c8e8b4f374243703b6541506c2589e77ff78`。AST合格。

### AIME-1993-15 — 除外候補

**判定理由：** 一次資料で照合不能(取得失敗)：1993 Problems/Answer Key。参考答997を一次確認済みと扱わない。

- 原文（一次）：未入手。一次資料で照合不能(取得失敗)。
- 答え（一次）：**未入手**。未入手。一次答未入手につき比較不能。HF参考値のみ。
- 二次参考：`997`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：HF参考：AB=1995/AC=1994/BC=1993、CからABへの高さH、ACH/BCHの内心からCHへの垂足R/Sを保持。
- 枝・不等式・非退化：cy>0、0<H.x<1995で二つの直角三角形を非退化にする。指定三辺は鋭角三角形なので高さ内部条件は整合。m,n>0と既約性あり。
- 目標量：RS=m/nのm+n。分数の通常の正分母表記を採用。
- 入力：[元DSL](../dsl/AIME-1993-15.json)。SHA-256 `ea0eb84003d0660c4216f31177a735dbf55d79a0060560214d43031aba128788`。AST合格。

### AIME-1994-02 — 除外候補

**判定理由：** 一次資料で照合不能(取得失敗)：1994 Answer Key。Problems本文は確認済みだが、HF参考答312は未照合。

- 原文（一次）：[1994_AIME_Problems.html](primary/aops/1994_AIME_Problems.html)（Problem_2; line 610）。一次本文照合済み。
- 答え（一次）：**未入手**。未入手。一次答未入手につき比較不能。HF参考値のみ。
- 二次参考：`312`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：一次本文確認：半径20の円と直径PQ=10の小円がPで内接。CDをQで小円へ接する縦線、正方形を小円の外側へ配置。
- 枝・不等式・非退化：s>0、y<0<y+sがQを辺CD内部に置く。A/Bの大円周条件を保持。整数m/nはm+sqrt(n)の文字名で、分数と混同しない。
- 目標量：AB=s=m+sqrt(n)に対するm+n。
- 入力：[元DSL](../dsl/AIME-1994-02.json)。SHA-256 `19168ed238ff33503e0406359c3591e7e3faba41457a15ed4d13ea44aa3bb837`。AST合格。

### AIME-1994-08 — 除外候補

**判定理由：** 一次資料で照合不能(取得失敗)：1994 Answer Key。Problems本文は確認済みだが、HF参考答315は未照合。

- 原文（一次）：[1994_AIME_Problems.html](primary/aops/1994_AIME_Problems.html)（Problem_8; line 650）。一次本文照合済み。
- 答え（一次）：**未入手**。未入手。一次答未入手につき比較不能。HF参考値のみ。
- 二次参考：`315`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：一次本文確認：(0,0),(a,11),(b,37)をそのまま置き三辺等長を保持。
- 枝・不等式・非退化：面積>0で非退化。a,bの符号は限定せず鏡像を残す。
- 目標量：座標の積a*bを保持。
- 入力：[元DSL](../dsl/AIME-1994-08.json)。SHA-256 `ef3343be85707a0b7774990cf28a2922bee7c0482f78f3253d03d264e31af05e`。AST合格。

### AIME-1994-10 — 除外候補

**判定理由：** 一次資料で照合不能(取得失敗)：1994 Answer Key。Problems本文は確認済みだが、HF参考答450は未照合。

- 原文（一次）：[1994_AIME_Problems.html](primary/aops/1994_AIME_Problems.html)（Problem_10; line 658）。一次本文照合済み。
- 答え（一次）：**未入手**。未入手。一次答未入手につき比較不能。HF参考値のみ。
- 二次参考：`450`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：一次本文確認：C直角、CからABへの垂足D、三辺a,b,cの整数性、BD=29³を保持。
- 枝・不等式・非退化：a,b,c>0で非退化。通常角Bのcosを正の既約m/nへ結び、整数Bezout証人を保持。
- 目標量：cos Bの分子分母和m+n。BDの立方と取り違えなし。
- 入力：[元DSL](../dsl/AIME-1994-10.json)。SHA-256 `13eaa39b72e8bffc6d9e4ca60949e631c082d6f3fda21a678a11f52099c9d762`。AST合格。

### AIME-1995-04 — 合格

**判定理由：** 一次本文・解答224と一致。

- 原文（一次）：[1995_AIME_Problems.html](primary/aops/1995_AIME_Problems.html)（Problem_4; line 622）。一次本文照合済み。
- 答え（一次）：**224**。[1995_AIME_Answer_Key.html](primary/aops/1995_AIME_Answer_Key.html)（解答順序リスト第4項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`224`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：半径3/6の円の外接距離9、半径9の大円への内接距離6/3を保持。共通単位法線から両小円中心への符号付き距離を同符号3/6に指定。
- 枝・不等式・非退化：符号付き距離が共通外接線を選ぶ。弦両端は大円と同一直線上、AB>0で同一点を除く。法線の符号選択は直線の向きだけ。
- 目標量：大円の弦ABの長さ二乗を保持。
- 入力：[元DSL](../dsl/AIME-1995-04.json)。SHA-256 `f56bf681d1128051135ccf4249ed6ed23078c3a02513e8e326cf89d749d576c8`。AST合格。

### AIME-1995-09 — 合格

**判定理由：** 一次本文・解答616と一致。画像の必須追加条件はなく本文で完結。

- 原文（一次）：[1995_AIME_Problems.html](primary/aops/1995_AIME_Problems.html)（Problem_9; line 645）。一次本文照合済み。
- 答え（一次）：**616**。[1995_AIME_Answer_Key.html](primary/aops/1995_AIME_Answer_Key.html)（解答順序リスト第9項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`616`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：二等辺ABC、AM=11、DがAM上でAD=10、BDC=3BACを通常角で保持。
- 枝・不等式・非退化：s>0で非退化、Dの高さ11-10は原文長さの差。整数a,bおよびb>=0は原文のa+sqrt(b)表現をそのまま保持。
- 目標量：周長=a+sqrt(b)に対するa+b。平方根の係数や周長そのものへのすり替えなし。
- 入力：[元DSL](../dsl/AIME-1995-09.json)。SHA-256 `39cfb4e30c3e10d5e2a02fde6c131f362551c644330715c91e84c7c41152787e`。AST合格。

### AIME-1996-13 — 合格

**判定理由：** 一次本文・解答065と一致。現行版には必要なt>=1が既に入っている。

- 原文（一次）：[1996_AIME_Problems.html](primary/aops/1996_AIME_Problems.html)（Problem_13; line 653）。一次本文照合済み。
- 答え（一次）：**065**。[1996_AIME_Answer_Key.html](primary/aops/1996_AIME_Answer_Key.html)（解答順序リスト第13項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`65`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：三辺sqrt(30)/sqrt(6)/sqrt(15)、BC中点M、D=A+t(M-A)、ADB直角を保持。
- 枝・不等式・非退化：t>=1で線分ADがBC中点まで達する条件を保持。AD>0、BD>0とcy>0で退化除外。m,n>0・整数Bezout証人で既約分数。
- 目標量：Area(ADB)/Area(ABC)=m/nのm+n。面積比の逆転なし。
- 入力：[元DSL](../dsl/AIME-1996-13.json)。SHA-256 `26d32973acac9f90b467cc3c78198dd8ebafef2d4d1e37290e38856940514a07`。AST合格。

### AIME-1996-15 — 合格

**判定理由：** 一次本文・解答777と一致。

- 原文（一次）：[1996_AIME_Problems.html](primary/aops/1996_AIME_Problems.html)（Problem_15; line 663）。一次本文照合済み。
- 答え（一次）：**777**。[1996_AIME_Answer_Key.html](primary/aops/1996_AIME_Answer_Key.html)（解答順序リスト第15項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`777`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：平行四辺形、対角線交点O=AC中点、二つの2倍角条件とACB=r AOBを保持。
- 枝・不等式・非退化：dy>0で非退化・鏡映固定。AB=1は全条件と目標が角比なので相似正規化として許される。
- 目標量：(1000*r)//1は最大整数floor(1000r)で、rや四捨五入への取り違えなし。
- 入力：[元DSL](../dsl/AIME-1996-15.json)。SHA-256 `6a6aae4721e04df587587ff6001a6c44ea2628241ab9164a2bee87887a8ad568`。AST合格。

### AIME-1997-04 — 合格

**判定理由：** 一次本文・解答017と一致。

- 原文（一次）：[1997_AIME_Problems.html](primary/aops/1997_AIME_Problems.html)（Problem_4; line 613）。一次本文照合済み。
- 答え（一次）：**017**。[1997_AIME_Answer_Key.html](primary/aops/1997_AIME_Answer_Key.html)（解答順序リスト第4項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`17`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：四円半径5/5/8/rの全六組を中心間距離=半径和として保持（AB=10は構成）。
- 枝・不等式・非退化：r>0なので囲む円の内接枝は除外。cy>0は鏡映固定。m,n>0・整数Bezout証人で既約分数を保持。
- 目標量：r=m/nに対するm+n。
- 入力：[元DSL](../dsl/AIME-1997-04.json)。SHA-256 `a5d74a6a0925ee13cbaffe63227fefc600dd173fe1562796ff3b922a0c27bd43`。AST合格。

### AIME-1997-07 — 合格

**判定理由：** 一次本文・解答198と一致。

- 原文（一次）：[1997_AIME_Problems.html](primary/aops/1997_AIME_Problems.html)（Problem_7; line 625）。一次本文照合済み。
- 答え（一次）：**198**。[1997_AIME_Answer_Key.html](primary/aops/1997_AIME_Answer_Key.html)（解答順序リスト第7項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`198`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：車速度(2/3,0)、嵐中心速度(1/2,-1/2)、初期中心(0,110)、半径51を両時刻で保持。
- 枝・不等式・非退化：0<t1<t2と二つの境界条件を保持。直線相対運動と円の二交点の時刻順が進入/退出に対応し、同じ交点二回を除く。
- 目標量：(t1+t2)/2を保持。
- 入力：[元DSL](../dsl/AIME-1997-07.json)。SHA-256 `5b1706a435bde7cb7911dea329f41ce6d108e1fce5dc0f1ec51430fb274ac246`。AST合格。

### AIME-1998-06 — 合格

**判定理由：** 一次本文・解答308と一致。

- 原文（一次）：[1998_AIME_Problems.html](primary/aops/1998_AIME_Problems.html)（Problem_6; line 628）。一次本文照合済み。
- 答え（一次）：**308**。[1998_AIME_Answer_Key.html](primary/aops/1998_AIME_Answer_Key.html)（解答順序リスト第6項）。一致（一次答とHF secondary_answer。先頭0は整数表記の差）。
- 二次参考：`308`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：平行四辺形、DAをAの先へ延長したP=-tD（t>0）、PCとAB/DBの交点Q/R、PQ=735/QR=112を保持。
- 枝・不等式・非退化：b,dy>0、Q/Rの線分上条件、P-Q-R-C順序の距離和を保持。鏡映・合同固定だけで尺度は変更しない。
- 目標量：RCを保持。
- 入力：[元DSL](../dsl/AIME-1998-06.json)。SHA-256 `7865b7a85754ba34efa870093a01fed654709fb7345695952f24b03f28fa9690`。AST合格。

### AIME-1999-02 — 除外候補

**判定理由：** 一次資料で照合不能(取得失敗)：1999 Problems/Answer Key。HF参考答118は未照合。八つの合同枝はASTでも全数確認済み。

- 原文（一次）：未入手。一次資料で照合不能(取得失敗)。
- 答え（一次）：**未入手**。未入手。一次答未入手につき比較不能。HF参考値のみ。
- 二次参考：`118`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：HF参考：絶対座標の平行四辺形、原点通過、向かい合う二組の辺の切断をeで選択。二四角形の全六点対距離を八つの巡回/反転対応で一致させる。
- 枝・不等式・非退化：隣接辺切断は三角形/五角形になり合同不可。頂点を含む合同切断は対角線だが、AC/BDと原点の行列式は非零。従って向かい合う辺の内点に限定しても原文の合同切断を失わない。
- 目標量：切断線の正の傾き=m/n、整数Bezout証人で既約、目標m+n。
- 入力：[元DSL](../dsl/AIME-1999-02.json)。SHA-256 `132bce8a265a34029130ccc90139234ef501a8731c4f693efb845477fc7d8c18`。AST合格。

### AIME-1999-09 — 除外候補

**判定理由：** 一次資料で照合不能(取得失敗)：1999 Problems/Answer Key。HF参考答259は未照合。

- 原文（一次）：未入手。一次資料で照合不能(取得失敗)。
- 答え（一次）：**未入手**。未入手。一次答未入手につき比較不能。HF参考値のみ。
- 二次参考：`259`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：HF参考：a,b>0、複素乗数w=(a,b)、|w|=8、|w-1|=|w|を保持。任意zでの等距離条件は両距離に|z|が掛かるためz=1の条件と同値。
- 枝・不等式・非退化：正のa/bと既約正分数条件を保持。全点条件を恣意的な一標本へ落としたものではなく、複素積の距離保存比による同値変換。
- 目標量：b²=m/nに対するm+n。
- 入力：[元DSL](../dsl/AIME-1999-09.json)。SHA-256 `ebc441e7a5d1608cf31a923f9600cd3fb6696cd47073f269f33c01704b5ca02a`。AST合格。

### AIME-1999-12 — 除外候補

**判定理由：** 一次資料で照合不能(取得失敗)：1999 Problems/Answer Key。HF参考答345は未照合。

- 原文（一次）：未入手。一次資料で照合不能(取得失敗)。
- 答え（一次）：**未入手**。未入手。一次答未入手につき比較不能。HF参考値のみ。
- 二次参考：`345`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：HF参考：AB=23+27、PがAから23、内心IのABへの垂足T=P、内接半径IT=21を保持。
- 枝・不等式・非退化：cy>0で非退化三角形。Incenterにより傍心の枝を混ぜず、内接円と線分接点を表す。
- 目標量：三辺長の和で元の周長を保持。
- 入力：[元DSL](../dsl/AIME-1999-12.json)。SHA-256 `64424fee99d9fb38475b505e85f337a0bc98811ced197bb35571c62e8303c563`。AST合格。

### AIME-1999-14 — 除外候補

**判定理由：** 一次資料で照合不能(取得失敗)：1999 Problems/Answer Key。HF参考答463は未照合。

- 原文（一次）：未入手。一次資料で照合不能(取得失敗)。
- 答え（一次）：**未入手**。未入手。一次答未入手につき比較不能。HF参考値のみ。
- 二次参考：`463`。HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。
- 条件：HF参考：三辺13/14/15、P内部、角PAB=PBC=PCAの巡回方向を保持。
- 枝・不等式・非退化：正の三外積とcy>0で内部・非退化。別のBrocard点の逆順角に取り違えなし。m,n>0と既約性あり。
- 目標量：tan(PAB)=m/nに対するm+n。
- 入力：[元DSL](../dsl/AIME-1999-14.json)。SHA-256 `03533e821553e1b9876e96c3f801cc1c7a27a223cca469600cc4956050e49814`。AST合格。

### HMMT-2012-FEB-GUTS-01 — 除外候補

**判定理由：** 公式答え未入手。指定保存資料にGUTS冊子がなく、問題番号もcorpus indexのまま未確認。参考答sqrt(10)は一次未照合。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`\sqrt{10}`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：辺2の正方形、AX=XB=sqrt(2)、Xが正方形の外部を保持。
- 枝・不等式・非退化：外部条件を四つの厳密不等式のorで指定。長さ条件と合わせて辺上/内部のXを除く。
- 目標量：五角形A-X-B-C-Dの五対角線AB/AC/XC/XD/BDのmaxを保持。
- 入力：[元DSL](../dsl/HMMT-2012-FEB-GUTS-01.json)。SHA-256 `313cfb118f2e6a515463eb234419a3c10a3ff79fadc9f812120e7bee9b40e227`。AST合格。

### HMMT-2013-FEB-TEAM-03 — 除外候補

**判定理由：** 公式答え未入手。TEAM冊子・公式番号が未確認。参考答7/2の一致は判定不能。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`\frac{7}{2}`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：ABC外心O、AC=7、AOCの円、BCへの接線条件、AB上の第二交点F、FOとBCの交点Eを保持。Cは構成上円周上なので接点C。
- 枝・不等式・非退化：c,ay>0、AOC面積>0、F!=A、F!=Oを明示。BCを直線として扱う点は一次本文の線分/直線表記を要確認。
- 目標量：BEの長さを保持。
- 入力：[元DSL](../dsl/HMMT-2013-FEB-TEAM-03.json)。SHA-256 `c20487e7f105b3f6ab9f1d7b1b78bbbbb4e0f3316b6c779bbe196566ddd4e69a`。AST合格。

### HMMT-2014-FEB-TEAM-08 — 除外候補

**判定理由：** 公式答え未入手。TEAM冊子・公式番号が未確認。参考答96/41の一致は判定不能。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`96 / 41`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：AB=4/AC=5/BC=6、三鋭角、外心O、垂足D、AOとBCの交点E、XY平行AO、YO垂直AXを保持。
- 枝・不等式・非退化：XはD/Eの厳密内点、YはAD上を0<=s<=1と解釈。A!=O,D!=E,X!=Y,Y!=Oを明示。一次の線分表記は未確認。
- 目標量：BXを保持。
- 入力：[元DSL](../dsl/HMMT-2014-FEB-TEAM-08.json)。SHA-256 `f8cdba7960fd49d2b2a4075a569b812c06d24ace51ba1f6256477911b8b18e80`。AST合格。

### HMMT-2015-FEB-GUTS-02 — 除外候補

**判定理由：** 公式答え未入手。GUTS冊子・公式番号が未確認。参考答2の一致は判定不能。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`2`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：AB=BC=CD=DE=1、ABC/ACD/ADEの直角を保持。
- 枝・不等式・非退化：各辺に対して他三頂点が厳密に左側という15条件で凸五角形の順序を指定。辺/対角線のゼロ長を排除。
- 目標量：AEを保持。
- 入力：[元DSL](../dsl/HMMT-2015-FEB-GUTS-02.json)。SHA-256 `5ff4313c102fe91dbeafbf9e5df8d2554ac4a8a823c4ab435798a877a79c9778`。AST合格。

### HMMT-2016-FEB-GEO-01 — 修正要

**判定理由：** 公式答え{2,6}の転記は一致。修正対象は幾何DSLでなく採点・出力契約。公開結果モデルはanswersリストを持つため、スカラーtargetだけを根拠に表現不能とはしない。一方2または6の一方だけで正答扱いすることは不可。

- 原文（一次）：[hmmt-2016-geo-problems.pdf](/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2016-geo-problems.pdf)（PDF p1; 同名.txt line 4）。公式本文照合済み（保存テキスト＋PDF目視）。
- 答え（一次）：**{2, 6}**。[hmmt-2016-geo-solutions.pdf](/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2016-geo-solutions.pdf)（PDF p1; 同名.txt Answer line 8）。一致（保存公式答と既存official_answer）。HF二次答はこの行に存在せず比較対象なし。
- 二次参考：`なし`。この行にはHF二次答の保存値なし。既存official_answerを保存公式原資料へ再照合。
- 条件：公式問題PDF p1と照合：QWARTZSPHINXの順序、全辺2、各角90/270度を隣接辺直交で保持。QWを水平固定した後は全辺が軸平行。
- 枝・不等式・非退化：非隣接54辺組の閉包の矩形分離を全組要求するので非交差と頂点相異を保持。凹凸・左右の枝を恣意的に固定していない。
- 目標量：原問は全可能値の集合、公式解答は{2,6}（PDF p1）。target=Area(S,I,X)は各許容配置の量として正しく、その像の集合が答え。既存READMEが認める集合採点未実装を解消し、完全な答え集合との一致を要求する必要がある。
- 入力：[元DSL](../dsl/HMMT-2016-FEB-GEO-01.json)。SHA-256 `40f7619eabc820552c73d68a1a2220eb0e2ea3c4113561ee37cc32db6ebba736`。AST合格。
- 提案：[修正案](proposed-fixes/HMMT-2016-FEB-GEO-01.md)。未適用。

### HMMT-2016-FEB-GUTS-03 — 除外候補

**判定理由：** 公式答え未入手。GUTS冊子・公式番号が未確認。参考答sqrt(2)の一致は判定不能。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`\sqrt{2}`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：単位円の正八角形P-R-O-B-L-E-M-Zを中心角pi/4で直接定義し、MR/OZの交点Iを構成。
- 枝・不等式・非退化：頂点順序と対角線名を保持。固定式を静的に読むだけで座標評価はしていない。
- 目標量：LIの長さを保持。
- 入力：[元DSL](../dsl/HMMT-2016-FEB-GUTS-03.json)。SHA-256 `d1fb9bf24c8b4e78a6942569cabce083a685e37b5d646c5b7478d8ebce09e0b7`。AST合格。

### HMMT-2016-FEB-TEAM-03 — 除外候補

**判定理由：** 公式答え未入手。TEAM冊子・公式番号が未確認。参考答14040の一致は判定不能。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`14040`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：鋭角ABC、内心I/外心O、AI=97、BC=144、OI垂直AIを保持。
- 枝・不等式・非退化：三頂点の内積>0で鋭角、ay>0で鏡映固定、OI>0で角OIAの定義域を保持。
- 目標量：ABC面積を保持。
- 入力：[元DSL](../dsl/HMMT-2016-FEB-TEAM-03.json)。SHA-256 `951d79daa648bf6ccf00fbd7068152c0830a11584c6867208a1604a7d3aad7fe`。AST合格。

### HMMT-2016-FEB-GUTS-10 — 除外候補

**判定理由：** 公式答え未入手。GUTS冊子・公式番号が未確認。類似するGEO-02と本文が異なるため照合済みにはできず、参考答91/6も未確認。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`\frac{91}{6}`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：13/14/15三角形の外心O、AOB/AOCの外心U/Vを保持。
- 枝・不等式・非退化：ay>0、AOB/AOCの面積>0で各外心を定義可能にする。
- 目標量：U/V間距離を保持。保存公式2016 GEO-02は垂心Hを使う別本文で、外心Oを使うこの行に公式答14を転用してはいけない。
- 入力：[元DSL](../dsl/HMMT-2016-FEB-GUTS-10.json)。SHA-256 `689c97d307e6a8f035ae7827493a0c4871d0f4b245094c4aea3ec1e01ca56ed7`。AST合格。

### HMMT-2017-FEB-GUTS-06 — 除外候補

**判定理由：** 公式答え未入手。GUTS冊子・公式番号が未確認。参考答169の一致は判定不能。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`169`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：凸四角形、AC=7/BD=17、M/P/N/QをAB/BC/CD/DAの中点へ順に対応。
- 枝・不等式・非退化：全8個の辺/他頂点の外積>0で凸性・非退化を保証。ACを水平に固定するだけで形の自由度は残す。
- 目標量：MN²+PQ²を保持。中点名P/Nの取り違えなし。
- 入力：[元DSL](../dsl/HMMT-2017-FEB-GUTS-06.json)。SHA-256 `651c1227a28e07084cd971dbfe1b27f2d4ad4e290b1152c3465bd6ad2baafb32`。AST合格。

### HMMT-2020-FEB-GUTS-02 — 除外候補

**判定理由：** 公式答え未入手。GUTS冊子・公式番号が未確認。参考答33度の一致は判定不能。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`33^{\circ}`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：単位外接円上A/B/C、M=(1,0)、MB=MC、D=(1,dy)のMでの接線、AM=AC、DMC=38度を保持。
- 枝・不等式・非退化：弦BCに対してA/Mを反対側に置きAを含まない弧中点を選ぶ。AMに対してD/C同側を正の外積積で指定。三角形面積と必要距離>0。
- 目標量：Degrees(Angle(A,C,B))で度数法のACBを保持。単位円正規化は角度目標と整合。
- 入力：[元DSL](../dsl/HMMT-2020-FEB-GUTS-02.json)。SHA-256 `b712d9961fa8ad073e5c9aca81073ecb16f238b830b253f9a881a9f047d823d6`。AST合格。

### HMMT-2021-FEB-GUTS-03 — 除外候補

**判定理由：** 公式答え未入手。GUTS冊子・公式番号が未確認。参考答673の一致は判定不能。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`673`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：半径2021、Dが90度位置、第一象限のC、扇形内接円の中心J/半径rと二境界への符号付き距離r、OJ+r=2021、CD=CEを保持。
- 枝・不等式・非退化：cx,cy,jx,r>0、jy=r、cy*jx-cx*jy=2021rで小円をOA/OCの内側へ置く。EはOJ延長上の円周接点、OJ>0で分母を保護。
- 目標量：r//1でfloor(r)を保持。
- 入力：[元DSL](../dsl/HMMT-2021-FEB-GUTS-03.json)。SHA-256 `d3b5dc0fb2f2d5822e45c8fabb253d8041ced67d2c4bfc21d6811f28da15cd53`。AST合格。

### HMMT-2021-FEB-GUTS-09 — 除外候補

**判定理由：** 公式答え未入手。GUTS冊子・公式番号が未確認。参考答141の一致は判定不能。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`141`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：共通中点原点、対称端点A/D,B/E,C/F、線分長7/10/18を保持。内積二乗条件が二直線の鋭角60度を表す。
- 枝・不等式・非退化：AB<AE、BC<BFが原文の端点方向の選択を保持。長さが正なのでゼロベクトルは除外される。
- 目標量：六三角形の符号なし面積和にsqrt(3)を掛けるK sqrt(3)を保持。
- 入力：[元DSL](../dsl/HMMT-2021-FEB-GUTS-09.json)。SHA-256 `78a43411f568b7c8ce022dae1c310b372d6b1b9598398b61abc7d39ab051e48c`。AST合格。

### HMMT-2022-FEB-GUTS-01 — 除外候補

**判定理由：** 公式答え未入手。GUTS冊子・公式番号が未確認。参考答3の一致は判定不能。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`3`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：正2022角形の一中心角2pi/2022、正の外接半径r、周長2022*PQ=157/25（6.28の厳密表記）を保持。
- 枝・不等式・非退化：r>0で非退化。最近整数の半整数タイ規則は原文で未指定だが、この与件は通常の最近整数を問うものとして+1/2後のfloorに対応。
- 目標量：2022*Area(OPQ)の最近整数をfloor(area+1/2)で表す。半径/周長と面積の混同なし。
- 入力：[元DSL](../dsl/HMMT-2022-FEB-GUTS-01.json)。SHA-256 `245ebd5d0cb564e7a429242f303e3ad0f92a8fc4b1da4ddb0d16cd6b6c37faba`。AST合格。

### HMMT-2022-FEB-TEAM-03 — 除外候補

**判定理由：** 公式答え未入手。TEAM冊子・公式番号が未確認。単位正規化の対応は記号的に確認したが、公式答えと原問の証明要求は未完了。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`\sqrt{3}R`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：鋭角ABC、単位外接円、弦中点を中心から正方向へ正規化した小弧AB/AC中点X/Y、内接円への直線XYの接条件を保持。
- 枝・不等式・非退化：鋭角・面積>0・弦中点と原点の距離>0・XY>0で通常の小弧と接線を指定。
- 目標量：R=1の相似正規化によりDSLはXY/Rという無次元係数を返す。原問の長さへはRを掛ける。参考答sqrt(3)Rをそのまま数値目標と比較してはならない。原問の証明要求も数値出力だけでは満たさない。
- 入力：[元DSL](../dsl/HMMT-2022-FEB-TEAM-03.json)。SHA-256 `cbebab77bf813e4d823a774e9aa54262871a1aede013a8997ace0557c51058c8`。AST合格。

### HMMT-2022-FEB-GEO-07 — 合格

**判定理由：** 公式問題PDF p1と解答PDF p3の16902に一致。抽出テキストで崩れたsqrt(a/b)をPDFで確認。

- 原文（一次）：[hmmt-2022-geo-problems.pdf](/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2022-geo-problems.pdf)（PDF p1; 同名.txt line 41）。公式本文照合済み（保存テキスト＋PDF目視）。
- 答え（一次）：**16902**。[hmmt-2022-geo-solutions.pdf](/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2022-geo-solutions.pdf)（PDF p3; 同名.txt Answer line 148）。一致（保存公式答と既存official_answer）。HF二次答はこの行に存在せず比較対象なし。
- 二次参考：`なし`。この行にはHF二次答の保存値なし。既存official_answerを保存公式原資料へ再照合。
- 条件：公式PDF p1：辺10の正方形内P、四外心の順序、PA+PB+PC+PD=23sqrt(2)、外心四角形面積50を保持。
- 枝・不等式・非退化：0<x,y<10で外心の基礎三角形は非退化。外心四角形の頂点は正方形中心の上下左右に並び、符号なしAreaが元の面積に対応。
- 目標量：四辺の全六ペアのminのmaxは重複を数える第2最大値。その二乗=a/b、a,b>0と整数Bezout証人で既約、目標100a+bを保持。
- 入力：[元DSL](../dsl/HMMT-2022-FEB-GEO-07.json)。SHA-256 `243b7dec3e96f2a9eed6ba61a8246b4ed9cec9257a71c9bce2a20e42da15ac84`。AST合格。

### HMMT-2022-FEB-GEO-08 — 合格

**判定理由：** 公式問題PDF p1-2と解答PDF p4の2402に一致。

- 原文（一次）：[hmmt-2022-geo-problems.pdf](/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2022-geo-problems.pdf)（PDF p1,2; 同名.txt line 45）。公式本文照合済み（保存テキスト＋PDF目視）。
- 答え（一次）：**2402**。[hmmt-2022-geo-solutions.pdf](/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2022-geo-solutions.pdf)（PDF p4; 同名.txt Answer line 187）。一致（保存公式答と既存official_answer）。HF二次答はこの行に存在せず比較対象なし。
- 二次参考：`なし`。この行にはHF二次答の保存値なし。既存official_answerを保存公式原資料へ再照合。
- 条件：公式PDF p1-2：焦点±f、短半軸7の端点Tの距離和50、Fの距離和50、H=FAB垂心、Hを通る準線とA/Bの焦点距離=準線距離を保持。
- 枝・不等式・非退化：f>0、fy>0は非退化と鏡映固定。準線方向の単位長とFから準線への距離>0で退化放物線を除く。
- 目標量：AH²+BH²を保持。長軸50/短軸14を半軸と取り違えていない。
- 入力：[元DSL](../dsl/HMMT-2022-FEB-GEO-08.json)。SHA-256 `044153464a2f3a8ac6eb0310f7b741815cee84f0f026b672229f7f07d804e078`。AST合格。

### HMMT-2023-FEB-GEO-06 — 合格

**判定理由：** 公式問題PDF p1と解答PDF p3の68に一致。

- 原文（一次）：[hmmt-2023-geo-problems.pdf](/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2023-geo-problems.pdf)（PDF p1; 同名.txt line 17）。公式本文照合済み（保存テキスト＋PDF目視）。
- 答え（一次）：**68**。[hmmt-2023-geo-solutions.pdf](/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2023-geo-solutions.pdf)（PDF p3; 同名.txt Answer line 110）。一致（保存公式答と既存official_answer）。HF二次答はこの行に存在せず比較対象なし。
- 二次参考：`なし`。この行にはHF二次答の保存値なし。既存official_answerを保存公式原資料へ再照合。
- 条件：公式PDF p1：CAB=ADB=30度、ABD=77度、BC=CD、BCD=n度を保持。
- 枝・不等式・非退化：全8個の辺/他頂点の外積>0で凸四角形の順序・非退化を保証。n>0とIsInteger(n)。AB=1は角度と辺比だけの問題の相似正規化。
- 目標量：度数法の整数nでありラジアン値ではない。
- 入力：[元DSL](../dsl/HMMT-2023-FEB-GEO-06.json)。SHA-256 `b878de21b4753343976d47a908b007e1af0de8bcd0a1974bba8f5a88c42aa76b`。AST合格。

### HMMT-2024-FEB-GUTS-06 — 除外候補

**判定理由：** 公式答え未入手。GUTS冊子・公式番号が未確認。参考答sqrt(7)/12の一致は判定不能。

- 原文（一次）：未入手。公式本文未入手（コーパス本文のみ）。
- 答え（一次）：**未入手**。未入手。公式答え未入手につき比較不能。コーパス参考値のみ。
- 二次参考：`\frac{\sqrt{7}}{12}`。保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。
- 条件：コーパス参考：BC=1、M/NがAB/ACの中点、P/QがBCの1/3・2/3、A/P/Qの円にM/Nを置き五点共円を保持。
- 枝・不等式・非退化：ay>0でABCとAPQの非退化・鏡映固定。三等分点P/Qの交換に目標は依存しない。
- 目標量：ABCの面積を保持。
- 入力：[元DSL](../dsl/HMMT-2024-FEB-GUTS-06.json)。SHA-256 `b1835a5e644475fabe725fe842dfccbf589f3aa53ee0efaf4b0153004ee35e6a`。AST合格。

