# Q27a：時間・回数の探索と既存seedによる確認

結論は[answer.md](answer.md)。Aの核としては不可。強い効果のseed再現は確認したが、深い理論が不可欠な現象には到達していない。

## 保存したもの

| ファイル | 内容 |
|---|---|
| `answer.md` / `sources.md` | 結論・根拠・過去12本との自己点検、文献の確認範囲 |
| `preregistration.md` / `selection.json` / `registration-lock.json` | seed1一括集計前の予言、固定113問・閾値・方策、ローカル時刻とハッシュ |
| `explore.py` / `exploration-*.csv` / `exploration-summary.json` | seed0からの探索。集計結果を見て候補を選んだ段階 |
| `confirm.py` / `confirmation-start.json` / `confirmation-summary.json` | 固定手順の別seed確認、開始時刻と実行コードハッシュ |
| `confirmation-per-problem.csv` / `confirmation-classes.csv` | 全113問の両側の件数・効果量・費用比、停止分類。`delta_conservative_*`は2つのWilson区間の端を引いた記述的な幅で、多重比較調整済みの区間ではない |
| `local-seed0.csv` / `local-seed1.csv` | 292問ごとの記述統計。各seed内で計算した参考の最小費用も含むが、主検証はseed0で固定した方策のみを使用 |
| `pipeline-fixed-cohorts.csv` / `pipeline-zero-cohort.csv` | 局所hit0群29問と高p・長時間1問の完成solverの時間・成否 |
| `confirmation-size-strata.csv` | 変数数別の分布。漸近的計算量の推定ではない |
| `supplement.py` / `supplement-summary.json` | PSLQ、精密化、msolve、作図展開、GMB、許容条件の補助確認 |
| `precision-reversals.csv` / `msolve-descriptive.csv` | 精度増加での隣接成否逆転、実根数別の既存時間 |
| `refinement-history-audit.csv` / `dose-input-inventory.csv` | 原形Oの段階履歴、15問60入力の変数数・条件数 |
| `input-manifest-*.json` | 読んだ計算用入力のSHA-256とサイズ |
| `verify.py` / `verification.json` | ハッシュ、固定条件、113問の算術、basinsとの独立照合 |

`nfev`は保存されたtelemetryの残差評価回数。`sec`は1開始の局所処理の秒数。`wall_time_s`は完成solver全体。これらを混同しない。局所の`hit`は参照解と照合した既存の終点分類で、厳密な座標の証明でも全値回収でもない。

## 再集計

リポジトリルートから、指定Pythonと既存numpyだけで順番に実行する。新しい局所探索は行わない。**結果・集計時刻を上書きするため、初回結果を残す場合はQ27a内へコピーしてから再実行する。** 事前登録・選定・登録ハッシュは再生成しない。

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q27a/explore.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q27a/confirm.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q27a/supplement.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q27a/verify.py
```

初回の探索集計本体は0.95秒、確認集計本体は0.52秒。import、文献調査、コード作成、報告作成の時間を含まない。処理速度の比較実験ではない。

## 実施範囲

新規solver実行0回。src・既存データ・他担当の成果物は変更していない。pip install、git fetch、commit、pushなし。封印tarとunseen-1983のsolver結果は参照していない。計算は単一プロセス、numpyの数値スレッドを1に制限した。

初回の`explore.py`はpandasのimportで停止した。データ集計前の失敗であり、その後stdlib+numpyへ変更して一度集計した。予言固定後のconfirm.pyに結果を変える修正はしていない。確認結果を用いた追加の対象選定・新規solver計算も行っていない。文献・他の既存表の補助確認は記述的なものとして分けた。
