# Decoding diagnostic note

Read during long-cap repair generation on2026-09-26, before selection/SFT.

The [official Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B#best-practices)
suggests32768 output tokens generally and81920 for difficult competition-style
problems. It recommends presence_penalty1.5 in its non-thinking general preset
and describes0–2 as a range for reducing endless repetition, with possible
quality/language-mixing costs. Its two non-thinking reasoning presets disagree
between sections; there is no unique reasoning preset to quote from that page.

This study inherits presence_penalty0.2 from the previous comparison. Repetition
in our outputs does not establish that this parameter caused the failure, or
that increasing it would solve the geometry. No ongoing repair or main-proof
evaluation setting was changed after reading this guidance. A separate bounded
decoder diagnostic requires its own recorded configuration and must not
be silently pooled with the frozen comparison. One H14 attempt is now frozen
in `decoder-diagnostic-protocol.json`: the non-thinking general preset and
81920 output tokens. It has no training adoption, repair, or tuning loop.

Current evidence: the4096 cap truncated17/32 initial candidates; rerunning with
32768 produced27 natural completions. Five remained capped. Their preserved
tails and whole-block syntax checks are in `long-truncation-diagnostic.json`.
Four parse but have no return statement; one has a syntax error. Thus these
five are not merely completed returning programs missing their closing fence.

The separate diagnostic has now completed:162 tokens, natural stop. It returned
`AH*AR/4`, which disagreed with all56 visible/repair/selection/final cases.
This output was not adopted or repaired. Raising the limit while changing the
sampling preset removed truncation in this one run but did not supply a correct
procedure. It does not isolate which sampling parameter affected repetition.
See `qwen/.runtime/program_self_training_20260926/decoder-diagnostic-check.json`.

Both trained models' main24-output evaluations completed with natural stop
in all48 outputs, including40 proofs and8 elementary retention responses.
Thus the proof comparison itself is not censored by the generation limit.
