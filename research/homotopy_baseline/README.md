# Homotopy continuation baseline

This directory is deliberately outside `src/geotarget`.  It is an experiment
arm, not a product engine.  The Python side accepts the V15 JSON contract,
lowers an admitted algebraic formulation to a square polynomial system, and
the Julia side performs polyhedral homotopy continuation.  Exact target
descriptors are accepted only after root certification and exact elimination.

The two translator modes are:

* `core`: rational/algebraic straight-line geometry; no dynamic trigonometry;
* `extended`: `core` plus constant rational-`pi` trigonometry and guarded,
  phase-only unit-circle lowering.

Unsupported inputs are reported with stable reason codes.  A numerical result
without a certificate is never presented as an exact answer.

## Commands

```bash
PYTHONPATH=src:. /home/kabatan/work/solver/.venv/bin/python \
  -m research.homotopy_baseline analyze examples/problem.json
PYTHONPATH=src:. /home/kabatan/work/solver/.venv/bin/python \
  -m research.homotopy_baseline solve examples/problem.json \
  --mode core --completeness complete --seconds 180 --seed 0 \
  --output /tmp/geotarget-hc-result.json
PYTHONPATH=src:. /home/kabatan/work/solver/.venv/bin/python \
  -m research.homotopy_baseline compare \
  /home/kabatan/work/solver-artifacts/experiment-freeze-20260727/product-145-20260727-v4/development145.jsonl \
  --mode core --completeness target --seconds 180 --seed 0 \
  --output /tmp/geotarget-hc-compare.json
```

The Julia environment is materialized from the adjacent `julia/Project.toml`
and its checked-in `Manifest.toml` (Julia 1.12.6, HomotopyContinuation 2.22.2,
Nemo, and Singular).  The worker fixes Julia and BLAS/OpenMP thread counts to
one.  A solve is explicitly a hybrid **HC + Krawczyk certification + exact
Groebner elimination** baseline; a numerical path or a rounded decimal is
never promoted to an exact answer.

The `--completeness complete` policy performs the additional exact ideal-degree
check and may claim `exact_complete`. The paired `--completeness target` policy
keeps the same certified/exact target authority but deliberately reports
`answers_found_completeness_unknown`, making a target-oriented comparison with
the current solver possible without conflating it with an all-roots proof.

`core` rejects trigonometric/periodic DSL constructs.  `extended` additionally
handles constant rational-π angle expressions and phase-only
`PointOnCircle` parameters by replacing each phase with a unit-circle pair;
mixed phase use and uncertified arc bounds fail closed.  The admission report
records these reasons independently of problem IDs or known answers.

Comparison artifacts belong outside Git.  The `compare` command alternates
current-first and homotopy-first order by case, keeps truth out of workers,
and records raw arm results for an offline scorer to consume.
