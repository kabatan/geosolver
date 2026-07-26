from functools import lru_cache
from typing import List

@lru_cache(maxsize=64)
def _first_primes(k: int) -> List[int]:
    """Return first k primes (small k; simple trial division is fine).
    
    Cached to avoid redundant computation for repeated calls with same k.
    """
    k = int(k)
    if k <= 0:
        return []
    primes: List[int] = []
    candidate = 2
    while len(primes) < k:
        is_prime = True
        for p in primes:
            if p * p > candidate:
                break
            if candidate % p == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(candidate)
        candidate += 1 if candidate == 2 else 2
    return primes
