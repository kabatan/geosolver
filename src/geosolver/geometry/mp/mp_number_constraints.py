"""
Numeric constraint helpers extracted from mp_impl.
"""

from __future__ import annotations

from mpmath import exp as mp_exp, mpf, pi as mp_pi, sin as mp_sin

from geosolver.geometry.mp.mp_conversion import is_near_integer, round_to_nearest_int, to_mpf

_MP_PRIMES_UNDER_1000 = [
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83,
    89, 97, 101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157, 163, 167, 173, 179,
    181, 191, 193, 197, 199, 211, 223, 227, 229, 233, 239, 241, 251, 257, 263, 269, 271, 277,
    281, 283, 293, 307, 311, 313, 317, 331, 337, 347, 349, 353, 359, 367, 373, 379, 383, 389,
    397, 401, 409, 419, 421, 433, 439, 443, 449, 457, 461, 463, 467, 479, 487, 491, 499, 503,
    509, 521, 523, 541, 547, 557, 563, 569, 571, 577, 587, 593, 599, 601, 607, 613, 617, 619,
    631, 641, 643, 647, 653, 659, 661, 673, 677, 683, 691, 701, 709, 719, 727, 733, 739, 743,
    751, 757, 761, 769, 773, 787, 797, 809, 811, 821, 823, 827, 829, 839, 853, 857, 859, 863,
    877, 881, 883, 887, 907, 911, 919, 929, 937, 941, 947, 953, 967, 971, 977, 983, 991, 997,
]


def mp_is_integer(x: object) -> mpf:
    x_mpf = to_mpf(x)
    return mp_sin(mp_pi * x_mpf) ** 2


def mp_is_prime(x: object) -> mpf:
    x_mpf = to_mpf(x)
    x_rounded = round_to_nearest_int(x_mpf)
    tol = mpf("1e-10")
    if is_near_integer(x_mpf, x_rounded, tol) and x_rounded in _MP_PRIMES_UNDER_1000:
        return mpf(0)

    integer_residual = mp_sin(mp_pi * x_mpf) ** 2
    positivity_residual = mp_exp(-(x_mpf - mpf(2)))
    non_prime_penalty = mpf(1)
    return integer_residual + positivity_residual + non_prime_penalty
