"""
Numeric Constraint Functions

微分可能な数値制約関数を提供します。
これらの関数はsolverとoptimizerで使用可能な残差ベースの制約関数です。
"""

from typing import Any

from sympy import Eq, Or, Piecewise, exp, pi, sin
from sympy.ntheory.primetest import isprime

from geosolver.geometry.registry import geometry_symbol

__all__ = [
    "Degrees",
    "IsInteger",
    "IsPrime",
]


# =============================================================================
# Degrees - radian-to-degree conversion
# =============================================================================


@geometry_symbol("Degrees", category="numeric")
def Degrees(angle: Any) -> Any:
    """Convert an angle in radians to degrees.

    The solver's geometric angle primitives use radians.  Keeping this as a
    registered scalar function (rather than only rewriting a top-level target)
    makes the conversion usable in constraints and nested expressions too.
    """
    return angle * 180 / pi


@Degrees.set_mpmath
def _Degrees_mpmath(angle):
    """mpmath high-precision radian-to-degree conversion."""
    from mpmath import mp

    return angle * 180 / mp.pi


# 1000未満の素数リスト（事前計算）
_PRIMES_UNDER_1000 = [
    2,
    3,
    5,
    7,
    11,
    13,
    17,
    19,
    23,
    29,
    31,
    37,
    41,
    43,
    47,
    53,
    59,
    61,
    67,
    71,
    73,
    79,
    83,
    89,
    97,
    101,
    103,
    107,
    109,
    113,
    127,
    131,
    137,
    139,
    149,
    151,
    157,
    163,
    167,
    173,
    179,
    181,
    191,
    193,
    197,
    199,
    211,
    223,
    227,
    229,
    233,
    239,
    241,
    251,
    257,
    263,
    269,
    271,
    277,
    281,
    283,
    293,
    307,
    311,
    313,
    317,
    331,
    337,
    347,
    349,
    353,
    359,
    367,
    373,
    379,
    383,
    389,
    397,
    401,
    409,
    419,
    421,
    433,
    439,
    443,
    449,
    457,
    461,
    463,
    467,
    479,
    487,
    491,
    499,
    503,
    509,
    521,
    523,
    541,
    547,
    557,
    563,
    569,
    571,
    577,
    587,
    593,
    599,
    601,
    607,
    613,
    617,
    619,
    631,
    641,
    643,
    647,
    653,
    659,
    661,
    673,
    677,
    683,
    691,
    701,
    709,
    719,
    727,
    733,
    739,
    743,
    751,
    757,
    761,
    769,
    773,
    787,
    797,
    809,
    811,
    821,
    823,
    827,
    829,
    839,
    853,
    857,
    859,
    863,
    877,
    881,
    883,
    887,
    907,
    911,
    919,
    929,
    937,
    941,
    947,
    953,
    967,
    971,
    977,
    983,
    991,
    997,
]
_IS_PRIME_CONDITION = None


# =============================================================================
# IsInteger - 微分可能な整数性制約関数
# =============================================================================


@geometry_symbol("IsInteger", category="numeric")
def IsInteger(x: Any) -> Any:
    """
    微分可能な整数性制約関数

    引数が整数のとき0を返し、それ以外で正の値を返す残差関数。

    実装: sin(π*x)² を使用
    - xが整数のとき sin(π*x) = 0 → 残差 = 0
    - xが非整数のとき sin(π*x) ≠ 0 → 残差 > 0

    Args:
        x: 判定する数値

    Returns:
        残差（0 = 整数、正の値 = 非整数の度合い）

    Examples:
        >>> IsInteger(5)
        0
        >>> IsInteger(5.5)
        1.0
    """
    return sin(pi * x) ** 2


# mpmath backend for IsInteger
@IsInteger.set_mpmath
def _IsInteger_mpmath(x):
    """mpmath高精度版"""
    from geosolver.geometry.mp.mp_number_constraints import mp_is_integer

    return mp_is_integer(x)


# =============================================================================
# IsPrime - 微分可能な素数性制約関数
# =============================================================================


@geometry_symbol("IsPrime", category="numeric")
def IsPrime(x: Any) -> Any:
    """
    微分可能な素数性制約関数

    引数が素数のとき厳密に0を返し、それ以外で正の値を返す残差関数。

    実装アプローチ:
    1. 整数性チェック: sin(π*x)²
    2. 素数リストとの完全一致チェック（素数なら厳密に0）
    3. それ以外は正の残差

    Args:
        x: 判定する数値

    Returns:
        残差（0 = 素数、正の値 = 非素数の度合い）

    Examples:
        >>> IsPrime(7)
        0  # 素数なので厳密に0
        >>> IsPrime(8)
        >0  # 合成数なので正の値

    Note:
        - 1000未満の素数リストを使用
        - 素数の場合は厳密に0を返す
    """
    # 数値入力の高速パス（SymPy Piecewise 構築を避ける）
    if isinstance(x, int | float):
        if x < 2 or int(x) != x:
            return 1.0
        return 0.0 if isprime(int(x)) else 1.0

    # 整数性チェック
    integer_residual = sin(pi * x) ** 2

    # 素数リストに含まれるかをチェック（キャッシュして構築コストを削減）
    global _IS_PRIME_CONDITION
    if _IS_PRIME_CONDITION is None:
        _IS_PRIME_CONDITION = Or(*[Eq(x, p) for p in _PRIMES_UNDER_1000])

    # 非素数の場合の残差
    # 1. x < 2 にペナルティ
    positivity_residual = exp(-(x - 2))

    # 2. 非整数にペナルティ
    # 3. 素数でない整数に大きなペナルティ
    non_prime_residual = integer_residual + positivity_residual + 1

    # Piecewise: 素数なら0、それ以外は残差
    return Piecewise((0, _IS_PRIME_CONDITION), (non_prime_residual, True))


# mpmath backend for IsPrime
@IsPrime.set_mpmath
def _IsPrime_mpmath(x):
    """mpmath高精度版"""
    from geosolver.geometry.mp.mp_number_constraints import mp_is_prime

    return mp_is_prime(x)
