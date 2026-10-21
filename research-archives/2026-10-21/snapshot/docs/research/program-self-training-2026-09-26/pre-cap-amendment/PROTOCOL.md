# Executable-experience self-training pilot

Written before this study's model generation and training, 2026-09-26.

Question: can the model turn numeric experience into reusable executable
procedures, learn those self-generated procedures, and improve untaught
general geometry proofs using weights alone? Same-configuration proof gains
are valid outcomes. Passing numerical tests or improving tool-assisted code
alone is not the primary research outcome.

## Inputs and separation

Use H01,H04,H07,H13,H14,H15,DA01,DA05, matching the previous answer-OPD pilot.
All descriptions and model interactions are English. Only the allowed scalar
givens enter `solve(givens)`; hidden construction coordinates, target proof
statements, general relations, authored solutions and grading repairs are not
provided to the generating or trained model.

A deterministic CPU construction oracle samples nonsimilar numerical
configurations and measures the requested distances/areas directly. The four
disjoint sets per configuration are: visible examples4, repair-feedback4,
private selection24, private final24. This is448 geometric instances in total.
Numerical construction code follows the given construction, not the target
closed-form identity. Known relations may be separately used to audit the
oracle, never as label generation, sampling/filtering or model feedback.
Coordinates, branch checks and shape signatures remain in private provenance.
This is a learning-method pilot using direct construction labels, not yet a
fresh end-to-end repository-solver corpus for unknown mathematics.

## Candidate collection and execution

Start from the original frozen Qwen3.5-9B revision
c202236235762e1c871ad0ccb60c8ee5ba337b9a, not an OPD checkpoint.
Generate4 candidates per configuration in non-thinking mode, temperature0.7,
top_p0.95, top_k20, presence_penalty0.2, cap4096, context16384.
Each prompt supplies the geometry specification and4 visible I/O examples.
Ask for one closed Python fence defining a synchronous `solve(givens)` that
returns a finite real scalar, with code only and no proof prose.
Allowed numerical modules are math,cmath,statistics,fractions,decimal,
itertools,functools. Ordinary Python control flow and numerical algorithms
are permitted; no target-specific formula grammar or auxiliary construction
is supplied. No external files, oracle, network or geometry package is usable.

Frozen extraction rule: last closed python/py/unlabelled fence that parses
and satisfies the top-level synchronous solve(givens) interface and import
policy. Later invalid fences are skipped and recorded, without numerical
selection between fences. Multiple definitions within that program use normal
Python semantics. Strip only a terminal assistant EOS marker before matching
fences. A truncated generation is a format failure even if an earlier block
happens to compile. Preserve the raw output and hashes.

Execute in an OS-isolated minimal Python environment with no repository,
home, model, answer files or network. Apply wall/CPU/memory/output limits.
Compare scalar outputs with abs tolerance1e-7 plus relative tolerance1e-6.
Record every failure and execution time; NaN, infinity, non-scalars and
exceptions fail. Isolation checks precede executing model-generated code.

Candidates failing visible/repair cases receive at most one repair attempt.
Feedback gives syntax/runtime errors or up to4 failed inputs with expected
and actual scalar values, but never a repaired program or general formula.
All4 repair cases are exposed in that repair request, including if the first
attempt has a format failure. A candidate passing public checks is not
repaired on private selection failures. No root/agent edits to candidate math.

Strip comments and docstrings by a recorded AST normalization so unverified
natural-language explanations are not trained. Reject semantics that depend
on docstrings/dunder reflection. Re-execute normalized code and require raw/normalized public outputs agree
within abs1e-12+relative1e-12. Acceptance
requires all public and private selection cases. Keep up to2 distinct
normalized programs per configuration in original candidate-index order;
do not select using proof scores, final tests or human-preferred formulas.
One terminal candidate per trajectory: successful repair replaces its failed
first attempt. Record initial-to-repair yield, deduplication and runtime.

Freeze accepted training data before opening private-final outcomes. Test
all accepted programs on the24 private-final cases without feeding results
back or changing acceptance. Finite tests do not prove general correctness.

## Learning gate and comparison

If fewer than4 of the8 configurations produce an accepted program, stop this
pilot before SFT and report candidate supply as insufficient at this budget.
Coverage4–5 is a narrow diagnostic, not a broad-positive claim. Predominantly
lookup/memorization or solver reimplementation is reported separately and
cannot be called extraction of general geometric relations.

If the gate passes, run one fixed32-update assistant-only LoRA SFT per arm,
fresh from the same base:

1. Program SFT: configuration/function specification without concrete I/O
   examples -> normalized self-generated accepted program.
2. Numeric SFT: the same supported configurations, visible+repair numeric
   instances -> numerical answer only; no proof/explanation teacher.

Both use bf16 base, r8alpha16 dropout0, attention+linear-attention+MLP module
coverage from the working OPD engine, AdamW5e-6 weight_decay0, grad_accum4,
clip1, fixed seed2026092701. Deterministic shuffled repetition reaches32
updates, each averaging4 example losses. Save16 if convenient but do not
evaluate/select that dose. Training targets must fit completely; never train
a truncated program as if complete. All dataset hashes and actual target
token counts are recorded before training.

This is update-matched, not token-matched: programs and numeric outputs differ
in length, and accepted programs encode test-based selection. The numeric
control is a practical comparator, not a clean identification of representation
effects independent of supervision quantity. No duplicated code disguised as
new geometric experience. If dataset/target lengths make this recipe
infeasible, record a pre-training implementation amendment.

## Evaluation and decision

Reuse the frozen previous24 evaluation jobs:8 configurations×2 fixed
prompt/seed formulations for primary proofs,2 other configurations×2 for
secondary proofs, and4 elementary retention problems. Retain all8 primary
configurations even if some supplied no accepted training code. Compare each
new arm with the preserved base outputs only after model revision, generation
driver, jobs and settings are verified identical. Temperature0.7/top_p0.95/
top_k20/presence0.2, cap32768/context40960, no thinking/hint/tools.

Additional mechanism probes: for the base, generate4 candidates per
configuration without examples, with the same paired seeds/settings as the
initial4 example-conditioned candidates. No repairs or training-data adoption
from this control. Compare initial candidate quality at equal generation
budget to diagnose how much numeric examples help beyond existing model
knowledge. This comparison does not remove geometry-description priors.
After SFT, generate one no-example candidate per configuration per trained
arm and compare only with sample0 of the preserved base no-example outputs;
never compare one trained sample to the base best of4. Execute on the private
final cases, without feedback. Code use is diagnostic, not untaught proof
ability. No-program-collection or no-numeric-experience training control has
been run, so causal attribution of proof gains remains limited.

Blind and shuffle proof outputs; reuse the established frozen GRADING.md,
separating sufficient correct general arguments from unretracted false
ancillary claims. Include reference-only old answers for calibration, never
double-count them. Record mathematical adjudications before opening each
batch key. Report the known prior grading corrections and any new ones.

Candidate-positive primary signal: net gain at least4/16 vs base across at
least2 configurations, and retention loses fewer than2/4. Program vs numeric
differences determine whether the procedure route adds practical value at
this budget. Small selected tasks, two formulations of the same configuration
and one training seed do not establish reproducibility. A promising program
arm requires a second seed or unused proof formulations before a reproducible
claim; a code-only improvement does not count as proof transfer.

No indefinite hyperparameter search. If accepted code is available but this
fixed SFT recipe fails the proof endpoint, report that the experience
compression part works and the code-to-proof learning link remains unsupported.
If neither candidate supply nor proof transfer succeeds, deprioritize this
concrete recipe; do not declare solver+ML impossible or novelty established.

Cost is measured from generation/training/evaluation receipts, including
load overhead, with CPU oracle and execution time separate. No paid remote
GPU is used. Reuse the verified process-local NVIDIA library recovery for
the existing host mismatch; no system changes are part of this study.
