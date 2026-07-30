# Small exact-polynomial coefficient monodromy D0

Status: `GENERATED_D0_PASS; THIN_REAL_CONNECTION_PASS; PROPOSALS_ONLY`.

- Candidate SHA-256: `60e1019ed384744fc8209169066b327d742ab84e5293c2de0729c03c7131631d`.
- Runner SHA-256: `1242b8d7024644179ad36e7f61c11fe3dcdc943076a91ede3e7d697a63429ee0`.
- Aggregate SHA-256: `71fd71311c37a7b2d38b82eafaafb1d1621ee06a880798fd310aea520cc31cb0`.

## Mechanism

The candidate admits only an exact-rational, square-free, univariate source
block of degree 2 through 8 with bounded coefficient size. Given one
source-replayed root, it embeds the source as `P(x)-p=0`. Roots of `P'` provide
coefficient-space discriminant values. Fixed lollipop loops around those
values are tracked by complex predictor/Newton correction and may return on a
different sheet at `p=0`.

Every return point is a proposal only. The generated assessor independently
factors the untouched exact source polynomial, reapplies strict source bounds,
and emits a rational descriptor only after exact Horner replay. Complex,
out-of-bound, repeated-root, malformed, nonfinite, and budget-exhausted paths
fail closed. Numerical monodromy never claims root or target completeness.

The first 75% of charged work is an identical baseline. Candidate and control
both spend the remaining 25%; unused tracker budget becomes evaluation filler
with no proposal authority. Candidate output is a union with the retained
baseline descriptor.

## Generated D0

The panel has 160 cases: separated, affine-scaled, and close rational roots;
strict-bound, repeated-root, and real-plus-complex-sheet counters; degrees
2/4/6 and ten replicates.

- Complete sets: `50 -> 130`.
- Descriptor gain/loss: `+220/-0`; strict gains in 80 cases and all 3 positive
  families.
- False/extra and charged-work mismatch: 0.
- Canonical replay rejected 110 complex or strict-bound proposals.
- Repeated-root applicability: `0/30`, as required.
- Nonzero rational equation-scale metamorphics: `90/90`.

No formal truth, scorer, case outcome, development score, validation, sealed,
or holdout input was read. The generated exact factorer is verifier-only and
is not imported by the candidate.

## Next gate

Before any real screen, perform a source-only capability census for an
already-existing exact polynomial projection. Do not build a compiler. A thin
adapter may proceed only when it can provide exact rational coefficients, a
square-free certificate, source bounds, and an already canonical-replayed
start root, while retaining at least 75% common-control work. Every proposal
must return through the existing canonical source replay. Stop if fewer than
three anonymous source structures qualify, if compilation/path overhead
exceeds the 25% route budget, or if any control descriptor is lost.

## Thin real-source connection

Decision: `GO_SOURCE_ONLY_D1_ELIGIBLE`.

Entrypoint: `thin_real_connection.py:connect`.

- Mechanism manifest SHA-256: `495d8586847bfb7ce3e501075007fabf73a5f79119962357280e407f85852cb4`.
- Thin adapter SHA-256: `7717d71071e9d600a1ec2a1bad3fccd5d20f4b264d5bc7af4efa7cbfc8e7241f`.
- Source-only runner SHA-256: `24f4ffc918afc2f1f8c6d46a7d61c6f4d12ae8748bc79207f0458f292c0862a4`.
- Source-only aggregate SHA-256: `19e638669ae23e43365b8909ec774e2e50faaa5c9b9100b5abb2efb814c8d436`.

The adapter imports the existing source-only semantic polynomial compiler,
bounded linear auxiliary reducer, and source-coordinate reconstruction only
after checking their frozen SHA-256 values. It admits exactly one raw variable
which remains the same sole reduced variable, one QQ polynomial equation of
degree 2--8, an exact square-free gcd certificate, and no periodic source
reconstruction or selector replay obligation. It does not add a symbolic
backend, eliminator, geometry compiler, or output authority.

The common numerical baseline keeps `ceil(0.75 * total_work)` and its opaque
payload/descriptor bytes are returned unchanged and in their original order.
The monodromy side is additive. Every real reconstructed proposal is passed to
the caller's existing canonical exact/source replay; only the descriptor
returned by that authority can be appended. Compiler mismatch, ineligibility,
bad start replay, complex proposal, reconstruction failure, or replay failure
is fail-closed.

The source-only generated smoke read no corpus truth, scorer, historical
outcome, validation, or sealed data. Across 30 cases in three rational
polynomial families it activated 30/30, added 60 descriptors, and had zero
baseline losses, false/extra descriptors, replay rejections, payload rewrites,
or 75% floor mismatches. Multivariate, repeated-root, and unsupported inputs
were rejected. This is mechanism/connection evidence only; it does not claim
real-corpus recall or completeness.

Formal D1 must supply the already frozen canonical replay callback and the
common baseline result. It may route only with the structural checks above and
must retain the same dependency hashes and baseline floor.

## Runner-compatible full-worker binding

Status: `SOURCE_ONLY_FULL_BINDING_PASS; READY_FOR_FORMAL_OWNER_D1`.

- Entrypoint: `full_worker.py`.
- Worker SHA-256: `1bbb1dc6cfd9e8d86c77ad04ac0e40eebe15e5214d0b0af694ce29be3f1bfa71`.
- Smoke runner SHA-256: `188b2683614968ec8f30c05b36e1c33e893f646157f12a28042d11e43646f6c7`.
- Smoke aggregate SHA-256: `8e93bad65222d0d87af34ab1c5d5910b10d1462b33c9337a6c98a6af376e053e`.
- Current adaptive entrypoint SHA-256: `7d6f168d8679732c672842e6b7a44573d190449ad0fbe4cc09a7b9112ddc9500`.
- Current adaptive wrapper SHA-256: `4c4640a3bce5719d66f577c0093eabe93916476e319b8a595003a16f73dfb9b4`.

The full worker imports the existing progressive-adaptive full wrapper after
checking both current hashes. Search, endpoint replay, HP/restoration,
descriptor key, PointOnCircle, zero-dimensional, precision preload, CLI, dry
plan, execute handshake, and final result schema remain that worker's objects.
Only `BASE._service_candidates` is decorated.

The decorator passes 75% of the available post-search service wall to the
unchanged adaptive HP/canonical service. Its descriptor mapping is frozen in
insertion order and serialized to an opaque baseline payload. If that baseline
contains an authority-approved endpoint, coefficient monodromy may use the
remaining wall. Every new point is converted only by the existing
`_fresh_replay_candidates` and then serviced by the captured unchanged
HP/canonical function. Only the descriptor key returned by that path is
appendable. Timeout, compiler ineligibility, callback failure, or any custody
exception returns the baseline mapping unchanged.

Three source-only smokes passed without truth, scorer, case outcome, or
holdout access. The execute fixture retained `R:+2` first and added canonical
`R:-2`; the expired-deadline fixture retained only `R:+2`; and an opaque
`sin(x)` source failed closed with only `R:+2`. All three kept the full plan
binding and canonical-authority identity. These are connection smokes, not
real-corpus recall or timing evidence.
