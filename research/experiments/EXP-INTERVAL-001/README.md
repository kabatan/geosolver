# EXP-INTERVAL-001

Disposable, truth-blind low-dimensional interval/Krawczyk rescue prototype.
It emits local-search proposals only; canonical source replay remains the sole
answer path.

Run the generated checks with the campaign Python 3.12 environment:

```bash
/home/kabatan/work/solver/.venv/bin/python -m pytest -q \
  research/experiments/EXP-INTERVAL-001/test_interval_rescue.py
/home/kabatan/work/solver/.venv/bin/python \
  research/experiments/EXP-INTERVAL-001/run_generated_s0.py
```

The second command prints the deterministic artifact stored at
`results/generated-s0.json`. No formal dataset, scorer, Gold/validation/sealed
answer data, or champion solve is opened by either command.
