# Adversarial audit

- Scope: development `screen24`, seed 0, fixed 7 CPU lanes, ABBA order;
  no 98/holdout truth was read.
- Scores: control/candidate/candidate-r2/control-r2 were respectively
  `15/24`, `14/24`, `14/24`, `14/24`; all non-equal rows were `MISSING`.
- The apparent first-pair loss was one case with zero cache hits. The first
  control obtained one exact confirmation there, while the repeated control
  did not; both candidate repeats had the same miss. This is deadline/child
  execution jitter, not a cache-caused loss.
- Activation: candidate repeats produced 49 and 47 cache-hit terminals. They
  completed 153 and 149 HP attempts versus 103 and 107 for controls, while
  the repeated B/A pair had identical exact-set score.
- Soundness boundary: the cache is populated only by an
  `authority_pass=true` result from the frozen exact replay. A hit emits no
  descriptor and has `authority_pass=false`, so an ordinary/alternate witness
  cannot become authority. The worker's HP loops are serial; temporary reuse
  of the charged ordinary object does not cross concurrent calls.
- Identity scope: the key is the exact algebraic target value (primitive
  minimal polynomial plus real-root ordinal), not a configuration. A later
  configuration with another branch/raw-target witness is skipped only after
  the same target value already has one source/guard/branch/raw-target exact
  witness. The skipped witness is not promoted or merged into that witness.
- Added candidate-private fixtures cover pre-confirmation, failed-first
  replay, alternate branch/raw-target metadata, distinct targets, duplicate
  targets, and root-ordinal separation.
- Disposition: no soundness defect found. Recall is neutral under the repeat,
  activation is strong, but no formal speed/recall promotion gate is met yet.
