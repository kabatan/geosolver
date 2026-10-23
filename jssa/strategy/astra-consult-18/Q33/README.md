Q33の開発記録調査と小再現（2026-10-24）。結論は[answer.md](answer.md)、候補一覧は[observations.md](observations.md)。観測の説明状況とデータの絶対パス・行・キーは[observations.csv](observations.csv)にある。

参照した依頼は[codex-tasks-1023.md のQ33](../../codex-tasks-1023.md)と[codex-session-01a1171a-summary.md](../../codex-session-01a1171a-summary.md)。作業開始時の手元のタスク文にはQ33がなかったためユーザー本文に従い、最終整理時には追加されたQ33節と共通4基準を読み直した。

`git branch -a`で`experiment`・`origin/experiment`を確認し、既存worktree `/home/kabatan/work/solver-experiment` の `7b6691be8d8a15a7a95816b532cad06cc2819112` を参照した。手元に`origin/claude/project-thread-nycxfb`はなかった。参照先は追跡済みの整理資料とローカル保存の生記録を含み、両者を同一視しない。下記パスはこの計算機のもの。

| 所在ID | 内容と入口 |
|---|---|
| S01 | [9/7改善報告](/home/kabatan/work/solver-experiment/research-archives/2026-09-08/snapshot/benchmarks/solver-improvement-report-20260907.md:89)。F07/F08/F12/F20/F23の採否と段階別成績 |
| S02 | [旧段階の生記録・保存ソース](/home/kabatan/work/solver-experiment/research-archives/2026-09-08/local/benchmarks/local-evaluation/solver-improvement-20260907) と [969実行の比較CSV群](/home/kabatan/work/solver-experiment/research-archives/2026-09-08/snapshot/benchmarks/solver-improvement-results-20260907)。stage10/11の`regression-*/assessment.jsonl`、stage8/11/12の`rejected-*-cases.csv` |
| S03 | [解析Jacobianの24問比較](/home/kabatan/work/solver-experiment/research-archives/solver-evidence/optimization-speed-20261011/algebra-analytic-stable-v3-paired/comparison.json)、同フォルダの`records.jsonl`。保存版は [source-snapshots.tar.gz](/home/kabatan/work/solver-experiment/research-archives/solver-evidence/optimization-speed-20261011/source-snapshots.tar.gz) と同名の索引JSON |
| S04 | [同一ソースの対応記録](/home/kabatan/work/solver-experiment/research-archives/solver-evidence/optimization-speed-20261011/evaluation-slice-paired.jsonl:1)、[失根監査](/home/kabatan/work/solver-experiment/research-archives/solver-evidence/optimization-speed-20261011/evaluation-hmmt2013-root-loss-audit.json)、[不採用記録・計測の限界](/home/kabatan/work/solver-experiment/research-archives/solver-evidence/optimization-speed-20261011/evaluation-negative-receipt.json) |
| S05 | [10/11全323問の対応CSV](/home/kabatan/work/solver-experiment/research-archives/solver-evidence/optimization-20261011/final-paired-seed0.csv)、[当時のREADME](/home/kabatan/work/solver-experiment/research-archives/2026-10-21/snapshot/README.md:64) |
| S06 | [solver-analysis報告](/home/kabatan/work/solver-experiment/research-archives/solver-evidence/solver-analysis/report/research-report-ja.md)、同ディレクトリの`fragments/{damping,mid,exactification}_results.md`と隣接`analysis/*/summary.json`。生の[分母床対照](/home/kabatan/work/solver-experiment/research-archives/solver-analysis/development/denominator-pair-v1/summary.json)・[提案継続428腕](/home/kabatan/work/solver-experiment/research-archives/solver-analysis/analysis/development-comparisons-v1/multiplicity-proposal-runs.jsonl)は`solver-evidence`の外にある |
| S07 | [保存された回帰テスト](/home/kabatan/work/solver-experiment/research-archives/2026-10-21/snapshot/tests/test_solver_improvement_regressions.py:19)。距離0は19行、先頭恒等式は210行 |
| S08 | [Newton変更の180条件レビュー](/home/kabatan/work/solver-experiment/research-archives/solver-evidence/optimization-speed-20261011/evaluation-trust-review-receipt.json)、[修正・再生記録](/home/kabatan/work/solver-experiment/research-archives/solver-evidence/optimization-speed-20261011/refinement-receipt.json) |

セッションは2026/09/07・09/08・09/11・10/11の候補ファイルを先頭metadataのcwdで選び、プロジェクトに属する13本へ`rg -z --threads 1 -n -i -m 80`で検索した。語は「なぜか、予想外、unexpected、regress、同一ソース、悪化、丸め、hypot、500桁、250桁」等。巨大ファイルの全文表示や展開保存はしていない。[session-index.json](session-index.json)に13本、[session-excerpts.jsonl](session-excerpts.jsonl)に66抜粋を保存した。66は重複を含む抜粋数で、66件の現象ではない。全期間・全発言の網羅調査でもない。

主な照合箇所は9/7の`01a07b0b…`行3192・3271・3345・3450（F20・F08）、10/11の`01a1294e…`行4613・6261（全体と追加高速化）、`01a12a1c-63c2…`行947（解析Jacobian）。会話の主張だけで採用せず、上表の結果ファイルで照合した。別の多項式コーパス作業は除外した。

git履歴は`git log --all`のコミットメッセージを`regress|unexpected|不安定|なぜ|回帰`で検索し、solver・testsに関係する7件を[git-history.json](git-history.json)へ保存した。数値型のdispatch修正、幾何・数値検証の修正、回帰テスト追加が中心で、新しい未説明現象として水増ししなかった。

小再現の条件は[replay-plan.md](replay-plan.md)に実行前記録と訂正を残した。求解は常時1プロセス・CPU 31固定、BLAS等も1スレッド。独立した読取だけ最大3並列とした。各求解はsolver設定180秒、外側75秒上限、1コマンド最大2求解。全16求解は打切りなし、プロセス実時間の合計187.10秒。時間は共有ホストの値である。

R1・R2は自然4問にそれぞれA→B→B→A、合計16求解。R1はPython版mpmath、R2は保存版と対応するgmpy backend。2腕内では同じ環境を使った。[replay-environment.json](replay-environment.json)に依存版・入力hash・ソース差を、各`runs/*.receipt.json`に実行command・source hash・結果hashを保存した。Pythonソース差はR1が`float_expressions.py`、R2が`analytic_jacobian.py`、R3が`mpmath_refiner.py`の各1ファイルだけだった。

R3の当初の完全求解案は30秒設定が旧公開APIの最低180秒制約に拒否された。求解前の2エラーは`setup-errors/`へ残し、成功・失敗数に含めない。その後、距離0の同じ回帰例で、120桁の開始点 `(2+ε, sqrt(2)+ε)`（ε=1e−40、1e−60）を固定し、元のpost-LM closureと最終検証器だけを直接実行した。各点を180桁の既定検証と350→500桁の高精度検証へ渡した。後者は元の[assemble_exact_results.py](/home/kabatan/work/solver-experiment/research-archives/2026-09-08/local/benchmarks/local-evaluation/solver-improvement-20260907/stage8-scalar-budget-source/src/geosolver/engine/standard/orchestration/assemble_exact_results.py:220)が250桁候補へ選ぶ段階に対応する。R3は2腕×2開始点であり、ABBA反復でも自然問題の正答率比較でもない。

R1の残差例 `[0.1,0.2,0.3]` では二つのノルム式が1 ulp異なる。ただしこれは演算差の小例で、実際の探索で最初に分岐した点を同定したものではない。目的関数をnormからnorm²に変えた実験とも区別する。

追試する場合は、以下の各行を別コマンドとして順に実行する。保存済みの求解結果は上書きしない仕様なので、新しい一時ディレクトリへスクリプトだけを複製する。元のarchiveとプロジェクトPythonが存在する環境を想定する。

```bash
q33_rerun_dir="$(mktemp -d /tmp/q33-rerun-XXXXXX)"
cp jssa/strategy/astra-consult-18/Q33/reproduce.py jssa/strategy/astra-consult-18/Q33/stability_probe.py jssa/strategy/astra-consult-18/Q33/analyze.py "$q33_rerun_dir/"
q33_python=/home/kabatan/work/solver/.venv/bin/python
"$q33_python" "$q33_rerun_dir/reproduce.py" prepare
"$q33_python" "$q33_rerun_dir/reproduce.py" run norm HMMT-2013-FEB-GEO-04 --seed 1 --indices 0 1
"$q33_python" "$q33_rerun_dir/reproduce.py" run norm HMMT-2013-FEB-GEO-04 --seed 1 --indices 2 3
"$q33_python" "$q33_rerun_dir/reproduce.py" run norm HMMT-2011-FEB-ALGGEO-18 --seed 0 --indices 0 1
"$q33_python" "$q33_rerun_dir/reproduce.py" run norm HMMT-2011-FEB-ALGGEO-18 --seed 0 --indices 2 3
"$q33_python" "$q33_rerun_dir/reproduce.py" run analytic HMMT-2023-FEB-GEO-04 --seed 0 --indices 0 1
"$q33_python" "$q33_rerun_dir/reproduce.py" run analytic HMMT-2023-FEB-GEO-04 --seed 0 --indices 2 3
"$q33_python" "$q33_rerun_dir/reproduce.py" run analytic HMMT-2024-FEB-GEO-10 --seed 0 --indices 0 1
"$q33_python" "$q33_rerun_dir/reproduce.py" run analytic HMMT-2024-FEB-GEO-10 --seed 0 --indices 2 3
timeout 60 "$q33_python" "$q33_rerun_dir/stability_probe.py" stage8-scalar-budget-source
timeout 60 "$q33_python" "$q33_rerun_dir/stability_probe.py" stage9-noadaptive-source
"$q33_python" "$q33_rerun_dir/analyze.py"
```

保存結果の再集計だけならプロジェクトPythonで`analyze.py`を実行する。出力は[replays.csv](replays.csv)、[candidate-transitions.csv](candidate-transitions.csv)、[stability.csv](stability.csv)、[replay-summary.json](replay-summary.json)、[historical-checks.json](historical-checks.json)。ソースsnapshotは索引のSHA256を照合して`/tmp`に展開し、製品ソースは変更していない。全新規ファイルは5,000,000 bytes未満を確認する。
