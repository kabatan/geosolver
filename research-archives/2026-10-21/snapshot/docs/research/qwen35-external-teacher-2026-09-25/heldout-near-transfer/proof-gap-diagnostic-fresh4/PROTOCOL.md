# Fresh4 construction-to-relation proof-gap diagnostic

## Purpose

This CPU-frozen diagnostic separates three stages on one matched numerical item
per source ID (H03, H04, H14): identifying/proving the construction bridge,
using an already established bridge, and finishing the requested relation and
numerical application. It is for stage localization, not a confirmatory result.

Condition C retains B's general projection lemma and adds a target-specific
claim, explicitly labels that added claim a conjecture, and requires a proof
or refutation from the stated construction.
For H03 and H14 the claim is the hidden construction-to-foot mapping. H04
already defines P as the foot, so its claim is the downstream identity linking
the perpendicular-bisector construction to AT.

Condition D also retains B's general lemma, but replaces C's claim/proof task
with a supplied decisive construction-to-foot/projection derivation and asks
for downstream relation use, branch handling, and application. D is a separate
proof-supplied branch from B, not another monotone hint added to C. It is an
execution diagnostic only. Its supplied bridge must never be scored as an
independent proof or independent transfer.

Both conditions are built from the existing relation-given fresh4 jobs, so they
share the same original English problem, generic projection lemma, numerical
givens, job seed, and standard instructions. Each C/D pair has a unique job ID
but the same `seed` and `english_problem` as its paired fresh4 item. No expected
target value, answer key, construction parameter, or model output is included.

## Interpretation

Score H03, H04, and H14 separately. For A (original), B (generic lemma), and
C (B plus a target-specific claim), grade both mapping/claim proof and
downstream reasoning.
For D, mark the bridge as `supplied/not scored`; grade only downstream
mathematics, branches, and application. D success cannot establish independent
proof ability.

- C succeeds while B fails: a target claim may help focus search, but the
  evidence remains small and prompt-sensitive.
- C fails while D succeeds: the supplied construction bridge helps execution;
  the main observed gap is before or during bridge derivation.
- D fails: downstream relation execution, branch control, or application also
  remains a problem; inspect the response to localize it.
- B succeeds but A fails: the generic relation helps, while discovery or the
  construction bridge remains unresolved.

These patterns are diagnostic, not causal proof by themselves: C and D differ
in the amount of mathematical help; only one numeric item per source is used;
fresh4 source families have been examined in earlier work; and prompt changes
can affect generation. The first fresh4 numeric instance is reused exactly to
pair conditions and is not a new untouched holdout.

## Reproduction and integrity

From the repository root, run:

```bash
python3 docs/research/qwen35-external-teacher-2026-09-25/heldout-near-transfer/proof-gap-diagnostic-fresh4/build_proof_gap_diagnostic.py
```

The builder reads the frozen fresh4 and relation-given job files to assemble
prompts. It hashes the named audit/protocol sources as opaque bytes, but does
not parse answer keys, construction-check values, model outputs, or scores; it
does not invoke a model or GPU. It refuses to overwrite generated artifacts.
`hashes.json` records source and generated SHA-256 digests. Do not modify the
fresh4 source jobs. Freeze decoding and scoring before any later evaluation.
