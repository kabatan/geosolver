"""
Numeric constraint helpers extracted from mp_impl.
"""

from __future__ import annotations

from mpmath import exp as mp_exp
from mpmath import mpf
from mpmath import pi as mp_pi
from mpmath import sin as mp_sin
from sympy.ntheory.primetest import isprime

from geosolver.geometry.mp.mp_conversion import is_near_integer, round_to_nearest_int, to_mpf


def mp_is_integer(x: object) -> mpf:
    x_mpf = to_mpf(x)
    return mp_sin(mp_pi * x_mpf) ** 2


def mp_is_prime(x: object) -> mpf:
    x_mpf = to_mpf(x)
    x_rounded = round_to_nearest_int(x_mpf)
    # The search residual remains smooth away from integers, but acceptance is
    # no longer capped by a lookup table.  The tolerance follows the active
    # precision so a near-integer cannot pass the 180-digit final gate.
    from mpmath import mp

    tol = max(mp.eps * 100, mpf("1e-100"))
    if is_near_integer(x_mpf, x_rounded, tol) and isprime(int(x_rounded)):
        return mpf(0)

    integer_residual = mp_sin(mp_pi * x_mpf) ** 2
    positivity_residual = mp_exp(-(x_mpf - mpf(2)))
    non_prime_penalty = mpf(1)
    return integer_residual + positivity_residual + non_prime_penalty
