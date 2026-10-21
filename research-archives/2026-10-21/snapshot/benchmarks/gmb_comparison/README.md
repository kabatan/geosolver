# GMB公開36問とGeoSolverの比較準備

目的は、**問題の仮定を満たす非退化な配置を一つ出せるか**を、同じPC・1コア・180秒で比較すること。
証明の発見、厳密な座標の出力、すべての配置の列挙は、この比較の成功条件にしない。

2026-08-31時点で36問のGeoSolver入力を作成し、作成担当とは別の担当者による意味監査を完了した。
ユーザー承認により原問題を基準とし、公開GMB入力で条件が欠ける2000 P1・2015 P3だけを補った。
現在は**公式GMB入力34問＋原文準拠の補正版2問**として、36問すべての入力準備が整っている。
公式入力の原本・過去の再現結果は保存し、この比較は「原文準拠版」として区別する。
過去の本測定結果・中断campaign・rawは `experiment` ブランチ／専用worktreeへ移管しました。[保存先](../../docs/research/experiment-archive.md)を参照してください。

入力の確認結果は [preflight-report.json](preflight-report.json)、問題別の確認は
[reviews/README.md](reviews/README.md) を参照する。

## 座標をどう固定したか

原文で相異なることを確認した二点を `(0,0)` と `(1,0)` に置く。
除くのは平行移動の2自由度、回転の1自由度、正の拡大縮小の1自由度だけである。
各問題の長さの絶対値に意味がないことも確認した。

例えば三角形の第三頂点は `Point(x,y)` のまま残す。二等辺・正三角形などに固定せず、
原文が許す形の自由度と鏡映した配置を残す。
したがって「すべての座標が一意になるまで点を指定する」という正規化ではない。
求める値は全問 `target: "0"` とし、もともとの証明すべき結論を条件へ加えない。
自由度が残る場合と条件が重複する場合は、自然問題とは別の人工問題で動作を確認した。

作図で定まる点は構成式で表し、原文が枝を指定していない交点等は未知点と所属条件で表す。
公開GMB入力のパラメータ化・枝指定も確認し、翻訳の根拠を問題ごとに記録した。
これは入力表現を含む処理全体の比較であり、最適化アルゴリズムだけを同一表現で比較した実験ではない。

## 保存内容

| 場所 | 内容 |
| --- | --- |
| `cases/` | 公開 `GeometryProblem` 形式の36問。solverに渡す部分だけを保存 |
| `audit/` | 原文の各仮定と両DSLの対応、固定した二点、枝・内外・退化条件、結論の分離 |
| `reviews/` | 別担当者の36件のレビュー、監査したファイルのhash、含意証明と反例 |
| `source-manifest.json` | 公開GMB入力・公式問題PDF・補助一次資料のURLとSHA-256 |
| `gmbl-original-aligned/` | 不足条件だけを補った2問。公式入力の代替コピーであり、原本は変更しない |
| `input-adjustments.json`, `alignment.py` | 補正版の選択規則・差分・hashと、追加条件だけの変更であることの検査 |
| `protocol.json` | 比較対象、予算、seed、共通判定、計時、保留事項に関する規則 |
| `checker.py`, `checker_geometry.py` | solverの幾何実装を再利用しない、独立した配置検査器 |
| `witness.py`, `observation.py`, `measurement_worker.py` | 受理された候補の配置と出力時刻を記録する計測処理 |
| `prepare.py`, `canary.py` | 静的な事前検査と、人工問題だけを使う計測器の試験 |
| `authorization.py`, `campaign.py`, `assessment.py` | 本測定の認可・固定入力による実行・別工程での採点 |

原文PDFはrepo外の研究資料ディレクトリへ置き、ソース台帳に保存場所を記録した。
元の `solver-a0`、323問の開発corpus、GMB実装・入力原本・過去の測定結果は変更していない。

## 成功と時間の定義

主比較に数えるのは、各solverが自ら受理して出力し、かつ共通検査に合格した配置だけ。
GeoSolverの途中の未受理候補を、GMBの受理済み出力と比較しない。

- GeoSolverは有限の厳密化処理から返った `accepted_candidates` を観測する。
  solver本体の探索・精密化・停止条件は変えない。
- 出力する点・直線・円は、その候補revisionの座標から計算する。座標の再精密化はしない。
- 時間は新しいworkerの起動直前から、配置ファイルの書出し完了まで。
  GeoSolverの `model_materialized` eventの `emitted_seconds` を用いる。
  既存GMBでは同eventの `elapsed_seconds` が書出し後の時刻に当たる。
- 問題読込、import、入力検証、図形への変換、計測処理を時間に含める。
  共通採点は別に行い、その時間は別欄で報告する。
- したがって測るのは**有効配置の出力時間**。未出力の最初の探索点や、処理途中の受理時刻ではない。
  これを「最初の数値解を内部で発見した時間」と読み替えない。
- 制限時間後に得た座標を、それ以前の候補の時刻に結び付けない。
  失敗・未出力も分母に残し、成功した試行だけの時間平均で速さを比較しない。

承認された初回比較は既存GMB再現と同じCPU 4、1コア、180秒、seed 0/1/2、逐次実行。
これは3反復の記述的な比較であり、研究計画書の20反復の正式比較を実施済みと扱わない。

GeoSolverの108試行をseed順・各seed内で問題ID順に実行し、次に補正版GMBの6試行を
同じ順で実行する。未変更34問のGMBは、過去の102試行をhash検証して流用する。
両者は同時刻の交互実行ではなく、CPU 4も専有しない。CPUのSMT兄弟・負荷・周波数等を
記録するが、経時的な負荷差を完全に除去した速度比較とは主張しない。

期限内に正しい受理済み配置を出力できた後にプロセスがtimeout/crashとなった場合も、
「最初の有効配置の出力」には数え、プロセスの正常完了とは分けて報告する。
CPU固定違反・残存子プロセス・観測エラー・出力記録の不整合は測定上の問題として区別し、
成功扱いにしない。失敗試行も分母に残し、自動再実行しない。

## 共通検査

入力はGMBL原文と、点・直線・円の座標だけ。元solverのlossや「成功」ラベルを採点根拠にしない。
仮定、構成、枝、定義域を独自の式で検査し、証明すべき結論は別欄の診断にする。
後から配置を動かして合格させる処理はない。

既定は80桁計算・無次元残差 `1e-6`。`1e-3` と `1e-9` でも感度を報告する。
閾値は人工例で決め、自然問題の成績や保存済みGMB配置を見て調整していない。
境界に近すぎる不等式、枝のtie、不足した座標、未対応式は成功としない。
GMB実装の人工的な点間距離制限・線分端から20%の制限は原文の条件としてコピーしない。

等式の許容誤差とstrict条件の必要な余裕は同じ向きには変化しないため、
三つの閾値の成功集合が包含関係になるとは限らない。
これは数値的な品質検査であって、一般的な存在証明ではない。
`original_problem_valid` はchecker単体では `None` のままとし、原文との対応は独立入力監査で補う。

## 原文との比較範囲

- **2010 P2**：ユーザー承認により `0 < tf < 1`。原文の端点配置を除く共通範囲で比較する。
- **2014 P4**：両入力ともP・Qを辺の内部に取る。原文を閉じた辺と読む場合の境界配置まで含むとは主張しない。
- **2000 P1**：接線をNよりMに近い側に選ぶ条件を、別の比較用GMB入力へ追加した。
- **2015 P3**：A,B,C,K,Qの円周順序と同値な二つの反対側条件を、別の比較用GMB入力へ追加した。

最後の2問は、他の条件から不足分が従うわけではないことを有理数座標の反例で確認した。
GeoSolver入力はすでに原文の条件を保っていたため、今回変更していない。
2026-08-31の承認に基づき、GMB側だけ別入力へ不足分を追加し、数学的な仮定をそろえた。
既存のparam・define・assert・evalはすべて維持し、結論を仮定に加えていない。
補足レビューは `reviews/alignment/` に保存し、未変更の公式入力についての旧監査も残した。
反例の存在は、過去のGMB実行が実際にその不正配置を返したという主張ではない。

本比較には `preflight-report.json` の各問の `comparison_input.path/sha256` を用いる。
この台帳では2問だけ補正版を選ぶ。公式GMB再現用の既存runner・結果を、そのまま
補正版の測定として扱わない。特に改訂2問の旧成績を補正版の成績として流用しない。
GMBのsoft lossや人工的な余裕の実装自体は変えず、出力の妥当性は引き続き共通検査器で確認する。

## 再確認方法

repo直下のGeoSolver用 `.venv` を使う。GMB専用の古いPython環境とは混ぜない。

```bash
.venv/bin/python -m benchmarks.gmb_comparison.prepare \
  --output benchmarks/gmb_comparison/preflight-report.json
.venv/bin/python -m pytest \
  tests/test_gmb_comparison_preparation.py tests/test_gmb_comparison_checker.py \
  tests/test_gmb_input_alignment.py
```

`--require-ready` を付けた検査は現在36問すべて合格し、終了コード0になる。
古いレビューを付けたままDSLを変更した場合や原典hashが変わった場合も検出する。
入力準備の合格は、本測定の実行許可を意味しない。

人工試験は、まだ存在しない出力ディレクトリを指定する。

```bash
.venv/bin/python -m benchmarks.gmb_comparison.canary \
  --output benchmarks/local-evaluation/gmb-comparison-canary-new \
  --cpu 4 --timeout 30
```

2人工問題それぞれで計測なし／ありを実行し、正常終了、答え・候補記録の完全一致、
全出力の独立検査、revisionと時刻、CPU固定、子プロセス終了を確認する。
実行前のコードhashと人工入力、実行後のログ・座標・SHA-256を保存する。
過去の出力ディレクトリは上書きしない。

自然問題は、承認済みprotocol、最新コードで合格した人工試験、全36問の入力監査を
確認した上で作成するcampaignに限って実行できる。workerも問題・seed・CPU・予算・
入力とmanifestのhashを再検査する。単に人工試験フラグを立てても自然問題は動かない。

```bash
.venv/bin/python -B -m benchmarks.gmb_comparison.campaign prepare \
  --output benchmarks/local-evaluation/gmb-geosolver-new-campaign \
  --canary benchmarks/local-evaluation/gmb-comparison-canary-new \
  --legacy /home/kabatan/work/solver-experiment/research-archives/2026-09-08/local/benchmarks/local-evaluation/gmb-imo39-seed0-cpu4-20260831 \
  --legacy /home/kabatan/work/solver-experiment/research-archives/2026-09-08/local/benchmarks/local-evaluation/gmb-imo39-seeds1-2-cpu4-20260831
.venv/bin/python -B -m benchmarks.gmb_comparison.campaign run \
  --campaign benchmarks/local-evaluation/gmb-geosolver-new-campaign
.venv/bin/python -B -m benchmarks.gmb_comparison.assessment \
  --campaign benchmarks/local-evaluation/gmb-geosolver-new-campaign
```

`prepare`の前に計測処理と入力をcommitし、上記canaryを新しいディレクトリで実行する。
`--legacy`は封印済みの過去GMB計測ディレクトリをseedごとに指定する（上記はexperimentブランチ専用worktree内の2026-08-31計測）。
公式入力34問×3seedのGMB実行はその封印済み結果を再利用するため、対応するseedの計測が見つからないと`prepare`は失敗する。
`run`は全rawを`RAW_SHA256SUMS`で封印し、`assessment`が別ディレクトリへ採点結果を出す。
測定中・測定後の成績に合わせて入力や検査閾値を変えない。solver本体は`solver-a1`に固定する。
