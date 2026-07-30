# PARTIAL_IDEAL_REGULAR_ROOT_JOIN_V1 independent audit

## Decision

**GO for experimental measurement; HOLD for collector/common-worker target authority.**

The frozen candidate at the hashes below passes all 17 CPU14 adversary checks.
It may emit `THREE_WAY_JOIN_READY_EXPERIMENTAL`, but it deliberately emits
neither `authority_pass` nor `target_release`, sets
`all_target_authority_conjuncts_present=false`, and leaves common-worker
integration on `HOLD`.  This is the correct policy boundary for the current
artifact.

Before the frozen run, the audit found three P0 bindings and one descriptor
compatibility defect:

1. caller-supplied source SHA could be paired with a different in-memory
   document;
2. caller-supplied rational target could disagree with the degree-one
   descriptor relation;
3. the join trusted proof status/booleans without replaying the statement,
   cofactor identity, and ordinary-proposal binding;
4. sign/scaled degree-one polynomials and malformed ordinal/multiplicity were
   accepted.

The candidate owner fixed all four before this audit freeze.  The public proof
API now reads and hashes the raw source itself, derives `q` from the bound
ordinary proposal, and the join invokes an exact proof replay.  Degree-one
descriptors must be primitive, leading-positive, multiplicity one, and use
zero-based real-root ordinal zero.

## The theorem that is actually available

Let `F_full` denote the full source semantics and let `g_i`, for `i in I`, be
the adopted exact source equalities.  `I` may be a strict subset: every valid
full source configuration still satisfies every adopted equality.  The
partial-ideal artifact `C` proves by exact QQ replay

```text
T(x) - q = sum_i a_i(x) g_i(x).
```

It therefore proves that **every** valid full source configuration has target
`q`; this is not a statement about one local component.  The typed artifact
`R` proves at least one full source/guard-valid configuration exists in its
rational Krawczyk box.  A primitive degree-one polynomial has one real root,
with ordinal zero.  Consequently:

```text
C: target image is a subset of {q}
R: target image is nonempty
degree one: {q} has exactly one element
---------------------------------------
target image is exactly {q}
```

Local uniqueness of the source root in `R`'s box is stronger than necessary;
global source-root uniqueness is not required.  This is why two or more
configurations with the same target are a positive case, whereas another
component with a different target makes the ideal remainder nonzero and is
rejected.

## Scope of `R`

The source-root conjunct is adequate only inside the independently audited
nonrecursive typed-compiler closure:

- the proof, typed job, certificate, and raw source bytes share the same SHA;
- `target_read=false`, the compiled target is constant zero, and source target
  text is never used by the root worker;
- `reconstruction=[]` and `replay_obligations=[]`;
- the Krawczyk certificate verifies a unique regular root in its rational box;
- all compiled strict source predicates/guards are interval-valid;
- the pinned typed adapter and local worker adapter hashes match.

Thus `R` supplies existence plus the full guards/definedness supported by that
closure.  A source with an intersection branch selector produces a valid
partial ideal proof when the target identity does not depend on the branch,
but typed job preparation rejects it; it cannot bypass `R` scope.  Recursive
guards, branch replay, reconstruction, unsupported target operations, or an
unproved symbolic denominator remain fallback-only.

The current API still assumes the pinned worker-launch closure supplies an
authentic certificate.  A collector integration must preserve that contained
launcher/process/hash boundary rather than accepting arbitrary user-provided
certificate mappings.

## Cofactor and artifact binding

The accepted artifact is bound to:

- raw source SHA;
- the canonical SHA of the complete ordinary proposal;
- primitive degree-one relation and rational root;
- adopted source constraint ordinals and AST node hashes;
- adopted exact equations;
- target-minus-`q` expression;
- Groebner reduction and exact zero remainder;
- explicit source-equation cofactors;
- canonical statement SHA.

`verify_subset_proof` reparses the same raw bytes, recompiles the equations and
target, recomputes Groebner/cofactor evidence, and compares mandatory fields
and the complete statement.  The audit changed the cofactor list and then
rehashed the statement; replay still rejected it.  A proof from mutated source
bytes and a proof replayed against a different ordinary `q` were also rejected.

The inconsistent/unit ideal is rejected explicitly.  This prevents a vacuous
ideal proof even though, with a correct same-source `R`, root existence would
already contradict that case.

## Collector contract

The present artifact has no collector release seam.  A later collector may
promote the exact singleton only if it atomically verifies all of the
following:

1. same raw source SHA, typed job/system SHA, subset statement SHA, and
   ordinary proposal SHA/descriptor;
2. contained pinned source-root worker certificate with all source predicates
   valid and empty replay/reconstruction;
3. exact replay of `T-q = sum a_i g_i` over adopted raw-source equality nodes;
4. primitive normalized degree-one descriptor, multiplicity one, ordinal zero;
5. final canonical source replay of the emitted descriptor.

A local `R` witness without the universal ideal identity is not completeness.
A degree greater than one is not completeness.  A nonzero ideal remainder is
not completeness.  Such cases must keep the numerical baseline and must not
early-stop.  Duplicate proofs use the stable key `(source_sha,
ordinary_proposal_sha, statement_sha)` and must deduplicate to the same exact
descriptor.  Multiple source configurations that share `q` are not duplicate
targets; they are already covered by the universal identity.

## Adversary matrix

| Near miss | Expected boundary | Result |
|---|---|---|
| inconsistent/unit ideal | reject | PASS |
| different target on another source component | nonzero remainder, reject | PASS |
| two configurations with the same target | universal identity accepted | PASS |
| symbolic/zero denominator | reject/fallback | PASS |
| quadratic/square relation | reject v1 | PASS |
| negative-leading or nonprimitive linear relation | reject noncanonical descriptor | PASS |
| wrong root ordinal or multiplicity | reject | PASS |
| branch-valued target | reject | PASS |
| branch selector in source | partial proof may hold, but `R` preparation rejects | PASS |
| raw source mutation | proof replay rejects | PASS |
| statement/cofactor mutation, including rehash | proof replay rejects | PASS |
| wrong ordinary proposal/`q` | proof replay rejects | PASS |
| duplicate proof | stable identity key | PASS |
| typed guard-certificate mutation | join HOLD | PASS |
| local experimental join | never emits collector authority | PASS |

## Freeze and reproduction

Candidate hashes at the passing audit run:

- `ideal_membership.py`:
  `74915d163e471df9e745735a8f5e3f7a128950d72c94d581c6435ffd081b60b4`
- `typed_join.py`:
  `a2ecdd7c406642464f550e3ce91d2cc24ed0f8c67ad7f513a62c6350ee930e26`
- `run_generated.py`:
  `385f91a74456b1bf4e0fe046a70b2aebde1911d6cfdab2a59459058ea2b5cca2`
- `run_source_only_readiness.py`:
  `99c1b4b002bde5f09223c3d73ccd50c2bc0a838b01d4787225a221bc2ee48c79`

Run command:

```bash
taskset -c 14 env \
  PYTHONPATH=/home/kabatan/miniforge3/envs/py312/lib/python3.12/site-packages \
  /home/kabatan/.local/share/uv/python/cpython-3.12.11-linux-x86_64-gnu/bin/python3.12 \
  research/experiments/EXP-V15-243-001/audits/partial_ideal_regular_root_join_v1/run_adversary.py
```

Result: `17/17`, worker return code zero, CPU affinity exactly `[14]`, Python
3.12.11, SymPy 1.14.0.  No truth values, selected case IDs, formal scorer, or
holdout corpus were used.  The machine-readable result is in
`AUDIT_RESULT.json`.
