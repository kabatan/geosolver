# S3 jobs=1 ABBA orchestration

`run_s3_abba.py` invokes the existing sibling `run_arm.py` sequentially on the
development partition. It uses the fixed S3 contract: jobs 1, 180/146 seconds,
256 starts, 600 callbacks per start, aggregate cap 153600, and an explicitly
selected CPU. The default seed list is 0 through 4; each seed runs control,
candidate, candidate replicate, control replicate.

Dry planning is the default:

```bash
python research/campaigns/EXP-GLOBAL-001/run_s3_abba.py \
  --control-arm /path/to/control/arm.json \
  --candidate-arm /path/to/candidate/arm.json \
  --raw-root /outside/repo/s3-abba \
  --cpu 0
```

Add `--execute` only after reviewing the dry orchestration manifest. The same
raw root may be reused to transition from dry planning to execution or resume
an interrupted execution. Existing leg output is accepted only when its
`CAMPAIGN_PLAN.json` and `RESULT.json` match the frozen arm, entrypoint hash,
seed, CPU, dataset hash, and all fixed budgets. Partial, changed, or mismatched
output stops the campaign. Validation, sealed, and holdout names are rejected;
the orchestrator never reads an offline score or passes truth to a worker.
