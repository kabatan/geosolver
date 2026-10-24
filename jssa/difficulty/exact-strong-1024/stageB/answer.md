| 予測 | 固定した条件 | 観測 | 判定 |
|---|---|---|---|
| E1 | 開発外で解ける数 ≤ 26 | 20/29 | 当たり |
| E2 | 開発外でsolver ≥3/5正解・強化版未解決 ≥3問 | 8問 | 当たり |
| E3 | 開発群で解ける割合 ≤45% | 39/122 = 32.0% | 当たり |
| E4 | 開発群でsolver ≥1/3正解・強化版未解決 ≥半数 | 82/122（必要61問） | 当たり |
| E5 | 未解決側の次数中央値 ≥ 解決側の2倍、かつ時間切れ率が高い | 次数 4.000 対 4.000、時間切れ 15/38 対 0/59 | 外れ |
| E6 | 両方解けた問題で強化版の時間中央値 < solver | 0.906秒 対 2.694秒（58問） | 当たり |

開発外は20/29問、以前のmsolveが答え集合を出せなかった開発群は39/122問を解けた。`verified_complete` と `direct_verified` だけを数えた。`verified_subset` は未解決に含む。開発5問は別掲し、評価には入れていない。

解けなかった計92問のうち54問は変換不能であり、対応する構文・定数の範囲が差の解釈に大きく影響する。

## 4基準

| 基準 | 今回言えること |
|---|---|
| ① 直感に反するか | solverが正解できてもこの強化版が解けない例は、開発外8問（3/5以上正解）、開発群82問（1/3以上正解）。ただし変換の未対応や実装上限も含み、数学的な難しさとは直結しない。 |
| ② 深い理論が必要か | この結果だけでは必要性を示せない。πを含む目標、未対応命令、有限標本による復元、根の扱いなどの制約を区別する必要がある。 |
| ③ 広く再現するか | 固定した2群で比較したが、開発外は29問、各問1回、同じ実装・同じ機械に限る。開発群は既存msolveの失敗に条件付けた標本である。 |
| ④ solverならではか | この固定パイプラインに対する差はある。他の厳密法全般の限界、solverだけに可能な能力、深い理論による優位とは結論しない。 |

## 対象と実行

事前登録commitは `893453ed`。開発外34問から指定5問を除く29問を先に全て実行し、[中間集計](progress-a.md)を保存してから開発群122問を実行した。各問1回、全工程600秒、8 GiB、最大4並列、各1 CPU。再試行・対象の交換・求解コード変更・solverの再実行・システム導入・commit/pushは行っていない。

開発群は元比較 `exact-comparison-pc-20261022/aggregate/cases.csv` の `msolve_class != answer_set_matches` 全122問。[targets-dev.csv](targets-dev.csv)に元の区分、根拠パス、SHA-256、取得元commitとGit blobハッシュを実行前に固定した。現在のremote branchから元結果を直接読めなかったため、取得済みの同一blob（SHA-256 `5f8d89cf92fd84b7e7fa1de72aa65cd8fe2234174c3873bd7b9c6109ce6979cd`）をsource-audit.jsonの来歴に照合して用いた。隣のexact-scaling-1024の結果は対象の探索時に参照しただけで書き換えていない。

元比較の対象内訳は、正次元65、未対応15、実行エラー15、未知数0が13、時間切れ9、自由パラメータ3、記録なし2問。この元比較で記録なしだった2問も今回の122問から除いていない。

入力DSLファイルとコードの事前ハッシュは [pre-run-hashes.json](pre-run-hashes.json)。凍結srcは `sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5`。各問の開始直前と実行中15秒ごとに照合し、全て一致した。[監査記録](integrity-audit.json)、[開始時負荷](load-at-start.csv)、[集計方法](measurement-notes.md)。`verified_complete` も凍結版の数値最終検証契約に対する結果であり、形式証明ではない。

## 結果区分と欠測

| 区分 | 開発外29問 | 開発群122問 |
|---|---:|---:|
| `algebraically_empty` | 0 | 0 |
| `direct_unresolved` | 0 | 0 |
| `direct_verified` | 1 | 14 |
| `error` | 0 | 1 |
| `lift_unresolved` | 0 | 6 |
| `nonfinite_target` | 0 | 7 |
| `resource_limit` | 0 | 0 |
| `timeout` | 1 | 14 |
| `unsupported` | 7 | 47 |
| `verified_complete` | 19 | 25 |
| `verified_subset` | 1 | 8 |
| `worker_error` | 0 | 0 |
| 強化版の結果欠測（分母に残す） | 0 | 0 |
| solverの欠測seed（分母145/366に残す） | 1 | 0 |

変換不能・時間切れ・メモリ・未解決の理由コードは次のとおり。同一問題の複数理由は重複して数えるため、行の合計は未解決問題数と一致しない。候補ごとの詳細は保存した結果JSON、問題ごとの一覧は [unresolved-reasons.csv](unresolved-reasons.csv)。

| 区分・理由コード | 開発外 | 開発群 |
|---|---:|---:|
| `error / TypeError` | 0 | 1 |
| `lift_unresolved / FREE_COORDINATE_SAMPLING_INCOMPLETE` | 0 | 6 |
| `nonfinite_target / NO_UNIVARIATE_TARGET` | 0 | 7 |
| `timeout / TIME_LIMIT` | 1 | 14 |
| `unsupported / ANGLE_TARGET` | 2 | 8 |
| `unsupported / NONALGEBRAIC_CONSTANT` | 0 | 1 |
| `unsupported / NONALGEBRAIC_PI` | 3 | 17 |
| `unsupported / UNSUPPORTED_BOOLEAN_GUARD` | 0 | 9 |
| `unsupported / UNSUPPORTED_COMMAND` | 1 | 4 |
| `unsupported / UNSUPPORTED_DSL` | 1 | 5 |
| `unsupported / UNSUPPORTED_GUARD_TYPE` | 0 | 3 |
| `verified_subset / FREE_COORDINATE_SAMPLING_INCOMPLETE` | 0 | 7 |
| `verified_subset / verification_unresolved:` | 0 | 1 |
| `verified_subset / verification_unresolved:domain_boundary_unresolved` | 1 | 0 |

時間切れの直近記録段階（両群合計）: `lift_and_final_verify` 1問, `saturate_eliminate_lex` 14問。段階ごとの所要時間全体が記録されたという意味ではない。

明示されたメモリ上限・MemoryErrorは0問。原因が記録されていない終了をメモリ不足とは推測しない。

## E5：目標の一変数多項式の次数

得られた消去式のgcdの次数を比較した。変換不能を未解決側から除く。直接評価などで式を得ていない場合は次数0にせず欠測とした。次数分布は「次数:件数」。式が得られた問題だけの中央値であり、時間切れで式が得られなかった問題への偏りがある。

| 群・側 | 次数が得られた分布 | 次数中央値 | 次数欠測 / 対象 | 時間切れ / 対象 |
|---|---|---:|---:|---:|
| 開発外・解けた | 2:9, 4:5, 6:2, 8:1, 16:2 | 4.000 | 1/20 | 0/20 |
| 開発外・解けない（変換不能除外） | 4:1 | 4.000 | 1/2 | 1/2 |
| 開発群・解けた | 1:4, 2:8, 4:7, 6:2, 7:1, 8:2, 20:1 | 4.000 | 14/39 | 0/39 |
| 開発群・解けない（変換不能除外） | 1:1, 2:4, 4:8, 10:1, 16:1 | 4.000 | 21/36 | 14/36 |
| 合計・解けた | 1:4, 2:17, 4:12, 6:4, 7:1, 8:3, 16:2, 20:1 | 4.000 | 15/59 | 0/59 |
| 合計・解けない（変換不能除外） | 1:1, 2:4, 4:9, 10:1, 16:1 | 4.000 | 22/38 | 15/38 |

E5は **外れ**。次数条件は満たさなかった。時間切れ率条件は満たした。時間切れは定義上「解けない」に入るため、時間切れ率の差だけで高次数が原因とは示せない。次数欠測を除いた結果を全対象の分布と解釈しない。

## 時間の比較（両方解けた問題）

| 群 | 問題数 | 強化版の全工程・中央値秒 | solverの正解時間・中央値秒 | 開始時1分load average |
|---|---:|---:|---:|---|
| 開発外 | 19 | 0.904 | 1.038 | 21.00〜24.61 |
| 開発群 | 39 | 1.009 | 5.977 | 19.61〜45.95 |
| 合計 | 58 | 0.906 | 2.694 | 19.61〜45.95 |

solverは正解したseedの時間を問題ごとに中央値にし、その後、同じ問題集合で問題間中央値を取った。強化版は今回のwall_seconds。実行ワーカーは、利用可能な32 CPUのうち1 CPUに固定した（凍結実行器の割当）。共有機で他ジョブが動いており、load averageは全体負荷である。solverは別時点の既存計測で負荷・並列数が揃っていないため、E6の数値判定を速度の一般的優位と解釈しない。開始直前の外部ハッシュ監査はwall_secondsに含まれない。

## 開発に使った5問（段階Aの既存結果）

| 問題 | 結果区分 | 全体壁秒 |
|---|---|---:|
| AIME-2005-I-01 | `unsupported` | 0.403 |
| AIME-2012-I-14 | `verified_complete` | 0.502 |
| HMMT-2011-FEB-GUTS-01 | `verified_subset` | 0.903 |
| HMMT-2019-FEB-GUTS-17 | `verified_subset` | 363.888 |
| HMMT-2023-FEB-GUTS-03 | `verified_complete` | 0.703 |

5問中、答え集合を確認したのは2問。一部確認2問、変換不能1問。今回は再実行していない。詳細は [段階Aの記録](../dev5-results.md)。

## solver側の出典と成果物

- 開発外A：[unseen-2/a/per-run.csv](../../unseen-2/a/per-run.csv)、Q30、seed 301〜305、`matched` と `wall_seconds`。
- 開発外B：[unseen-2/b/results.csv](../../unseen-2/b/results.csv)、Q30、seed 301〜305、`matched` と `wall_seconds`。
- 開発群：[mechanism-attribution/attribution.csv](../../../results/mechanism-attribution/attribution.csv)、323問×3 seedの既存本計測、seed 0〜2、`matched` と `wall_s`。

比較には上記の既存記録だけを用い、旧msolve集計内のsolver時間を流用していない。各出典のSHA-256は事前ハッシュ一覧に保存した。欠測seedは5または3の分母に残し、正解と数えない。HMMT-2015-FEB-GUTS-24のseed 301は `process_crash` / `missing_record=True` で、既存CSVには時間欄があるが正解seedの時間比較には使っていない。正解時間の欠測は中央値の対象数と別にper-problem.csvへ記録した。

[per-problem.csv](per-problem.csv)に151問の群・区分・時間・次数・solver正解数/seed数・正解時間中央値・欠測・負荷を保存した。[summary.json](summary.json)が集計値、[degrees.csv](degrees.csv)が次数の根拠。生ログ・作業ファイルはリポジトリ外の `/tmp/exstrong-stageB-jbagxjld` に保存し、[raw-log-hashes.csv](raw-log-hashes.csv)にパス・サイズ・SHA-256を残した。結果JSONは各3 MB未満で `results/` に保存した。
