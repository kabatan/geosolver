# Retention numerical-extraction repair, 2026-09-30 JST

This is a disclosed measurement repair, not a change to model generation,
training, questions, numerical tolerances, reasoning rubric, or branch thresholds.
It was identified before canonical main grades and condition mapping were joined.

The frozen retention prompts request a numerical value and brief justification;
they do not require an `Answer:` line or a boxed answer. The inherited strict
numeric parser recognizes mainly those markers or a bare numerical response.
Inspection found correct explicitly stated final values recorded as unparsed.
For example, the Base median answer explicitly states its exact length under
`Final Conclusion`, but the inherited parser returns no numerical expression.
Treating these parse failures as evidence of elementary ability loss would not
measure the intended retention criterion.

The correction is restricted to the 28 retention outputs. The main and short
parsers remain unchanged. Every original output and every original native score
is preserved. There is no regeneration, best-of selection, or use of an expected
value to select the model's claim.

Two fresh-context AI readers independently read all 28 shuffled condition-hidden
questions and complete final answers. No expected values or condition mapping
are supplied. They transcribe the last unambiguous committed requested value,
quote its exact passage, and record full-text coverage and content SHA256.
They do not solve the problem to supply a missing value. Ambiguous or absent
claims remain unparsed. Disagreement must be resolved from the text before
joining the condition mapping or answer key. Exact symbolic agreement of the
transcriptions is verified before any corrected numerical scoring.

After extraction commitments are saved, the unchanged absolute/relative
numerical tolerance is applied to those claims. Corrected retention rows are
used with the unchanged `decide.py` thresholds. The original parser scores and
original-parser branch decision are retained as a sensitivity/provenance record.
The main condition-hidden reasoning packets are unchanged by this repair.

This is a post-output procedural amendment prompted by a verified measurement
failure; it must be reported explicitly. It does not establish perfect blinding
or independent human review. Supplemental evidence is saved under runtime
`review-retention-extraction/` and `retention-extraction-correction-{phase}.json`
(`phase` is `initial` or `branch`).
