"""Stratified random choice of representative cases from the 60 s screen.

Population: cases whose DSL has at least one unknown and whose polynomial
translation succeeded (whatever msolve then did). Strata by the number of DSL
unknowns; the seed is fixed before looking at any per-case timing.
"""

import json
import random
import sys
from pathlib import Path

screen = Path(sys.argv[1])
per_stratum = int(sys.argv[2]) if len(sys.argv) > 2 else 10
SEED = 20261021
STRATA = {"1-2": (1, 2), "3-4": (3, 4), "5+": (5, 99)}

population = {k: [] for k in STRATA}
for f in sorted(screen.glob("*.json")):
    d = json.loads(f.read_text())
    if d.get("status") == "unsupported" or not d.get("nvars"):
        continue
    n = d["dsl_vars"]
    for k, (lo, hi) in STRATA.items():
        if lo <= n <= hi:
            population[k].append(d["id"])
rng = random.Random(SEED)
chosen = []
for k in STRATA:
    ids = sorted(population[k])
    pick = sorted(rng.sample(ids, min(per_stratum, len(ids))))
    print(f"# stratum {k}: population {len(ids)}, chosen {len(pick)}", file=sys.stderr)
    chosen += pick
print("\n".join(chosen))
