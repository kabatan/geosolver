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

The aggregate output path is mandatory, absolute, and outside this candidate
directory.  Raw worker rows exist only in a temporary directory.
