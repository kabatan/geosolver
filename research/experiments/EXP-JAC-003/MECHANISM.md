# EXP-JAC-003 mechanism phase

This phase is deliberately isolated from the frozen development truth and K0
outcomes.  It adds one unexported Core seam and a research-only runner; it does
not connect the candidate to the global solver, checkpoint, wire protocol,
Python DSL or plugin ABI.

## Ownership graph

1. `HarnessJac003` owns an opaque join and saved start index.
2. `CandidateJac003.compile_dependencies` sees only the typed graph and emits
   conservative residual-to-variable supports.
3. The candidate compiler makes two immutable copies: a provider projection
   (`row_supports`, `groups`, `structural_nonzeros`) and a route projection
   (`variable_count`, `residual_count`, `structural_nonzeros`, `color_count`).
4. The exact integer route decides dense versus colored without IDs, operation
   names, constants, starts, targets or outcomes.
5. Core validates and content-seals the provider, then the research runner
   passes it positionally to `_solve_local_with_provider`.  The public
   `solve_local` methods and keywords are unchanged.
6. `SafetyJac003` emits dense and candidate matrices without truth.  Only the
   separate Python assessor opens analytic truth and Gold.

The K0 compiler stops after dependency construction.  It does not construct a
coloring or route.  K1 therefore pays the complete coloring, hash, route and
provider construction cost inside each case wall.

## Failure semantics

The sealed path reserves `2*color_count + 2*active_column_count` Jacobian
callbacks plus the next trial callback before beginning an iteration.  An
invalid grouped plus/minus probe, nonfinite residual or residual-length drift
discards the entire group result and retries every affected column.  If an
independent column has no usable side, the attempt fails closed.  Deadline and
cancellation are checked before every sealed callback.

The public dense and public `jacobian_entries` paths retain their pre-refactor
behavior.  Provider types/functions remain unexported and are absent from every
wire or checkpoint object.

## Formal order

`formal_abba.py` must be the single child of the repository exclusive-run
helper with label `EXP-JAC-003-development-abba`.  It performs, in order:

1. source/input/environment verification;
2. Julia and Python mechanism tests;
3. public-surface and checkpoint replay;
4. candidate-only safety capture plus independent truth assessment;
5. exact frozen K0 replay;
6. four fresh-process K0/K1/K1/K0 segments with distinct writable depots.

It creates only a nonofficial staging directory.  After the outer audit is
complete, an independent host observer and source observer are filled from the
templates.  `finalize_abba.py` validates and hash-binds those records, then
renames the whole staging directory to the official path exactly once.
`assess_development.py` may run only after this source and runner are frozen.

No development result, including a pass, authorizes product connection.  A
pass authorizes only result-blind preregistration of generator-disjoint locked
families under the card's rules.
