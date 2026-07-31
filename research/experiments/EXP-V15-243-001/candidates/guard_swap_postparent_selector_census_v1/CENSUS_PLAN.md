# GUARD_SWAP_POSTPARENT_SELECTOR_CENSUS_V1

## Hypothesis

The stopped guard/equation-swap integration selected only fixed lanes 7, 15,
and 23.  Zero activation therefore did not establish that its completed
24-lane parent streams lacked usable finite source-invalid near-roots.  Before
building a selector, this census tests the necessary prevalence claim on the
already frozen observations.

This is a source-only census, not a proposal generator.  It does not rerun an
optimizer or continuation, select a postlude, evaluate a target, inspect
truth, or change a source.  Each of the 18 physical sources is handled in a
fresh process.  Completed parent streams from both arms are hash-validated and
deduplicated; incomplete streams contribute no invented observations.

The coordinator requires exactly jobs 0--35, exactly the two frozen arms for
each source, 18 distinct source hashes, and trial-declared job/source/arm
parity.  A completed stream is included only when its full 24 parent records,
parent-before-postlude flags, ordered stream digest, and combined-stream parent
origins agree.

## Frozen eligibility

An archived endpoint counts only when all of the following hold under a fresh
call to the frozen typed source adapter:

1. it is finite, inside literal source bounds, source-invalid, and has
   residual infinity norm at most the old `1e-9` entry tolerance;
2. the complete old analytic residual Jacobian and a provenance-approved
   violated smooth strict-guard row exist; and
3. the exact old `_select_pair` routine returns a `PairCertificate`, using the
   endpoint's original lane start for the frozen coordinate metric.

Guard signatures contain only typed structural fields (`source_kind`, guard
kind/operator, side) and are SHA-256 hashed.  Source identifiers, endpoint
coordinates, target/truth fields, per-source hashes, and per-source labels are
not persisted.  The aggregate records sorted multiplicities only.

## Fixed gate and consequence

The selector lineage may proceed only if there are eligible endpoints in at
least four independent physical sources and at least two distinct typed guard
signatures, with all 18 fresh workers successful.  Passing yields only
`GO_SELECTOR_PROTOTYPE_HOLD`; it is not authority or release.

Failure yields `STOP_SELECTOR_CENSUS`.  It may not be repaired by choosing
different observed lanes, loosening residual/rank/slope tolerances, or using
case/family/target/outcome fields.  A future reopen requires new anonymous
parent observations or a separately generated and reviewed expansion of the
source-DAG derivative coverage.

## Bindings

- frozen run manifest:
  `ab7c9a73fb75d0302cbc79330939f62ac20944b73622df8a35ea41cb6a327ac1`
- frozen search plan:
  `654b213ca116badca3a303a3feebb0cfa7dbc4de3a38f823afac1bd0bf0a0088`
- old continuation kernel:
  `aee0886c6a3e37ea1069128de9523a0b5647e15eba8e8622b7fa0865dc6f07ef`
- old typed adapter:
  `b9dabe71cb863a4bed906201de0833b2d97230d7a430118c95a2d61f01cedd3e`

The aggregate output path is mandatory, absolute, one-shot, and outside this
candidate directory.  Raw worker rows and process statuses exist only in a
temporary directory.  Every worker uses the pinned Python 3.12.11 interpreter
under the hash-pinned process-group guard and `_limit_exec`, with a 30-second
wall limit, 256 MiB root RSS, 512 MiB group RSS, 2 GiB address space, 1.5 GiB
data, and 16 KiB combined stdout/stderr.  Timeout, RSS/monitor/output breach,
limit setup failure, nonzero exit, or descendant leak is a census failure.

Additional execution bindings:

- serialized plan artifact:
  `e4aa6596773b82d21d9144c78eadb83d87e11e3db21ef6c305b1597d734d1380`
- root-scoped process guard:
  `e7d5bb89ae2a296c6c7f5f43d532a9cc384f092504008d052f733060e9510901`
- `safe_subprocess.py`:
  `76aa547f235bd0ae11c8b567461384b22537a9b98c990db2ed126db0a19b55c5`
- `_limit_exec.py`:
  `2173e83e6bcdc96bff5de5957f96b85a1281f7070e9e21deea047f81a16af8fb`
- pinned Python:
  `ccc93c55c24bb92866cc2f9eff61b124abf5d1ee6c8da0ef9b5eed4d78a21f07`
