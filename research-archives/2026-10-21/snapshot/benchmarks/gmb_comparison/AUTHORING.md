# 36問の変換・監査契約

本作業は実験準備であり、36問をGeoSolverへ渡して探索・精密化・性能測定しない。
既存のGMB成績に合わせたDSL・初期値・許容誤差の調整もしない。
元のsolver-a0、GMB実装、既存323問、過去artifact、無関係な研究文書は変更しない。

## 入力

- 公式GMB commit: f070afe18ed874b3a31db519ea6f593f40a1be00。
- `benchmarks/gmb/.runtime/source/problems/IMO/*.smt2` の公開36問。
- 原文は公式IMO英語問題PDF。年別公式ページのDownload PDFから確認したURLは
  `https://www.imo-official.org/assets/documents/problems/<year>/<year>_eng.pdf`。
  旧 `/problems/<year>/eng.pdf` は調査時点で404のため使わない。
- 原資料の作業用保存先はrepo外の `/home/kabatan/work/solver-research-assets/gmb-comparison-source-materials/imo/`。
- 各問題は `cases/IMO_YYYY_PN.json`（GeometryProblem公開形）と
  `audit/IMO_YYYY_PN.json`（意味監査）を持つ。

## 数学的な変換

1. targetは全問文字列 `0`。結論は条件へ追加せず、auditのgoalへ分離する。
2. 同一の図形配置を表すだけの平行移動・回転・正の一様拡大縮小を除く。
   原文で相異なることが保証され、長さの絶対指定を壊さない二点を `(0,0),(1,0)` にできる。
   どの二点か、非一致の根拠、尺度不変性を問題ごとに記録する。
3. 残りの形の自由度は固定しない。鏡映の同値性を証明していない場合、上下どちらも残す。
   点数と等式数の単純な差を理由に座標を追加固定しない。
4. 原文が定める作図を直接構成にする。証明由来の補助条件・GMB出力座標・収束を助ける
   特殊三角形等は追加しない。
5. 交点の番号を機械的に翻訳しない。`rs-neq`はexclude等で意味を保持する。
   `rs-arbitrary`に一意の幾何枝が指定されていない場合、まず原文を確認する。
   必要なら交点を未知点＋両図形への所属で表し、その表現選択を明記する。
6. `OnLine`等の数値残差は `left = 0` のRelationConditionにする。bool guardと混同しない。
7. 辺の内部・半直線・点順・角の向き・外接/内接・非退化条件を省略しない。
   sourceにない全点間最小距離や単純な全点相異条件も追加しない。
8. 原文と公開GMBLの条件が食い違う場合、片側だけ黙って修正して既存GMB成績と比較しない。
   不一致を記録し、対応方針を確認する。入力ファイルを作れることと比較可能性を分ける。

## audit JSON

各auditは少なくとも次を持つ。

- `case_id`
- `source`: `official_url`, `gmbl_relative_path`, `gmbl_sha256`, `official_pdf_sha256`
- `normalization`: `anchors`, `fixed_coordinates`, `removed_continuous_dof`, `justification`,
  `scale_invariant`, `reflection_fixed`
- `clauses`: 原文の仮定ごとに `id`, `statement_ja`（要約）, `gmbl`, `geosolver`, `status`
- `goal`: 証明/求値すべき結論の要約と、探索に含めなかったこと
- `source_differences`: 原文/GMBL間およびGMBの実行上の制限との差
- `open_issues`: 不確定点。疑わしい点は空欄にせずここへ記録する。
- `author_review`: 担当者、読んだ一次資料、静的検査結果
- `comparison_status`: `draft` または `blocked`（独立監査完了前にreadyとしない）

`gmbl`と`geosolver`は読み手が該当条件を特定できる文字列配列とする。
本文全体の転載ではなく、数学的条件の日本語要約・参照URL・hashを保存する。

## 検査

- authorとは別の担当者が全36問を再確認する。
- 公開モデル・validator・compilerによる静的検査は可。36問のsolve、最適化、精密化は不可。
- 共通検査器はsolverの幾何演算を採点根拠に再利用しない。
- 人工例で変換、枝、scale、条件破壊、自由度残存、矛盾条件を検査する。
- 保存済みGMB座標の採点は、規則固定後の別工程とする。本準備中に結果を見て閾値を調整しない。
- 本比較の停止/受理/計時契約が確認できなければ実行をロックする。

## 分担

- 2000-2006（12問）、2007-2013（13問）、2014-2020（11問）のauthorは各自のcases/auditだけを編集。
- 共通検査器担当は独立した検査moduleと専用testsだけを編集。
- 独立reviewerは `reviews/` 内に所見を記録。author入力を直接書き換えない。
- rootは原資料・統合manifest・静的検査・計測準備・全体整合性を担当。
- branch/worktreeの追加、commit、pushは各担当で行わない。

## 原問題へそろえることへの承認後

2026-08-31に、数学の原問題を基準とし、公式GMB入力との差を明示する方針が承認された。
2000 P1・2015 P3の不足条件だけを `gmbl-original-aligned/` の別ファイルへ追加した。
公式GMB原本、旧audit/reviewのJSON、過去の測定結果は保存する。

旧auditの `blocked` は「未変更の公式GMB入力との比較」についての記録である。
これを削除せず、新旧入力・GeoSolver DSL・旧監査のhashに結び付いた
`reviews/alignment/` の補足レビューで、承認した不足条件に限って解消する。
入力台帳 `input-adjustments.json` で2問だけを切り替え、事前検査に実際の選択結果を保存する。
新たな構成・結論の混入や、無関係な構文不正・hash不一致を、この承認で免除しない。
