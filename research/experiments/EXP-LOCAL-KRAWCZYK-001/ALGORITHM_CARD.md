# Local near-root Krawczyk rescue D0

Status: `GENERATED_D0_PASS; PROPOSALS_ONLY; READY_FOR_THIN_D1_CONNECTION`.

- Entrypoint: `candidate.py:rescue`.
- Candidate SHA-256: `fe846017d75043507916c80b988ca75192997040ca9a96891ab1b0c81b47adde`.
- Runner SHA-256: `9a99b493243b4136cd7eb420188268a792684855ddcfab06246d32813d4251dd`.
- Aggregate SHA-256: `214ad5934675796ea6d2501bdf85e1a40bae540555075849d4f25df1d9b062e8`.

## Hypothesis and mechanism

A numerical baseline or reservoir sometimes reaches a small-residual point but
does not complete HP/exactification. When the already compiled source residual
DAG has a complete safe interval extension and interval Jacobian, a single
trust-region box around that point can cheaply prove the existence and
uniqueness of a regular root. The resulting enclosure midpoint remains only a
proposal to the unchanged HP/canonical source, guard, and raw-target replay.

The candidate imports `EXP-INTERVAL-001/interval_rescue.py` only after checking
SHA-256 `b2a17ddc6321c3157f89965a8c76fd18f376c8974c3d4288bf430ff70bc6e2a3`.
It directly reuses that module's typed expression nodes, outward interval
forward evaluation, interval Jacobian, and one-box Krawczyk implementation. It
does not parse source text, add operations, create a symbolic/interval backend,
or change a compiler/platform.

Eligibility is mechanical: dimension 1--2, square residual DAG, existing
validated-DAG provenance, one branch throughout the local box, strict guards
known interior throughout that box, supported arithmetic nodes only, and a
finite positive trust radius. Optional literal bounds only clip the symmetric
local box. No subdivision, bisection, root enumeration, or inferred global
domain is performed.

The first `ceil(0.75 * work)` is reserved for the numerical baseline. Each
local attempt is capped at one capability/domain interval evaluation, two
Krawczyk interval F/J evaluations, and one canonical acceptance call. Unused
side work has no proposal authority. Baseline payload and descriptor byte
strings retain their input order and representation.

## Prior failure and reopen difference

The earlier global `EXP-INTERVAL-001` route stopped after a truth-blind
development formulation audit found 0/145 applicable: 109 exceeded dimension
two, 35 lacked literal finite source bounds, one was nonsquare, and all exposed
some geometry/opaque syntax. Its predecessor also spent 24.6% more work for
only two unrelated generated gains. Reopening global subdivision, inventing
bounds, or building a broad interval geometry compiler remains prohibited.

This candidate changes the missing premise rather than retuning that route. It
does not discover a domain or search boxes. It consumes a near-root and trust
radius already produced by the numerical solver, validates exactly one local
box using the existing typed DAG, and has a fixed 25% maximum share. The box is
a local root-certificate domain, not a claim about the complete source domain.
Canonical source/guard/raw-target acceptance remains the only descriptor seam.

## D0 design and authority boundary

The generated, source-only gate contains three positive families:
well-conditioned scalar roots, coupled two-variable roots, and nearly singular
but regular two-variable roots. Negative and near-miss gates cover an exactly
singular root, strict-guard boundary, unsupported non-polynomial node, opaque
callback, and a local box far from every root. Metamorphics cover variable and
residual permutation plus residual and coordinate scaling.

The generated verifier is outside the candidate. It accepts a proposal only
when it matches an exact generated source root and the claimed point lies in
the returned enclosure. This stands in for, but does not replace, the frozen
HP/canonical replay. The candidate itself cannot insert an answer and reports
`proposal_authority=false`.

No formal corpus, scorer, historical case outcome, validation, sealed, or
holdout data was read. The CPU31-only generated run certified 30/30 positive
local boxes across all three families and produced descriptor gain/loss
`+30/-0`. False/extra descriptors, canonical rejections, baseline payload
changes, and 75/25 work-split mismatches were all zero. All five negative and
near-miss fixtures stayed baseline-only. Variable/residual permutation and
residual/coordinate scale metamorphics passed 4/4. Unit tests passed 4/4.

This is generated mechanism evidence, not real-source applicability or recall
evidence. D1 may proceed only through an existing typed-DAG object plus the
unchanged canonical callback; a source-text adapter or interval compiler is
still out of scope.
