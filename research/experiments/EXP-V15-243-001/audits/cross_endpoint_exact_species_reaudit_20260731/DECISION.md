# Cross-endpoint exact-species racing re-audit

## Verdict

`PRE_CODE_STOP_DUPLICATE_SCHEDULER_COMPOSITION`

No candidate worker or generated runner was added.  No formal CPU, real case,
scorer, truth, validation, sealed input, or individual case result was read or
executed.

The requested policy would keep a partial record per source-valid endpoint,
give each endpoint a cheap exactification rung, and allocate at most 25% of
work according to proof progress, cost, and descriptor-species breadth while
preserving at least 75% ordinary exact HP.  That is a direct composition of
already implemented mechanisms; it does not introduce a new proof operation,
a reusable proof fragment, or a new authority theorem.

## Binding overlap

| Requested component | Existing implementation/evidence | Consequence |
|---|---|---|
| Cross-endpoint rung interleaving, immutable endpoints, no permanent discard | `cross_endpoint_hp_rungs`; `wave17_cross_endpoint_hp_rung_racing_g0/g1` | Endpoint age/restart state and FIFO insurance already exist. |
| Progress/cost ranking across endpoints with 75% insurance and censor retention | commit `b75145de`, `cross_endpoint_hp_voi_racing_d0` | Replacing residual/stability/hint progress with exactification progress is an observation-field substitution, not a new scheduler. |
| Precision/degree/height ladders and coordinate-first versus source-link routes | `adaptive_exact_coordinate_first_wave2` | The proposed exactification rungs and certificate families already exist per endpoint. |
| Precision proof-lane fragments, reject-first ordering, and source-bound warm state | `wave12_hp_precision_scheduler` | Partial mandatory-lane state and cost-aware proof-tail scheduling already exist. |
| Cost-aware descriptor-species racing with 75% ordinary and 25% side | commit `022763fd`, `EXP-MULTITARGET-001/species_racing.py` | Good--Turing/Chao2 species allocation is already implemented and generated-tested. |
| Dominance-safe same-work handoff preserving the control union | commit `689330f8`, `species_racing_repair_a.py` | The proposed quota/union safety repair is already implemented with generated loss zero. |
| Skip repeated confirmations only after exact identity is proved | commits `2d9e7cf0`, `9492c1fc`, `exact_authority_cache_v1` | Cache activation increased HP attempts but produced no recall gain; saved work alone is not a reopen signal. |
| Final source/guard/branch/raw-target replay | `exact_outer_decorator` and current `archive_progressive_hybrid_exact_outer_v1` | The authority boundary is already conjunctive and must remain downstream of any scheduler. |

The strongest direct duplicate is not merely generic portfolio prior art.
`022763fd` already fixes a 75% ordinary prefix, races the remaining 25% among
proposal routes using exact descriptor species and measured cost, retains all
same-target observations until canonical authority, and never claims
completeness.  `689330f8` then makes the handoff dominance-safe by retaining
the complete control union.  `b75145de` supplies the missing endpoint-local
progress/censor state.  Combining these policies with the existing adaptive
exactification ladder changes only which existing score fields feed an
existing allocator.

## Current exact-outer gap is not a reopen mechanism

The current exact outer launches one frozen degree-eight exact child for each
ordinary HP attempt and retains no cross-endpoint partial-proof object.  That
absence does not itself establish novelty.  The requested design records
telemetry such as precision, degree, height, coordinate/source-link route, and
certificate progress, then restarts or advances an existing rung.  It does not
define a proof fragment that can be soundly resumed or shared without
replaying the existing child.  Its state is therefore scheduling state already
covered by the mechanisms above, not new mathematical state.

The live exact-coordinate breadth lineage is also held because the child lacks
original-AST definedness markers and a complete branch/definedness inventory.
A scheduler cannot synthesize those obligations.  The aggregate
`NO_TARGET_AUTHORITY` signal and the cache's increased HP-attempt throughput do
not repair that authority gap.

## Reopen gate

Reopen only for a materially different artifact, for example a source-bound,
hash-bound, resumable exact proof fragment that:

1. carries completed original-AST definedness, equation, guard, and branch
   obligations rather than progress telemetry;
2. is continued by a later precision/degree/height rung without recomputing
   the charged prefix;
3. cannot cross endpoints or sources without failing closed;
4. still ends in canonical source/guard/branch/raw-target and descriptor replay;
5. shows equal-work strict gain in at least two unrelated certificate families
   over both the existing species racer and HP-VOI/rung controls.

Changing quotas, thresholds, route order, progress weights, degree/height
caps, or the 75/25 split is not a reopen condition.
