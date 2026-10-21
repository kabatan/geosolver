# Post-hoc constant-prediction baseline

This exploratory check asks whether the numeric-only diagnostic's new-shape outputs could be explained by emitting a typical target for each construction family. It uses only the 80 frozen training targets to form arithmetic means/medians. It fits no scale rule, shape feature, or geometric formula. It does not alter the preregistered strict score or primary evaluation. The existing diagnostic still reports strict 0/10 for each arm.

The per-source baselines use the known source ID, making them a deliberately strong post-hoc reference: for each heldout `variant-09`, predict either the mean or median of that source's eight training values. Global baselines use the mean or median of all 80 values. Errors are unweighted across the 10 source types. Relative error is `abs(prediction - expected) / expected`; absolute log ratio is `abs(log(prediction / expected))`.

## New-shape heldout comparison

The target and train-mean/train-median columns show the numeric scales; all error columns are relative error, lower is better.

| Source | Heldout target | Train mean | Train median | Source-mean RE | Source-median RE | Global-mean RE | Global-median RE | Base RE | SFT-A RE | SFT-B RE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DA01 | 12.139 | 9.455 | 9.054 | 0.221 | 0.254 | 0.182 | 0.460 | 0.628 | 0.168 | 0.086 |
| DA02 | 7.362 | 5.164 | 5.453 | 0.299 | 0.259 | 0.348 | 0.110 | 0.976 | 0.161 | 0.433 |
| DA03 | 93.464 | 36.332 | 33.982 | 0.611 | 0.636 | 0.894 | 0.930 | 0.964 | 0.582 | 0.582 |
| DA04 | 11.737 | 7.044 | 6.502 | 0.400 | 0.446 | 0.154 | 0.442 | 0.941 | 0.113 | 0.454 |
| DA06 | 1.360 | 1.440 | 1.348 | 0.059 | 0.009 | 6.299 | 3.819 | 6.818 | 0.076 | 0.076 |
| DA07 | 2.887 | 13.636 | 7.791 | 3.723 | 1.699 | 2.439 | 1.270 | 0.018 | 4.024 | 4.024 |
| DA08 | 3.399 | 1.095 | 0.830 | 0.678 | 0.756 | 1.921 | 0.928 | 5.153 | 0.355 | 0.355 |
| DA11 | 6.751 | 8.567 | 7.544 | 0.269 | 0.118 | 0.470 | 0.029 | 0.892 | 0.289 | 0.289 |
| DB02 | 7.986 | 10.100 | 10.765 | 0.265 | 0.348 | 0.243 | 0.179 | 0.534 | 0.094 | 0.094 |
| DB12 | 9.065 | 6.438 | 6.342 | 0.290 | 0.300 | 0.095 | 0.277 | 0.108 | 0.108 | 0.108 |

Aggregate errors across the 10 heldout sources:

| Predictor | Mean RE | Median RE | Mean absolute log ratio | Median absolute log ratio |
| --- | ---: | ---: | ---: | ---: |
| Source training mean | 0.681 | 0.294 | 0.562 | 0.348 |
| Source training median | 0.483 | 0.324 | 0.537 | 0.329 |
| Global training mean (9.927) | 1.305 | 0.409 | 0.790 | 0.342 |
| Global training median (6.554) | 0.844 | 0.451 | 0.757 | 0.599 |
| Base model | 1.703 | 0.916 | 1.785 | 1.937 |
| SFT-A | 0.597 | 0.164 | 0.389 | 0.165 |
| SFT-B | 0.650 | 0.322 | 0.471 | 0.346 |

The SFT outputs are better than either global constant on the relative-error summaries and mean absolute log ratio; SFT-B's median absolute log ratio (0.346) is slightly above the global-mean baseline (0.342). The source-conditioned median is a competitive explanation: its median relative error (0.324) is close to SFT-B (0.322), and its mean relative error (0.483) is lower than either SFT seed (0.597/0.650). SFT-A has a notably lower median relative error and both seeds have lower mean absolute log ratio than the source-median baseline. The per-source rows are mixed: the SFTs improve over source medians on several families, while both miss DA07 badly where its heldout value is below the training-family center.

So typical-value behavior plausibly explains a substantial part of the apparent continuous-error improvement, particularly for seed B; the comparison does not show that it explains all of it. The SFTs still score strict 0/10, the split is only 10 source types, and this post-hoc source-aware baseline is not evidence of accurate geometry solving or a causal evaluation.

## Seen-example leave-one-out check

For each diagnostic `variant-01` training example, its target was removed from both its source's 8 values and the global 80 before calculating means/medians. This prevents the baseline from reading the evaluated label. The table compares those 10 LOO targets with the same per-arm diagnostic predictions.

| Predictor | Mean RE | Median RE | Mean absolute log ratio | Median absolute log ratio |
| --- | ---: | ---: | ---: | ---: |
| Source LOO mean (7 values) | 0.972 | 0.640 | 0.712 | 0.683 |
| Source LOO median (7 values) | 0.860 | 0.628 | 0.708 | 0.663 |
| Global LOO mean (79 values) | 5.204 | 0.670 | 1.158 | 1.033 |
| Global LOO median (79 values) | 3.453 | 0.777 | 1.205 | 1.074 |
| Base model | 4.105 | 0.817 | 1.554 | 1.143 |
| SFT-A | 1.240 | 0.398 | 0.616 | 0.487 |
| SFT-B | 1.247 | 0.398 | 0.623 | 0.487 |

The LOO comparison is also exploratory. SFT improves on the global constants and has lower median errors than the source LOO constants, while mean relative error remains higher than the source LOO mean/median baselines. No target value from a `variant-01` row is used in its own LOO prediction.

## Reproduction

Run the small stdlib-only script; it validates row coverage and provenance/metric consistency, then rewrites the runtime JSON report with input hashes and full per-source records:

```bash
python3 docs/research/related-numeric-sft-2026-09-28/coarse-error-baseline.py
```

The machine-readable output is `qwen/.runtime/related_numeric_sft_20260928/coarse-error-baseline.json`. It records mean/median predictions, per-row relative and log-ratio errors, LOO results, aggregate metrics, and SHA-256 hashes of the three read-only inputs.
