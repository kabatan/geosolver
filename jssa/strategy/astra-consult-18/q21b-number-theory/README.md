**Q21b 再現手順**

結論・候補(a)〜(h)・測定結果は[answer.md](answer.md)。[protocol.md](protocol.md)は主実験の結果を見る前、[followup-protocol.md](followup-protocol.md)は主実験の結果を見た後、追加診断の結果を見る前に保存した。両者を事前登録済みの未知データ検証とは呼ばない。

リポジトリのルートで、以下を順番に実行する。指定の環境だけを利用し、依存追加は不要。各呼出しは1 threadで、新しい局所探索・全solver実行を含まない。出力先はこのディレクトリだけで、再実行すると既存のQ21b成果物を上書きする。

```bash
export PYTHONPATH=src
export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21b-number-theory/analyze.py census
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21b-number-theory/analyze.py precision
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21b-number-theory/analyze.py replay
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21b-number-theory/followup.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q21b-number-theory/verify.py
```

PSLQ関連の1呼出しは2秒で打ち切る。Linuxの`SIGALRM`を使うため、別のスレッド内から実行しない。タイムアウトはマシン負荷で再現しないことがあり、成功・不成功とは別に保持する。主精度実験全体の上限は20分。今回の3310呼出しは約3.05秒、追加診断は約17.35秒で終了した。文献調査・コード作成・集計を含む作業も指定の2時間内。

| ファイル | 内容 |
|---|---|
| `manifest.json`, `saved-candidate-manifest.json` | Python・パッケージ版、ソース246ファイル、主入力5ファイル、保存結果316ファイルのSHA-256 |
| `values.json`, `answer-census.csv`, `answer-values.csv` | 323問・338答値の厳密式、最小多項式、次数、高さ、根号深さ。πの7値は代数的集計から除外 |
| `precision.jsonl`, `precision.csv`, `precision-summary.csv` | 331値×10桁数の生の返却値・判定・集計 |
| `precision-per-value.csv`, `problem-summary.csv` | 初回成功格子点、残る全格子点でも成功する最初の点、既存の局所探索p・変数数・人間難度 |
| `saved-candidates.csv`, `replay-selection.json` | 保存高精度値と参照値の一致桁数、固定選定規則で選んだ6問 |
| `recoding-replay.json`, `recoding-replay.csv` | 原形／有理シフト、保存値／理想値、80／120桁の54呼出し |
| `bound-experiment.json`, `bound-experiment.csv`, `bound-reversals.csv` | 3・4次の全10問×5桁数×4係数上限の200呼出し、適格な上限間での逆転 |
| `oracle-diagnostic.csv`, `oracle-summary.json` | 真の次数・高さを与える対照。未知の問題を解いた成績ではない |
| `final-verifier.csv` | 誤多項式8件の追加検証。全件棄却 |
| `human-strata.csv`, `human-contrasts.csv` | 大会別の人間難度上下半分、中央値差とbootstrap区間 |
| `verification.json` | 入力非改変、集計、厳密な有理変換、上限逆転の会計を独立に確認した結果 |
| `sources.md` | 文献書誌、確認できた部分、未確認部分、既存報告との重複 |

`precision`は正解式を丸めた入力を使う。`replay`は既存solverの保存値も使うが、参照値と一致した候補を選ぶ機構診断であり、ブラインドな成功率ではない。`wrong`は返された多項式が参照最小多項式と違うことを意味し、完成solverの最終誤答を意味しない。`stable_correct_grid`は離散的な測定点に限る安定性で、未測定の全精度での保証ではない。

手順上の小さな誤りとして、追加スクリプト作成時に空のプレースホルダーを作業ルートへ一時作成し、直後に削除した。既存ファイルの内容変更や成果物の範囲外への残存はない。検算スクリプト初回には閉じ括弧の構文誤りがあり、修正後の実行がPASSした。報告時に、プロトコルで約束した保存候補の有無を`problem-summary.csv`へ結合する集計処理を補った。実験を再実行したり研究用の対象・条件・閾値を変更したりしていない。
