# Q27e データの意味と範囲

この調査は既存データ再解析である。機械学習モデルの学習、未知問題への外挿評価、新規の数値探索は行っていない。

| 資料 | 行数・範囲 | 今回の利用 |
|---|---:|---|
| minima/basins-323.csv | 323問、p非欠測292問 | seed 0の局所hit率、終点分類、クラスタ統計 |
| minima/raw-323 | 55,097完了記録 | 始点・終点の保存状況、nfev・時間・残差の分布。反復軌道ではない |
| minima/raw-323-seed1 | 55,142完了記録 | 固定群のp・nfev再現。全記録でstart/xは未保存 |
| ghost-1023/human_feat.csv | 323問、human非欠測131問 | human、contest、入力の構造量のみ。C・fast・alg・logCは選択に使わない |
| results/stage-profile-20261023/per-case.csv | 969行＝323×3seed | 発見はseed 0、固定後の再現はseed 1/2 |
| start-feasibility-1023/per-problem.csv | 292問 | 許容始点の割合と条件別hit率 |
| ghost-pairs-match/per-problem.csv、false-attractors/per-problem.csv | 保存終点の集計 | 退化・衝突・その他の失敗分類。因果ラベルとはしない |
| q21d-conditioning/per-problem.csv | 323問、cond数値230問 | 正解点近傍の尺度を固定した条件数等。statusを併記 |
| q21b-number-theory/problem-summary.csv | 323問、stable_correct_grid非欠測315問 | 答えを知った同定実験の格子。πや未成功を0で埋めない |
| q22a-hidden-coincidence/features.csv | human131問、solution_dependent_count非欠測121問 | 一致数・作図深さ。解法の証明深さとは異なる |
| astra-consult-17/H/sources/comparison-cases.csv | 323問 | msolve分類、系サイズ、次数等。独立の新実行ではない |
| benchmarks/extra-variables | 15問×k=0..3の入力・規則 | 計測値の原表は本チェックアウトにない。本文の既存集計と区別 |
| results/gmb-success-definition/per-trial.csv | 独立検査対象136行 | human131問との共通IDは0。成功率の母数はこの136行だけではない |

`joined-discovery.csv`は入力の列のうち必要なものをまとめた323行である。元のidを一切正規化せず一意に結合した。`extremes-full.csv`はhumanあり131問全件、`extremes-local.csv`は局所pとの共通109問全件を順位差で並べている。ファイル名にextremesとあるが、middle群も削除していない。

`group-statistics.csv`は各群の非欠測件数も含む。各行のn_measuredを見ずに群の中央値を比較しない。とくに以下の列は注意が必要である。

- `cost0`は正答なら実時間、誤答なら180秒。`wall_time_s0`は実時間。全問時間中央値5.177秒は後者を969行で計算したもの。
- pは局所LMのhit割合。完成solverの成功確率ではない。変数0では未定義。
- `collision_failure_fraction`はcollision_failure/max(1, n_records−success)。失敗0件でも0になる便宜的な集計であり、条件付き確率として使うなら失敗0件を欠測にすべきである。本文の局所失敗原因の議論では、失敗のない行を「退化しない証拠」と数えていない。
- `degenerate_failure_fraction`はfalse-attractorsの既存定義をそのまま利用。分類の代理指標で、真の極小の数学的認証ではない。
- `cond`はQ21dで採用された正解図近傍の行列の条件数。rank不足・差分不安定等を含むstatusとセットで使う。κだけからα、γ、開始領域の体積は出ない。
- `real_solutions`は既存msolve集計値。positive_dimensional等の行にある0は、有限な解がゼロという意味ではない。`bezout`も真の解数ではない。この注意を無視した全行中央値に理論的意味を与えない。
- `stable_correct_grid`はQ21bの有限精度格子上の成功が後続格子でも保たれる側の開始点。実際の最小必要桁数の厳密な閾値ではない。`heuristic_digits`は(d+1)log10(max(2,H))。
- `solution_dependent_count`は既存Q22aの数値図・摂動と構文上の除去規則に依存する。隠れた定理や解答の必要ステップ数の真値ではない。
- `all/hit/miss_*_median`は保存試行単位の中央値。`nfev`は残差評価回数でありNewton反復数ではない。

群は既に観測したhuman、p、Cを使って選んでいる。発見群でpやCの差が大きいこと自体は選択の結果でもある。別seedでの固定群の比較は問題内の再現であり、問題外一般化ではない。以前の研究でも使われた開発集合なので、完全盲検の確認研究とは呼ばない。

再解析時に新規書込したのはQ27e内だけである。入力manifestに封印tarとunseen-1983のsolver結果は含まれない。欠測がある資料を新規の大計算で埋めなかった。
