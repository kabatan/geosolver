# Branch cleanup archive — 2026-08-11

This record accompanies the cleanup that retains only `main` and `experiment`
as local branches. The extra branch histories were joined to `experiment` by
the tree-preserving archive merge `ba2ea313` (the merge has no tree changes;
its additional parents retain the original commits and evidence). Therefore
the branch names can be removed without making their committed experiments
unreachable from `experiment`.

The two worktrees that had uncommitted material were committed before the
archive merge:

- `4a177932` — `codex/exp-authority-adversary`: captured
  `audits/quadratic_virtual_substitution_source_closure/{AGGREGATE.json,VERDICT.md}`.
- `ab4c4fee` — `codex/exp-cross-endpoint-vieta`: captured the five modified
  `cross_endpoint_vieta_v1` connector/manifest/test files.

The detached `control-0967` worktree was already represented by the retained
history (`0967ff1c` is reachable from `main` and the geometry branches) and
contained no uncommitted changes.

To inspect an archived experiment after branch deletion, use its commit below,
for example `git show <commit>:<path>` or `git log --all <commit>`. The archive
merge is intentionally first-parented to the previous `experiment` tip
`faf60573`; it does not mix experimental code into the checked-out tree.

| Deleted branch | Tip | Tip subject |
| --- | --- | --- |
| `codex/audit-partial-ideal-regular-root-join` | `649288cb` | research: audit partial ideal regular root join |
| `codex/exp-adaptive-deflation-one` | `b7483d74` | experiment: test adaptive deflation-one proposals |
| `codex/exp-adaptive-deflation-one-real-gate` | `e038858a` | experiment: stop deflation after zero real misses |
| `codex/exp-anisotropic-normal-gn` | `477c7f80` | experiment: connect spectral cosh to current campaign |
| `codex/exp-archive-dual-admission-exact` | `a48ec508` | audit: stop duplicate dual admission composition |
| `codex/exp-archive-exact-outer` | `4cd7ff9f` | experiment: reopen archived champion under exact outer |
| `codex/exp-archive-exact-reflect-point` | `a0f2edec` | experiment: contain reflect arm child lifecycle |
| `codex/exp-archive-progressive-exact-outer` | `ec10e4ed` | experiment: contain archived exact worker children |
| `codex/exp-authority-adversary` | `4a177932` | archive: capture quadratic VS source-closure evidence |
| `codex/exp-authority-cache` | `9492c1fc` | experiment: record authority cache D1 hold |
| `codex/exp-branching-svgd-connector-audit` | `fabfc6b4` | research: stop branching SVGD before connector |
| `codex/exp-branching-svgd-d0` | `9cfdabc0` | research: prototype branching SVGD cleanroom D0 |
| `codex/exp-categorical-exact-coordinate-portfolio` | `e750b7da` | experiment: fail prejoin process on stop |
| `codex/exp-certified-hermite-witness` | `d9c66ef0` | experiment: hard-contain Hermite repair OR |
| `codex/exp-checkpoint-genealogical-ams` | `6bbb6fde` | experiment: hold AMS current-campaign connector |
| `codex/exp-coefficient-monodromy` | `44437e46` | research: record monodromy repair A zero activation |
| `codex/exp-config-first-source-derived-target` | `ee005983` | experiment: stop config-first target before connector |
| `codex/exp-continuation` | `e3d07a94` | research: stop duplicate continuation lane |
| `codex/exp-cross-endpoint-hp-rung-racing` | `e8d6df78` | experiment: audit cross-endpoint HP rung state |
| `codex/exp-cross-endpoint-proof-racing` | `24a2c9a7` | audit: stop duplicate cross-endpoint species racing |
| `codex/exp-cross-endpoint-vieta` | `ab4c4fee` | archive: capture cross-endpoint Vieta working-tree evidence |
| `codex/exp-ed-critical-slice` | `96859ce6` | research: test guard boundary conormal sampling |
| `codex/exp-evaluator` | `bc77e965` | research: capture per-case CPU and peak RSS |
| `codex/exp-exact-gram-chirotope` | `ca704205` | experiment: gate semantic branch exact-trial reorder |
| `codex/exp-exact-typed-angle-current-connector` | `b5d47cc5` | experiment: audit typed angle current connector |
| `codex/exp-exact-typed-angle-current-repair-a` | `d12af3e6` | audit: stop typed angle repair before formal screen |
| `codex/exp-exact-typed-angle-equality` | `807be91d` | experiment: add exact typed angle equality fallback |
| `codex/exp-exceptional-stratum` | `4141cd64` | experiment: prototype exceptional stratum fibre products |
| `codex/exp-gp-analytic-connector-audit` | `f9292240` | research: stop analytic varpro at source gate |
| `codex/exp-gp-variable-projection` | `5dcbf645` | research: test analytic projected derivative reopen |
| `codex/exp-guard-relative-merge-tree-portal` | `5d91fb64` | experiment: record portal Repair A stop evidence |
| `codex/exp-guard-swap` | `55f30120` | research: test guard equation swap breadth |
| `codex/exp-guided-target-ideal-membership-v1` | `93ad0fa1` | research: stop typed-cover target repair after activation gate |
| `codex/exp-homotopy-baseline` | `81943c7c` | Label missing admission metadata without inference |
| `codex/exp-krawczyk-c3v-connector` | `efc08e11` | experiment: connect local Krawczyk proof to C3V link |
| `codex/exp-local-krawczyk` | `0346339c` | experiment: prototype local-box krawczyk rescue |
| `codex/exp-local-monodromy-orbit` | `9ac2604b` | research: prototype local monodromy orbit ledger |
| `codex/exp-macaulay-pep-d0` | `c4a49058` | experiment: prototype rank-completing Macaulay proposals |
| `codex/exp-msolve-bigint-transport-reopen` | `aaa4a2f1` | research: audit msolve production connector |
| `codex/exp-multi-target-sparse-cofactor` | `542844a9` | experiment: stop sparse cofactor on real compiler gate |
| `codex/exp-multitarget` | `75a27963` | experiment: hold species real connection |
| `codex/exp-noise-aware-sqp` | `d956baf4` | experiment: test noise-aware rank-deficient SQP polish |
| `codex/exp-nullspace-low-height-current-repair` | `f6694721` | experiment: connect exact low-height transport fallback |
| `codex/exp-operator-graph-divide-concur` | `34939dae` | experiment: add operator graph divide-concur gate |
| `codex/exp-particle-consensus` | `aa71e14b` | experiment: connect particle consensus full worker |
| `codex/exp-particle-consensus-tail-union` | `282b0b7d` | experiment: reopen particle tail with charged FD |
| `codex/exp-poc-corrective-stored-endpoint` | `8e62c6a1` | research: close stored point-on-circle lane |
| `codex/exp-post-endpoint-angle-ray` | `5f9dee88` | research: record rank v2 and S3 preflight |
| `codex/exp-primitive-element-current-v4` | `5f9dee88` | research: record rank v2 and S3 preflight |
| `codex/exp-progressive-exact-particle-tail` | `5f252d30` | experiment: close particle tail runtime pins |
| `codex/exp-progressive-exact-spectral-cosh` | `f050a7bc` | audit: pass spectral tail to formal screen |
| `codex/exp-proof-obligation-sbfe-connector-audit` | `39d40246` | audit: stop proof-obligation SBFE connector |
| `codex/exp-proof-obligation-sbfe-d0` | `ee29f3e6` | experiment: add proof-obligation SBFE D0 |
| `codex/exp-qreflect-current-repair` | `d234a821` | experiment: repair exact point reflection dispatch |
| `codex/exp-rank-guard` | `8aa01f6a` | research: qualify trust radius v2 arm |
| `codex/exp-research-round14` | `eef704ee` | experiment: test partial border-basis Hermite witness |
| `codex/exp-rowspace-quotient` | `77242a8b` | research: audit rowspace quotient and test dual Bregman lane |
| `codex/exp-scheduler` | `56b2c279` | experiment: combine exact authority cache with DiGS Repair B |
| `codex/exp-sector-certified-integer-angle-relation` | `f536cc99` | experiment: sector-certify integer angle relations |
| `codex/exp-semantic-cut-bundle-connector-audit` | `01d5ef26` | experiment: stop semantic cut connector at seam gate |
| `codex/exp-semantic-cut-bundle-gn` | `128ff5f1` | research: prototype semantic invalid cut bundle GN |
| `codex/exp-semismooth` | `4645062b` | research: prototype typed active-stratum semismooth lane |
| `codex/exp-singular-pep-rank-completion` | `a77f6d24` | research: prototype singular PEP rank completion |
| `codex/exp-source-analytic-derivative-energy-transport` | `ae3f1537` | experiment: test source derivative energy start transport |
| `codex/exp-source-ideal-signed-automorphism-orbit` | `9be6ad40` | experiment: stop automorphism orbit on zero activation |
| `codex/exp-source-period-quotient-cyclotomic-witness` | `44ee17a3` | experiment: stop duplicate cyclotomic phase witness |
| `codex/exp-source-quadratic-moment-round` | `5d4ce0f9` | research: stop quadratic moment candidate at blind gate |
| `codex/exp-stateful-resume-universal-restart` | `43cb9b50` | audit: hold wall-quantum restart without state seam |
| `codex/exp-structure` | `7c64bf7e` | campaign: add resume-safe S3 ABBA runner |
| `codex/exp-target-constrained-nra-witness` | `ccf774e4` | research: record authority audit stops |
| `codex/exp-thom-hermite-target-fibre-exhaustion` | `b5b01ede` | experiment: stop standalone Hermite route after census |
| `codex/exp-trace-closed-angle-lift` | `d7b3ff83` | experiment: prototype trace-closed angle lift |
| `codex/exp-trig-operator-lift-d0` | `2ef1ff6f` | experiment: stop trig connector after source seam audit |
| `codex/exp-typed-semantic-equal-qbar-pi-affine` | `ba720862` | experiment: stop typed semantic repair after no-gain trace |
| `codex/geometry-kernel-finalist` | `8f03ed7e` | test: cover callback snapshot metamorphisms |
| `codex/geometry-kernel-iterative` | `51c7f8d7` | perf: execute raw libmp programs iteratively |
| `codex/geometry-kernel-lab` | `c8171e6a` | Fix S3 launcher venv bootstrap |
| `codex/geometry-kernel-native` | `830427fd` | fix: reject source-exact radicals in native admission |
| `codex/geometry-kernel-promote` | `720ae718` | build: attest callback snapshot in optimized closure |
| `codex/geometry-kernel-snapshot` | `b3ca63c7` | test: cover snapshot dispatch metamorphisms |
