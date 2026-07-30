# Local monodromy orbit ledger v1

## Hypothesis

A rank-deficient endpoint cluster may be several local branches/sheets collapsed
at one singular germ.  Continuing a small generic source-slice loop and storing
the induced witness permutation can expose local branch/component diversity
that a single endpoint or tangent proposal misses.

## Disposable mechanism

- Trigger only when the local Jacobian rank is below the source codimension.
- Follow `P_t(v)=0` on a small loop of the generic local projection `t` in both
  directions, matching witness points continuously.
- Union the endpoint permutations into local orbits and attach normalized
  source-tangent labels to the localized witnesses.
- Return replayed real witness points as branch/component proposals.
- Keep the frozen baseline in 12/16 start slots; this side lane owns only 4/16.

Inputs are local source coefficients/DAG state, rank, guard and source replay.
No case ID, family, target, truth, answer count or prior case outcome is visible.
Opaque/nonpolynomial and regular germs fall back before evaluating a fibre.
Degree changes, path ambiguity, nonreal witnesses, source residual failures and
guard failures are fail-closed.  Canonical source replay remains authoritative.

This is a toy D0 only: no real connector, homotopy backend, scheduler framework
or reusable infrastructure was built.  The code is intentionally disposable.

## Evidence and disposition

Generated D0: 12 rank-deficient cases, 5 families, `11 wins / 0 losses / 0
false / 0 extra`; 4 families have positive signal.  The guard near-miss adds no
proposal and rejects the unsafe sheet.  Eight tests cover loop reversal, root
label permutation, ambient coordinate permutation/scale, residual scaling,
source replay, the 75/25 quota, regular fallback and opaque fallback.

`D0_PASS`; eligible only for a future thin real-seam experiment when a
rank-deficient local cluster exposes a safe polynomial slice/fibre.  Until then,
do not spend time building a generic complex continuation backend.

Primary basis: Edwards and Hauenstein,
[On computing local monodromy and the numerical local irreducible decomposition](https://arxiv.org/abs/2412.17952),
and the authors' [LocalMonodromy.jl](https://github.com/P-Edwards/LocalMonodromy.jl).

## Reopen/stop rule

Advance only if a real source seam supplies a local rank-deficient germ and the
side route finds distinct replay-safe configurations without reducing the 75%
baseline quota.  Stop on zero activation, any false/extra/invalid result, or if
the seam degenerates into the already-terminal regular-root residual return
monodromy mechanism.
