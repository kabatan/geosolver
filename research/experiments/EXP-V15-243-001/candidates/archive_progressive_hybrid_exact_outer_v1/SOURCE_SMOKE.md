# Unit and source-only smoke ledger

Date: 2026-07-31 (Asia/Tokyo)

All Python processes used `taskset -c 31`. The historical CLI dry plans carry
`--cpu 15` only because their schema accepts first-sibling IDs `[0,15]`; no
`--execute` or child process was run. No scorer, truth, real case result,
validation, sealed data, or formal CPU was accessed.

## Results

- 7 unit tests passed.
- One shared BASE simultaneously contained the progressive search fields and
  the historical champion-v2 + POC HP callable captured by exact_outer.
- A generated 32-start scheduler run retained 4/16 original-order baseline
  handoffs and 4/16 counter-Cauchy handoffs after all-start first service.
- An ordinary ready descriptor without exact-tail deadline failed closed.
- A simulated matching exact replay published the exact descriptor, not the
  ordinary descriptor.
- The positive-dimensional dry plan reported search arm
  `progressive_adaptive_hybrid_64_600`, mode `CONFIRM_ALL_AUTHORITIES`, capture
  count 1, baseline fraction 0.25, and ordinary authority bypass false.
- The zero-dimensional dry plan reported `source_exact_zero_dimensional`,
  progressive search not invoked, and authority logic unchanged.
- The archive exact-only control remained on its historical search arm with
  the same `CONFIRM_ALL_AUTHORITIES` boundary.

## Fixed-path PLAN hashes

The absolute output path is part of each PLAN. Repeating the positive candidate
dry-run at the same path reproduced the same hash.

- Progressive + exact positive: `7e80206473656e99002d27418af656df84846a7debea4d5a1b6d291765841209`
- Progressive + exact zero: `00f29bcf777be45581f3b2ca532e50216e3aeab904f1d5c7c24e3033be385fc2`
- Archive exact-only positive control: `6f19df49347c04aa2e93b21cf311e18754e3c75c431efd0da3db9b12c651b72e`

Raw dry artifacts are outside Git under
`/tmp/geotarget-archive-progressive-exact-source-smoke-v1/`.
