# Fresh4 stage-localization result (2026-09-25)

## Question and scope

Where does Qwen3.5-9B get stuck when solving H03, H04, and H14? This is a
diagnostic of the current external-teacher positive control. It does not test
whether the model independently discovers a reusable geometric relation from
its own verified work, and cue-assisted answers do not count as unhinted
transfer.

The frozen [plan](WHY_FAILURE_DIAGNOSTIC_PLAN.md),
[rubric](STAGE_LOCALIZATION_GRADING.md), and
[prompt/protocol audit](heldout-near-transfer/proof-gap-diagnostic-fresh4/PROTOCOL.md)
preceded the fresh4 answers. All tasks were in English. The original base and
previously trained all-37 low-dose adapter each answered two fresh numeric
instances per source ID without hints. The untouched base then answered the
same six instances with a generic projection lemma (B). For the first numeric
instance of each ID it answered with an unproved target claim (C), then with
a supplied construction proof (D). C and D are different prompt branches,
not cumulative steps. All 24 generations ended naturally (`stop`), with
cap 32768, context 45056, temperature 1, top-p 0.95, top-k 20, and presence
penalty 1.5. The longest completion was 12,465 tokens, so truncation does not
explain these failures.

The 12 unhinted A/E answers were [blind graded and frozen before the
condition mapping was opened](../../../qwen/.runtime/qwen35_external_teacher_20260925/blind-why-fail-fresh4-ae/AE_BLIND_GRADE_FREEZE.json);
the [joined scores](../../../qwen/.runtime/qwen35_external_teacher_20260925/scored-why-fail-fresh4-ae/RESULTS.md)
preserve each job. The packet and all score-bearing grade hashes still match
the pre-unblinding [validation record](../../../qwen/.runtime/qwen35_external_teacher_20260925/blind-why-fail-fresh4-ae/AE_BLIND_GRADE_FREEZE_VALIDATION.json);
the ancillary second-review note was finished after that freeze. The proof rubric requires a valid construction argument,
branch, exact application, and no unresolved false claims. A correct value
or a useful final subderivation is recorded separately from a complete proof.

## Scores and stage diagnosis

| Condition | H03 | H04 | H14 |
|---|---|---|---|
| A: unhinted base, 2 per ID | Complete proof 0/2; exact 0/2 | Complete proof 1/2; exact 2/2 | Complete proof 0/2; exact 0/2 |
| E: all-37 low-dose SFT, 2 per ID | Complete proof 0/2; exact 0/2 | Complete proof 1/2; exact 1/2 | Complete proof 0/2; exact 1/2 |
| B: generic projection lemma, 2 per ID | Correct foot claim 1/2, foot proof 0/2; exact 0/2 | Valid final downstream derivation 2/2 and exact 2/2; strict whole-answer proof 0/2 because contradictory preliminary claims remain | Correct foot mapping/proof 0/2; exact 0/2 |
| C: unproved target claim, 1 per ID | Supplied foot claim not proved; downstream wrong; exact 0/1 | Assumes supplied identity rather than proving it; exterior branch and exact value 1/1 conditional on that identity | Supplied foot claim not proved; right-triangle calculation and exact area 1/1 conditional on it |
| D: construction proof supplied, 1 per ID | Foot/selected-root proof supplied; downstream circle-center argument wrong; exact 0/1 | Final conditional derivation and exact 1/1; strict whole-answer proof 0/1 because a false preliminary relation remains | Final conditional right-angle/area calculation and exact 1/1; strict whole-answer proof 0/1 because a false auxiliary dot product remains |

**H03 has two observed bottlenecks.** Without the target proof, the model does
not derive the second circle-median intersection as the foot from H to the
median. B produces the correct foot *claim* once, but no proof, selected root,
or correct answer. C supplies that claim and still obtains an invalid
refutation/acceptance and wrong center. Even D, which supplies the complete
foot proof, answers `OZ=13/2` for `OH=13`. The missing downstream step is that
each median contains G and each foot P_i satisfies `HP_i ⟂ GP_i`; hence the
P_i circle has diameter HG and center at the midpoint of HG. The Euler-line
identity then gives `OZ=(2/3)OH=26/3`. The model instead repeatedly substitutes
the nine-point center or midpoint of OH. See the [B grade](../../../qwen/.runtime/qwen35_external_teacher_20260925/blind-why-fail-fresh4-ae/grades-condition-B-generic-lemma-H03.json),
[C grade](../../../qwen/.runtime/qwen35_external_teacher_20260925/blind-why-fail-fresh4-ae/grades-condition-C-claim-only-H03.json), and
[D grade](../../../qwen/.runtime/qwen35_external_teacher_20260925/blind-why-fail-fresh4-ae/grades-condition-D-proof-supplied-H03.json).

**H14 is mainly stuck at the construction bridge in these probes.** B twice
misidentifies R through a false reflection argument. C states the supplied
`R=proj_AM(H)` claim and computes the correct `507/200`, but its attempted
proof from D, E, P, Q relies on invalid continuity and an asserted “known
theorem”; it does not establish the chosen intersection. D supplies that
construction proof, after which the answer correctly derives the right angle,
positive `HR=13/5`, and exact area. D still has an unretracted auxiliary
vector error, so it is conditional execution evidence, not a complete strict
proof. See [B](heldout-near-transfer/proof-gap-diagnostic-fresh4/condition-B-H14-grades.json),
[C](../../../qwen/.runtime/qwen35_external_teacher_20260925/blind-why-fail-fresh4-ae/grades-condition-C-claim-only-H14.json), and
[D](heldout-near-transfer/proof-gap-diagnostic-fresh4/condition-D-H14-grades.json).

**H04 has no hidden foot-identification step:** the original question defines
P as the foot. The base already produced one complete proof in two fresh4
instances. With B's generic projection lemma, both outputs contain a sound
final derivation from `TA=TP` through the nonzero acute factor and `T-B-C`
branch to `AT²=BT·TC`, and both exact values are correct. Their unretracted
false exploratory statements fail the strict whole-answer rubric; an
[independent review](heldout-near-transfer/proof-gap-diagnostic-fresh4/condition-B-H04-independent-review.md)
confirmed that separation. In C the model accepts the supplied downstream
identity without deriving it; in D it derives and applies it correctly after
the bridge is supplied, but again leaves an earlier false relation unretracted.
See the [B adjudication](../../../qwen/.runtime/qwen35_external_teacher_20260925/scored-why-fail-fresh4-lemma/grades-H04-adjudicated.json),
[C grade](../../../qwen/.runtime/qwen35_external_teacher_20260925/scored-why-fail-fresh4-claim/grades-H04.json),
and [D independent review](heldout-near-transfer/proof-gap-diagnostic-fresh4/condition-D-H04-independent-review.md).

## Interpretation limits

- The two numeric instances per ID are variants of one construction, not
  independent families. C and D have only one completion per ID. These
  observations localize failures in the sampled outputs; they do not measure
  the model's underlying success probability precisely.
- C and D change prompt content and available mathematics. Their successes
  are conditional capability probes, not independent geometric discovery or
  a causal decomposition of learning.
- The all-37 adapter has seen a teacher answer for each of these source IDs.
  Its 0/2 H03 proof, 1/2 H04 proof, and 0/2 H14 proof provide no reliable
  same-ID proof gain in this small test. This cannot isolate training dose,
  teacher style, optimization, or model capacity as the cause.
- The original research target remains self-generated, independently checked
  geometric relations and their use on different constructions. The current
  external-teacher diagnostic is a lower-bar positive control only.

No new training was started for this stage-localization request. GPU
generation is complete and the GPU worker has exited.
