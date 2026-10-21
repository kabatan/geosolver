# Forced-final follow-up for length-stopped Thinking traces

Purpose: inspect what a long, unfinished Thinking trace can express when asked
to give a final answer. This is a **separate conditional intervention**, not a
natural Thinking success or a replacement for the long-cap result.

Input eligibility is fixed: a completed 81,920-token Thinking output from
`THINKING_LONGCAP_REVISION.md` whose `finish_reason` is `length` and whose
generated raw text has no `</think>` marker. Preserve the exact prompt token
IDs and all generated completion token IDs. Append the Qwen team's published
early-stopping text, including `</think>`, then let the same base or adapter
generate a final answer. Do not alter the original English problem, prior
trace, model weights, or answer key. Use the original job seed and decoding
settings; maximum 16,384 new final tokens and context 102,400. This context
fits the 81,920-token trace plus prompt, forced marker, and final budget, but
must be checked per job before generation. Record the prefix and forced-text
hashes, finish reason, final text, token count, and adapter.

The [official Qwen3 thinking-budget example](https://qwen.readthedocs.io/en/latest/getting_started/quickstart.html#thinking-budget)
uses a two-stage continuation with an early-stopping phrase. It is documented
for Qwen3, not specifically validated for Qwen3.5-9B; treat this use as an
exploratory adaptation. The output answers only: "Given this long trace and
an explicit instruction to finish, can the model produce a valid proof?"
It does not establish that the model would naturally finish or that SFT
transferred a geometric relation. The original length-stopped item remains
missing a final answer in the primary comparison.
