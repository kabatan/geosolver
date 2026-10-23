# 実装固定：コード監査後・探索結果を得る前

2026-10-23。事前登録 P0 はコード監査で外れた。中止基準 S0 は不該当。登録本文・対象・seed・成否基準は変更しない。

## コードで確認した事実

- `nomad_config.py:78` は `BB_OUTPUT_TYPE OBJ` の1出力だけ。EB/PB の制約出力は設定していない。`guard_penalty` 既定値は `1e6`（18,45行）。
- `nomad_blackbox_adapter.py:126-140` は `score = scaled_norm_sq + (0 if hard_feasible else guard_penalty)` を `setBBO` で渡す。有限な hard 不許容点も return 1（164行）。これは有限の段差罰則であり、数学的な無限大の extreme barrier でも progressive barrier でもない。
- 評価が非有限などで status != OK なら return 0（96-118行）。`DISCO_MADS_HID_CONST true` と出力値 `1e20` はこの失敗評価の扱いに関わる別の設定。hard 不許容の `1e6` とは区別する。
- `build_guard_feasible_ledger.py:31-38` は元の guard と hard を通る候補を選ぶ。`final_verifier.py:206-213` は高精度で元の hard 条件を検証する。
- `run_search.py:434-447` などには NOMAD 前の別経路があり、disco_mads 指定でも NOMAD 未到達になり得る。これを検査して未到達率を報告する。

## 介入点

実 worker のみで `sitecustomize` を有効にする。`run_search._run_search_baseline` の search_mode が `disco_mads` である間の `NomadBlackboxAdapter._evaluate` だけに介入する。hybrid_legacy_nomad 内の後段 NOMAD と rescue は通常のまま。すなわち既定の1段目への介入であり、局所 LM 等は変更しない。

両条件とも元の `_evaluate` を一度だけ呼び、point proxy が setBBO の payload を一時保持する。元の `evaluate_search_point` の返却値を同じ呼出し内で観測し、元実装と同じ順序・尺度で等式の二乗ノルムを得る。B は payload をそのまま返す。N は有限な hard 不許容点の payload だけをこの二乗ノルムに置き換える。罰則を加えた float から引き算すると桁落ちするため、その方法は用いない。

`adapter.records` の score・hard_feasible・guard_ok を含む全フィールドは元のままにする。候補の抽出・順位づけ・後段への受け渡しは元の規則を保つ。評価関数・制約条件・出発点生成を差し替えず、NOMAD へ返す1スカラーだけを変更する。これにより軌道とその後の候補集合が変わることは介入の帰結である。

両条件で、元 payload と再計算した二乗ノルム＋罰則が一致することを各評価で確認する。非有限評価は元の return 0 を維持し payload を捏造しない。hook 読込み失敗は exit 91、監査不一致は実行の不適合として記録する。

ログは開始点・実効パラメータ・各点の元 hard 判定・等式二乗ノルム・元 score・実際に返した score・評価失敗・候補集計を記録する。native NOMAD の poll 受理フラグを直接観測していないので、「等式が減るのに罰則込み目的が増える評価」を実際の拒否ステップと断定しない。

既存 `benchmarks.research_runner._run_one` をそのまま呼ぶ。環境変数が競合しないよう別プロセスのランナーを最大4個とし、各問題・seed の B/N は同じ CPU slot で順次実行する。一時フォルダも nomad-wall/ 配下。参照答は solver へ渡さず、実行後だけ既存の集合一致採点に用いる。

本実験前の検証は、合成 evaluator による payload・記録不変性と、最初の事前選定問題・seed 0 の本実行を兼ねた配送確認に限る。配送確認の成否による対象の差し替えや結果の除外はしない。
