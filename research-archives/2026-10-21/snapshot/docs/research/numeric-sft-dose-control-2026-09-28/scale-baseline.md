# Single-length scale baseline

This is a posthoc exploratory baseline, run after the reserved-shape results had been observed. It asks how much those results can be explained by a one-length size rule. It is not a replacement for the primary evaluation and cannot establish that SFT failed to learn geometry.

The sole predictor per source is `prediction = c × L`, where `L` is the first positive explicitly assigned two-point length in the problem body after removing the fixed instruction prefix. `c` is the median of `training target / L` over that source's eight correct training examples. No heldout target or model error was used to select `L`; source templates with inconsistent first-length fields cause the script to stop.

DA02 starts with a 60° angle, so the first length is AB. DB12 starts with a 45° angle, so the first length is BC; its ratio statements occur later. The other first-length fields are selected directly by problem-text order.

## Feature and fitted scale by source

| Source | First length L | n train | c = median(y/L) |
|---|---:|---:|---:|
| DA01 | AB | 8 | 0.5197149098 |
| DA02 | AB | 8 | 0.4187623926 |
| DA03 | BC | 8 | 2.775979576 |
| DA04 | AP | 8 | 1.373753881 |
| DA06 | AO | 8 | 0.17000668 |
| DA07 | AM | 8 | 0.7829936908 |
| DA08 | OQ | 8 | 0.0496443327 |
| DA11 | AB | 8 | 0.5899372606 |
| DB02 | AB | 8 | 0.870749153 |
| DB12 | BC | 8 | 0.6571223253 |

## Reserved-shape comparison

`precise` uses the frozen scorer tolerances (absolute error ≤ `absolute_tol` or relative error ≤ `relative_tol`). RE is absolute relative error. `within10` counts relative error ≤10%. All values aggregate the same 30 reserved prompts.

| Predictor | Precise | RE median | RE mean | Mean abs log ratio | Within 10% |
|---|---:|---:|---:|---:|---:|
| First-length scale baseline | 0/30 | 0.1793 | 0.2640 | 0.3079 | 9/30 |
| Correct512 | 0/30 | 0.1695 | 0.2969 | 0.2441 | 13/30 |

The scale baseline is competitive but the metrics are mixed: its mean RE is lower (0.2640 vs 0.2969), while Correct512 has lower median RE (0.1695 vs 0.1793), lower mean abs-log (0.2441 vs 0.3079), and more within10 cases (13/30 vs 9/30). This simple size rule can account for some numerical performance, but it does not uniformly match Correct512; neither result alone establishes or rules out learning geometric relations.

Macro average of the ten source-level means:

- Scale baseline: mean-source RE `0.2640`, mean-source abs-log `0.3079`, mean-source within10 `30.00%`.
- Correct512: mean-source RE `0.2969`, mean-source abs-log `0.2441`, mean-source within10 `43.33%`.

## Per-source averages

Each row averages the three reserved variants in that source. `RE mean` and abs-log compare the simple baseline with Correct512 on the same gold values.

| Source | Scale RE mean | Correct512 RE mean | Scale abs-log | Correct512 abs-log | Scale within10 | Correct512 within10 |
|---|---:|---:|---:|---:|---:|---:|
| DA01 | 0.0956 | 0.0779 | 0.1031 | 0.0728 | 2/3 | 2/3 |
| DA02 | 0.1919 | 0.3056 | 0.1877 | 0.3224 | 0/3 | 1/3 |
| DA03 | 0.1691 | 0.0236 | 0.1848 | 0.0233 | 1/3 | 3/3 |
| DA04 | 0.2059 | 0.2231 | 0.2363 | 0.1977 | 0/3 | 1/3 |
| DA06 | 0.6126 | 0.4755 | 0.4646 | 0.3777 | 0/3 | 0/3 |
| DA07 | 0.5634 | 0.9643 | 0.8420 | 0.6376 | 0/3 | 0/3 |
| DA08 | 0.5429 | 0.6467 | 0.8055 | 0.5451 | 0/3 | 0/3 |
| DA11 | 0.1049 | 0.1032 | 0.1137 | 0.1133 | 1/3 | 2/3 |
| DB02 | 0.1287 | 0.1140 | 0.1169 | 0.1156 | 2/3 | 1/3 |
| DB12 | 0.0246 | 0.0349 | 0.0250 | 0.0352 | 3/3 | 3/3 |

The feature map, per-source coefficients, and per-prompt predictions/errors are preserved in `scale-baseline.json`. The script is rerunnable with the four frozen runtime inputs and uses no model inference.

This is only a coarse size-scaling diagnostic. A better Correct512 score than this baseline would show that one proportional length per source does not explain all performance; it would not by itself prove general geometric reasoning. A competitive baseline would likewise not disprove geometry learning.

Input SHA-256 values are recorded in the JSON. Precise tolerances: absolute `0.0001`, relative `1e-05`.
