# Q27d 再現手順

成果は[answer.md](answer.md)。原データは読取専用、出力はこのフォルダ内のみ。新規局所探索・完成solver実行は行わない。

repo直下から指定Pythonで順に実行する。

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q27d/explore.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q27d/validate.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/strategy/astra-consult-18/Q27d/supporting_checks.py
```

使用する追加ライブラリは既設NumPy・SciPy。最初の探索コード案はpandasが無いためimport段階で終了。インストールせず標準csvへ書き換え、seed 1を開く前に固定した。

`validate.py`は初回に計画・コード・seed 0表のハッシュを`registration-lock.json`に保存し、それからseed 1を読む。再実行時にハッシュが変わっていれば止まる。入力が同じなら探索出力も決定的に再現される。実時間は再実行で変わる。

| ファイル | 内容 |
|---|---|
| `census-seed0.csv`, `census-both-seeds.csv` | 292問のd、native条件数m、局所p、開始数、代数系の次数、完成solver成績、許容条件・同定集計 |
| `by-*.csv`, `dimension-*.csv` | サイズ・密度・次数・許容条件ごとの記述集計 |
| `curve-fits.json`, `curve-cv-predictions.csv`, `curve-seed-replay.json` | 指数・べき・ロジスティック・段差・一定値の比較。問題等重みの二乗誤差、IDハッシュ5分割 |
| `preregistration.md`, `registration-lock.json` | 別seed確認の事前固定。未知問題の盲検ではない |
| `validation.json`, `validation-groups.csv` | 主予言3本、dをそろえた隣接対照、bootstrap |
| `expansion.csv`, `supporting-checks.json` | 43問展開比較、既存7問追試、GMB・PSLQ等の照合 |
| `zero-hit-replay.csv`, `secondary-replay.json` | 局所0-hitと完成solver、規模順位逆転の別seed確認 |
| `degree-replay.csv`, `real-root-counts.csv` | 答え次数・式の最大次数・msolve実根数の分離 |
| `*-manifest.json`, `seed-metadata.csv`, `data-audit.json` | 入力SHA-256と分母・seedメタデータ照合 |

`real-root-counts.csv`は`supporting_checks.py`で再生成できる。入力は`census-both-seeds.csv`の`msolve_class=answer_set_matches`の185問を`real_solutions`で1〜2、3〜8、9以上に分け、各群の問題数・平均d・平均p/p1を出したもの。

定義と注意：

- dはDSLの探索変数数、mはrawの`n_constraints`。`degree`は答えの最小多項式の次数、`max_degree`は変換後の多項式系の最大次数。真の複素根数ではない。
- pはseed 0の完了開始のhit率、p1はseed 1。pF/pIは許容／非許容開始ごとの成功率。観測開始0の群は欠測。
- `large_poly`はN≥10またはD≥8という既存Q21cに合わせた区分。変換不能で両方欠測の行はFalseとなるため、その区分で群間因果比較はしない。
- 曲線はd=1〜9の8水準の近似。段差は訓練群で両側10問以上の切断点から選ぶ。
- 隣接対照bootstrapは問題単位でd層を保つ。探索後の選定を補正した発見確率ではない。
- 完成solver969実行、選定36問の精密化、GMBの保存採点出力136件は別の分母。一つの成功率へ結合しない。
- 元15問dose-responseの個別rawはこの作業ツリーで欠けており、既存補足表の二次引用に限定した。

封印tar、unseen-1983のsolver結果、fetch、src変更、pip install、commit/pushは使っていない。
