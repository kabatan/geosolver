# sol-4：退化解を消す介入

事前登録 `jssa/difficulty/ghost-1023/preregistration-2.md` の B を実行した。
判定と数値は [score.md](score.md)、出発点別は [per-start.csv](per-start.csv)、
問題別は [per-problem.csv](per-problem.csv)。基準・指標・58問の対象は変更していない。

## 結果

| 項目 | 結果 |
|---|---:|
| 固定対象 | 58問 |
| 元の保存済み出発点 | 11,038 |
| 安全確認前の found=1 点対 | 474 |
| 安全確認後の treatment 点対 | 276 |
| treatment が0組の問題（対象に保持） | 5 |
| 同数の placebo を構成できなかった問題（対象に保持） | 7 |
| 全保存済み出発点を完了した treatment | 56/58問 |
| 全保存済み出発点を完了した placebo | 50/58問 |
| B1 | 不成立 |
| B2 | 不成立 |
| B3 | 判定不能 |

各分類の出発点数：

| 分類 | original | treatment | placebo |
|---|---:|---:|---:|
| error | 104 | 104 | 104 |
| hit | 5078 | 5078 | 4776 |
| left_box | 1566 | 1634 | 1290 |
| missing_placebo_pairs | 0 | 0 | 1306 |
| not_run_deadline | 0 | 202 | 51 |
| stuck | 3025 | 3772 | 2486 |
| wrong_answer | 1222 | 234 | 983 |
| wrong_branch | 43 | 14 | 42 |

## 実行内容と固定条件

実験前に [protocol.md](protocol.md) と [plan.json](plan.json) を保存した。
plan は対象ID、点対、hit上の最小距離、除外理由、L、問題番号、placebo抽出結果、
使用入力のSHA-256を保持する。実行時のplan SHA-256は
`ba1426bcf24782e58459300742f03a34497380041026e4f11056c854ce1ccd73`。

- Pythonは `/home/kabatan/work/solver/.venv/bin/python`。環境の書き換え・依存追加はしない。
- 最大4プロセス、BLAS/OMP/MKL/NumExprは各1スレッド。
- seed 0 の raw-323 の保存済み start を、その問題の保存順にそのまま使う。
  元が200個未満の6問も補充しない。全armで元の同じ列を予定し、実行済みはその先頭部分。
- 点名は ghost_scan.point_names、座標は construction_coordinates。
  Lは元のhit図の直径の中央値。全hitで |PQ| > 0.02 L の点対のみを採用する。
  この正しい図を傷つけない確認は両armに適用する。
- treatmentは安全な found=1 の全点対。placeboは安全な found=0 の点対から同数を
  非復元抽出する。辞書順の候補に default_rng([7, basins-323全行の0始まり番号])。
  番号・復元の有無は事前登録で未指定だったため実行前に固定した。
- 最適化の追加行は厳密に max(0, 1-|PQ|/(0.02 L))。w=1。
- smb._collect_local_start_record をそのまま使う。プロセス内で残差関数を一時的に
  ラップし、元の等式・guard・hard feasibility の全行の後ろに追加行を連結する。
  元のbundle・評価器・bounds・configは変えない。srcは編集しない。
- LM max_nfev=80、ftol=xtol=gtol=1e-14。
  元から n_vars>n_constraints の7問は元と同じPowell経路、maxiter=400。
  追加行でLM/Powellの分岐を切り替えない。
- 各問題・各armの探索全体の締切は 120.0 秒。
  evaluator構築後から計測し、probe_basinsと同じように締切を局所探索へ渡す。
  追加行の評価費用もこの締切に入る。締切途中の出発点は返却されず欠測になる。
- 元の終点採点経路で箱、元の等式ノルム<=1e-8、guard、hard feasibility、
  元の答え（相対許容誤差1e-6）を採点する。追加罰則が小さいだけではhitにしない。
- 追加点対が探索途中に未定義なら、元の探索側の非有限値罰則と同じ1e10を追加行に返す。
  発生回数はper-problemの *_nonfinite_penalty_calls に保存した。
- 原則として残差評価の式に不要な作図を共有するキャッシュを利用するが、元のfloat精度は変えない。

## うまくいかなかった点・限界

1. 7問では、指定数の安全な found=0 点対が存在せず、事前登録のplaceboを構成できない。
   点対重複、treatmentの間引き、別問題への差し替えはしていない。
   この7問も58問の対象に残し、placeboを欠測にした。個別内訳はscore.md。
2. 120秒締切により一部のarmが全保存済み出発点を完了できなかった。
   完了した出発点数を分母にして別のpを作ることはせず、固定列全体のpを欠測にした。
   欠測を含むpの可能範囲から、全58問のB1/B2および全救済例のB3の保証範囲を求めた。
   完全ケースだけの数値は補助記述であり、事前登録の母集団を置き換えない。
3. 安全確認で全点対が除かれた5問もそのまま0行追加として実行した。
   ここを対象から落として改善を大きく見せることはしていない。
4. sol-1のfound=1は数値探索の閾値による発見であり代数的証明ではなく、
   found=0は不存在の証明ではない。罰則は局所探索の軌道を変えるが、全ての退化解を
   数学的に除去する強制制約ではない。
5. 追加評価による時間増加は締切下の完了率に影響する。CPUを他タスクと共有しており、
   保存済み元データと同一の実時間費用を再現できるとは限らない。
6. 実行中に他タスクがprobe_basins.pyのケース読込・CLIを一時的に変更した。
   実験workerは変更前にimport済みの関数を保持する。変更時のdiffで使用関数に変更が
   ないことを確認した。集計時にはこのファイルを含む全凍結入力が初期SHAに一致した。
   初期SHAと一致する[元ソース](probe-basins-at-freeze.py.txt)も保存した。

**B2 を満たしたとは言えないため、退化解が当たり外れの原因だとは主張しない。**

## 検証

- 元のhitに対する追加罰則0の確認：9,874件。
- 座標の同時float評価と元の高精度評価の比較：99組の検査、
  最大相対差 3.52e-15。
- 空のラップと元の残差ベクトルの完全一致：58問。
- 元の探索の再実行：9出発点で元の終点・分類と一致、相違0。
- sol-1の退化解の証人に罰則が働くことの確認：53問。
- 全保存済み介入終点 20,517個を元の評価器で再採点し、
  分類・残差・答えの相違0。終点なしのerrorは0個。
- 両CSVの58問・11,038行・キー一意性・成功率・救済定義の整合性を検証した。

詳細はverification.json、audit.json、summary.json、各log。

## 時間・環境

- 作業開始（最初の記録時刻）UTC：2026-10-23T06:44:33Z。
- 実験開始UTC：2026-10-23T06:50:50.626401+00:00。
- 実験終了UTC：2026-10-23T07:06:01.526837+00:00。
- 本実験の実時間：910.900秒（15.182分）。
- arm別処理時間の合計：3589.807秒（並列分を加算）。
- 実行前検証：24.285秒。集計：3.233秒。
- 終点再採点とCSV監査：4.165秒。
- 実装・調査を含むこの報告作成までの経過：1432.142秒（23.869分）。
- Python：3.12.11 (main, Oct  7 2025, 15:34:39) [Clang 20.1.4 ]。NumPy 2.5.1、SciPy 1.18.0。

## 再実行

既存のplanとcheckpointを保持するrunは同条件の再開専用。prepareはplanを上書きしない。
初回のコマンドは以下。全出力はこのディレクトリ内。

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/ghost-intervention/run.py prepare --workers 4
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/ghost-intervention/verify.py
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/ghost-intervention/run.py run --workers 4
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/ghost-intervention/summarize.py
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/ghost-intervention/audit.py
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/ghost-intervention/report.py
```

今回の作業で作成・変更したファイルはこのディレクトリ内だけ。
既存ファイル、src、Python環境の変更やgit commit/pushはしていない。
同じ作業フォルダの他タスクによる変更はそのまま保持した。
