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
/home/kabatan/work/solver/.venv/bin/python \
  research/experiments/EXP-INTERVAL-001/run_interval_metamorphic_s0.py
/home/kabatan/work/solver/.venv/bin/python \
  research/experiments/EXP-INTERVAL-001/formulation_audit.py
```

The commands print deterministic aggregate artifacts stored in `results/`.
The formulation audit reads only the already-isolated development formulation
bytes, emits no case rows, and skips identity/answer-like values without JSON
deserialization. No scorer, Gold/validation/sealed answer data, or formal solver
execution is opened by these commands.
