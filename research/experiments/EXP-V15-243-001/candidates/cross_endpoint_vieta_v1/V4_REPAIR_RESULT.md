# V4 repair checkpoint

## Outcome

`UNIT GO / REAL CUSTODY DRY VALIDATION HOLD / HEAVY REPLAY HOLD`

- The mathematical Vieta core is unchanged.
- Raw id-bearing source SHA and canonical id-stripped projection SHA are now
  independently authenticated and cross-bound.
- RESULT/PLAN/lane and HP provenance use the raw SHA; candidate inputs,
  ranking, subset hashes, and sidecar use only the projection SHA.
- A worker requires inherited coordinator capability and official-lock FDs and
  is confined to its coordinator mode-0700 temp root.
- Canonical factor replay returns a concrete descriptor plus proof record.
  The same fallback object is directly unioned with concrete records, which
  are deduplicated before emitted/unobserved/fallback counters are derived.
- CPU14 unit after adding the disposable root-only manifest builder: 26 passed
  in 0.29 seconds. Dual-SHA/id mutation, crossed HP
  binding, duplicate JSON key, proof mutation, partial sibling retention,
  concrete dedup, and direct worker without inherited FDs are covered.

`build_v4_manifest.py` discovers only ordinary HP trees through their PLAN
schema, authenticates adjacent RESULT/PLAN/authority triples and 768/1024
numeric parity, ranks projection-source groups and degree-2..6 subsets by the
frozen SHA rules/caps, writes the private v2 panel with mode 0600, and calls
`connector.validate_private_subset` on every row before publication. Its
public aggregate contains counts and hashes only. Generated tests confirm that
unrelated scorer/outcome-shaped trees are skipped and guard/source-binding or
output-root mutations fail closed.

No real artifact, scorer, Julia process, or heavy/global-lock gate was run by
the candidate agent. The next mandatory step is a benchmark-owner-only v4
manifest build followed by `custody-dry-validate` under CPU14 and the official
global lock. Heavy QQBar replay remains blocked until that aggregate reports
at least one authenticated subset and receives an independent containment
re-audit.
