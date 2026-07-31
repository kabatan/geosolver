# CANDIDATE_GUIDED_TARGET_BOUND_SUBSET_MEMBERSHIP_V1

## Disposition

`REPAIR_B SYNTHETIC_GO / AGGREGATE CENSUS READY / AUTHORITY HOLD`

Repair A's root-owned census found no powered-remainder failures.  Instead,
76/85 requests stopped at the source-equality gate and 9/85 at target
lowering.  Repair B changes the equality-selection mechanism; it does not
change a score threshold, selected-generator cap, polynomial cap, or timeout.

## Mechanism

The frozen candidate accumulated every safely lowered equality and rejected
the whole proof whenever that count exceeded 12.  Repair B separates
candidate discovery from proof selection:

1. lower mechanically safe source equalities independently;
2. order only the equality-variable component connected to
   `h = raw_target - q`;
3. try deterministic singleton, growing-prefix, and bounded-window subsets;
4. accept only an exact source-generator cofactor identity for `h` or `h^2`.

At most 12 generators participate in any proof, exactly as before.  The
larger candidate ledger is not a larger proof basis and does not weaken the
cofactor, polynomial, or wall-time gates.  It only prevents unrelated safe
equalities from consuming the entire proof budget.

Every proof binds the source SHA, the complete ordinary proposal, the AST
digest of every source constraint, the whole constraint-ledger digest,
selected ordinals and node hashes, excluded ordinals and node hashes, the
power, exact remainder, and exact cofactor statement.  Replay reconstructs
all of them from immutable source bytes.

Excluded constraints are not assumed, reduced, or used in C's identity.  A
future join must separately require R: an audited typed regular-root
certificate over the full source, all source equalities, guards, predicates,
and branches.  C alone never proves existence, guards, full-source coverage,
target-set completeness, or authority.

## Synthetic D0

CPU 14 synthetic evidence:

- direct target equality after 16 irrelevant safe equalities: repaired;
- non-radical square target equality after 16 irrelevant equalities: repaired;
- a two-generator target chain after 16 irrelevant equalities: repaired;
- all three were rejected by the frozen all-candidate gate, so the activation
  is attributable to subset selection rather than a raised proof cap;
- a source where only an omitted unsupported Distance equality determines h
  remained NOT_PROVED;
- two-target, wrong-q, and unit-ideal negatives remained NOT_PROVED;
- forged selected/excluded ledger, wrong proposal, and source mutation failed
  exact replay;
- authority and release events were zero.

No corpus source, individual source result, truth, scorer, case ID, family,
outcome, known target count, validation, or sealed data was read.

## Aggregate-only census

The root-owned runner emits only fixed failure-taxonomy counts, direct/square
power counts, typed-prejoin intersection counts, and the number of distinct
signatures.  It emits no paths, endpoints, relations, q values, raw reasons,
signature values, histograms, or individual records.  Its proposal is a
projection only; all outputs fix complete ordinary binding false,
`authority_pass=false`, `target_release=false`, and common integration HOLD.
