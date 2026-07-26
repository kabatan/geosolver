# Out-of-development 98-case audit — 2026-07-22

## Conclusion

`champion_v2_poc_preloaded` is not sufficiently general yet. Its improvement
over the historical baseline is concentrated in development, and neither
49-case out-of-development partition passes the predeclared 47/49 gate.

| partition | historical baseline | current champion | change | gate |
|---|---:|---:|---:|---:|
| development | 121/145 | 131/145 | +10 | 138/145 not met |
| validation | 37/49 | 38/49 | +1 | 47/49 not met |
| sealed | 42/49 | 44/49 | +2 | 47/49 not met |
| validation + sealed | 79/98 | 82/98 | +3 | — |
| all 243 algebraic cases | 200/243 | 213/243 | +13 | 231/243 not met |

The current rate is 90.34% on development but only 83.67% on the other 98
cases, a 6.67 percentage-point generalization gap. The baseline-to-champion
gain is 6.90 points on development and only 3.06 points on the other 98.
This is strong evidence of development-local optimization or split-dependent
coverage, even though no individual held-out failure was exposed.

## Frozen-arm validation comparison

Before opening validation, two already-frozen arms were declared:

| arm | development | validation |
|---|---:|---:|
| `champion_v2_poc_preloaded` | 131/145 | **38/49** |
| `champion_v2_poc_archive_levy_tail` | 130/145 | 37/49 |

The development ordering did not reverse. Archive Levy therefore does not
provide a more general replacement; both arms fail the validation gate by a
wide margin. Following the predeclared rule, only the current champion was
then frozen and submitted once to sealed, where it scored 44/49.

## Custody and interpretation

- validation subset SHA-256:
  `d0ed12f49397f6909dd061b7dd0e88bebc89ee95f7e8c1f7b661bcaa8ea4818d`
- sealed subset SHA-256:
  `4ab112fdead52e769af344ff17f581fa89cfea5f3ecde6ee996a56eae64ac36a`
- dataset SHA-256:
  `e587c6ea3f315f270e13cae859bba947f52e59afb651b7485061fdc49be06b8f`
- common run: seed 0, 180 s total, 146 s search, 256 starts,
  600 callbacks/start, cap 153600, jobs 7, pinned CPUs
  `1,2,3,5,6,7,9`, native thread count one.
- the solver received formulation only; truth was used after completion by
  the exact-descriptor-set scorer.
- individual case outcomes, IDs, targets, logs, and timings were not emitted
  to the repository or inspected. Only aggregate summaries were opened.
- no sealed-specific adjustment is permitted after this run.

These 98 cases are unused by the current champion but are not historically
pristine: a pre-split baseline run covered all 247 source cases, and a later
inventory recorded partition-level baseline failure counts. Therefore this is
an out-of-development generalization audit, not a claim about a never-before-
seen prospective corpus.

## Public aggregate artifacts

- `results/fresh98-validation-champion-v2-poc-aggregate-20260722-v1.json`
- `results/fresh98-validation-archive-levy-aggregate-20260722-v1.json`
- `results/fresh98-sealed-champion-v2-poc-aggregate-20260722-v1.json`

The raw case artifacts remain in the repository-external 0700 custody area.
They must not be used to tune the solver against these 98 cases.
