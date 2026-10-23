# Q14：NOMAD の hard 罰則

判定と結果は [answer.md](answer.md)、コード上の根拠は [code-audit.md](code-audit.md)。事前登録本文は [preregistration.md](preregistration.md)。src/ や既存データの変更・インストール・ネットワーク接続・commit・push は行わない。

## 固定した比較

292問の id と n_vars から SHA-256 順で選んだ24問 × seed 0,1,2 × 通常 B / 罰則除去 N の144予定枠。初回は121 rawと23失敗・欠測記録を保存した。CLI未起動22枠の補足は別扱い。`summary.json` の `complete=true` は144枠全てを計上した意味で、全枠の正常完了を意味しない。選定は [selected-cases.csv](selected-cases.csv)、出典・src のハッシュは [selection-manifest.json](selection-manifest.json)、実行前に固定したコード・DSL・実行環境は [campaign-manifest.json](campaign-manifest.json)。成績による対象変更はない。

N は既定1段目 NOMAD に返す有限の hard 罰則 `1e6` だけを除く。元の候補 score と hard フラグ、後段 NOMAD、LM、精密化、最終検証は維持する。詳細は [implementation.md](implementation.md)。実 worker への導入は patch/sitecustomize.py。合成 evaluator による配送・不変性の確認は [patch-check.json](patch-check.json)。

ランナーは `benchmarks.research_runner._run_one` を再利用。180秒、cores=1、外側の監視188秒、4並列以下、数値ライブラリ1スレッド。各問題・seed の B/N は同じ CPU slot で順番に走る。参照答は solver には渡さず、実行後に既存 canonical-key 集合一致で採点する。**高負荷環境なので時間は参考値。**

## ファイル

- `runs/{B,N}/runs/<id>/<seed>.json`：既存ランナー形式の raw。エラーも含む。
- 同じ場所の `*.audit.jsonl`：worker の hook、NOMAD の入口とパラメータ、各評価の元目的値・返却目的値・hard 判定。
- `*.receipt.json`：CPU、開始終了、load average、ランナー例外。
- `per-run.csv`、`per-problem.csv`、`summary.json`：事前登録に従う採点・集計。全144実行が揃うまで P1/P2 は null。
- `paired-checks.csv`：両条件の最初の NOMAD 入力、CPU の一致。片方が未到達なら座標比較は欠測。
- `trace-pairs.csv`、`trace-summary.json`、`objective-ordering-examples.json`：既存ログだけの事後記述。残差の大小は答え集合の正しさではなく、native poll の受理／拒否も直接測定していない。P1/P2 は変更しない。
- `directory-preparation.json`：途中で出力先エラーがあったため、残る全登録出力フォルダを先に作った記録。元の失敗結果は保持する。
- `nomad-parameter-help.txt`：インストール済み NOMAD 4.5.1 の一次資料（組込み help）。
- `initial-attempt-inventory.json`：元121 rawのハッシュと、初回の未起動・最終欠測23枠。失敗計上用の記録は `failure_accounting_record=true` で実測と区別する。
- `completion/`：初回未起動22枠の事後補足。21 rawと最終結果欠測1件の記録。主解析を上書きしない。
- `completion-summary.json`、`completion-per-run.csv`、`completion-merged-per-run.csv`、`completion-merged-trace-pairs.csv`：事後補足と、未起動分を補った参考集計。主解析は引き続き `summary.json`。

## 再集計（探索は実行しない）

repo のルートで次を実行する。bytecode は作らず、出力はこのフォルダ内だけ。

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/nomad-wall/aggregate_robust.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/nomad-wall/trace_diagnostics.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/nomad-wall/final_analysis.py
```

本実行は `campaign.py --run`。コード・入力の固定ハッシュが違えば開始せず、raw がある実行は正誤・エラーを問わず再実行しない。初回の `--first-pair` は本実験の最初の1対であり、主集計に含める。`select_cases.py` は既存選定表を上書きしない。

engine_error の `diagnostics: null` に対する読み取り補正だけを [reporting-fix.md](reporting-fix.md) に記録した。元の集計コード・事前基準・raw は変更していない。

1ファイル20MiBを上限とする RLIMIT_FSIZE を実行ヘルパーに設定した。一時ファイルも各実行の `*.temp/` 内に限定した。

補足の起動障害と逐次化は `completion-sequential-receipt.json` に記録した。補足でも最終結果が得られなかった1件は `completion-missing-result.json`。成功と推定せず、再実行もしていない。
