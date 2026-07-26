# Experiment runtime freeze

Use the existing absolute interpreter
`/home/kabatan/work/solver/python/.venv/bin/python` with native thread counts
fixed to one.  The historical recorded environment and the current venv agree:

- Python 3.12.11
- NumPy 2.5.1
- SciPy 1.18.0
- mpmath 1.3.0
- SymPy 1.14.0

No package install or lockfile is needed for this reproduction.

Five fresh one-core measurements put the champion-v0 worker import at
0.016--0.018 seconds, but its first `PRECISION_RUNTIME` load at 0.862--0.881
seconds (about 141--143 MiB peak RSS).  That transitive load nearly consumes
the historical one-second endpoint-selection window.  Pre-importing the four
top-level numerical packages still leaves 0.308--0.315 seconds; additionally
pre-importing `scipy.optimize`, `scipy.linalg`, and `numpy.polynomial` still
leaves 0.207--0.213 seconds.

For the experiment-only worker wrappers, load the existing
`PRECISION_RUNTIME` once before search and return that same module object when
the arm's `_fresh_replay_candidates` asks for it.  The preload remains charged
to the case's 180-second wall budget; only its placement before creation of the
one-second selection deadline changes.  Do not change package versions,
selection duration, replay thresholds, starts, callback work, or shared worker
files.

The inherited `_load_module` always executes a new module even when its name is
already present in `sys.modules`.  Consequently, a plain preload is
insufficient: the wrapper must narrowly intercept only the matching
`PRECISION_RUNTIME` path and return the preloaded object, delegating every
other module load unchanged.
