# Integrated H01/H07 worked-answer comparison candidate

`train-38-direct-multi.json` is the integrated worked-answer dataset. It consists of the common 32-row base plus six full audited teacher examples: H01 and H07 v0, v1, and v2 once each. H07 prompts explicitly map the first circle to A and the second to B. It is compared with `train-38-repeat.json`, the same base plus three exact v0 prompt/answer copies per H01 and H07 source.

Both groups have 38 unique row IDs and 32 unique sources; H01 and H07 each have four presentations including the base row, and every other source has one. The six matched addition slots have the same source sequence and use the same seed/order. Exact H01 acute-branch arithmetic and H07 radial/area checks are in `comparison-audit.json`.

The earlier balanced true/false relation QA is separate: use `train-38-balanced-qa.json`, `balanced-qa-protocol.json`, `balanced-qa-token-audit.json`, and `balanced-qa-audit.json`. Its answer key is `qa-answer-key.json`; it is not mixed into the integrated direct-multi arm.

## Token counts

CPU token counts use the Qwen3.5-9B tokenizer at revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a` and mirror train.py's non-thinking chat template and assistant-through-EOS loss.

| Dataset | Prompt tokens | Assistant tokens incl. EOS | Assistant tokens excl. EOS | Total sequence tokens | Max sequence |
|---|---:|---:|---:|---:|---:|
| Integrated direct-multi | 9888 | 22757 | 22719 | 32645 | 1238 |
| Exact-repeat control | 9839 | 22645 | 22607 | 32484 | 1238 |

The two protocols use seed 2026092431, lr=1e-5, one epoch, 38 updates, 32 unique sources, and matching optimizer/LoRA/model settings. They are train.py compatible. No GPU training or evaluation was run; frozen evaluation inputs and outputs were not modified or opened.
