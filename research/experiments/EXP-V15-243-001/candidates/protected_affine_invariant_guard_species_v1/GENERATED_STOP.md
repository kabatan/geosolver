# Generated decision: STOP

The frozen generated gate was executed once against candidate SHA-256
`54f15070104265e48a5ebb77db23da4d4a546c841589afd1eca4f2001f787bc2`.
The aggregate `RAW_RESULT.json` has SHA-256
`e4d4e4bd3b33ded69fbfb5b21a7a6930a3a06c7faa9ccabaf8138c46eba16eed`.

The mechanism is stopped before any real screen:

- unit tests: 7/7 passed;
- paired generated runs: 1,440;
- root-class gains/losses: +47/-15 across seven gain structures;
- false roots, protected-ordinal failures, permutation failures, inactive runs:
  all zero;
- translation parity: 28 mismatches in 144 comparisons;
- coordinate-scale parity: 14 mismatches in 144 comparisons;
- periodic-chart parity: 3 mismatches in 18 comparisons; and
- candidate/control CPU ratio: 1.263961216, above the frozen 1.15 cap.

The 75/25 permutation protection worked, but it did not provide zero recall
loss.  Removing coordinates from the score was also insufficient to make the
online mechanism representation-invariant: transformed prefix observations,
local endpoints, whitening, and the evolving archive can produce a different
side order.  The score/archive work additionally cost about 26.4% CPU.

An independent static review also found that the preregistered metamorphic
gate covered only translation, coordinate scale, and periodic chart, and
compared final root sets rather than schedule/feature parity.  That gap does
not weaken the STOP decision: the candidate already failed every mandatory
transform class that was executed, as well as the loss and CPU gates.  No
expanded or tuned rerun is authorized.

Reopen only for a different representation and selection mechanism that makes
the complete side schedule itself identical under the applicable source
transformations before search begins (for example, a canonical exact feature
representation with a statically frozen side permutation), while preserving
the 75% protected portfolio.  Threshold, radius, quota, whitening cutoff, and
transform-subset tuning are not reopen gates.

`authority_pass` and `target_release` remain false.
