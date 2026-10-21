# H01 v1/v2 candidate audit

These are draft English teacher examples for the two H01 rows marked `train` and tagged as shape augmentations by the benchmark authoring metadata. At the model-visible level, the geometry template is unchanged: only the numeric givens `BC` and `AM` change. The internal generator parameter `u` is not present in either prompt or answer; these examples should therefore be described as numeric counterfactuals, not as model-visible shape conditioning. Each reuses the audited general construction proof in `external-H01-v0` from the 2026-09-24 teacher set; only the givens and final substitution change. The prompt wording follows that set's English prompt template.

| Variant | Verified givens | Let `m=BC/2`, `t=AM` | Acute-angle check `t²−m²` | Independent exact substitution | Benchmark label |
| --- | --- | --- | ---: | --- | --- |
| v1 | `BC=22`, `AM=13` | `m=11`, `t=13` | `169−121=48>0` | `13−121/13=(169−121)/13=48/13` | `48/13` |
| v2 | `BC=18`, `AM=11` | `m=9`, `t=11` | `121−81=40>0` | `11−81/11=(121−81)/11=40/11` | `40/11` |

For both cases, the audited relation gives `MP=m²/t`; the positive value `t²−m²` puts the projection strictly between `M` and `A`, so `AP=t−m²/t`. The authoring rows record generator parameter `u=1/3` and tag these as shape augmentations, but that hidden parameter is not an input to the model. The exact arithmetic above independently reproduces each stored label. These files are candidate data for review; they are not training results and establish no transfer claim.

## English and proof consistency

The English problem statement preserves the audited source statement's triangle type, definitions of `H`, `M`, and `P`, requested quantity, and prompt instructions; only `BC` and `AM` are replaced by the corresponding v1/v2 givens. The proof text through the general relation is an exact match to the audited `external-H01-v0` answer. The final application uses the candidate's own givens.

## Chat-template tokenization

Counts below use the local Qwen3.5-9B tokenizer at revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a` on CPU. I applied `apply_chat_template` with `enable_thinking=False`, matching the training driver. The prompt count includes the assistant generation header. The assistant-span count includes the final `<|im_end|>` token; the no-EOS-loss target count is one token shorter.

| Candidate | Prompt tokens | Assistant span, including EOS | Target tokens with final EOS masked | Prompt + assistant span |
| --- | ---: | ---: | ---: | ---: |
| v1 | 211 | 300 | 299 | 511 |
| v2 | 211 | 298 | 297 | 509 |

Both rendered conversations begin with the user message and end the assistant span with `<|im_end|>`. The raw candidate answers contain no chat-control or thinking tokens. Both sequences are far below the configured 8,192-token limit.

## v3/d1 overlap check

I compared the candidate prompts and answer strings against the H01 v3 training row and H01 d1 benchmark input. Neither full `(BC, AM)` pair nor either exact answer-label string appears in the candidate examples. Candidate v1 shares the single given `AM=13` with v3, while its `BC` value differs; v2 has no shared given with either comparison row. This is a partial single-value overlap, not an exact problem/label duplicate. The comparison used benchmark inputs and labels only; no model evaluation outputs were read.

This exact-number check does not remove construction-family overlap: both candidates explicitly repeat the same general H01 relation and proof, which can be instantiated with the v3 or d1 givens. That is intentional teacher content, not an accidental copy of their numeric answers. If v3/d1 are used to test whether the model independently discovers the H01 relation, they are no longer independent tests after training on these examples; they can only test application of the taught relation to a new numeric pair.
