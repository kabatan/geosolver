# Numeric SFT dose-control data audit

`prepare_data.py` prepared the data on CPU only. It did not run training or model evaluation. The machine-readable reproduction record is `data-audit.json`; the exact per-row shuffle is in `shuffle-map.json`.

- `train-correct.json` is byte-identical to the frozen prior `train.json` (80 rows, 10 sources × 8).
- With seed `2026092817`, `train-shuffled.json` changes only each row's `target`. All 80 rows receive another row's target from the same source; there are zero fixed points, and every source's target multiset is unchanged. IDs, order, messages, and other fields match `train-correct.json`.
- `fit-jobs.json` has 110 answer-free, greedy-seeded jobs with the exact training prompt prefix: 80 `trained_all` jobs from the original training rows and 30 `reserved_shape` jobs from variants 10–12 of each source. Seeds run from `2026092811` through `2026092920` in job order. `fit-answer-key.json` stores each provenance ID and its true numerical target separately.
- The source provenance has 120 records, 12 per source. All 12 shape signatures within each source are distinct at eight decimal places. The minimum within-source Euclidean signature separation is `0.00020103817275679586`; the maximum recorded numerical audit residual is `2.2445050829673173e-12`. Frozen source hashes and the preceding 120-point audit metadata match.
- Eight old `*jobs.json` evaluation manifests were checked, including archived diagnostics. None contains a variant 10–12 ID or exact problem prompt. This establishes absence from those model-evaluation jobs; it does not imply the researcher had never inspected the constructed provenance records.

## SHA-256

| File | SHA-256 |
| --- | --- |
| `prepare_data.py` | `404904066df4e79f4ae0a37e2a5c4ea25f4fdd0a2c5a3b8136d9482795004b5b` |
| `train-correct.json` | `778b87cfce6ea7271e971f8c727a5663468b783d21e7d21199bae7ccf46e26c9` |
| `train-shuffled.json` | `9858b82131a70352ba5a890a0681282bb6a161b16fe642afa6457e51a8d451d8` |
| `shuffle-map.json` | `7a813efd61b9e5cb4e8442def7d9e3747041e6d0de1142cbaf3250a337bb908f` |
| `fit-jobs.json` | `f9ecd36632e850b9789f2faa42d4d40ee205aba0a0690b22a171a72eff15ede1` |
| `fit-answer-key.json` | `afc613e67d443e49abd02c440c3581056ce4b5ef5debb878bfd42432449fc695` |

The old `data-provenance.json` source SHA-256 is `4a810fddbbc9fcedb49914806b2323ce5cc9974ef5e36d91350212f1090b26eb`. Full source and old-job hashes appear in `data-audit.json`.
