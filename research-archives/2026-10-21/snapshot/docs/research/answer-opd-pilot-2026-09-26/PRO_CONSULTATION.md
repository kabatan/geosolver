# GPT-6-Pro design consultation

Consultation: https://chatgpt.com/c/6ab6a6d0-0c94-83e9-bbcc-b5231b596610

The follow-up response completed in 6m51s, before this pilot's GPU runs. It
recommended same-mode frozen-teacher training first, 128 reasoning rollouts /
32 updates at 2048 tokens, then either a longer-prefix test or continuation
to 64 updates. Thinking-teacher experiments need a no-answer thinking-teacher
control. If a same-mode benefit appears, prioritize a matched wrong/shuffled
answer control before answer-only SFT. It explicitly distinguished non-thinking
reasoning answers from answer-only output, and did not require successful
frozen-teacher proof generation as a precondition.

Adopted: same-mode initial arm, two bounded doses, primary proof evaluation,
positional KL diagnostics, no artificial EOS, and label-shuffle follow-up for
a positive signal. The existing 4096-token choice was retained to cover more
of these long geometry derivations. The draft 128-update endpoint was reduced
to 64 before any GPU run to prioritize diagnostic value and cost.

The cited new primary source was independently opened and read:
[What Does Privileged Information Add to On-Policy Self-Distillation?](https://arxiv.org/html/2609.20612v1).
It reports that cross-mode reference-free and wrong-answer controls can improve
over base; this motivates a control, not a prediction that our same-mode
geometry arm will behave the same. Its KL profiles do not establish teacher
quality or replace actual training outcomes.

This consultation is advice, not experimental evidence. The local protocol,
receipts, and independently graded generations determine the conclusion.

## Interim-result consultation (after step32, while step64 is running)

Sent the complete step32 primary/secondary/conservative/retention/numeric
counts, the boundary-case sensitivities, prefix truncation, KL movement, and
measured costs to the same GPT-6-Pro conversation. Its response completed in
6m27s. It advised stopping simple dose increases if step64 remains below the
registered candidate threshold and clean proofs do not improve. A threshold
crossing must still be reported as candidate positive even if conservative
scores decline; the conservative score must not retroactively replace the
registered main endpoint. Step64 is dose continuation, not independent
replication. A matched wrong-label control is useful for attributing a positive
effect but is not required to decide against scaling an unconfirmed recipe.

It emphasized that truncation alone does not justify a longer run. Audit
whether valid new mathematical work continues near the cutoff, versus
repetition or an uncorrected decisive error. Root had already commissioned a
fixed original-round-1 audit of eight prefixes; this selection was not based
on evaluation success. Unlike Pro's suggested 16-prefix early/late audit, the
executed audit is only the original eight and is labeled accordingly.

One proposed (not executed or authorized as part of the principal arm)
follow-up was a matched two-arm comparison with generation cap5632, full
context, but loss on first4096 versus first2048+last2048 completion tokens,
both from base with128 rollouts/32 updates. This changes position coverage
while holding the maximum supervised token count fixed. It requires a
longest-prompt memory preflight and is not proven to fit merely because a
prior5670-token probe fit. Pro proposed an approximately6-GPU-hour ceiling
and making this contingent on several configurations still showing valid
progress at cutoff. These are resource-allocation suggestions, not empirical
evidence of effectiveness, a revised main protocol, or an automatically
triggered follow-up. No new hyperparameter arm has been launched.
