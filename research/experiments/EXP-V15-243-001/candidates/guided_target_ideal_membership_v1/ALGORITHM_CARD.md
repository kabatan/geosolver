# CANDIDATE_GUIDED_TARGET_IDEAL_MEMBERSHIP_V1

## Disposition

`PROOF_ONLY_GO / THREE_WAY_JOIN_EXPERIMENTAL / COMMON_AUTHORITY_HOLD`

This candidate does not install a solver decorator, return a target to a
collector, or claim target authority.  The initial 75/25 portfolio integration
was stopped after the proof-conversion audit established that subset ideal
membership alone does not prove source-root existence, guards, or branches.

## Mechanism

An existing ordinary HP result supplies an untrusted, primitive degree-one
descriptor.  The candidate reads the immutable source bytes itself, derives
the unique rational root `q` internally, and selects only mechanically safe
QQ-polynomial source equalities.  It then requires:

1. exact Groebner remainder of `raw_target - q` modulo the selected ideal is
   zero;
2. an independently reconstructed bounded polynomial-cofactor identity
   `raw_target - q = sum(h_i * source_equation_i)`;
3. the selected ideal is not the unit ideal;
4. the proof artifact replays exactly from source bytes and the complete
   ordinary proposal before any join.

Supported v1 expressions are polynomial arithmetic and closed affine geometry:
Point, Vector, Dot, signed Area2, Midpoint, Centroid, Circle center extraction,
point-center Reflect, PointOnSegment, Line, ParallelLine, PerpendicularLine,
and zero-valued OnLine/Collinear/Parallel/Perpendicular relations.  Symbolic
division, Distance, sqrt, abs, unsigned Area, Angle, trigonometry, min/max,
Intersect/selectors, containers, options, and recursive guards are outside the
proof subset.

Unsupported constraints may be ignored because every adopted equation is an
exact consequence of the original source.  Unsupported raw targets cannot be
ignored and fail closed.  Unnormalised line expressions are adopted only as
zero-equivalent relations; a nonzero line residual is never treated as the
canonical normalized value.

## Experimental three-way join

The only join evaluated is:

`audited typed regular-root + all nonrecursive typed guards`

plus

`subset universal target cofactor identity`

plus

`primitive degree-one descriptor with unique real ordinal 0`.

The source-root job is produced by the independently audited
`typed_guard_algebraic_extension` adapter.  It strips answer/post-processing
before compiler entry, rejects recursive guards and replay obligations, and
binds source, system, and job hashes.  The local Julia Krawczyk certificate
must prove strict inclusion, a unique regular root, and every source predicate.

Even when all three conjuncts verify, the result is only
`THREE_WAY_JOIN_READY_EXPERIMENTAL`: `authority_pass=false`,
`target_release=false`, `all_target_authority_conjuncts_present=false`, and
common worker integration remains HOLD pending policy and independent review.

## Binding hardening

- Public proof API accepts only a source path and the complete ordinary HP
  proposal; caller-supplied source digests, q values, or relations do not
  exist.
- Source bytes and SHA-256 are read internally.
- Degree-one coefficients must be primitive, leading-positive, and select a
  multiplicity-one ordinal-zero isolator.
- The complete ordinary proposal is canonically hashed.
- Join verification recompiles the source, recomputes Groebner reduction and
  cofactors, and exactly compares statement, node hashes, candidate relation,
  ordinary hash, and statement hash.
- Source mutation, forged proof artifacts, wrong ordinary proposals, tampered
  certificates, unit ideals, and recursive guards fail closed.

## D0 and source-only evidence

CPU 14 generated D0:

- affine, point-reflect/vector/dot, line-incidence, and renamed/permuted/scaled
  affine families: 4/4 subset identities proved;
- wrong q, noncanonical degree-one descriptors, unsupported-only constraint,
  inconsistent/unit ideal: all rejected;
- actual typed source job and Julia Krawczyk worker: 1/1 experimental join;
- source mutation, forged subset proof, wrong ordinary binding, certificate
  mutation, and recursive guard: all rejected;
- authority and target release events: zero.

The root-owned outcome-blind source readiness panel selected one endpoint per
source by first HP service ordinal from PLAN only.  On 135 anonymized requests,
the audited nonrecursive typed compiler was ready for 29 requests across 29
anonymous structural signatures.  The fixed gate of 10 attempts / 2
signatures passed.  This is a compiler upper bound, not a degree-one join or
target-authority count.

No scorer, truth, formal score, case ID, family, answer value, outcome, or
known target count was read by candidate routing.  The source-only readiness
compiler did not receive the raw answer.

## Current dependency freeze

Independent adversarial audit commit `649288cb` passed 17/17 binding and
non-overclaim checks.  The four audited candidate files remain byte-identical
to the hashes recorded by that audit; the later joint census runner is a
separate aggregate-only measurement surface and cannot emit authority.

The census reconstructs an internal synthetic proposal because the frozen
proof API requires its input token to say `authority_pass=true`.  That token
is bound only to the root-owned degree-one projection, is never returned, and
does not represent the unavailable complete ordinary proposal.  Census and
join outputs remain `authority_pass=false`, `target_release=false`, and
`common_worker_integration=HOLD`.  The aggregate exposes only the number of
distinct structural signatures, not the signatures or singleton histograms.

The mechanism hash in `arm.json` is SHA-256 over, in listed order,
`filename NUL decimal-byte-length NUL file-bytes` for `ideal_membership.py`,
`typed_join.py`, `run_generated.py`, `run_source_only_readiness.py`, and
`run_degree1_joint_census.py`.

- exact algebraic compiler:
  `f127f7f1e2f93161e1353f07222e93ffacfa1c2dbd4e68e5b1fd23a8a3b10318`
- typed guard adapter:
  `1d93005c49cf4e3360b8b64449022be46e97ae59cc437ef889f5289e239709b4`
- local typed worker adapter:
  `711a14c9bcce7bd99c770768199f4b778b819434b1bcf0b9454024d0cea68150`
- Julia local validated worker:
  `7086842164b868ff44ad3150a28b3836aae9898572e144e0cd3ad3953f553c14`
