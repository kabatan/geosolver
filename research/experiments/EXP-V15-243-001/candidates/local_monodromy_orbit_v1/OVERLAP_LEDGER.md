# Prior-overlap decision

Disposition: **GO as a distinct toy D0**.

| Prior mechanism | Prior state/trigger | Why this candidate is distinct |
|---|---|---|
| `numeric_monodromy_branch_discovery` and `wave17_real_return_monodromy_thin` | A fresh source-replayed **regular full-rank root**, frozen left inverse, and a closed 2-D residual-space loop; reservoir state is other returned source roots/sheets | This candidate starts at a **rank-deficient singular germ**, loops a local generic source slice, and stores localized witness permutation orbits plus tangent state at the same germ |
| `EXP-REAL61-004/coefficient_monodromy_parameter_homotopy` | Generic global coefficient fibre `F(x)-p`, transport of a zero-dimensional regular cover back to `p=0` | This candidate does not enumerate a global coefficient cover; it asks for the local irreducible branch structure near one singular point |
| `wave14_conjugate_monodromy_proposal` | Square polynomial holomorphic/conjugate loops and generated complex proposals | No conjugation certificate is used; local witness-set orbits, guard replay and real tangent proposals are the output |
| witness-set literature note | Global positive-dimensional witness sets and trace tests, not implemented | The present code is the first narrow local-germ orbit/tangent prototype in the archive |

The terminal coordinate-covariance failure of thin residual return monodromy is
not reopened: no residual loop plane is selected here.  Ambient permutation and
scale covariance are tested through the source-to-local chart, while all
emitted points are replayed in the original source coordinates.

If an attempted real binding lacks singular local witness/tangent state and is
only a different residual loop around a regular root, this candidate must stop
pre-code.  The next independent queue item is singular polynomial eigenproblem
rank completion, not another return-path variant.
