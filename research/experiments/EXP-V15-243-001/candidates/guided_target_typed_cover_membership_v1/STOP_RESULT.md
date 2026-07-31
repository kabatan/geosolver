# Repair C stop result

- Command: CPU14-pinned `run_generated.py` under the frozen Python runtime.
- Runtime: 0.28 seconds; exit 1 because the predeclared 3/3 activation gate failed.
- Old closed-affine compiler misses: 3/3.
- Complete typed-cover identities: 2/3 (Distance/sqrt and
  Circle/constant-PointOnCircle); Area/abs did not prove.
- Negatives: wrong q, wrong branch, inconsistent cover witness, invalid
  source-root certificate, omitted equation, source mutation, and selector
  replay all rejected.
- Authority and release events: zero.
- Formal scorer/corpus, Julia, and global lock: unused.

An independently produced truth-blind aggregate fixed the current development
ceiling at three sources, below the formal gate of four sources in two groups.
No real-corpus run or post-result cap tuning is useful or permitted.  Reopen
only when an audited overdetermined exact source-root certificate raises that
ceiling above the frozen gate.
