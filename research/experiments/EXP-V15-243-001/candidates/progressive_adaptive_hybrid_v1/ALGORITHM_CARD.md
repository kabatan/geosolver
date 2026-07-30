# Progressive adaptive hybrid v1

## Reopen gate

Formal-owner aggregate only showed that both fixed progressive profiles lost
recall while retaining about 20% geometric-mean speed.  Case identities and
truth were not disclosed.  This arm reopens the scheduler only if it can keep
prefix starvation protection without ending a promising narrow-basin lane at
an intermediate tranche.

## Mechanism

- immutable original-prefix starts receive 64-callback probes in ordinal
  blocks of eight, so a useful early block can hand off before the full prefix
  consumes the search window;
- the probe uses `max(0.5, min(4, 2*remaining/unserved))` to prevent a long
  callback from monopolizing all unserved starts;
- after each completed block, up to half its starts are sent directly to a
  fresh original 600-callback service, with 25% original-order regular
  baseline quota and 25% counter-Cauchy quota; a block with no completed or
  pre-deadline endpoint evidence continues probing without a deep handoff;
- remaining slots use only semantic validity, residual/guard rank, optional
  model ratio/rank stability, charged work, measured wall, and ambiguity;
- a completed fast probe earns the full remaining global wall horizon for its
  600-callback handoff; only a probe that timed out or consumed at least 90% of
  its admission cap is classified as demonstrated starvation and remains
  capped at four seconds;
- no checkpoint is claimed: a deep handoff is charged original-start
  reexecution through the frozen local kernel.

No problem ID, family, answer, target count, prior formal outcome, validation,
or sealed information is an input.  The frozen source replay, HP/restoration,
canonical descriptor authority, exact-set deduplication, and result schema are
unchanged.

## Generated S0

`S0_EVIDENCE.json` binds the candidate bytes and records all-start first
service, callback reconciliation, counter-Cauchy/IID coverage, long-callback
starvation protection, useful preemption re-handoff, and fail-closed accounting.
A synthetic radius-`1e-12` basin reaches rungs `[64, 600]`; its completed probe
gets more than four seconds for the deep service.  Variable/residual
permutation and positive affine variable/common residual scaling preserve the
complete `(start, rung)` decision trace.  This is mechanism evidence only and
does not claim recall or speed improvement.

`FULL_BINDING_SMOKE.json` records the common-runner arm-contract dry plan and a
current-hash full-v15 execution on a generated one-variable source.  The smoke
completed all 16 probes and eight 600-callback handoffs while preserving the
source and frozen canonical result schema.  Raw files remain outside Git.  No
scorer, formal screen, benchmark truth, validation, or sealed input was used.
