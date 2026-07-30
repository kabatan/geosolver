# Diffusive-Gibbs portal — prospective G1 reopen

## Reopen basis

Frozen G0 (`e53660ad...`) passed `gain 10 / loss 0 / false 0`, equal productive
callbacks, 75% incumbent lanes, and `48/48` metamorphic checks.  Historical G1
was correctly stopped at `238/330` metamorphic agreement even though its raw
gain was positive.  Its fixture supplied an oracle chart and polished in raw
physical coordinates, making rotation/reflection and scaling part of the toy
runner rather than a valid portal comparison.

This prospective arm keeps the G0 kernel and noise schedule byte-identical.  A
candidate-local adapter constructs a chart only from the first original-order
full-rank anchor differences.  It fails closed to no portal proposals when the
chart is unavailable.  The first 12 of 16 incumbent lanes execute before the
portal and their complete float64 evaluation trace must be byte-identical to
control.  Portal outputs are proposals only and always return to source replay.

The portal receives exactly five opaque fields: residual, finite,
`semantics_valid`, violation, and violation vector.  It receives no family,
case identifier, truth, target, answer, prior result, oracle origin, or oracle
basis.

## Prospective G1

- 540 generated cases: multi-sheet, narrow-basin, ill-scaled, singular-hidden,
  and semantic-moat; positive, negative, and near-miss roles.
- 384 productive source callbacks per arm; no dummy padding.
- rotation, reflection, translation, variable/residual permutation, residual
  sign, coordinate scale, and equation scale.
- Gate: loss/false zero, 75% byte-identical insurance, callbacks and CPU no
  more than 1.10x, 100% metamorphic agreement, and gains in at least two
  families.

Result: `gain 52 / loss 0 / false 0`; gains in 4/5 families, including narrow
basin `+22`, ill-scaled `+15`, semantic `+8`, and multi-sheet `+7`.  The
singular family activated on 72/108 cases but tied.  Productive callback ratio
was `1.000`, AB/BA CPU ratio `0.9850`, byte-identical insurance mismatches were
zero, and metamorphic agreement was `120/120`.

Frozen kernel SHA is `e53660ad...`, portal adapter SHA is `7cb8acd0...`, runner
SHA is `8596d047...`, and the labeled kernel+adapter+runner closure SHA is
`be634474...`.

Decision: `GO_INTEGRATION_SMOKE`, not formal promotion.  The next arm must bind
the portal inside the current adaptive `run_local_arm`, charge scout calls to
the shared ledger/deadline, preserve source tags and every-fourth
counter-Cauchy lane, and use the same frozen local solver/canonical authority
for both arms.  No formal screen, validation, or sealed input was accessed.
