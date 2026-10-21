# Scale-normalized behavior (posthoc)

The length field and median coefficient come unchanged from the previous scale baseline. No new model was run. These diagnostics describe saved outputs; they do not identify an internal algorithm or establish a causal reason for transfer.

| Arm | Split | n | Within-source correlation of log(y/L) | Normalized pair-order matches | Squared-log improvement over cL |
|---|---|---:|---:|---:|---:|
| base | trained_all | 72 | 0.0544 | 133/245 | -7.8676 |
| base | reserved_shape | 28 | -0.0574 | 16/27 | -14.1635 |
| correct128 | trained_all | 80 | 0.4646 | 194/280 | -3.0072 |
| correct128 | reserved_shape | 30 | -0.0589 | 21/30 | -5.4368 |
| correct512 | trained_all | 80 | 0.9463 | 259/280 | 0.9005 |
| correct512 | reserved_shape | 30 | 0.1954 | 19/30 | 0.3368 |
| shuffled512 | trained_all | 80 | 0.1914 | 164/280 | -0.3343 |
| shuffled512 | reserved_shape | 30 | 0.1550 | 19/30 | -0.5183 |

Base has 8 nonpositive trained outputs and 2 nonpositive heldout outputs, omitted from log analysis. Thus base columns are incomplete and not directly comparable. All positive-label SFT arms include all 80/30 outputs.

The 30 heldout rows are only 3 shapes in each of 10 sources; their 30 within-source pairs are dependent. This is not 30 independent tests. A high correlation with poor precision can coexist: following the direction of geometric variation is weaker than learning an exact reusable relation.

Reproduce with `python3 shape_residual.py`. Per-source figures, every normalized row, and input hashes are in `shape-residual.json`.
