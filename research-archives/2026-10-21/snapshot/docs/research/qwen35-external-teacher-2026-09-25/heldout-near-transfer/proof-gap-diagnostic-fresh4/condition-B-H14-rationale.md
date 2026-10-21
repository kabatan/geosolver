# Condition B: H14 grading

Both fresh4 H14 completions ended naturally (`finish_reason=stop`): instance 1 used 10,221 completion tokens and instance 2 used 12,465. I graded only each output's `final_text`, against the frozen B prompt, H14 answer-key entries, and the stage-localization rubric.

Neither answer correctly maps the constructed point `R` to the orthogonal projection of `H` onto `AM`. Both instead repeatedly claim that `R` is the reflection of `H` across `M` (and instance 1 ultimately asserts `AH ⟂ AR`). Neither proves the required construction link, derives the valid right angle `HR ⟂ AR`, or handles the positive `HR` branch. The supplied general lemma therefore does not rescue either answer: its hypothesis is not established for the point used.

The exact answers are also wrong: instance 1 gives `507/160` instead of `507/200`; instance 2 gives `17/2` instead of `289/39`. Both are clear failures rather than borderline grades; see `condition-B-H14-grades.json` for per-component mapping, downstream, branch, and exact scores.
