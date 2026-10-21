# Frozen grading rules

Primary success means a complete, correct derivation of the stated general
claim under the problem's assumptions. Coordinates, vectors, algebra, and
standard theorems are accepted. A special numerical example, merely naming
the desired configuration-specific lemma, or an unproved decisive identity is
not a proof. A substitution that is asserted to simplify but actually does not
is an error. Routine arithmetic need not be expanded into every elementary
operation when the supplied expressions make the step directly checkable.

For each anonymous output record:

- `complete_proof`: true/false, based on a sufficient correct argument.
- `decisive_step`: the exact argument that succeeds, or the first decisive gap.
- `ancillary_math_error`: any unretracted incorrect claim outside an otherwise
  sufficient argument. Report a conservative total excluding these outputs
  as well as the main complete-proof count. Retracted exploratory attempts do
  not invalidate a later correct proof.
- `numeric_correct`: true/false/null (numeric tasks only).
- `confidence`: high/medium/low; uncertain algebra must be checked rather than
  guessed.

No credit merely for producing the target statement. Proof tasks already give
the statement. Conditions needed for a division or directed-length argument
must be handled, but a solution can use the explicit global nondegeneracy
assumption rather than repeatedly restating it.

Outputs will be randomly shuffled and assigned anonymous IDs before grading.
The scoring agent must not open raw checkpoint folders, unblinding keys, or
result summaries. Training implementers and data authors may grade if the
condition identity is withheld; that is procedural blinding, not a claim that
an independent human audit has occurred. No grading solution is sent to the
training model. Root adjudication and any numerical/symbolic checks are saved.

These are small selected development tasks. Two samples of one theorem are
not two independent theorems. Report per-configuration results and paired
sample changes, not only pooled percentages.
