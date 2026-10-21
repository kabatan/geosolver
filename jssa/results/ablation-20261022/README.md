# アブレーション（凍結版 60db4b6、323問×seed 0）

- スイッチ: ローカルブランチ `jssa-ablation`（67ad79a、push していない）。環境変数 `GEOSOLVER_ABLATE_*` で各部品を1つずつ止める。engine lockは更新済み。各実行の config_snapshot に有効なスイッチを記録した。
- 基準: 本計測（jobs 6）のseed 0。
- 負荷: NO_ANALYTIC_JAC は jobs 5、他は jobs 6。NO_ANALYTIC_JAC・NO_RESCUE・NO_SCALE_CHART の実行中は、書き換え実験（CPU 20、1件ずつ）も並行していた。そのため時間比の1.1〜1.2倍程度は負荷差の可能性があり、部品の効果とは断定しない。
- 各スイッチで止めるもの:
  - NO_ALGEBRAIC: 有限個の多項式による候補生成（代数的前処理）。
  - NO_NOMAD: 主探索のPyNomadを止め、SciPy multistartに切り替える（救済探索はNOMADのまま）。
  - NO_ANALYTIC_JAC: 解析的なJacobianを使わず、数値差分にする。
  - NO_RESCUE: 救済探索。
  - NO_SCALE_CHART: 正の拡大縮小による候補生成。
  - NO_SECOND_ATTEMPT: hybridの第2探索。
- 結果: `ablation-summary.md`（表）、`ablation-vs-baseline.csv`、各armの `*-per-run.csv` と `*-summary.json`。
