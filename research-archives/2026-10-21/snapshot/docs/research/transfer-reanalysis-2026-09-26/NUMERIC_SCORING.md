# Frozen numerical evaluation scoring

`score_numeric.py` compares the exact requested value for the 24 frozen v2 jobs (12 configurations, two inference seeds each). It is a numeric-answer scorer only: it does not judge the derivation, geometric branch choices, or whether the explanation justifies the answer. Keep that proof review separate and blind to condition labels where applicable.

For each response, the scorer finds explicit `Answer:`/`Final Answer:` lines (including `**Answer:** value`) and `\boxed{...}` markers in the post-`</think>` answer. It chooses the marker that occurs last in the generated text, then sends only that selected expression to `qwen.answer_check.extract_answer` and `answers_equal` for conservative parsing and exact symbolic comparison. Thus a later correction overrides an earlier box, and a final unclosed box remains the commit and becomes `unparsed` rather than falling back to an earlier answer. An absent or unsupported final commit is `unparsed` (`numeric_correct: null`), distinct from a parseable but wrong value (`false`). The scorer never searches arbitrary proof text for a convenient number.

Each condition must have a complete `generate_batch.py` receipt and exactly one `*-0.json` result for every frozen job. It checks the jobs-manifest hash, job IDs, frozen message/seed/variant/replicate fields, sample index, model revision and adapter against the receipt, plus the receipt’s single-sample setting. Across conditions it checks shared run settings and, by `job_id`, identical seeds, serialized prompts, and prompt-token IDs. Each output row stores raw JSON and text SHA-256 hashes, prompt hashes, exact expected label, commit chosen, parsed value/status, completion-token count, and finish reason. Run receipt hashes/settings are included for provenance.

The report gives counts overall, by source configuration, and by transfer group. Pairwise comparisons join on `job_id`: correct beats incorrect, equal correctness is a tie, and any pair containing an unparsed result is reported separately rather than called a loss. Per-configuration paired IDs are included. Natural finish reasons are counted separately from `length` and other non-natural finishes; completion length is measured from `completion_ids`.

Example invocation after the same v2 job set has completed in all conditions:

```bash
qwen/.venv/bin/python docs/research/transfer-reanalysis-2026-09-26/score_numeric.py \
  --jobs docs/research/transfer-reanalysis-2026-09-26/eval-jobs-v2.json \
  --answer-key docs/research/transfer-reanalysis-2026-09-26/answer-key.researcher-only.json \
  --condition base=/path/to/base-output \
  --condition code128=/path/to/code128-output \
  --condition numeric128=/path/to/numeric128-output \
  --condition opd32=/path/to/opd32-output \
  --out /path/to/numeric-score.json
```

The answer key is read locally for scoring and is never supplied to generation. CPU-only synthetic checks:

```bash
qwen/.venv/bin/python -m unittest discover \
  -s docs/research/transfer-reanalysis-2026-09-26 \
  -p 'test_score_numeric.py' -v
```

The tests cover last-commit precedence over an earlier box, unparsed versus incorrect, complete 24-job paired joins and hashes, per-configuration aggregation, and failure on a missing expected output. They use synthetic jobs and outputs, not model results.
