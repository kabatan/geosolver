# コード監査：hard feasibility の役割

対象は `src/` の凍結版 60db4b6。現在の作業ツリーとの差分はない。各ソースの SHA-256 は [selection-manifest.json](selection-manifest.json) に保存した。以下は探索成績に依存しないコード上の事実である。

## 結論

**hard feasibility は、NOMAD の目的値に加える有限の一定罰則として実装されている。明示的な extreme barrier / progressive barrier ではない。** 有限な不許容点には勾配のある制約違反量を返しておらず、単に `1e6` を加算する。このため依頼の「既に PB 等で壁を持たないなら中止」には該当しない。

## 実際の呼出しと値

| 論点 | 凍結コード | 確認結果 |
|---|---|---|
| 既定の入口 | [external_pipeline_config.py](../../../src/geosolver/engine/standard/contracts/external_pipeline_config.py) 60,124–151行 | primary は disco_mads、production は外部 seed 1個 |
| 実 worker | [worker.py](../../../src/geosolver/runtime/worker.py) 90–106行 | production_baseline_tier を作って external pipeline を呼ぶ |
| Native への出力型 | [nomad_config.py](../../../src/geosolver/engine/standard/search/nomad_config.py) 76–91行 | `BB_OUTPUT_TYPE OBJ`。制約出力 PB/EB はない |
| 罰則の大きさ | 同 18,45行 | `guard_penalty = 1e6` |
| hard 不許容 | [nomad_blackbox_adapter.py](../../../src/geosolver/engine/standard/search/nomad_blackbox_adapter.py) 119–140,164行 | 目的値に罰則を加算し、callback は成功 `1` を返す |
| 計算が非有限 | 同 92–118行 | failure record を保存し `0` を返す。hard の単なる不許容とは別 |
| Native 呼出し | [nomad_backend.py](../../../src/geosolver/engine/standard/search/nomad_backend.py) 105–130行 | adapter と build_params の結果をそのまま PyNomad.optimize に渡す |
| 候補収集 | 同 133–156行、[build_guard_feasible_ledger.py](../../../src/geosolver/engine/standard/search/build_guard_feasible_ledger.py) 31–38行 | 元の score を用い、guard と hard の通る候補から ledger を作る。無い場合の fallback 選択も存在 |
| 最終判定 | [final_verifier.py](../../../src/geosolver/engine/standard/evaluation/final_verifier.py) 202–213行 | 高精度で元の domain/hard 条件と残差を検査 |

元の等式残差を `F_i(x)`、利用される尺度を `s_i`、hard を通る集合を `H` とすると、有限評価で NOMAD に渡す目的値は

```text
f_B(x) = Σ_i (F_i(x)/s_i)^2 + 10^6 · 1[x ∉ H]
f_N(x) = Σ_i (F_i(x)/s_i)^2
```

尺度がない場合は元の residual_norm_float の二乗を使う。N は今回の介入条件であり、凍結版の既定動作ではない。

許容点 x の等式二乗ノルムが `1e6` 未満なら、不許容な y は等式だけをどれほど減らしても `f_B(y) < f_B(x)` を満たせない。これは**目的値の順序における障害**を示す。しかし、NOMAD が途中の点を評価せず別の許容点へ跳ぶ可能性もあり、許容集合が不連結だとか native の特定 poll が実際に拒否されたという証明ではない。

## EB / PB / hidden constraint の区別

インストール済み PyNomadBBO 4.5.1 の組込み help を [nomad-parameter-help.txt](nomad-parameter-help.txt) に保存した。`BB_OUTPUT_TYPE` の説明では PB と EB は独立した制約出力型であり、OBJ は最小化する目的値である。ここでは OBJ 一つしか指定していない。

`DISCO_MADS_HID_CONST true`、`DISCO_MADS_HID_CONST_OUTPUT_VALUE 1e20` は hidden-constraint 領域を扱う設定である。組込み help も hidden constraint のモードと不連続性検出のモードを区別している。**disco_mads という名称だけから、hard の段差が PB に変換されると解釈してはいけない。** 今回はこの設定を変更しない。

LM では [scipy_multistart_backend.py](../../../src/geosolver/engine/standard/search/scipy_multistart_backend.py) 477–496,530–536行により hard の違反が最終残差行 `1e4` になる。二乗和での段差は `1e8`。NOMAD の段差 `1e6` と同じ数値ではなく、差分ヤコビアン・MINPACK の停止判定も NOMAD にはない。「同じ壁」は、条件の不連続な罰則化という共通部分に限定する。

## 完成 solver への一般化で必要な注意

`run_external_pipeline.py:351–354,391` では algebraic branch discovery が成功すると通常の探索を迂回する。`run_search.py:332–357,434–447` にも整数・1変数の別経路がある。従って「292問の n_vars>=1」も「disco_mads の既定設定」も、NOMAD が必ず使われることを意味しない。

`algebraic_branches.py:664–679` の optional symbolic request には1.5秒の wall deadline がある。実際、最初の本実行の HMMT-2014-FEB-GEO-01 / seed 0 は B が exact_polynomial 由来で NOMAD 未到達、N が NOMAD 到達だった。この N の全200評価は hard 許容で、payload の変更は0だった。**介入が発動していない対でも経路差が起きた**ため、後の経路差や時間差を全て罰則除去に帰してはいけない。高負荷による期限の影響と整合するが、これだけで原因を一意に確定してはいない。

文献に関する主張は、新しい barrier 法を提案したというものではない。利用可能な一次資料として凍結コードと実環境の NOMAD 組込み help を確認した。利用者指定に従いネットワークを使っておらず、最新文献の網羅調査は行っていない。
