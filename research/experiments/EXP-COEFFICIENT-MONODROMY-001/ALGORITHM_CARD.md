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

## Runner-compatible full-worker binding and Repair A

Status: `D1_75_25_STOP_NONPROMOTE; REPAIR_A_CORE15_PASS; FORMAL_RERUN_REQUIRED`.

- Entrypoint: `full_worker.py`.
- Repair-A worker SHA-256: `727e4e2ec867fb040bc7b59568a676df061dc83a59a46d32a70fb9e2fbb4d4eb`.
- Core-15 runner SHA-256: `becc86f25a9f2e1320f42dd4d8952e304eb00fe86e425470042493dd80af8b37`.
- Core-15 aggregate SHA-256: `8863ae045b1211c1a6be1137eae01a22d755f2df0290a703c3ba805bf65e3953`.
- Current adaptive entrypoint SHA-256: `7d6f168d8679732c672842e6b7a44573d190449ad0fbe4cc09a7b9112ddc9500`.
- Current adaptive wrapper SHA-256: `4c4640a3bce5719d66f577c0093eabe93916476e319b8a595003a16f73dfb9b4`.

The first formal-owner D1 aggregate for the 75/25 service-wall version was
control `15/24`, candidate `13/24`, paired wins/losses `1/3`, with zero
false/extra/crash. It is non-promotable. No individual case, truth, scorer, or
outcome data was disclosed to this lane. The mechanism-level diagnosis is that
the wrapper shortened the already adaptive baseline HP/canonical service to
75% before attempting the additive route; that changed and sometimes starved
the baseline authority path.

Repair A removes that split. The captured adaptive service executes first with
the original hard deadline and produces the complete baseline attempt list,
descriptor insertion order, opaque payload, and statistics object. Search
results are neither unioned nor reclustered. Only wall time genuinely left
after that call is available to a separate coefficient-monodromy tail. Every
tail point still goes through the captured fresh source replay and the same
captured HP/canonical authority. The baseline prefix is checked again before
an accepted descriptor is appended.

If there is no authority-backed baseline start, no remaining wall, no new
canonical descriptor, or any side exception, the exact baseline return object
and all three contained objects are returned by identity. Side telemetry is
added only when a genuinely new canonical descriptor is appended; it cannot
rewrite the baseline result on a zero-gain path.

The source-only core-15 smoke passed 15/15 without truth, scorer, corpus
outcome, or holdout access: five eligible generated executions appended a
canonical side descriptor, five zero-tail executions returned the baseline by
identity, and five opaque inputs did the same. All 15 baseline calls received
100% of the original hard deadline. A separate injected post-replay side
exception also returned the exact baseline object. This is connection and
custody evidence only; a benchmark-owner formal rerun is still required.

## Benchmark-owner Repair A disposition

Status: `HOLD_ZERO_REAL_ACTIVATION`.

On the frozen screen24 at 30/20 seconds and seed 0, Repair A scored `16/24`
against the separately measured adaptive control's `15/24`, with zero
false/extra/crash.  This apparent gain is not attributed to monodromy: all 24
search artifacts had zero coefficient-monodromy counters, no canonical replay
directory was created, and no side descriptor was appended.  The sole paired
gain is therefore baseline wall-clock jitter, not a mechanism signal.  Further
seeds are not spent on this unchanged route.

Reopen only when a source-only audit demonstrates that the exact univariate
polynomial projection and reconstruction contract actually qualifies on real
solver inputs and reaches canonical replay before the deadline.  A sound
operator-level algebraic lowering is a possible distinct reopen mechanism;
loosening polynomial soundness, spending baseline time, or retuning the path
tracker is not.
