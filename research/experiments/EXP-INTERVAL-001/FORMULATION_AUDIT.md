# EXP-INTERVAL-001 development145 formulation-only audit

## Scope and non-leak boundary

This is a static application of the frozen interval gate to the 145
already-materialized worker inputs from the current development run. Those
inputs contain canonical formulation bytes only. The audit did not open the
outer JSONL dataset, split manifest, scorer, run result, offline score, search
artifact, Gold/truth store, validation partition, or sealed partition. It did
not execute the solver or evaluate a residual.

The byte reader does not call `json.loads` on a formulation document. It
lexically scans the root and decodes only these projections:

- `task`;
- `variables.names`;
- numeric `bounds`;
- `construction.{name,expr}`;
- `constraints.{def,value}` or a constraint expression string;
- guard expression strings.

The values of `id`, `answer`, `truth`, `gold`, `scorer`, and every unknown key
are skipped as raw JSON tokens. File basenames are used only by the operating
system to open a file; they are not parsed, copied, hashed individually, or
written to output. The result has no case rows, identifiers, per-case hashes,
or per-case decisions. Corpus binding is an order- and filename-independent
commutative closure digest.

## Aggregate result

- formulation closure: 145 files, 116,288 bytes;
- closure SHA-256: `f49a986c3f5993c29241d558be579b19ea1873e7fbc6314601abb2dbded7b1b9`;
- applicable: **0/145**;
- rejected by first fail-closed gate:
  - dimension outside 1--2: 109;
  - explicit finite bounds unavailable: 35;
  - nonsquare system: 1.

All 145 formulations lack explicit source bounds. Because solver policy forbids
inventing bounds, even the low-dimensional square subset cannot safely enter
interval subdivision. In addition, all 145 formulations expose at least one
geometry or opaque call in construction/constraint/guard syntax. Thus merely
relaxing the bounds gate would still not provide a complete smooth interval
extension.

Dimension distribution is 0:1, 1:6, 2:30, 3--4:84, and 5--8:24. Residual
dimension distribution is 0:1, 1:5, 2:31, 3--4:83, and 5--8:25.

Aggregate expression exposure counts are:

| Category | Cases exposed | Occurrences |
|---|---:|---:|
| geometry or opaque call | 145 | 3,042 |
| transcendental call | 37 | 117 |
| nonsmooth call | 9 | 27 |
| branch/comparison | 3 | 21 |
| opaque attribute/subscript syntax | 24 | 250 |
| arithmetic add | 40 | 133 |
| arithmetic subtract | 28 | 123 |
| arithmetic multiply | 69 | 370 |
| arithmetic divide | 58 | 215 |
| arithmetic integer power | 11 | 13 |

## Cost conclusion

Observed activation is zero, so estimated interval boxes, dual-DAG evaluations,
proposals, expression-node visits, and route wall time are all zero. If a future
formulation passes, the frozen per-case limits remain 32 boxes, at most 96
dual-DAG evaluations, four proposals, and 50 ms, with at least 25% baseline
launch quota.

This is a negative applicability result, not a recall result. No S1/S2 solver
run is justified for the current route. Reopen only when an unchanged-source
compiler can expose both literal finite boxes and a complete validated interval
extension for every residual dependency. Inferred search boxes or partial
geometry mirrors do not satisfy that gate.

The reproducible aggregate is
`results/development145-formulation-aggregate.json`; the scanner is
`formulation_audit.py`.
