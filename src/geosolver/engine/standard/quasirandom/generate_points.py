from typing import List, Tuple
from .primes import _first_primes
from .halton import _halton_value

def _generate_halton_points(
    n: int,
    bounds: List[Tuple[float, float]],
    n_points: int,
    start_index: int = 1,
) -> List[List[float]]:
    """Generate deterministic Halton points in the given bounds (no f eval).

    This is used to add a small number of diverse *uninformed* local-optimization
    starts. It helps discover basins that don't show up as low-cost samples.
    """
    n_points = int(max(0, n_points))
    if n_points == 0:
        return []
    primes = _first_primes(n)
    pts: List[List[float]] = []
    for t in range(n_points):
        sample_id = int(start_index) + t
        pt: List[float] = []
        for j, (lo, hi) in enumerate(bounds):
            u = _halton_value(sample_id, primes[j])
            val = float(lo + u * (hi - lo))
            val = max(float(lo), min(float(hi), val))
            pt.append(val)
        pts.append(pt)
    return pts
