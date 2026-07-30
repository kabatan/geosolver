# Source-only applicability seam audit

## Aggregate evidence available without formal scoring

The archived semantic-algebraic-lift census
(`5780c8dc...786`) reports, for development145 source syntax only:

- semantic frontend upper bound: 141/145;
- finite phase replay ledger: 141/145;
- selector ledger syntax-complete: 145/145;
- conservative auxiliary proxy: median 3, maximum 67, all 145 below its
  emitter cap of 128.

The census itself says this is conditional syntax coverage, not authority, a
solved count, or proof of affordable algebra. D0 therefore does not reproduce
that frontend and makes no activation estimate from these counts.

## Thin-copy compatibility

The archived exact target exporter (`b44ef826...b55f2`) already emits variables,
the target variable, polynomial equations and sparse terms, coefficient domain,
predicates, reconstruction data, and replay obligations. The following seam is
mechanically plausible but incomplete:

1. accept only `coefficient_domain == "QQ"`;
2. accept only a direct target chart whose unique target-image equation is
   affine in `__target`, then split it into `__target - tau` and source
   equations;
3. orient only strict polynomial predicates into `g > 0`;
4. attach a separately proposed square-free `p(t)` and rational isolating
   interval;
5. pass the exact payload to `certify`, then require `verifier.verify` before
   any canonical replay.

The current exporter also emits non-strict `ge` bounds/semantic predicates and
does not emit `p(t)` or an isolating interval. Silently dropping or strengthening
those predicates would be unsound. Consequently the current source seam is
**PARTIAL / HOLD**: exact-QQ equations are reusable by a thin adapter, but the
predicate semantics and target proposal producer must be supplied explicitly.

No formal execute, scorer, truth, case identity, answer, validation, sealed
data, or CPU 0--6 was accessed in this audit.
