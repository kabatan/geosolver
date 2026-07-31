# RR07_POST_ENDPOINT_EXACT_REOPEN

- Reopen: RR-07 existed only as a reverse-macro planning rule in
  `EXP-GEOSPEC-001/reports/reverse_macro_rules.md`; no executable post-HP
  authority connector was found.
- Mechanism: consume exact post-HP side/tangent invariants, check
  `a=b+c-2t`, apply exact SSS/Heron inverse, enumerate both reflections, and
  hand each branch to an existing untouched replay callback.
- Scope: rational exact invariant subset only.  No DSL parser/compiler change,
  inferred bounds, source mutation, or case/family/truth routing.
- Gate: first require the complete typed source pattern (incircle contact plus
  an independent positive tangent length) in >=4 sources and >=2 typed
  contact actions.  Do not spend endpoint/exact-worker budget when prevalence
  is lower.  Only after that gate, require real replay in >=3 sources and >=2
  actions, including >=1 old no-bounded-relation source.  Generated analogues
  are D0 only and cannot satisfy either real gate.
- Authority: every public terminal remains proposal/prejoin-only with
  `authority_pass=false`, `target_release=false`, and no completeness claim.

## Disposition

- Generated D0: PASS, 5 positive sources / 3 actions, 10 exact reflection
  checks, 4/4 near-miss rejections.  Artifact SHA-256
  `fd20ffbcb0f3c004895ddb2caaa46984904aa894aafe695e8772b1b828156a08`.
- Anonymous real static gate: STOP, only 1 strict typed source / 1 typed
  action; one further contact source lacked an independent positive tangent
  constraint.  Endpoint and exact worker were deliberately not consumed.
  Aggregate SHA-256
  `e6c353962945e4dbe852e0e7fd277a7ad2d65463971e2ed2733a2edf4fc82c70`.
- Reopen gate: a new truth-blind corpus must contain at least 4 strict typed
  sources and 2 contact actions.  Merely finding more `Incircle`, `Incenter`,
  or contact operators without the independent tangent invariant does not
  reopen RR-07.
- Mechanism SHA-256: `candidate.py`
  `ad657621b9253e06b0e7f02d92e0a9fecaf555feef015ed0636fc38ff892d952`;
  real gate
  `3fbcf5167c85a5ea36c1211a3ad4ff7c6e86493871d44c3ebbee0b14ba426adf`.
