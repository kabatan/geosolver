# H01/H07 relation-discrimination candidate audit

This CPU-authored, untrained candidate set adds three English relation-check QAs per construction to the heldout-excluded 32-row teacher base. It does not use excluded-family problems, answers, or model outputs. It does not modify the main comparison datasets or frozen evaluation inputs, and establishes no transfer result. All three H07 candidate prompts explicitly state that the first circle is tangent at A and the second circle at B.

## QA distinctions

| Case | Plausible false relation | Audited true relation and branch |
|---|---|---|
| H01 v0 | Confuse `AP` with `MP` | `MP=m²/t`; acute angle gives `t²−m²>0`, so `0<m²/t²<1` and `AP=t−m²/t` |
| H01 v1 | Replace projection formula with `AP=t−m` | Same projection identity and acute branch |
| H01 v2 | Treat projection length as `MP=m` | Same projection identity and acute branch |
| H07 v0 | Use `AB²` instead of tangent radius `OA²` | `M=λN`, `0<λ<1`, `λ=OA²/ON²`, so `OM·ON=OA²` |
| H07 v1 | Use `AB²/ON²` instead of `OA²/ON²` | Same ordered-ray radial relation |
| H07 v2 | Use `λ` instead of `1−λ` in the area | `PQ=AB(1−λ)` and height `2MF`, so area is `AB·MF·(1−λ)` |

The H01 coordinate argument and H07 tangent-circle, radial, reflection, and area derivations follow relation statements in the audited v0 answers; no additional lemma is assumed. Numeric givens are limited to H01/H07 v0-v2. SymPy 1.14.0 verified the exact branch, true values, and unequal sides of every false claim. See `audit.json` for the exact calculations.

## Dataset and tokenization

The combined candidate dataset contains 32 allowed base examples plus six additions: 38 unique IDs, 32 unique sources, H01/H07 each presented four times, and all other sources once. No excluded source occurs. Maximum sequence length is 1238 tokens, under 8192.

Tokenizer revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`; counts mirror the training driver's non-thinking chat-template path. The six additions contain 2422 assistant target tokens including EOS. Per-example and combined counts are in `token-audit.json`.

No GPU training or evaluation was run.
