# EXP-CONTINUATION-001: stalled residual pseudo-arclength audit

Status: **STOP_BEFORE_CODE_EXACT_PRIOR_OVERLAP**

## Hypothesis requested

After an ordinary local attempt stalls at a finite, semantics-valid endpoint
`x0`, trace the residual curve

```text
H(x,t) = F(x) - t F(x0) = 0,       (x,t)=(x0,1) -> t=0
```

with an augmented pseudo-arclength predictor/corrector.  Service at most one
in four lanes, abort on guard/branch change, and submit only proposals that
pass the untouched canonical source replay.

## Overlap decision

This is equation-identical to the frozen `residual_value_curve` candidate.
Changing admission from an anonymous physical start to a stalled,
semantics-valid endpoint changes only the trigger; the prior audit explicitly
states that a stall-trigger or arclength-constant change does not reopen the
lineage.  It is also strictly covered by later trajectory and fold-branch
experiments:

| prior lineage | relevant frozen evidence | decision |
|---|---|---|
| `residual_value_curve` | pseudo-arclength solved all 20 simple folds, but the primary solved 81/100 versus direct LM 82/100 using 33,600 versus 12,895 F/J calls; two general improvement waves completed | terminal STOP, no real screen |
| `residual_continuation_v2` | three real screen waves were all source-solved 48 -> 48; safe-endpoint/CPU changed -7.233%, -3.455%, -7.159% | terminal STOP |
| `g0_trajectory_residual_transport` | actual stalled LM trajectory state, active nontrivial paths, 0/6 gain families, one loss, six scale-metamorphic failures | STOP_G0 |
| `g0_residual_level_arc_escape` | weak-progress/high-turn trajectory trigger, two mechanisms, gain in 1/6 families, callback ratio 1.162/1.166 | STOP_G0 |
| `wave17_residual_fold_branch_switch_g1` | frozen bordered pseudo-arclength, +60 roots in only one structure and 120/10,260 metamorphic mismatches | STOP_G1 |

The requested generated strata were already exercised without holdout access:

- S-shaped, simple/coupled folds, cusp/tangent and singular-no-fold controls;
- square no-real, inconsistent overdetermined and monotone/no-fold controls;
- strict semantic/guard near misses, with raw roots rejected;
- variable transforms, residual permutation, equation/coordinate scaling and
  opposite pseudo-arclength orientations.

The prior G0 fold candidate was strong on constructed curves, but its frozen
prospective G1 transfer failed breadth and redundant-row metamorphic gates.
Repeating those D0 cases or adding a `t` reparameterization check cannot repair
the observed efficacy/breadth failure.

## Safety and budget invariants

No solver, scorer, dataset, target, truth, validation, sealed, HP or CAS input
was executed or opened.  No shared worker, compiler, harness, public API or
canonical replay path was changed.  The ordinary numerical baseline therefore
remains 100% untouched, exceeding the requested 75% insurance floor.

## Reopen gate

Do not reopen this lane through a new stall threshold, row metric, step
schedule, direction share, endpoint service fraction, `t` parameterization or
predictor/corrector constant.  Reopen only with a different evolution
equation or basin-transition invariant that:

1. predicts recovery outside folds/periodic covers on at least three unrelated
   anonymous structures;
2. is invariant to residual redundancy as well as permutation and scaling;
3. beats the frozen one-direction comparator and direct LM under equal work;
4. preserves at least 75% literal baseline work and uses untouched canonical
   replay as the sole authority.

The adjacent direct oriented-residual PTC route is not such a reopen: its
frozen G1 transfer already regressed 104 -> 89 solved cases and is terminal.

