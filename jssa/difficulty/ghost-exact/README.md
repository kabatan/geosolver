# sol-1: 点対の一致を加えた等式系（数値探索）

開始 UTC: 2026-10-23T05:22:58.332262+00:00。最終更新 UTC: 2026-10-23T06:32:31.789091+00:00。
完了 292 / 292 問。実測 wall time 4173.423 秒
（69.557 分）、問題別処理時間の合計 27626.945 秒。
worker 数 8。Python 3.12.11、NumPy 2.5.1、
SciPy 1.18.0。
完了済み 52 問を再開時に再利用。
点対を最大 8 組ずつ分配する（各点対の乱数・計算条件は不変）。
wall time は初回開始からの経過で、中断・再開の準備と破棄された未完了試行の時間も含む。
問題別secondsは準備と点対処理時間の合計（同じ問題の点対を並列処理した時間は加算）。

## 手順

- 対象は `minima/basins-323.csv` の n_vars >= 1（全体292問）。DSL は `benchmarks/cases.jsonl`。
- 点名は `ghost_scan.point_names` を使い辞書順に並べた0始まりの添字 i,j。
  座標式は `probe_basins.construction_coordinates` から取得。元の等式のIR残差 F に
  座標式の差 x_P-x_Q, y_P-y_Q の2行を追加する。同じ作図を毎回4回評価しないよう、
  これらを1つのIR残差ベクトルにまとめ、既存のfloat評価器で評価する。
  指定の point_names は Area などのスカラー名も返す。その候補名も規則どおり保持し、
  座標を定義できない点対の失敗を隠さず記録する（例: AIME-2006-I-07 の Areg）。
- 過去の記録は cls == hit の x だけを使用し、全hitで常に一致する点対を除く。
  一致判定は既存の `ghost_scan.py` と同じ：距離 < 1e-6 * max(1, 全有限点の原点からの距離の最大値)。
  当たりが無い問題は除外なし。両CSVの has_hits 列で区別する。
- 各残存点対ごとに `np.random.default_rng([0, i, j])`、`infer_problem_bounds` の箱から
  一様乱数で独立な20出発点。見つかった後も20回すべて実行する。終点や過去の乱数出発点を初期値に使わない。
- `scipy.optimize.least_squares(method="lm", max_nfev=100*n, ftol=xtol=gtol=1e-14)`。
  max_nfev は当該SciPy版の既定値と同じ。箱は初期値だけに使い、探索中は無拘束。
  不等式・ガード・hard-feasibility・正解値の条件や罰則は加えない。
  残差行数 < n の場合だけ0行を追加してLMの m>=n 制限に対応（目的関数とランクは不変）。
- 有限な終点の拡張残差のユークリッドノルム <= 1e-10 を found=1 とする。
  best_res は20回の返却終点の最小ノルム（全失敗なら inf）。
  終了ステータスにかかわらずこの残差条件で判定する。
  未定義・非有限値を有限な罰則に置き換えない。LM例外は n_failed/errors、上限停止は n_limit に記録。
- 成功終点で拡張系（0埋め前）の中心差分Jacobianを計算。
  各変数の刻みは 1e-6 * max(1, abs(x_j))、最大特異値の1e-8倍未満を0とし、dim=n-rank。
  最大特異値が0ならrank=0。点対のdimは20回で見つかった成功終点の最大値。
  問題のmax_dimもその最大値。見つからなければ -1。
  次元計算に失敗した場合は n_rank_failed に記録し、その終点の次元を欠測にする。
  found=1 だが全成功終点で次元が計算できなかった点対の dim は空欄。
  問題のmax_dimは有効な次元の最大値（発見があって全次元欠測なら空欄）。
  n_pairs_dim_unknown>0 の問題では max_dim は不完全な観測値として扱う。

## 数値集計（解釈なし）

| 項目 | 値 |
|---|---:|
| 完了問題 | 292 |
| has_hits=0 の問題 | 29 |
| 除外前の点対 | 7686 |
| 全hitで一致するため除外した点対 | 20 |
| 調べた点対 | 7666 |
| found=1 の点対 | 648 |
| G=1 の問題（n_pairs_found>0） | 65 |
| LM出発点 | 153320 |
| LM例外で終点が得られなかった出発点 | 25595 |
| max_nfev に達した出発点 | 13357 |
| 成功終点の次元計算失敗 | 230 |
| found=1 だが次元がすべて欠測の点対 | 34 |
| 全20出発点でLM例外になった点対 | 1186 |

max_dim の問題数（None は欠測）: `{-1: 227, 0: 32, 1: 19, 2: 5, 3: 2, 4: 1, 5: 1, None: 5}`。

## 出力列と限界

`per-pair.csv` の先頭6列は id,P,Q,found,best_res,dim。has_hits と点添字、
試行数・成功数・例外数・上限停止数、0埋め行数を付記する。best_x は最小残差の証人、
dim_x/dim_res/singular_values は最大次元の証人（同次元なら残差最小）、errors は例外内訳。
`per-problem.csv` の先頭7列は id,n_vars,n_pairs,n_pairs_found,max_dim,has_hits,n_hits。
n_pairs は除外後、n_pairs_total は除外前。n_pairs_excluded と実測seconds等を付記する。
status=ok は処理完了を表し、全試行の数値収束を意味しない。
n_pairs_all_failed は全試行が例外になった点対数で、これらの found=0 は探索不能を含む。

「厳密解あり」はタスク指定の残差閾値による数値判定で、代数的な存在証明ではない。
found=0 は20個の出発点では発見しなかったことだけを表す。
n-rank はその終点での数値的な接空間の次元であり、特異解では局所解集合の次元と一致しない場合がある。
非有限値や差分誤差、尺度の違いによる限界を含む。事前登録H1〜H4の検定や結果の解釈は実施しない。
例として AIME-2007-II-15 の r=4 付近では PointOnSegment の片側が定義域外となり、
指定の中心差分を評価できない。片側差分や別の方程式への置き換えは行わない。

## 再実行

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python \
  jssa/difficulty/ghost_exact.py --workers 8 --chunk-size 8
```

`--ids ID ...` で問題を限定、`--out DIR` で別の出力先を指定できる。
`--resume` は既存CSVの完了済み問題を再利用する（計算条件を変えて再開しないこと）。
依存環境の変更、solver本体の変更、commit/pushは行っていない。
sol-2 の per-triple.csv / per-problem-triple.csv には触れない。

入力とコードの SHA-256:

- `benchmarks/cases.jsonl`: `c5f92269783add80779a38b4159f298b7f49300386bca0008bb02d3c82d3fccb`
- `jssa/difficulty/minima/basins-323.csv`: `2b240b15e67903c3d161a736a4bf766aa2b282bcbb42742bcaec2ec917f46420`
- `jssa/difficulty/ghost-1023/preregistration.md`: `4d9b4676e45145c7ed3cc1f181f9911bb39e374d06f1c1512f3e131f8280a60a`
- `jssa/difficulty/ghost_exact.py`: `a8ad708066b3a48bdec00507a37dd078ddb4516d0978fef2eb88d89c03c5d85f`

## 出力の検証

全292問のID・点添字・20試行・除外数・集計・例外内訳の整合性を検証した。
保存された最小残差の証人 6480 個を再評価し、元の等式残差が保存時と同じことと、
拡張残差のノルムが best_res と一致することを確認した。
次元が計算できた成功点対 614 個では保存した証人から中心差分・SVDを再計算し、
dim と特異値が一致した。検証所要時間 20.162 秒。
別途、3問で座標差と construction_coordinates の高精度評価の一致を確認し、
既知の線形系でランクとLM用の0行追加を検証した。
2問12点対では問題単位の実行と点対分配後の全CSV数値が完全一致し、再開でも保持された。
初回は4プロセスで52問を完了後に中断し、残り240問を8プロセスで点対単位に再分配した。
LM出発点の集計は保存した本実験の件数で、中断時の未完了試行や小規模検証の重複実行を含まない。
