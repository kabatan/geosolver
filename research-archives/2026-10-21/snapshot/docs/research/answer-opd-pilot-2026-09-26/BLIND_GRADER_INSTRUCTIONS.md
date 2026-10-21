# Anonymous proof grading task

Read `GRADING.md` and only the assigned anonymous packet. Do not open training
outputs, evaluation directories, private unblinding keys, other graders'
results, or study result summaries. Do not infer a training condition from
style. You may use CPU Python/SymPy to check the supplied algebra or construct
a valid counterexample to an intermediate claim. Do not run GPU work.

Read each answer in full, in manageable chunks; long exploratory passages can
contain both retracted errors and a later sufficient proof. A correct target
statement is not evidence: the target was supplied in the question. Do not
repair the model's missing central argument and then credit that repair to it.
Conversely, directly checkable substitutions and routine simplifications do
not have to be expanded into every arithmetic operation.

Produce a JSON list, one row per assigned anonymous ID:

```
{
  "anonymous_id": "A001",
  "complete_proof": false,
  "decisive_step": "Quote or precisely locate the decisive argument or gap.",
  "ancillary_math_error": false,
  "confidence": "high",
  "checks": "Specific symbolic/numerical checks performed, or not needed."
}
```

`ancillary_math_error` is `false` when absent, otherwise a string describing
an unretracted error outside an otherwise sufficient argument. Retracted
exploratory mistakes alone do not invalidate a later correct proof. Use
confidence `medium` or `low` for unresolved mathematical ambiguity and report
it explicitly; do not guess a positive result. Root will adjudicate.

Save grades incrementally after each answer, plus any small check scripts and
their outputs in the assigned grading directory. Report progress by completed
answer count, without needing any condition identity. This is procedural LLM
blinding, not independent human or formal verification.
