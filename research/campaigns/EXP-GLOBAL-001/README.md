# EXP-GLOBAL-001 — general solver improvement campaign

This directory contains only the small common harness and compact experiment
records.  The restored solver, datasets, workers, and raw run artifacts stay
outside Git.

## Isolation contract

- Integration branch: `experiment@9b939486` in its own worktree.
- Product source reference: `0967ff1c`; no merge or rebase from `main`.
- Frozen runtime default: `/home/kabatan/work/solver-experiment-runtime/solver`.
- Development dataset default:
  `/home/kabatan/work/solver-artifacts/experiment-freeze-20260727/product-145-20260727-v4/development145.jsonl`.
- Validation and sealed partitions are intentionally unsupported by this
  harness.  The existing confidential custodian wrapper remains the only final
  gate.
- Every formulation is checked against the archived 145-case
  `INPUT_MANIFEST.json` before a worker is launched.  Truth stays in the outer
  scorer process and is never materialized into a worker input.

## Arm contract

Each disposable arm supplies `arm.json` with `id`, `base_commit`, `entrypoint`,
and `mechanism_hash`.  `entrypoint` may be relative to the manifest, absolute,
or use `frozen://`.  `mechanism_hash` is the SHA-256 of the entrypoint bytes;
an experiment card may additionally record a transitive closure hash.

Dry-plan the frozen control:

```bash
/home/kabatan/work/solver/.venv/bin/python \
  research/campaigns/EXP-GLOBAL-001/run_arm.py \
  --arm research/campaigns/EXP-GLOBAL-001/arms/frozen-champion/arm.json \
  --partition screen24 \
  --output /home/kabatan/work/solver-experiment-results/control-screen24
```

Add `--execute` to run.  S1 uses `--jobs 1 --cpus 0 --total-seconds 30
--search-seconds 20 --seed 0`; S3 uses 180/146 seconds, 256 starts, 600
callbacks, seeds 0–4, first with jobs=1 ABBA and then jobs=7 throughput.

`TELEMETRY.json` is truth-free and can be given to candidate authors.
`OFFLINE_SCORE.json` is assessor-only development evidence.  Raw result roots
must remain outside the repository.

Paired runs are compared with `compare_runs.py`.  Repeat `--control` and
`--candidate` once per seed.  The report includes exact McNemar/binomial
probabilities, 10,000-resample family-clustered recall intervals, and paired
all-case wall-time ratios; deadline-censored cases are never removed.
