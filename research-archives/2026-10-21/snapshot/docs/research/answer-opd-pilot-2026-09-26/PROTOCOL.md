# Answer-privileged self-distillation pilot

2026-09-26. Written before this study's model generation or training. The data
manifest and exact commands complete this protocol; changes made before the
first run will be recorded below.

## Question and scope

Can numerical answers, supplied only to a frozen self-teacher, improve the
student's **untaught general proofs**, using its weights alone at evaluation?
The research intent remains the original user's intent in
`../intent-realignment-2026-09-26/CORRECTION.md`.

This is a local learning-component pilot, not a new end-to-end solver corpus.
Numerical labels come from the existing verified construction dataset; its
authoring code uses configuration-specific mathematical checks. Those checks,
relations, and solutions are never presented to the learning model. A positive
result would still need replication using the intended solver-generated data.

## Data and arms

Use 8 configurations: H01, H04, H07, H13, H14, H15, DA01, DA05. The 4 existing
numerical variants per configuration yield **32 numeric conditions**, not 128
independent examples. Repeated sampling is counted as rollouts, not new shapes.
The English problem is constructed from the existing NUMERIC_EN template and
canonical givens. Student input asks to solve with justified steps. Teacher
input differs only by a final-numeric-answer hint. No completed proof, target
general relation, external rationalization, or auxiliary construction is a
training target. General-proof tasks are held outside the training pool.

The principal arm uses non-thinking mode for both teacher and student. The
teacher is the original frozen Qwen3.5-9B base; the student is that base plus
LoRA. This isolates the numeric privilege from a thinking/non-thinking mode
change. It is not a reproduction of paper 2609.25623.

## Update and cost

- Model revision: c202236235762e1c871ad0ccb60c8ee5ba337b9a.
- LoRA r=8, alpha=16, dropout=0; existing attention, linear-attention, and MLP
  module coverage. BF16 base, FP32 trainable adapter where PEFT defaults apply.
- Exact full-vocabulary forward KL(teacher || student), temperature 1. Only
  completion positions contribute. Teacher logits offloaded to CPU in chunks.
- AdamW, lr 5e-6, weight decay 0, gradient accumulation 4, clip norm 1.
- Generate 8 fresh trajectories from the current student, then take 2 updates.
  Each trajectory is consumed once. The second update therefore has one-update
  policy lag; this is batched on-policy distillation, not strict resampling
  after every optimizer update.
- Initial rollout/training prefix cap: 4096 tokens. A capped prefix is not
  called a complete correct solution. Evaluation retains a 32768-token cap.
- Stage 1: 128 rollouts / 32 optimizer updates. Stage 2: continue the same
  optimizer and student to 256 rollouts / 64 updates. Evaluate both predefined
  checkpoints, reporting both rather than selecting the better one silently.
- Stop stage 2 early only on numerical/implementation failure or simultaneous
  severe deterioration (at least 6/16 fewer primary proof successes and at
  least 2/4 fewer retention numeric answers). Otherwise a stage-1 null result
  is followed by the larger dose.
- No paid remote GPU is used. GPU time, rollout tokens, training tokens, peak
  allocated VRAM, natural termination and truncation are reported.

## Evaluation

Primary: one general-proof task for each of the 8 trained configurations,
2 decoding samples each, same prompts and paired seeds for base and both
checkpoints. These statements/solutions never enter training. The tasks are
general, without the numeric values/answers used in training. The target
statement itself is supplied at evaluation, as appropriate for a proof task.

Secondary: 2 existing different-configuration proof tasks, 2 samples each.
Retention: 4 numeric tasks outside the 8 trained configurations, 1 sample each.
Use non-thinking decoding throughout, temperature 0.7, top_p 0.95, top_k 20,
presence penalty 0.2. Score complete mathematical derivation separately from
numeric correctness. A correct conclusion with a missing decisive lemma,
circular reasoning, or a false key step fails the complete-proof endpoint.
Valid coordinate/vector proofs count; a syntactic proof style is not required.

An independent subagent receives shuffled anonymous outputs for grading.
Condition identities and checkpoint results are withheld from that grading
batch. The root agent adjudicates mathematical ambiguities and checks the
decisive argument; no grader-supplied repair is learned. Sampling repetitions
of one theorem are not independent theorems. This is exploratory evidence on
a selected small suite already used in earlier work, not a publishable blind
test of broad geometry ability.

## Decisions

A net gain of at least 4/16 primary successes across at least two configurations,
without loss of 2/4 retention answers, is a candidate positive signal. It needs
a second training seed or unused proof formulation to be called reproducible.
Smaller changes are weak signals, not an established benefit. Exact paired
wins/losses and per-configuration results take precedence over aggregate rate.

If both doses fail, inspect whether the student measurably changed, gradients
were finite, the adapter was actually used, and the teacher's label-dependent
signal reached mathematical reasoning. A bounded teacher-mode follow-up may then be run, explicitly labeled as exploratory.
A negative result justifies deprioritizing this concrete recipe under the local
budget; it does not prove numerical-to-proof transfer or self-distillation
impossible. A thinking-teacher follow-up requires a matched teacher-without-
answer control before attributing a positive effect to numeric privilege.

## Amendments before execution

Before any GPU execution, increased the prefix cap from the draft 2048 to
4096. This reduces the risk of measuring only opening prose and avoids making
prefix length a post-result rescue. The completed Pro consultation recommended 2048 initially (4096 if the
reasoning needs it), then a bounded 32-to-64-update extension and a shuffled-
label control if a benefit appears. We retain the already chosen 4096 cap to
cover more of these long geometry derivations, and adopt its cheaper 64-update
endpoint rather than the draft 128. This change is also before all GPU runs
and before any evaluation outcomes. A benefit triggers a label-shuffle control
at the same dose before attributing it to the correct numeric information.
During preflight the data builder briefly used an answer-only student prompt;
this was caught before any generation and replaced by the specified derivation
prompt. The four retention prompts were replaced by elementary geometry
problems so that the baseline is not expected to have a floor score.
Exact data hashes and settings will be preserved in machine-readable receipts. The prior proposal's 16 configurations × 8 non-similar instances is
not already available in the local data; this focused pilot deliberately uses
the existing 8 × 4 pool and states that limitation.
