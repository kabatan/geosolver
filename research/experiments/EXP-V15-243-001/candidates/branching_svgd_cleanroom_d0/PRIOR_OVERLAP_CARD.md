# Prior overlap audit

## Question

Is the requested mechanism merely a rename or parameter change of a repository
particle candidate?

## Inspected evidence

- `research/experiments/EXP-REAL61-008/annealed_svgd_root_emitter_v17/`
  implements ordinary annealed, fixed-population RBF-SVGD.  Its prior generated
  panel recorded 0 gains / 0 losses and higher callback work, then froze it as
  negative evidence.  It has no roles, offspring, genealogy, or random spine.
- `research/experiments/EXP-V15-243-001/candidates/epoch_d_stein_particle_portal_precode_stop/DECISION.md`
  stopped a one/two-update deterministic Stein portal because it duplicated
  that same SVGD family.  Its audit explicitly distinguishes Branching SVGD's
  absent random branching transition.
- Repository-wide searches for the combined E/O/S role state, role-specific
  offspring, old-particle recolouring, and uniform unique spine found no
  implementation.

These paths were inspected source-only in the external frozen experiment
runtime.  No formal results, truth, or case-level scorer output was opened.

## Conclusion

**Fresh mechanism.**  The deterministic improvement overlaps standard SVGD,
as it must, but the causal intervention tested here is the paper's role-coloured
branch transition.  It is structural rather than a bandwidth, step-size,
particle-count, or annealing parameter variant.  Therefore the duplicate-stop
rule does not apply.

Primary research evidence: [Branching SVGD, arXiv:2506.13916](https://arxiv.org/abs/2506.13916)
and [standard SVGD, arXiv:1608.04471](https://arxiv.org/abs/1608.04471).
