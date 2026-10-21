# Code and numeric SFT training-loss diagnostic

This diagnostic uses only the four existing `examples.jsonl` training logs. Loss is teacher-forced cross-entropy; it is not a measure of free-generation quality or mathematical acquisition.

## Position and loss validation

Both training paths are continuous after joining the old32 and continuation128 segments: positions 0–511, 512 records each, with no missing/nonfinite loss values.

| Group | Old32 rows | Continuation rows | Combined rows | Exact examples | Old32 coverage | Continuation coverage |
|---|---:|---:|---:|---:|---:|---:|
| Code | 128 | 384 | 512 | 13 | 13/13 | 13/13 |
| Numeric | 128 | 384 | 512 | 56 | 56/56 | 56/56 |

## Overall loss by segment

| Group | Segment | Rows | Target tokens | Example-mean loss | Token-weighted loss | Exposure per example |
|---|---|---:|---:|---:|---:|---:|
| Code | old32 | 128 | 31875 | 0.542411 | 0.501342 | 9–10 |
| Code | continuation128 | 384 | 95525 | 0.335507 | 0.378533 | 29–31 |
| Code | combined 128 updates | 512 | 127400 | 0.387233 | 0.409259 | 39–40 |
| Numeric | old32 | 128 | 2416 | 2.390292 | 2.390444 | 2–3 |
| Numeric | continuation128 | 384 | 7240 | 2.092308 | 2.091594 | 6–8 |
| Numeric | combined 128 updates | 512 | 9656 | 2.166804 | 2.166368 | 9–10 |

## First and last complete dataset passes

| Group | First full epoch | Example-mean loss | Token-weighted loss | Last full epoch | Example-mean loss | Token-weighted loss |
|---|---:|---:|---:|---:|---:|---:|
| Code | 0 | 0.579600 | 0.522821 | 38 | 0.231072 | 0.306945 |
| Numeric | 0 | 2.479358 | 2.479699 | 8 | 2.062384 | 2.061636 |

## Exact-example paired losses

Each before/after pair below uses the same exact training example IDs, so the comparison does not shift with the sampled composition.

| Group | Comparison | IDs | Before mean | After mean | Mean per-ID delta | Token-weighted delta | Loss lower / higher / same IDs |
|---|---|---:|---:|---:|---:|---:|---:|
| Code | first → final | 13 | 0.579600 | 0.229769 | -0.349831 | -0.216709 | 13 / 0 / 0 |
| Code | old32 final → continuation final | 13 | 0.480587 | 0.229769 | -0.250817 | -0.160930 | 13 / 0 / 0 |
| Numeric | first → final | 56 | 2.479358 | 2.061970 | -0.417388 | -0.418480 | 56 / 0 / 0 |
| Numeric | old32 final → continuation final | 56 | 2.300550 | 2.061970 | -0.238580 | -0.239333 | 56 / 0 / 0 |

## Limits

These values are teacher-forced cross-entropy on the training targets. Lower loss means closer fit to those targets under teacher forcing; it does not establish free-generation performance, mathematical reasoning, or acquisition of a general method. No new evaluation outputs were read.
