# Bridge follow-up rule, fixed before any bridge training or answer

The first bridge pass remains the ten-job comparison in `eval_jobs.json`. Before
any bridge model was trained or any fresh4 model answer was generated, a
GPT-5.6-Pro review flagged the instability of prior H04 single-sample outcomes.
This addendum fixes the follow-up rule without changing the first-pass jobs,
teachers, scoring rubric, or primary H03/H14 interpretation.

If either H03 or H14 has a complete-proof difference between its rotation's
treatment and matched control on **any** of that ID's two first-pass fresh4
jobs, run a complete second decoding-seed pass for the untouched base and all
six bridge arms on all ten jobs. Do not select only a favorable ID, arm, or
answer. Blind-grade the whole 70-answer second pass before opening its
condition mapping. The second-pass jobs are already fixed in
`eval_jobs_second_seed.json`, SHA-256
`935961492acc0f3387069dbf2cf9bcfb89d320a5806988ed6a08ad05c073324e`.
They retain every prompt and evaluation role, append `-seed2` to each job ID,
and transform each first-pass 31-bit seed with XOR `0x5A5A5A5A`. This is a
decoding-seed replication of the same numerical problems and checkpoints,
not a new configuration or independent training-seed replication.

If no H03/H14 complete-proof difference occurs, a full second pass is optional
only as a separately labeled exploratory diagnostic. H04 alone does not
trigger the primary follow-up.

The four existing source-retention items have a low base floor and are reported
descriptively, not used as a sharp pass/fail gate. If a retention claim is
needed, use the separately predeclared higher-base-performance retention
sentinel and keep it outside held-out transfer counts. Added-only teacher-token
gaps of 5.32–12.26% remain a disclosed confound even though merged-dataset
gaps are below 1%.
