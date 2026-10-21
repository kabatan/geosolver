# Conditional forced-final grading: H03

This is a separate diagnostic of the forced-final continuation. The original blind H03 grades remain unchanged. The answer was graded from `raw_final_text` only. This continuation is not a natural Thinking completion.

- Source: H03, fresh4 instance 1
- Finish reason: `stop`
- Generated continuation: 4,653 tokens; `raw_final_text` contains 14,885 characters
- Forced-final receipt: complete; generation elapsed 131.9 seconds

| Mapping claim / proof | Downstream relation / proof | Exact value | Complete proof |
|---|---|---|---|
| fail / fail | fail / fail | fail (13; expected 26/3) | fail |

The answer correctly derives the construction-only characterization `MA · MP = a²/4`, describing `Pa` as the inverse of `A` in the circle centered at `Ma` with radius `a/2`. It does not identify `Pa` as the foot of `H` onto `AMa` or derive the orthocenter projection identity needed for that mapping. It then asserts `Z = H` using an uncited “known result” and incomplete, internally inconsistent vector claims. The required relation is that `Z` is the midpoint of `HG`, giving `OZ = 2/3 OH = 26/3`; its final value `13` is wrong.

The per-entry machine-readable grade is in `forced-final-H03.json`.
