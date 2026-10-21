# Qwen3.5-9B Thinking comparison with an 81,920-token cap

## Question and protocol

The user asked whether enabling Thinking changes the earlier stage-localization
result, and specifically required a longer output budget so that truncated
reasoning would not be mistaken for an answer. We reran the frozen six English
fresh4 numeric probes: two instances each of H03, H04, and H14. These are
three construction families, **not six independent families**. The untreated
base and the existing all-37 low-dose SFT adapter were each run with Thinking
enabled, one sample per instance, output cap 81,920 and context 90,112. The
model revision, job prompts, per-job seeds, temperature 1, top-p 0.95, top-k
20, and presence penalty 1.5 were held fixed. The earlier non-Thinking runs
used cap 32,768 and context 45,056; every one of their completions ended
naturally before 13,000 tokens, so their cap was nonbinding. The two modes
have different prompt templates and may use very different compute; this is
an observed comparison, not an isolated causal estimate of a Thinking flag.

The [revised protocol](THINKING_LONGCAP_REVISION.md) and
[freeze](THINKING_LONGCAP_FREEZE.json) preceded the long-cap outputs. The base
Thinking run ended in 56.3 minutes and the adapter run in 101.4 minutes. The
[pinned Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B/blob/c202236235762e1c871ad0ccb60c8ee5ba337b9a/README.md)
recommends a long output budget up to 81,920 tokens for
hard mathematics; we used that recommendation as the diagnostic upper limit.

We graded only text after a generated `</think>` marker as a Thinking answer.
The one length-stopped trace without that marker has **no final answer** and
is separately audited. The 24 answers across four conditions were shuffled
into a [blind packet](../../../qwen/.runtime/qwen35_external_teacher_20260925/blind-thinking-fresh4-ae/packet.json).
H03, H04, and H14 were graded independently under the pre-existing
[rubric](STAGE_LOCALIZATION_GRADING.md), and the [grade hashes were frozen](thinking-comparison-blind/THINKING_BLIND_GRADE_FREEZE.json)
before condition labels were opened. A [reproducible join](join_thinking_grades.py)
and [per-job scores](thinking-comparison-blind/THINKING_JOINED_SCORES.json)
retain finish reason and token count for every output.

## Result

| Weights and mode | Final answers | Correct exact values | Complete proofs, blind grade |
|---|---:|---:|---:|
| Untreated base, non-Thinking | 6/6 | 2/6 | 1/6 |
| All-37 low-dose SFT, non-Thinking | 6/6 | 2/6 | 1/6 |
| Untreated base, Thinking | 6/6 | 4/6 | 1/6* |
| All-37 low-dose SFT, Thinking | 5/6 | 2/6 | 1/6 |

The asterisk is one H04 base-Thinking proof with an incorrect sentence about
the reason a denominator is nonzero. The blind grade and a separate
[adjudication](thinking-comparison-blind/H04_T014_ADJUDICATION.md) count the
proof: the nonzero fact also follows from the stated acute-angle premise and
from existence of the perpendicular-bisector construction. An earlier
base-only grade excluded this answer under the strictest reading of the
unretracted erroneous sentence. A second [independent audit](thinking-comparison-blind/H04_COMPLETE_PROOF_AUDIT.md)
confirmed the mathematical derivation while flagging the same sentence.
Under that sensitivity reading the base
Thinking complete-proof count is **0/6**. This ambiguity concerns only H04;
the H03 and H14 construction-proof counts are zero in all four conditions.

### By construction

| Condition | H03 exact / proof | H04 exact / proof | H14 exact / proof |
|---|---:|---:|---:|
| Base non-Thinking | 0/2, 0/2 | 2/2, 1/2 | 0/2, 0/2 |
| SFT non-Thinking | 0/2, 0/2 | 1/2, 1/2 | 1/2, 0/2 |
| Base Thinking | 1/2, 0/2 | 1/2, 1/2* | 2/2, 0/2 |
| SFT Thinking | 0/2, 0/2 | 2/2, 1/2 | 0/2, 0/2 |

The SFT Thinking outputs used 81,920, 45,531, 30,346, 19,720, 62,783,
and 42,461 generated tokens, respectively in H03/H03/H04/H04/H14/H14
order. Only H03 instance 1 hit the cap without closing Thinking. All six base
Thinking outputs ended naturally (22,513–62,861 tokens).

**H03.** The base Thinking model gave `28/3` for `OH=14`, but merely stated
the correct center relation without deriving that the three constructed
points are feet from the orthocenter to the medians. Its `OH=13` answer was
wrong. The SFT Thinking model gave `7` for `OH=14`; for `OH=13` it never
reached a final answer. Its unfinished 81,920-token trace did derive the
selected second intersection from circle power, but failed to connect that
point to the orthocenter projection, then never derived the diameter-`HG`
circle. The missing bridge is the identity
`(H-M_a)·(A-M_a)=BC²/4`: it matches the coefficient of the power-derived
second intersection and proves that point is the foot from `H` to `AM_a`.
See the [trace audit](thinking-comparison-baseline-audit/H03_FRESH4_0_ALL37_LOWDOSE_80K_TRACE.md)
and [blind H03 grades](thinking-comparison-blind/grades-H03.md).

**H04.** This problem gives the foot `P` in its statement and asks the model
to derive the downstream perpendicular-bisector product relation and select
the exterior branch. SFT Thinking gave both exact values correctly, with
one complete proof. It also had one complete proof without Thinking. The
base Thinking model gave one correct value and the disputed complete proof
noted above. H04 demonstrates some downstream capability but does not test
the hidden construction-to-foot bridge that blocks H03 and H14. See the
[blind H04 grades](thinking-comparison-blind/grades-H04.md).

**H14.** Base Thinking gave both exact areas, but in neither answer proved
from the construction that `R` is the foot from `H` to `AM`. SFT Thinking
gave neither exact area: one answer asserted `A,H,R` are collinear and
returned zero; the other stated a right angle at `R` but used incorrect
area legs. None of the eight H14 answers across the four conditions proved
the mapping. See the [blind H14 grades](thinking-comparison-blind/grades-H14.md).

## Conditional finish of the one capped trace

We preserved the exact 81,920-token H03 trace and appended a separately
documented [early-finish instruction](THINKING_FORCED_FINAL_DIAGNOSTIC.md),
then allowed up to 16,384 additional final-answer tokens. The continuation
stopped naturally after 4,653 tokens. It again characterized the constructed
point through circle power but did not prove it was the orthocenter foot. It
asserted `Z=H` and answered `13` for `OH=13`; the keyed answer is `26/3`.
This [conditional grade](thinking-comparison-blind/forced-final-H03.md) is
**not** added to natural Thinking success. It shows that the missing final
answer was not hiding a correct proof in this one recorded trace.

## Interpretation for the research plan

Increasing the budget resolved the main ambiguity from the 32,768-token
pilot: most Thinking outputs reached a final answer. The untreated base
produced more correct numbers with Thinking (2/6 to 4/6), but it still did
not prove the decisive H03/H14 construction links. The current external-
teacher SFT adapter did **not** show a numerical or complete-proof gain from
Thinking on these six probes (2/6 and 1/6 in either mode), and its H03/H14
Thinking outputs did not demonstrate the desired transfer. This is a
small, repeated-ID numeric probe, not a precise estimate of success rate or
a verdict on all teacher styles, SFT doses, or models.

The intended hypothesis concerns a model forming and reusing independently
verified geometric relations across different constructions. This all-37
external-teacher experiment is only a lower-bar positive control. The next
diagnostic or training change should target the **proof bridge** explicitly:
correctly identify the selected construction intersection, derive its
orthocenter-projection identity, and connect that identity to the requested
downstream relation, with varied proof styles and independent held-out
constructions. More thinking tokens by themselves were not enough in the
recorded H03/H14 cases.
