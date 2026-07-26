from functools import lru_cache

@lru_cache(maxsize=4096)
def _radical_inverse(index: int, base: int) -> float:
    """Van der Corput radical inverse in given base (deterministic in [0,1)).
    
    Cached to speed up Halton sequence generation.
    """
    index = int(index)
    base = int(base)
    if base <= 1:
        return 0.0
    result = 0.0
    f = 1.0 / base
    i = index
    while i > 0:
        result += (i % base) * f
        i //= base
        f /= base
    return result
